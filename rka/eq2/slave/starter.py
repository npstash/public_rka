from __future__ import annotations

from rka.components.cleanup import cleanup_manager
from rka.components.concurrency.rkathread import RKAThread
from rka.components.events.event_bus import EventBusFactory
from rka.components.events.event_system import EventSystem
from rka.components.impl.factories import HotkeyServiceFactory, InjectorFactory
from rka.components.network.network_config import NetworkConfig
from rka.components.ui.hotkeys import IHotkeyService, HotkeyEventPumpType
from rka.eq2.configs.shared.rka_constants import LOG_PARSER_SKIPCHARS, REMOTE_INJECTOR_PATH
from rka.eq2.parsing.combat_logparser import CombatLogParser
from rka.eq2.parsing.log_io import LogReaderFactory, TruncateLogHeader
from rka.eq2.parsing.parser_mgr import ParserManager
from rka.eq2.shared import ClientRequests
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.control.slave_bridge import SlaveBridge
from rka.eq2.shared.control.slave_interpreter import SlaveInterpreter
from rka.eq2.shared.control.slave_mgr import SlaveManager
from rka.eq2.shared.host import HostConfig
from rka.eq2.slave import logger


def handle_extra_command(_cmd: str) -> bool:
    return False


class SlaveRuntime:
    def __init__(self, host_config: HostConfig, network_config: NetworkConfig):
        self.__event_system = EventSystem.get_system('slave', bus_factory=EventBusFactory())
        self.__bridge = SlaveBridge()
        injector = InjectorFactory.create_injector(REMOTE_INJECTOR_PATH, injectionwait=0.1, singleusedelay=0.0)
        self.__interpreter = SlaveInterpreter(host_config, self.__bridge, [injector], self.__event_system)
        parser_mgr = ParserManager(host_config)
        if not host_config.client_ids:
            logger.error(f'No clients configured for this host: {host_config.host_id}')
            cleanup_manager.close_all()
            return
        # get latest log file's owner before truncating logs
        recent_client_id = host_config.get_recent_log_filenames_client()
        for client_id in host_config.client_ids:
            log_filename = host_config.get_log_filename(client_id)
            log_reader = LogReaderFactory.create_file_logreader(log_filename)
            log_reader = TruncateLogHeader(log_reader, LOG_PARSER_SKIPCHARS)
            log_reader.clear_logs()
            player_name = host_config.player_names[client_id]
            log_parser = CombatLogParser(client_id, player_name, log_reader, self.__event_system)
            log_injector = LogReaderFactory.create_file_loginjector(log_filename)
            parser_mgr.register_parser(log_parser, log_injector)
        self.__client_mgr = SlaveManager(parser_mgr, network_config, self.__interpreter, self.__bridge, self.__event_system)
        # start first player, without waiting for logfile activation
        parser_mgr.get_parser(recent_client_id).set_active(True)

        self.__hotkey_service: IHotkeyService = HotkeyServiceFactory.create_service(service_type=HotkeyEventPumpType.SERVICE_TYPE_CURRENT_THREAD_PUMP)
        self.__keyfilter = HotkeyServiceFactory.create_filter()
        self.__keyfilter.add_keys('consume control m', self.__interpreter.print_mouse_pos)
        self.__keyfilter.add_keys('consume alt control k', self.__interpreter.toggle_keep_clicking)
        self.__keyfilter.add_keys('consume control q', self.__client_cleanup_start)
        self.__keyfilter.add_keys('consume alt enter', lambda: None)
        self.__keyfilter.add_keys('1', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.COMBAT)))
        self.__keyfilter.add_keys('consume alt f', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.FOLLOW)))
        self.__keyfilter.add_keys('consume control f', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.STOP_FOLLOW)))
        self.__keyfilter.add_keys('consume alt z', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.GROUP_CURE)))
        self.__keyfilter.add_keys('consume alt y', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.ACCEPT)))
        self.__keyfilter.add_keys('consume alt o', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.CLICK)))
        self.__keyfilter.add_keys('consume alt s', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.START_OOZC)))
        self.__keyfilter.add_keys('consume control s', lambda: self.__client_mgr.send_client_event(ClientEvents.CLIENT_REQUEST(request=ClientRequests.STOP_OOZC)))

    def run(self):
        assert self.__keyfilter
        self.__hotkey_service.start([self.__keyfilter])

    def __client_cleanup(self):
        logger.info('cleanup start')
        self.__client_mgr.close()
        cleanup_manager.close_all()

    def __client_cleanup_start(self):
        close_thread = RKAThread('Cleanup thread', target=self.__client_cleanup)
        close_thread.close_resource()
        close_thread.start()


def run_slave(host_config: HostConfig, network_config: NetworkConfig):
    runtime = SlaveRuntime(host_config, network_config)
    runtime.run()
