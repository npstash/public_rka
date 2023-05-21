from __future__ import annotations

import os
from threading import RLock, Condition
from typing import Optional, List

from rka.app.app_info import AppInfo
from rka.components.cleanup import Closeable
from rka.components.events.event_bus import EventBusFactory
from rka.components.events.event_system import EventSystem
from rka.components.impl.factories import TTSFactory, OverlayFactory, InjectorFactory
from rka.components.io.filemonitor import IActiveFileMonitorObserver, IFileMonitor
from rka.components.io.injector import IInjector
from rka.components.io.log_service import LogService, LogLevel
from rka.components.network.network_config import NetworkConfig
from rka.components.rpc_services.server import Server
from rka.components.security.credentials import CredentialsManager
from rka.components.ui.alerts import Alerts
from rka.components.ui.overlay import Severity
from rka.eq2.configs import configs_root
from rka.eq2.configs.shared.game_constants import MONGODB_SERVICE_URI, MONGODB_CERTIFICATE_FILENAME, CENSUS_SERVICE_NAME, MONGODB_DATABASE_NAME
from rka.eq2.configs.shared.rka_constants import LOG_PARSER_SKIPCHARS, MAX_OVERLAY_STATUS_SLOTS, LOCAL_ABILITY_INJECTOR_PATH, LOCAL_COMMAND_INJECTOR_PATH, STAY_IN_VOICE
from rka.eq2.master import IRuntime
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.master.remote_event_bus import RemoteEventBusFactory
from rka.eq2.parsing.log_io import LogReaderFactory, TruncateLogHeader
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.host import HostConfig
from rka.services.broker import ServiceBroker


class Runtime(IRuntime, Closeable, IActiveFileMonitorObserver):
    @staticmethod
    def __get_local_injectors() -> List[IInjector]:
        injector_1 = InjectorFactory.create_injector(LOCAL_ABILITY_INJECTOR_PATH, injectionwait=0.0, singleusedelay=0.5)
        injector_2 = InjectorFactory.create_injector(LOCAL_COMMAND_INJECTOR_PATH, postifx='who')
        return [injector_1, injector_2]

    def __init__(self, host_config: HostConfig, network_config: NetworkConfig, server_id: str):
        Closeable.__init__(self, explicit_close=True)
        self.__lock = RLock()
        # general host information
        self.host_config = host_config
        # secure data
        self.credentials = CredentialsManager(configs_root, AppInfo.get_hostname())
        # main event systems
        EventSystem.get_main_system(bus_factory=EventBusFactory())
        # event system for events from clients
        self.remote_client_event_system = EventSystem.get_system('master', bus_factory=RemoteEventBusFactory(self))
        # event system for local clients (also to dispatch events to master)
        self.local_client_event_system = EventSystem.get_system('slave', bus_factory=EventBusFactory())

        # install service providers
        from rka.services.providers.ps_connector.ps_connector_apha.ps_java_connector import PSJavaProcessConnectorProvider
        ServiceBroker.get_broker().install_provider(PSJavaProcessConnectorProvider(credentials=self.credentials, auto_disconnect=STAY_IN_VOICE))
        from rka.services.providers.mongodb.__init__ import MongoDBClientConfig
        mongo_config = MongoDBClientConfig(
            service_uri=MONGODB_SERVICE_URI,
            tls_certificate_filepath=os.path.join(configs_root, MONGODB_CERTIFICATE_FILENAME),
            tls_certificate_file_password=self.credentials.get_credentials('mongodb')['certificate-password'],
        )
        from rka.services.providers.mongodb import MongoDBServiceProvider
        ServiceBroker.get_broker().install_provider(MongoDBServiceProvider(config=mongo_config))
        from rka.services.providers.census.census_multilayer_cache_provider import MultilayerCensusCacheProvider
        ServiceBroker.get_broker().install_provider(MultilayerCensusCacheProvider(mongo_database=MONGODB_DATABASE_NAME,
                                                                                  census_service_name=CENSUS_SERVICE_NAME,
                                                                                  file_cache=True))
        from rka.eq2.master.screening.provider import ScreenReaderProvider
        ServiceBroker.get_broker().install_provider(ScreenReaderProvider(detection_perdiod=1.0))

        # master-slave command control
        from rka.eq2.master.control.master_bridge import MasterBridge
        self.master_bridge = MasterBridge(self)
        from rka.eq2.master.control.master_interpreter import MasterInterpreter
        master_interpreter = MasterInterpreter(self, self.master_bridge)
        self.__server = Server(server_id, master_interpreter, network_config)
        from rka.eq2.master.control.action import action_factory
        action_factory.initialize_broker(self.__server)
        self.master_bridge.configure(self.__server, action_factory)

        # game data management
        from rka.eq2.master.game.ability.ability_ext_reg import AbilityExtConstsRegistry
        self.ext_consts_reg = AbilityExtConstsRegistry()
        self.ext_consts_reg.generate_ability_ext_code()
        from rka.eq2.master.game.census.census_service_bridge import CensusBridge
        self.census_cache = CensusBridge()
        from rka.eq2.master.game.ability.ability_registry import AbilityRegistry
        self.ability_reg = AbilityRegistry()
        from rka.eq2.master.game.ability.ability_locator import AbilityLocatorFactory
        AbilityLocatorFactory.initialize(self.ability_reg, self.census_cache, self.ext_consts_reg)
        from rka.eq2.master.game.ability.ability_controller import AbilityController
        self.ability_ctrl = AbilityController(self)
        from rka.eq2.master.game.effect.effect_mgr import EffectsManager
        self.effects_mgr = EffectsManager()
        from rka.eq2.master.game.player.playermgr import PlayerManager
        self.player_mgr = PlayerManager(self.effects_mgr)
        from rka.eq2.master.game.player.playerselectors import PlayerSelectorFactory
        self.playerselectors = PlayerSelectorFactory(self)
        from rka.eq2.master.game.ability.ability_factory import AbilityFactory
        self.registered_ability_factory = AbilityFactory(self.effects_mgr, self.ability_reg)
        from rka.eq2.master.game.ability.ability_factory import CustomAbilityFactory
        self.custom_ability_factory = CustomAbilityFactory(self.effects_mgr)

        # resources
        from rka.eq2.master.game.scripting.pattern_mgr import PatternManager
        self.capture_pattern_mgr = PatternManager(self)

        # build abilities
        self.player_mgr.initialize_players(self)

        # parser managers
        from rka.eq2.master.parsing.remote_parser_mgr import RemoteParserManager
        self.parser_mgr = RemoteParserManager(self)
        from rka.eq2.parsing.parser_mgr import ParserManager
        self.__local_parser_mgr = ParserManager(self.host_config)
        from rka.eq2.master.parsing import IDPSParser
        self.current_dps: Optional[IDPSParser] = None

        # triggers
        from rka.eq2.master.triggers.trigger_mgr import TriggerManager
        self.trigger_mgr = TriggerManager(self)
        from rka.eq2.master.triggers.trigger_db import TriggerDatabase
        self.trigger_db = TriggerDatabase(self)

        # local slave client controllers
        from rka.eq2.shared.control.slave_bridge import SlaveBridge
        local_slave_bridge = SlaveBridge()
        from rka.eq2.shared.control.slave_interpreter import SlaveInterpreter
        self.__injectors = Runtime.__get_local_injectors()
        local_slave_interpreter = SlaveInterpreter(host_config, local_slave_bridge, self.__injectors, self.local_client_event_system)
        from rka.eq2.shared.control.slave_mgr import SlaveManager
        # slave manager starts new RPC Client each time a local parser is activated. these clients are not started with slave.Starter
        self.__local_slave_mgr = SlaveManager(self.__local_parser_mgr, network_config.create_local_client_config(),
                                              local_slave_interpreter, local_slave_bridge, self.local_client_event_system)
        self.__local_slave_mgr.set_file_obeserver(self)
        from rka.eq2.master.control.client_controller import ClientControllerManager
        self.client_ctrl_mgr = ClientControllerManager(self)

        # game control and state objects
        from rka.eq2.master.game.engine.processor import ProcessorFactory
        self.processor_factory = ProcessorFactory(self)
        self.processor = self.processor_factory.create_processor()
        from rka.eq2.master.game.requests.request_factory import RequestFactory
        self.request_factory = RequestFactory(self)
        from rka.eq2.master.game.requests.request_controller import RequestControllerFactory
        self.request_ctrl_factory = RequestControllerFactory(self)
        self.request_ctrl = self.request_ctrl_factory.create_main_request_controller(self.processor, self.request_factory)
        from rka.eq2.master.game.state.playerstate import PlayerState
        self.playerstate = PlayerState(self)
        from rka.eq2.master.game.state.zonestate import ZoneState
        self.zonestate = ZoneState(self)
        from rka.eq2.master.game.state.zonemaps import ZoneMaps
        self.zonemaps = ZoneMaps(self)
        from rka.eq2.master.game.state.detriments import Detriments
        self.detriments = Detriments(self)
        from rka.eq2.master.game.state.combatstate import CombatState
        self.combatstate = CombatState(self)

        # create UI services
        self.tts = TTSFactory.create_tts().open_session()
        self.alerts = Alerts()
        self.overlay = OverlayFactory.create_overlay_on_new_thread(MAX_OVERLAY_STATUS_SLOTS)

        # start UI components
        self.overlay.show()
        from rka.eq2.master.ui.control_menu import ControlMenu
        self.control_menu = ControlMenu(self)
        from rka.eq2.master.ui.overlay_control import OverlayController
        self.overlay_controller = OverlayController(self)
        self.overlay_controller.setup_overlay_updates()

        # services which require access to credentials
        if not self.credentials.open_credentials():
            self.__get_master_password()
        self.group_tts = TTSFactory.create_group_tts(self.credentials)
        from rka.eq2.master.control.notification import NotificationServiceProxy
        self.notification_service = NotificationServiceProxy(self)
        self.notification_service.start()
        LogService.set_log_listener(self.__report_error_log, LogLevel.WARN)

        # local parsers. registering them is necessary to observe activation of log files and new client notification
        self.__register_local_parsers()
        # start recently active player, without waiting for logfile activation
        recent_client_id = self.host_config.get_recent_log_filenames_client()
        self.__local_parser_mgr.get_parser(recent_client_id).set_active(True)

        # player AI and automation rules
        from rka.eq2.master.game.automation.automation import Automation
        self.automation = Automation(self)

        # start discovering players
        self.__server.subscribe_for_new_client(self.client_ctrl_mgr.client_found)
        self.__server.subscribe_for_lost_client(self.client_ctrl_mgr.client_lost)
        self.__server.start_server()

        # register hotkeys and start receiving user requests
        from rka.eq2.master.control.keyspecmgr import KeySpecManager
        self.key_manager = KeySpecManager(self)

    def __get_master_password(self):
        conditional = Condition()

        def set_master_password(key: Optional[str]):
            if key:
                self.credentials.set_master_password(key, save_to_file=self.host_config.secure)
            with conditional:
                conditional.notify_all()

        self.overlay.get_text('Master password', set_master_password)
        with conditional:
            conditional.wait()

    def __report_error_log(self, msg: str, level: LogLevel):
        if level <= LogLevel.WARN:
            self.overlay.log_event(msg, Severity.Normal)
        else:
            self.overlay.log_event(msg, Severity.High)
            self.notification_service.post_notification(f'{level.name}: {msg}')

    def __register_local_parsers(self):
        from rka.eq2.master.parsing.dps_logparser import DpsLogParser
        local_players = self.player_mgr.get_players(and_flags=ClientFlags.Local, min_status=PlayerStatus.Offline)
        for player in local_players:
            log_filename = self.host_config.get_log_filename(player.get_client_id())
            log_reader = LogReaderFactory.create_file_logreader(log_filename)
            log_reader = TruncateLogHeader(log_reader, LOG_PARSER_SKIPCHARS)
            log_parser = DpsLogParser(self, player, log_reader, self.local_client_event_system)
            log_injector = LogReaderFactory.create_file_loginjector(log_filename)
            # activation of these parsers will cause the local slave manager to start local clients
            self.__local_parser_mgr.register_parser(log_parser, log_injector)

    def file_activated(self, _deactivated_monitor: IFileMonitor, activated_monitor: IFileMonitor):
        new_client_id = activated_monitor.get_monitor_id()
        self.current_dps = self.__local_parser_mgr.get_parser(new_client_id)
        from rka.eq2.master.parsing import IDPSParser
        assert isinstance(self.current_dps, IDPSParser)
        EventSystem.get_main_bus().post(MasterEvents.NEW_DPS_PARSER(dps_parser=self.current_dps))

    def run_blocking(self):
        self.key_manager.run_blocking()

    def close(self):
        self.automation.close()
        self.__server.close()
        self.overlay.close()
        self.tts.close_session()
        self.alerts.close()
        self.notification_service.close()
        self.parser_mgr.close()
        self.__local_parser_mgr.close()
        self.processor.close()
        for injector in self.__injectors:
            injector.close()
        self.__local_slave_mgr.close()
        self.remote_client_event_system.close()
        self.local_client_event_system.close()
        self.census_cache.close()
        EventSystem.get_main_system().close()
        Closeable.close(self)
