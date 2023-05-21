from typing import Any, Optional, List

from rka.components.rpc_services import IServer
from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.master import IRuntime
from rka.eq2.master.control import logger
from rka.eq2.master.control.action import ActionFactory
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.shared.control.action_id import ActionID


class MasterBridge:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__server: Optional[IServer] = None
        self.__action_factory: Optional[ActionFactory] = None

    def configure(self, server: IServer, action_factory: ActionFactory):
        self.__server = server
        self.__action_factory = action_factory

    def send_parser_subscribe(self, client_id: str, parse_filter: str, preparsed_logs: bool) -> (bool, Optional[List[Any]]):
        params = {'parse_filter': parse_filter, 'preparsed_logs': preparsed_logs}
        ac = self.__action_factory.new_action().custom_action(ActionID.PARSER_SUBSCRIBE, **params)
        return ac.call_action(client_id)

    def send_parser_unsubscribe(self, client_id: str, parse_filter: str, preparsed_logs: bool) -> bool:
        params = {'parse_filter': parse_filter, 'preparsed_logs': preparsed_logs}
        ac = self.__action_factory.new_action().custom_action(ActionID.PARSER_UNSUBSCRIBE, **params)
        return ac.post_async(client_id)

    def send_testlog_inject(self, client_id: str, testloglines: str) -> bool:
        params = {'testloglines': testloglines}
        ac = self.__action_factory.new_action().custom_action(ActionID.TESTLOG_INJECT, **params)
        return ac.post_async(client_id)

    def send_event_subscribe(self, client_id: str, event_name: str) -> (bool, Optional[List[Any]]):
        params = {'event_name': event_name}
        ac = self.__action_factory.new_action().custom_action(ActionID.EVENT_SUBSCRIBE, **params)
        return ac.call_action(client_id)

    def send_event_unsubscribe(self, client_id: str, event_name: str) -> bool:
        params = {'event_name': event_name}
        ac = self.__action_factory.new_action().custom_action(ActionID.EVENT_UNSUBSCRIBE, **params)
        return ac.post_async(client_id)

    def send_local_client_configure(self, client_id: str) -> bool:
        ac = self.__action_factory.new_action().custom_action(ActionID.GET_HOSTNAME)
        connected = ac.post_async(client_id)
        return connected

    def send_remote_client_configure(self, client_id: str) -> bool:
        ac = self.__action_factory.new_action().custom_action(ActionID.GET_HOSTNAME).window_activate(EQ2_WINDOW_NAME, set_default=True)
        connected = ac.post_async(client_id)
        return connected

    def send_switch_to_client_window(self, player: Optional[IPlayer], sync=False) -> bool:
        if not player:
            logger.warn('send_switch_to_client_window: player is invalid')
            return False
        window_name = player.get_client_config().get_host_config().local_window_title
        if not window_name:
            return False
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            return False
        ac_switch_to_client = self.__action_factory.new_action().window_activate(window_name)
        if sync:
            connected, result = ac_switch_to_client.call_action(main_player.get_client_id())
            return connected and result and result[0]
        return ac_switch_to_client.post_async(main_player.get_client_id())
