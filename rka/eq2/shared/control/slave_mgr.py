import time
from typing import Optional

from rka.components.events.event_system import EventSystem
from rka.components.io.filemonitor import IActiveFileMonitorObserver, IFileMonitor
from rka.components.network.network_config import NetworkConfig
from rka.components.rpc_services.client import Client
from rka.eq2.parsing.parser_mgr import ParserManager
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.control import logger
from rka.eq2.shared.control.slave_bridge import SlaveBridge
from rka.eq2.shared.control.slave_interpreter import SlaveInterpreter
from rka.eq2.shared.shared_workers import shared_worker


class SlaveManager(IActiveFileMonitorObserver):
    def __init__(self, parser_mgr: ParserManager, network_config: NetworkConfig, interpreter: SlaveInterpreter, bridge: SlaveBridge, event_system: EventSystem):
        self.__parser_mgr = parser_mgr
        self.__network_config = network_config
        self.__interpreter = interpreter
        self.__bridge = bridge
        self.__event_system = event_system
        self.__delegated_observer: Optional[IActiveFileMonitorObserver] = None
        self.__current_client: Optional[Client] = None
        self.__parser_mgr.set_file_obeserver(self)

    def set_file_obeserver(self, file_observer: IActiveFileMonitorObserver):
        self.__delegated_observer = file_observer

    def start_client(self, client_id: str):
        logger.info(f'start_client: {client_id}')
        if self.__current_client is not None:
            logger.warn(f'start_client: client is not cleared: {self.__current_client}')
            self.stop_client()
        self.__event_system.install_bus(client_id)
        self.__current_client = Client(client_id, self.__interpreter, self.__network_config)
        self.__interpreter.set_active_log(log_parser=self.__parser_mgr.get_parser(client_id), log_injector=self.__parser_mgr.get_loginjector(client_id))
        self.__bridge.set_active_client(client=self.__current_client)
        self.__current_client.start_client()

    def stop_client(self):
        client_id = self.__current_client.node_id
        logger.info(f'stop_client: {client_id}')
        self.__interpreter.set_active_log(None, None)
        self.__bridge.set_active_client(None)
        self.__current_client.close()
        self.__current_client = None
        self.__event_system.uninstall_bus(client_id)

    def send_client_event(self, event: ClientEvent):
        if not self.__current_client:
            logger.warn(f'send_client_event: no client set, cannot send {event}')
            return
        client_id = self.__current_client.node_id
        event.set_client_id(client_id)
        event.set_timestamp(time.time())
        bus = self.__event_system.get_bus(client_id)
        if not bus:
            logger.warn(f'send_client_event: no bus available for {client_id}, cannot send {event}')
            return
        bus.post(event)

    def __file_activated_queued(self, deactivated_monitor: IFileMonitor, activated_monitor: IFileMonitor):
        # run on a shared work thread to avoid race condition
        old_client_id = None
        new_client_id = activated_monitor.get_monitor_id()
        if self.__current_client is not None:
            old_client_id = self.__current_client.node_id
            logger.debug(f'file_activated: {new_client_id}, {old_client_id} from client node')
        elif deactivated_monitor is not None:
            old_client_id = deactivated_monitor.get_monitor_id()
            logger.debug(f'file_activated: {new_client_id}, {old_client_id} from monitor id')
        if old_client_id == new_client_id:
            logger.warn(f'activated file for an already active client id {new_client_id}')
            return
        if self.__current_client is not None:
            self.stop_client()
        self.start_client(new_client_id)
        if self.__delegated_observer is not None:
            self.__delegated_observer.file_activated(deactivated_monitor, activated_monitor)

    def file_activated(self, deactivated_monitor: IFileMonitor, activated_monitor: IFileMonitor):
        shared_worker.push_task(lambda: self.__file_activated_queued(deactivated_monitor, activated_monitor))

    def close(self):
        if self.__current_client is not None:
            self.stop_client()
