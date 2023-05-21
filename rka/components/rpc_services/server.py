import traceback
from threading import Condition
from typing import Dict, FrozenSet, List, Optional, Any, Callable, Tuple

from rka.components.impl.factories import DiscoveryFactory
from rka.components.io.log_service import LogLevel
from rka.components.network.discovery import INodeDiscovery
from rka.components.network.network_config import NetworkConfig
from rka.components.rpc_brokers.brokers import ClientBroker, ClientBrokerFactory, RPCCallToken
from rka.components.rpc_brokers.command_util import make_ping_command, commands_debug_str
from rka.components.rpc_services import IClientService, IServerService, IServer, IInterpreter, logger
from rka.components.rpc_services.remote import Remote


class ServerServiceWrapper(IServerService):
    def __init__(self, server: IServerService):
        self.__wrapped = server

    def __str__(self) -> str:
        return self.__wrapped.__str__()

    def register_client(self, client_id: str, client_addresses: List[str]) -> bool:
        try:
            return self.__wrapped.register_client(client_id, client_addresses)
        except Exception as e:
            logger.error(f'error when registering client {client_id}')
            traceback.print_exc()
            raise e

    def unregister_client(self, client_id: str):
        try:
            self.__wrapped.unregister_client(client_id)
        except Exception as e:
            logger.error(f'error when unregistering client {client_id}')
            traceback.print_exc()
            raise e

    def commands_from_client(self, client_id: str, commands: List[Dict[str, Any]]) -> Optional[List]:
        try:
            return self.__wrapped.commands_from_client(client_id, commands)
        except Exception as e:
            logger.error(f'error when handling command {commands}')
            traceback.print_exc()
            raise e


class ServerToClientRPCCall(RPCCallToken):
    def __init__(self, commands: List[Dict[str, Any]], completion_cb: Optional[Callable[[Optional[List]], None]] = None):
        RPCCallToken.__init__(self, commands, completion_cb)

    def call(self, rpc_proxy: IClientService, commands) -> Any:
        return rpc_proxy.commands_from_server(commands)


class Server(Remote, IServerService, IServer):
    def __init__(self, server_id: str, interpreter: IInterpreter, network_config: NetworkConfig):
        Remote.__init__(self, server_id, network_config.server_service, interpreter)
        assert server_id
        assert network_config
        self.__server_id = server_id
        self.__network_config = network_config
        self.__clients_lock = Condition()
        self.__broker_factory = ClientBrokerFactory(server_id, network_config.client_service.port)
        self.__clients: Dict[str, ClientBroker] = dict()
        self.__new_client_callback = None
        self.__lost_client_callback = None
        self.__service_wrapper = ServerServiceWrapper(self)

    def _create_node_discovery(self) -> INodeDiscovery:
        node_discovery = DiscoveryFactory.create_node_discovery_server(self.__server_id, self.__network_config.discovery_port)
        return node_discovery

    def _get_service_object(self) -> object:
        return self.__service_wrapper

    def start_server(self):
        self._start_services()

    def register_client(self, client_id: str, client_addresses: List[str]) -> bool:
        logger.info(f'register_client: cid:{client_id}, addr:{client_addresses}')
        with self.__clients_lock:
            if client_id in self.__clients.keys():
                client = self.__clients[client_id]
                client.add_client_addresses(client_addresses)
                logger.debug(f'client already registered: cid:{client_id}, updating addresses:{client_addresses}')
                new_registration = False
                registration_status = True
            else:
                client = self.__broker_factory.create_client_broker(client_id)
                client.observe_async_error(lambda: self.unregister_client(client_id))
                client.add_client_addresses(client_addresses)
                if self.__network_config.keepalive_ping:
                    client.start_ping(ServerToClientRPCCall([make_ping_command()]))
                self.__clients[client_id] = client
                registered = True
                logger.debug(f'cid:{client_id} registration status:{registered}')
                new_registration = True
                registration_status = True
        logger.debug(f'register_client: status:{registration_status}, new:{new_registration}')
        if registration_status and new_registration:
            if self.__new_client_callback is not None:
                self.__dispatch_for_new_client(client_id)
        return registration_status

    def unregister_client(self, client_id: str):
        logger.info(f'unregister_client: cid:{client_id}')
        client_to_close = None
        with self.__clients_lock:
            if client_id in self.__clients.keys():
                client = self.__clients[client_id]
                if self.__lost_client_callback is not None:
                    self.__dispatch_for_lost_client(client_id)
                del self.__clients[client_id]
                client_to_close = client
            else:
                logger.info(f'unknown cid:{client_id}, cannot unregister')
        if client_to_close:
            client_to_close.close()

    def commands_from_client(self, client_id: str, commands: List[Dict[str, Any]]) -> Optional[List[Any]]:
        logger.info(f'commands_from_client: cid:{client_id}, command:{commands}')
        with self.__clients_lock:
            if client_id not in self.__clients.keys():
                logger.warn(f'command to unknown cid:{client_id}')
                return None
        return self.dispatch_auto(commands)

    def __dispatch_for_new_client(self, client_id: str):
        logger.debug(f'__dispatch_for_new_client: cid:{client_id}')
        self.dispatch_async([lambda: self.__new_client_callback(client_id)])

    def __dispatch_for_lost_client(self, client_id: str):
        logger.debug(f'__dispatch_for_new_client: cid:{client_id}')
        self.dispatch_async([lambda: self.__lost_client_callback(client_id)])

    def subscribe_for_new_client(self, callback: Callable):
        logger.debug(f'on_new_client: callback:{callback}')
        self.__new_client_callback = callback
        with self.__clients_lock:
            for client_id in self.__clients.keys():
                logger.info(f'on_new_client: notifying for existing cid:{client_id}')
                self.__dispatch_for_new_client(client_id)

    def subscribe_for_lost_client(self, callback: Callable):
        logger.debug(f'on_lost_client: callback:{callback}')
        self.__lost_client_callback = callback

    def get_client_ids(self) -> FrozenSet[str]:
        with self.__clients_lock:
            return frozenset(self.__clients.keys())

    # all non-blocking commands - always None result
    # in case of blocking commands, - None means error/exception and stopped execution
    def send_to_client(self, client_id: str, commands: List[Dict[str, Any]],
                       completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> Tuple[bool, Optional[List]]:
        if logger.get_level() < LogLevel.DEBUG:
            logger.debug(f'server {self.node_id} sending to cid:{client_id}, commands:{commands_debug_str(LogLevel.DEBUG, commands)}')
        with self.__clients_lock:
            if client_id not in self.__clients.keys():
                if logger.get_level() <= LogLevel.INFO:
                    logger.info(f'cannot send {commands_debug_str(LogLevel.INFO, commands)} to {client_id} - not registered, probably already disconnected')
                return False, None
            client = self.__clients[client_id]
        logger.info(f'sending to cid:{client}, command:{commands_debug_str(LogLevel.INFO, commands)}')
        rpc_call = ServerToClientRPCCall(commands, completion_cb)
        connected, results = client.send_remote_call(rpc_call)
        log_level = LogLevel.DEBUG if connected else LogLevel.WARN
        logger.log(f'response: connected:{connected}, results:{results}', log_level)
        if not connected:
            self.unregister_client(client_id)
        return connected, results

    def close(self):
        with self.__clients_lock:
            for client_broker in self.__clients.values():
                client_broker.close()
            self.__clients.clear()
        Remote.close(self)
