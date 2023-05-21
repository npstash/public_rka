from subprocess import PIPE, Popen
from time import sleep
from typing import Optional, Type, Dict

import regex as re

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.rkathread import RKAThread
from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.components.security.credentials import CredentialsManager
from rka.log_configs import LOG_VOICE_AUDIO
from rka.services.api import IServiceProvider
from rka.services.api.ps_connector import IPSConnector, IPSConnectorObserver, PSTriggerInfo, PSTriggerEventData
from rka.services.providers.ps_connector.ps_connector_apha import APHA_PS_SERVER_ADDRESS, APHA_PS_SERVER_PORT
from rka.services.providers.ps_connector.ps_connector_apha.apha_connector import connector_jarfile_path
from rka.services.providers.ps_connector.ps_connector_common import PSConnectorObserverContainer, PSConnectorObserverEventDispatcher

logger = LogService(LOG_VOICE_AUDIO)


class PSJavaProcessConnector(IPSConnector, Closeable):
    def __init__(self, credentials: CredentialsManager, auto_disconnect: Optional[float]):
        Closeable.__init__(self, explicit_close=False)
        self.__credentials = credentials
        self.__auto_disconnect = auto_disconnect if auto_disconnect else 300.0
        self.__username = credentials.get_credentials("aphaps")["username"]
        self.__ps_connector_process: Optional[Popen] = None
        self.__trigger_definitions: Dict[int, PSTriggerInfo] = dict()
        self.__observer_container = PSConnectorObserverContainer()
        self.__previous_packet_type = 0
        self.__scheduler = RKAScheduler('PS timeout')
        self.__timeout_future: Optional[RKAFuture] = None
        trigger_pattern = r'id="(\d+)" ' \
                          r'title="(.+?)" ' \
                          r'active="(true|false)" ' \
                          r'category="(.*?)" ' \
                          r'regex="(.+?)" ' \
                          r'react="(.*?)" ' \
                          r'quantity="(.*?)" ' \
                          r'ignoreTimer="(.*?)" ' \
                          r'serverMsgActive="(true|false)" ' \
                          r'serverMsg="(.+?)" ' \
                          r'size="(.*?)" ' \
                          r'color="(.*?)" ' \
                          r'soundActive="(true|false)" ' \
                          r'sound="(.*?)" ' \
                          r'timerActive="(true|false)" ' \
                          r'timerShow1="(true|false)" ' \
                          r'timerShow2="(true|false)" ' \
                          r'timerShow3="(true|false)" ' \
                          r'timerPeriod="(\d+)" ' \
                          r'timerWarning="(.*?)" ' \
                          r'timerWarningMsg="(.*?)" ' \
                          r'timerWarningMsgSize="(.*?)" ' \
                          r'timerWarningMsgColor="(.*?)" ' \
                          r'timerWarningMsgSound="(.*?)" ' \
                          r'timerRemove="(.*?)" ' \
                          r'privatSound="(true|false)"'
        self.__trigger_def_re = re.compile(trigger_pattern)

    def add_observer(self, observer: IPSConnectorObserver):
        self.__observer_container.add_observer(observer)

    def remove_observer(self, observer: IPSConnectorObserver):
        self.__observer_container.remove_observer(observer)

    def send_trigger_event(self, trigger_id: int, line: str) -> bool:
        self.__schedule_timeout()
        if not self.__write(f'TRIGGER_EVENT'):
            return False
        if not self.__write(str(trigger_id)):
            return False
        return self.__write(line)

    def send_message(self, message: str) -> bool:
        self.__schedule_timeout()
        # TODO use other trigger, without TTS
        return self.send_trigger_event(2598, ";;;;" + message + ";;;;;" + self.__username + ";")

    def send_tts(self, tts_message: str) -> bool:
        self.__schedule_timeout()
        return self.send_trigger_event(2598, ";;;;" + tts_message + ";;;;;" + self.__username + ";")

    def __connector_closed(self):
        logger.info(f'__connector_closed: closed status = {self.is_closed()}')
        if self.is_closed():
            return
        Closeable.close(self)
        self.__observer_container.connector_closed()
        self.__observer_container.clear()
        if self.__ps_connector_process:
            logger.info(f'terminate connector')
            self.__ps_connector_process.terminate()

    # noinspection PyMethodMayBeStatic
    def __get_trigger_data(self, trigger_info: PSTriggerInfo, payload: str) -> Optional[PSTriggerEventData]:
        if not payload:
            logger.warn('__get_trigger_data: payload is None')
            return None
        payloads = payload.split(';')
        if len(payloads) != 11:
            logger.warn(f'__get_trigger_data: payload len is not correct: {payload}')
            return None
        sender = payloads[9]
        message = trigger_info.message
        for i in range(6):
            group_idx = i + 1
            payload_idx = i + 4
            if f'%{group_idx}' not in message:
                continue
            if not payloads[payload_idx]:
                logger.info(f'Expected group idx {group_idx} not found in payload: {payload}')
                continue
            message = message.replace(f'%{group_idx}', payloads[payload_idx])
        message = message.replace('%u', sender)
        # voice message is inside []
        voice_message = None
        voice_msg_match = re.search(r'\[(.*)\]', message)
        if voice_msg_match:
            voice_message = voice_msg_match.group(1)
        return PSTriggerEventData(trigger_info=trigger_info, ps_payload=payload, sender=sender, message=message, voice_message=voice_message)

    def __handle_input(self, line: str):
        if line.startswith('RECEIVED:'):
            line = line[len('RECEIVED:'):]
            match = re.search(r'type=(\d+)', line)
            if match:
                logger.info(f'server packet: {line}')
                packet_type = int(match.group(1))
                self.__previous_packet_type = packet_type
                if packet_type == 6:
                    match_clients = re.search(r'clients="(.*)"', line)
                    client_list_str = match_clients.group(1).replace('"', '')
                    if client_list_str.endswith(';'):
                        client_list_str = client_list_str[:-1]
                    client_list = client_list_str.split(';')
                    self.__observer_container.client_list_received(client_list)
                elif packet_type == 5:
                    match_msg = re.search(r'msg="(.*)"', line)
                    msg = match_msg.group(1)
                    self.__observer_container.message_received(msg)
                elif packet_type == 11:
                    match_cmd = re.search(r'cmd=(.*) param1=(.*) param2=(.*) ', line)
                    params = []
                    if match_cmd.group(2):
                        params.append(match_cmd.group(2))
                    if match_cmd.group(3):
                        params.append(match_cmd.group(3))
                    self.__observer_container.command_received(match_cmd.group(1), params)
                elif packet_type == 14:
                    pass
                elif packet_type == 15:
                    match_event = re.search(r'triggerId="(\d+)" sender=".*?" attrStr="(.*?)"', line)
                    if match_event:
                        trigger_id = int(match_event.group(1))
                        if trigger_id in self.__trigger_definitions:
                            trigger_info = self.__trigger_definitions[trigger_id]
                            payload = match_event.group(2)
                            trigger_data = self.__get_trigger_data(trigger_info, payload)
                            if trigger_data:
                                self.__observer_container.trigger_event_received(trigger_data)
                        else:
                            logger.info(f'Received unrecognized trigger_id={trigger_id}')
        elif 'id=' in line and self.__previous_packet_type == 14:
            match_trigger = self.__trigger_def_re.search(line)
            if match_trigger:
                trigger_id = int(match_trigger.group(1))
                title = match_trigger.group(2)
                active = match_trigger.group(3) == 'true'
                if active:
                    trigger_pattern = match_trigger.group(5)
                    message_active = match_trigger.group(9) == 'true'
                    message = match_trigger.group(10) if message_active else None
                    timer_active = match_trigger.group(15) == 'true'
                    timer = int(match_trigger.group(19)) if timer_active else None
                    private_sound = match_trigger.group(26) == 'true'
                    trigger_info = PSTriggerInfo(trigger_id, title, trigger_pattern, message, private_sound, timer)
                    self.__trigger_definitions[trigger_id] = trigger_info
        elif line.startswith('SERVER SOCKET CLOSED'):
            self.__connector_closed()

    def __out_loop(self):
        while self.is_running():
            connector_process = self.__ps_connector_process
            if connector_process:
                line = connector_process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                logger.detail(f'read: {line}')
                # this may close the connector if receives quit from connector peer
                self.__handle_input(line)
        self.__connector_closed()

    def __err_loop(self):
        while self.is_running():
            connector_process = self.__ps_connector_process
            if connector_process:
                line = connector_process.stderr.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                logger.warn(f'read: {line}')
        self.__connector_closed()

    def __write(self, line: str) -> bool:
        logger.debug(f'write: {line}')
        if not self.is_running():
            logger.warn(f'write: connector not running')
            return False
        connector_process = self.__ps_connector_process
        if not connector_process:
            logger.warn(f'write: connector process not up')
            return False
        try:
            connector_process.stdin.write(f'{line}\n')
            connector_process.stdin.flush()
            # yield for reading, there is some issue if writer dominates pipes
            sleep(0.01)
        except Exception as e:
            logger.warn(e.__str__())
            return False
        return True

    def __send_login(self) -> bool:
        if not self.__write(f'LOGIN'):
            return False
        if not self.__write(APHA_PS_SERVER_ADDRESS):
            return False
        if not self.__write(str(APHA_PS_SERVER_PORT)):
            return False
        aphaps_data = self.__credentials.get_credentials('aphaps')
        if not self.__write(aphaps_data['username']):
            return False
        if not self.__write(aphaps_data['password']):
            return False
        return True

    def __schedule_timeout(self):
        future = self.__timeout_future
        if future:
            future.cancel_future()
        self.__timeout_future = self.__scheduler.schedule(lambda: self.close_connector(), delay=self.__auto_disconnect)

    def start_connector(self) -> bool:
        if self.is_running():
            return True
        logger.info(f'start connector')
        try:
            cmd = ['java', '-jar', connector_jarfile_path]
            self.__ps_connector_process = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE, universal_newlines=True)
            if not self.__send_login():
                return False
        except Exception as e:
            print(e)
            return False
        logger.debug(f'subprocess started PID= {self.__ps_connector_process.pid}')
        RKAThread('PS Connector stdout reader', self.__out_loop).start()
        RKAThread('PS Connector stderr reader', self.__err_loop).start()
        self.__schedule_timeout()
        return True

    def is_running(self) -> bool:
        if Closeable.is_closed(self) or not self.__ps_connector_process:
            return False
        return self.__ps_connector_process.returncode is None

    def close_connector(self):
        logger.info(f'close connector')
        if not self.is_running():
            return
        self.__scheduler.close()
        if self.__write('QUIT'):
            # wait a bit for server response to close gracefully
            sleep(0.3)
        self.__connector_closed()

    def is_finalized(self) -> bool:
        return Closeable.is_closed(self)

    def close(self):
        self.close_connector()


class PSJavaProcessConnectorProvider(IServiceProvider):
    def __init__(self, credentials: CredentialsManager, auto_disconnect: Optional[float]):
        self.__credentials = credentials
        self.__auto_disconnect = auto_disconnect

    def service_type(self) -> Type[IPSConnector]:
        return IPSConnector

    def provide_service(self) -> PSJavaProcessConnector:
        connector = PSJavaProcessConnector(self.__credentials, self.__auto_disconnect)
        connector.add_observer(PSConnectorObserverEventDispatcher(EventSystem.get_main_bus()))
        return connector
