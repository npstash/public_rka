from __future__ import annotations

import pydoc
from threading import RLock
from typing import Iterable, List, Dict, Optional

from rka.components.events.event_system import EventSystem
from rka.eq2.configs.master.keyspecs import DefaultMainPlayerHotkeySpec
from rka.eq2.configs.shared.clients import client_config_data
from rka.eq2.configs.shared.hosts import hostid_to_hostconfig
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IHotkeySpec, logger, IClientConfig, InputConfig
from rka.eq2.master.control.input_config import InputConfigDelegate
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.master.triggers import ITrigger
from rka.eq2.shared import ClientConfigData
from rka.eq2.shared.host import HostConfig
from rka.eq2.shared.shared_workers import shared_scheduler


class ClientConfig(IClientConfig):
    __client_configs: Dict[str, ClientConfig] = None

    @staticmethod
    def get_all_client_configs() -> Dict[str, ClientConfig]:
        if ClientConfig.__client_configs is None:
            ClientConfig.__client_configs = {config_data.client_id: ClientConfig(config_data) for config_data in client_config_data}
        return ClientConfig.__client_configs

    @staticmethod
    def get_client_config(client_id: str) -> ClientConfig:
        if ClientConfig.__client_configs is None:
            ClientConfig.get_all_client_configs()
        return ClientConfig.__client_configs[client_id]

    def __init__(self, data: ClientConfigData):
        self.__client_data = data
        self.__inputs = InputConfigDelegate()
        self.__current_host_id: Optional[int] = None

    def get_host_config(self) -> HostConfig:
        return hostid_to_hostconfig[self.__current_host_id]

    def get_client_config_data(self) -> ClientConfigData:
        return self.__client_data

    def get_current_host_id(self) -> int:
        return self.__current_host_id

    def get_inputs_config(self) -> InputConfig:
        return self.__inputs

    def set_current_host_id(self, host_id: int):
        self.__current_host_id = host_id

    def set_inputs_config(self, inputs: InputConfig):
        self.__inputs.update_delegates(inputs)
        self.__inputs = inputs

    def produce_local_slave_controller(self, runtime: IRuntime, player: IPlayer) -> LocalClientController:
        assert self.__client_data.client_flags.is_local()
        from rka.eq2.configs.master.player_controls import get_controller_class_name
        local_client_ctrl_class = pydoc.locate(get_controller_class_name(player.get_server().value, player.get_player_name()))
        if local_client_ctrl_class:
            # noinspection PyCallingNonCallable
            return local_client_ctrl_class(runtime, player)
        else:
            return DefaultPlayerController(runtime, player)


class ClientControllerManager:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__lock = RLock()
        self.client_controllers: Dict[str, ClientController] = dict()

    def client_found(self, client_id: str):
        logger.debug(f'client_found: cid:{client_id}')
        player = self.__runtime.player_mgr.get_player_by_client_id(client_id)
        if not player:
            logger.error(f'found unknown cid:{client_id}')
            return
        logger.debug(f'client_found: player:{player}')
        controller = self.__create_client_controller(player)
        controller.notify_registered()

    def client_lost(self, client_id: str):
        logger.info(f'client_lost: cid:{client_id}')
        player = self.__runtime.player_mgr.get_player_by_client_id(client_id)
        if not player:
            logger.warn(f'lost unknown cid:{client_id}')
            return
        logger.info(f'client_lost: player:{player}, is remote {player.is_remote()}, is local {player.is_local()}')
        controller = self.__get_client_controller(player)
        if not controller:
            logger.error(f'client_lost: player:{player}, client controller not available')
            return
        # do this before controller is released, there are triggers which require parser to be available (for unsubscribing correctness)
        controller.notify_unregistered()
        self.__release_client_controller(player)

    def __create_client_controller(self, player: IPlayer) -> ClientController:
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.client_controllers.keys():
                self.__runtime.parser_mgr.register_remote_parser(client_id)
                if player.is_local():
                    self.client_controllers[client_id] = ClientConfig.get_client_config(client_id).produce_local_slave_controller(self.__runtime, player)
                else:
                    self.client_controllers[client_id] = RemoteClientController(self.__runtime, player)
            return self.client_controllers[client_id]

    def __get_client_controller(self, player: IPlayer) -> Optional[ClientController]:
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.client_controllers.keys():
                logger.error(f'release_client_controller: unknown {player}')
                return None
            return self.client_controllers[client_id]

    def __release_client_controller(self, player: IPlayer):
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.client_controllers.keys():
                logger.error(f'release_client_controller: unknown {player}')
                return
            self.__runtime.parser_mgr.unregister_remote_parser(client_id)
            del self.client_controllers[client_id]

    def add_client_trigger(self, player: IPlayer, trigger: ITrigger):
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.client_controllers.keys():
                return
            controller = self.client_controllers[client_id]
            controller.add_trigger(trigger)

    def get_client_triggers(self, player: IPlayer) -> List[ITrigger]:
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.client_controllers.keys():
                return []
            controller = self.client_controllers[client_id]
            return list(controller.get_triggers())

    def reload_all_triggers(self):
        with self.__lock:
            for client_controller in self.client_controllers.values():
                client_controller.reload_triggers()
                self.__runtime.trigger_mgr.reload_zone_triggers(client_controller.get_player())


class ClientController:
    def __init__(self, runtime: IRuntime, player: IPlayer):
        self.__runtime = runtime
        self.__player = player
        self.__triggers: List[ITrigger] = list()
        self.__triggers_started = False

    def __str__(self):
        return f'GameClientController for player {self.__player}'

    def _get_runtime(self) -> IRuntime:
        return self.__runtime

    # noinspection PyMethodMayBeStatic
    def _get_player_triggers(self) -> List[ITrigger]:
        return []

    def get_player(self) -> IPlayer:
        return self.__player

    def get_triggers(self) -> List[ITrigger]:
        return self.__triggers

    def add_trigger(self, trigger: ITrigger):
        self.__add_triggers([trigger])

    def __add_triggers(self, triggers: Iterable[ITrigger]):
        for trigger in triggers:
            self.__triggers.append(trigger)
            if self.__triggers_started:
                trigger.start_trigger()

    def __initialize_triggers(self):
        self.__add_triggers(self._get_player_triggers())
        self.__add_triggers(self.__runtime.trigger_mgr.get_player_triggers(self.__player))

    def __start_triggers(self):
        if not self.__triggers_started:
            for trigger in self.__triggers:
                trigger.start_trigger()
            self.__triggers_started = True

    def __stop_triggers(self):
        if self.__triggers_started:
            for trigger in self.__triggers:
                trigger.cancel_trigger()
            self.__triggers_started = False
        self.__triggers.clear()

    def reload_triggers(self):
        if not self.__triggers_started:
            return
        self.__stop_triggers()
        self.__initialize_triggers()
        self.__start_triggers()

    def notify_registered(self):
        logger.info(f'notify_registered: {self}')
        self.__runtime.remote_client_event_system.install_bus(self.__player.get_client_id())
        shared_scheduler.schedule(lambda: self.__runtime.capture_pattern_mgr.send_patterns_to_client(self.__player.get_client_id(), False), delay=5.0)
        self.__runtime.request_ctrl.player_switcher.add_player(self.__player)
        EventSystem.get_main_bus().post(MasterEvents.CLIENT_REGISTERED(client_id=self.__player.get_client_id()))
        self.__stop_triggers()
        self.__initialize_triggers()
        self.__start_triggers()

    def notify_unregistered(self):
        logger.info(f'notify_unregistered: {self}')
        # this does not stop player-zone triggers; those must be separately cancelled in trigger_mgr
        self.__stop_triggers()
        EventSystem.get_main_bus().post(MasterEvents.CLIENT_UNREGISTERED(client_id=self.__player.get_client_id()))
        self.__runtime.request_ctrl.player_switcher.remove_player(self.__player)
        self.__runtime.remote_client_event_system.uninstall_bus(self.__player.get_client_id())


class LocalClientController(ClientController):
    def __init__(self, runtime: IRuntime, player: IPlayer, hotkeys: IHotkeySpec):
        ClientController.__init__(self, runtime, player)
        self.__hotkey_spec = hotkeys

    def notify_registered(self):
        ClientController.notify_registered(self)
        self._get_runtime().master_bridge.send_local_client_configure(self.get_player().get_client_id())
        self._get_runtime().key_manager.set_hotkey_spec(self.__hotkey_spec)

    def notify_unregistered(self):
        self._get_runtime().key_manager.unset_hotkey_spec()
        ClientController.notify_unregistered(self)


class DefaultPlayerController(LocalClientController):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        LocalClientController.__init__(self, runtime, player, DefaultMainPlayerHotkeySpec(player))


class RemoteClientController(ClientController):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        ClientController.__init__(self, runtime, player)

    def notify_registered(self):
        ClientController.notify_registered(self)
        self._get_runtime().master_bridge.send_remote_client_configure(self.get_player().get_client_id())

    def notify_unregistered(self):
        ClientController.notify_unregistered(self)
