from typing import Set, List, Any, Dict, Callable, Tuple, Optional

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_RPC

logger = LogService(LOG_RPC)


class IClientService(object):
    def commands_from_server(self, commands: List[Dict[str, Any]]) -> Optional[List]:
        raise NotImplementedError()


class IServerService(object):
    def register_client(self, client_id: str, client_addresses: List[str]) -> bool:
        raise NotImplementedError()

    def unregister_client(self, client_id: str):
        raise NotImplementedError()

    def commands_from_client(self, client_id: str, commands: List[Dict[str, Any]]) -> Optional[List]:
        raise NotImplementedError()


class IClientBrokerProxy(object):
    def send_to_client(self, client_id: str, commands: List[Dict[str, Any]],
                       completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> Tuple[bool, Optional[List]]:
        raise NotImplementedError()


# noinspection PyAbstractClass
class IServer(IClientBrokerProxy):
    def start_server(self):
        raise NotImplementedError()

    def subscribe_for_new_client(self, callback: Callable):
        raise NotImplementedError()

    def subscribe_for_lost_client(self, callback: Callable):
        raise NotImplementedError()

    def get_client_ids(self) -> Set[str]:
        raise NotImplementedError()


class IInterpreter(object):
    def interpret(self, command: Dict[str, Any]) -> Optional[Any]:
        raise NotImplementedError()
