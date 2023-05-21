from typing import Optional, List, Dict, Any

from rka.app.app_info import AppInfo
from rka.components.rpc_brokers.command_util import set_command_returning, is_command_returning
from rka.components.rpc_services.client import Client
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.control import logger
from rka.eq2.shared.control.action_id import ACTION_ID_KEY, ActionID


class SlaveBridge:
    def __init__(self):
        self.__client: Optional[Client] = None

    def set_active_client(self, client: Optional[Client]):
        logger.debug(f'set_active_client: {client}')
        self.__client = client

    def __check_client(self) -> bool:
        if self.__client is None:
            logger.warn(f'No client service configured')
            return False
        return True

    @staticmethod
    def __check_result(command: Dict[str, Any], connected: bool, result: Optional[List]) -> bool:
        if not connected:
            logger.warn(f'failed to connect with server for command {command}')
            return False
        if is_command_returning(command) and not result:
            logger.warn(f'server has rejected {command}')
            return False
        return True

    def send_bus_event(self, event: ClientEvent) -> bool:
        if not self.__check_client():
            return False
        command = {ACTION_ID_KEY: ActionID.EVENT_OCCUR.value}
        command.update({'client_id': self.__client.node_id, 'event_name': event.name, 'event_params': event.get_params()})
        set_command_returning(command, True)
        return SlaveBridge.__check_result(command, *self.__client.send_to_server([command]))

    def send_hostname(self) -> bool:
        if not self.__check_client():
            return False
        command = {ACTION_ID_KEY: ActionID.REMOTE_HOSTNAME.value}
        command.update({'client_id': self.__client.node_id, 'hostname': AppInfo.get_hostname()})
        set_command_returning(command, False)
        return SlaveBridge.__check_result(command, *self.__client.send_to_server([command]))
