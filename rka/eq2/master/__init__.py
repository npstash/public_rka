from __future__ import annotations

from typing import Optional, Union

from rka.app.app_info import AppInfo
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_COMMON

AppInfo.assert_master_role()

logger = LogService(LOG_COMMON)


class BuilderTools:
    def __init__(self):
        # data management
        from rka.eq2.master.game.ability.ability_ext_reg import AbilityExtConstsRegistry
        self.ext_consts_reg: Optional[AbilityExtConstsRegistry] = None
        from rka.eq2.master.game.census.census_bridge import ICensusBridge
        self.census_cache: Optional[ICensusBridge] = None
        from rka.eq2.master.game.interfaces import IAbilityRegistry
        self.ability_reg: Optional[IAbilityRegistry] = None
        from rka.eq2.master.game.interfaces import IEffectsManager
        self.effects_mgr: Optional[IEffectsManager] = None
        from rka.eq2.master.game.interfaces import IPlayerManager
        self.player_mgr: Optional[IPlayerManager] = None
        from rka.eq2.master.game.player.playerselectors import PlayerSelectorFactory
        self.playerselectors: Optional[PlayerSelectorFactory] = None
        from rka.eq2.master.game.interfaces import IAbilityFactory
        self.registered_ability_factory: Optional[IAbilityFactory] = None
        self.custom_ability_factory: Optional[IAbilityFactory] = None


class HasRuntime:
    def has_runtime(self) -> bool:
        raise NotImplementedError()

    def get_runtime(self) -> IRuntime:
        raise NotImplementedError()


class TakesRuntime(HasRuntime):
    def __init__(self, runtime: Union[IRuntime, HasRuntime]):
        assert isinstance(runtime, (IRuntime, HasRuntime))
        self.__runtime = runtime
        self.__delegate = isinstance(runtime, HasRuntime)

    def has_runtime(self) -> bool:
        if self.__delegate:
            return self.__runtime.has_runtime()
        return True

    def get_runtime(self) -> IRuntime:
        if self.__delegate:
            return self.__runtime.get_runtime()
        return self.__runtime


class RequiresRuntime(HasRuntime):
    def __init__(self):
        HasRuntime.__init__(self)
        self.__runtime: Optional[IRuntime] = None

    def has_runtime(self) -> bool:
        return self.__runtime is not None

    def set_runtime(self, runtime: IRuntime):
        assert isinstance(runtime, IRuntime)
        self.__runtime = runtime

    def get_runtime(self) -> IRuntime:
        assert self.__runtime
        return self.__runtime


class IRuntime(BuilderTools, HasRuntime):
    def __init__(self):
        # security
        from rka.components.security.credentials import CredentialsManager
        self.credentials: Optional[CredentialsManager] = None

        # general host information
        from rka.eq2.shared.host import HostConfig
        self.host_config: Optional[HostConfig] = None

        # event systems
        # system for events from clients
        self.remote_client_event_system: Optional[EventSystem] = None
        # system for local clients (also to dispatch events to master)
        self.local_client_event_system: Optional[EventSystem] = None

        # command control
        from rka.eq2.master.control.master_bridge import MasterBridge
        self.master_bridge: Optional[MasterBridge] = None

        # UI services
        from rka.components.ui.tts import ITTSSession, ITTS
        self.tts: Optional[ITTSSession] = None
        self.group_tts: Optional[ITTS] = None
        from rka.components.ui.alerts import Alerts
        self.alerts: Optional[Alerts] = None
        from rka.components.ui.overlay import IOverlay
        self.overlay: Optional[IOverlay] = None
        from rka.eq2.master.ui.overlay_control import OverlayController
        self.overlay_controller: Optional[OverlayController] = None
        from rka.eq2.master.ui.control_menu import ControlMenu
        self.control_menu: Optional[ControlMenu] = None
        from rka.eq2.master.control.keyspecmgr import KeySpecManager
        self.key_manager: Optional[KeySpecManager] = None

        # data management - in builder tools
        BuilderTools.__init__(self)
        from rka.eq2.master.game.scripting.pattern_mgr import PatternManager
        self.capture_pattern_mgr: Optional[PatternManager] = None

        # game control
        from rka.eq2.master.game.ability.ability_controller import AbilityController
        self.ability_ctrl: Optional[AbilityController] = None
        from rka.eq2.master.game.engine.processor import ProcessorFactory
        self.processor_factory: Optional[ProcessorFactory] = None
        from rka.eq2.master.game.engine.processor import Processor
        self.processor: Optional[Processor] = None
        from rka.eq2.master.game.requests.request_factory import RequestFactory
        self.request_factory: Optional[RequestFactory] = None
        from rka.eq2.master.game.requests.request_controller import RequestControllerFactory
        self.request_ctrl_factory: Optional[RequestControllerFactory] = None
        from rka.eq2.master.game.requests.request_controller import RequestController
        self.request_ctrl: Optional[RequestController] = None
        from rka.eq2.master.game.state.playerstate import PlayerState
        self.playerstate: Optional[PlayerState] = None
        from rka.eq2.master.game.state.zonestate import ZoneState
        self.zonestate: Optional[ZoneState] = None
        from rka.eq2.master.game.state.zonemaps import ZoneMaps
        self.zonemaps: Optional[ZoneMaps] = None
        from rka.eq2.master.game.state.detriments import Detriments
        self.detriments: Optional[Detriments] = None
        from rka.eq2.master.game.state.combatstate import CombatState
        self.combatstate: Optional[CombatState] = None
        from rka.eq2.master.control.client_controller import ClientControllerManager
        self.client_ctrl_mgr: Optional[ClientControllerManager] = None
        from rka.components.ui.notification import INotificationService
        self.notification_service: Optional[INotificationService] = None

        # parser managers
        from rka.eq2.master.parsing.remote_parser_mgr import RemoteParserManager
        self.parser_mgr: Optional[RemoteParserManager] = None
        from rka.eq2.master.parsing import IDPSParser
        self.current_dps: Optional[IDPSParser] = None

        # triggers
        from rka.eq2.master.triggers.trigger_mgr import TriggerManager
        self.trigger_mgr: Optional[TriggerManager] = None
        from rka.eq2.master.triggers.trigger_db import TriggerDatabase
        self.trigger_db: Optional[TriggerDatabase] = None

        # player AI and automation rules
        from rka.eq2.master.game.automation.automation import Automation
        self.automation: Optional[Automation] = None

    def close(self):
        raise NotImplementedError()

    def has_runtime(self) -> bool:
        return True

    def get_runtime(self) -> IRuntime:
        return self
