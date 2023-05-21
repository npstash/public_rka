from typing import Tuple, List, Callable, Dict, Any, Optional

from rka.components.rpc_services import IClientBrokerProxy, logger


class ClientBrokerProxy(IClientBrokerProxy):
    def __init__(self):
        self.__target: Optional[IClientBrokerProxy] = None

    def set_target(self, target: IClientBrokerProxy):
        self.__target = target

    def send_to_client(self, client_id: str, commands: List[Dict[str, Any]],
                       completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> Tuple[bool, Optional[List]]:
        if self.__target is not None:
            return self.__target.send_to_client(client_id, commands, completion_cb)
        else:
            logger.error(f'ClientBrokerProxy::send_to_client: target is not set')
            return False, None


class ClientBrokerProxyFactory(object):
    @staticmethod
    def create_proxy():
        return ClientBrokerProxy()
