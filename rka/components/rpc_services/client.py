import traceback
from typing import List, Any, Dict, Callable, Tuple, Optional

from rka.components.impl.factories import DiscoveryFactory
from rka.components.io.log_service import LogLevel
from rka.components.network.discovery import INodeDiscoveryClient, INodeDiscovery
from rka.components.network.network_config import NetworkConfig
from rka.components.rpc_brokers.brokers import ServerBroker, RPCCallToken
from rka.components.rpc_brokers.command_util import commands_debug_str, is_any_ping_command
from rka.components.rpc_brokers.ping import Watchdog
from rka.components.rpc_services import IClientService, IServerService, IInterpreter, logger
from rka.components.rpc_services.remote import Remote


class ClientServiceWrapper(IClientService):
    def __init__(self, client: IClientService):
        self.__wrapped = client

    def __str__(self):
        return self.__wrapped.__str__()

    def commands_from_server(self, commands: List[Dict[str, Any]]) -> Optional[List]:
        try:
            return self.__wrapped.commands_from_server(commands)
        except Exception as e:
            logger.error(f'error when handling command {commands}')
            traceback.print_exc()
            raise e


class ClientToServerRPCCall(RPCCallToken):
    def __init__(self, client_id: str, commands: List[Dict[str, Any]], completion_cb: Optional[Callable[[Optional[List]], None]] = None):
        RPCCallToken.__init__(self, commands, completion_cb)
        self.__client_id = client_id

    def call(self, rpc_proxy: IServerService, commands: List[Dict[str, Any]]) -> Optional[List]:
        return rpc_proxy.commands_from_client(self.__client_id, commands)


class Client(Remote, IClientService):
    def __init__(self, client_id: str, interpreter: IInterpreter, network_config: NetworkConfig):
        Remote.__init__(self, client_id, network_config.client_service, interpreter)
        self.__client_id = client_id
        self.__network_config = network_config
        self.__server_broker = ServerBroker(client_id, network_config)
        self.__service_wrapper = ClientServiceWrapper(self)
        self.__node_discovery: Optional[INodeDiscoveryClient] = None
        self.__watchdog: Optional[Watchdog] = None

    def _create_node_discovery(self) -> INodeDiscovery:
        self.__node_discovery = DiscoveryFactory.create_node_discovery_client(self.__client_id, self.__network_config.discovery_port)
        self.__node_discovery.add_server_observer(self.__server_broker.server_addresses_update)
        return self.__node_discovery

    def _get_service_object(self) -> object:
        return self.__service_wrapper

    def __start_watchdog(self):
        if not self.__watchdog:
            self.__watchdog = Watchdog(local_id=self.__client_id, remote_id=self.__server_broker.get_remote_id(), ping_not_received_cb=self.__watchdog_fired)
        self.__watchdog.start_watchdog()

    def _start_services(self):
        Remote._start_services(self)

    def start_client(self):
        self._start_services()

    def __on_connection_failed(self):
        logger.warn(f'client {self} connection to server failed')
        self.__server_broker.close_connection()
        if self.__node_discovery:
            self.__node_discovery.clear_server_address_cache()

    def __watchdog_fired(self):
        if self.__server_broker.has_connection():
            logger.warn(f'client {self} watchdog fired, resetting discovery')
            self.__on_connection_failed()
        elif self.is_closed():
            logger.error(f'client {self} watchdog fired, but client is closed')
            watchdog = self.__watchdog
            if watchdog:
                watchdog.close()
                self.__watchdog = None
        else:
            # just ignore - nothing to monitor really
            logger.detail(f'client {self} watchdog fired, but client is not connected and not closed')

    def commands_from_server(self, commands: List[Dict[str, Any]]) -> Optional[List]:
        if self.is_closed():
            logger.warn(f'received command to a closed client: {commands}')
        else:
            if logger.get_level() <= LogLevel.DEBUG:
                logger.debug(f'received command: {commands_debug_str(LogLevel.DEBUG, commands)}')
        watchdog = self.__watchdog
        if watchdog:
            self.__watchdog.feed_watchdog(f'commands_from_server')
        elif is_any_ping_command(commands):
            self.__start_watchdog()
        results = self.dispatch_auto(commands)
        return results

    def send_to_server(self, commands: List[Dict[str, Any]], completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> Tuple[bool, Optional[List]]:
        if self.is_closed():
            logger.warn(f'cannot send: {commands_debug_str(LogLevel.DEBUG, commands)}, client already closed')
            return False, None
        if logger.get_level() <= LogLevel.INFO:
            logger.info(f'sending commands: {commands_debug_str(LogLevel.INFO, commands)}')
        rpc_call = ClientToServerRPCCall(self.node_id, commands, completion_cb)
        connected, results = self.__server_broker.send_remote_call(rpc_call)
        if connected:
            watchdog = self.__watchdog
            if watchdog:
                self.__watchdog.feed_watchdog(f'send_to_server')
        else:
            self.__on_connection_failed()
        return connected, results

    def close(self):
        logger.debug(f'stop client service: {self.__client_id}')
        watchdog = self.__watchdog
        if watchdog:
            self.__watchdog.close()
            self.__watchdog = None
        if self.__server_broker is not None:
            self.__server_broker.close()
            self.__server_broker = None
        Remote.close(self)
