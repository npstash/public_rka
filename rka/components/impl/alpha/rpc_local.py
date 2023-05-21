from typing import Dict

from rka.components.io.log_service import LogService
from rka.components.network.rpc import AbstractConnection
from rka.components.rpc_services import IClientService
from rka.log_configs import LOG_RPC

logger = LogService(LOG_RPC)
_local_service_registry: Dict[str, IClientService] = dict()


def register_local_service(virtual_addr: str, service):
    _local_service_registry[virtual_addr] = service


def unregister_local_service(virtual_addr: str):
    if virtual_addr in _local_service_registry.keys():
        del _local_service_registry[virtual_addr]
    else:
        logger.warn(f'error removing service with VA {virtual_addr} from registry: no such key')


class LocalRPCConnection(AbstractConnection):
    def __init__(self, local_address: str, virtual_addr: str):
        AbstractConnection.__init__(self, local_address, virtual_addr)
        logger.debug(f'connecting to Local Service host at {virtual_addr}')
        self.__service = _local_service_registry[virtual_addr]

    def get_proxy(self) -> object:
        return self.__service

    def close(self):
        logger.debug(f'closing connection {self}')
        self.__service = None
