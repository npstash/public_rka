import threading
import traceback
from http.client import HTTPException
from typing import Callable, List, Dict, Set, Optional, Tuple

from rka.components.impl.factories import ConnectionFactory
from rka.components.io.log_service import LogLevel
from rka.components.network.rpc import IConnection
from rka.components.rpc_brokers import logger


class Peer(object):
    RPC_send_lock_timeout = 30.0

    def __init__(self, local_id: str, remote_id: str, port: int):
        self.local_id = local_id
        self.remote_id = remote_id
        self.__port = port
        self.__connection_lock = threading.RLock()
        self.__connection: Optional[IConnection] = None
        self.__addresses_lock = threading.RLock()
        self.__addresses: Dict[str, str] = dict()  # remote address -> local address
        self.__local_address_list: List[str] = list()
        self.__remote_address_list: List[str] = list()
        self.__remote_address_set: Set[str] = set()

    def _get_connection(self) -> Optional[IConnection]:
        with self.__connection_lock:
            return self.__connection

    def _get_local_address_list(self) -> List[str]:
        with self.__addresses_lock:
            return self.__local_address_list

    def _get_local_address(self, remote_address: str) -> str:
        with self.__addresses_lock:
            return self.__addresses[remote_address]

    def _get_remote_address_list(self) -> List[str]:
        with self.__addresses_lock:
            return self.__remote_address_list

    def _get_remote_address_set(self) -> Set[str]:
        with self.__addresses_lock:
            return self.__remote_address_set

    def _update_addresses(self, addresses: Dict[str, str]):
        with self.__addresses_lock:
            self.__addresses = addresses.copy()
            self.__local_address_list = list(self.__addresses.values())
            self.__remote_address_list = list(self.__addresses.keys())
            self.__remote_address_set = set(self.__addresses.keys())

    def _connect(self, remote_address: str) -> bool:
        with self.__connection_lock:
            logger.debug(f'_connect to {remote_address}')
            if self.__connection is not None and self.__connection.valid_for(remote_address):
                return True
            self._disconnect()
            try:
                local_address = self._get_local_address(remote_address)
                self.__connection = ConnectionFactory.create_connection(local_address, remote_address, self.__port)
                logger.debug(f'new connection to {remote_address} is {self.__connection}')
                return True
            except OSError as e:
                logger.warn(f'exception {e} opening connection to {self.remote_id}')
        return False

    def _disconnect(self):
        with self.__connection_lock:
            if self.__connection is None:
                return
            try:
                logger.debug(f'_disconnect from {self.__connection.get_remote_address()}')
                self.__connection.close()
            except OSError as e:
                logger.warn(f'exception {e} closing connection to {self.remote_id}')
            finally:
                self.__connection = None

    def _call_with_connection(self, condition_and_results: Callable[[IConnection], Tuple[bool, Optional[List]]]) -> (bool, Optional[List]):
        logger.debug(f'_call_with_connection: condition {condition_and_results}, client {self.remote_id}')
        lock = self.__connection_lock
        locked = lock.acquire(timeout=Peer.RPC_send_lock_timeout)
        if not locked:
            logger.error(f'_call_with_connection: failed to acquire lock, client {self.remote_id}')
            traceback.print_exc()
            return False, None
        try:
            remote_addresses = self._get_remote_address_list()
            connection = self._get_connection()
            if connection is not None:
                # start checking from existing connection
                curr_remote = connection.get_remote_address()
                if curr_remote in remote_addresses:
                    idx = remote_addresses.index(curr_remote)
                    if idx != 0:
                        remote_addresses.insert(0, remote_addresses.pop(idx))
                else:
                    logger.warn(f'address {curr_remote} no longer on addr list despite being connected')
            condition_met = False
            connection_made = False
            results = None
            for remote_address in remote_addresses:
                if not self._connect(remote_address):
                    continue
                connection = self._get_connection()
                try:
                    logger.debug(f'_call_with_connection: connection {connection}, remote id {self.remote_id}')
                    condition_met, results = condition_and_results(connection)
                    connection_made = True
                    logger.debug(f'_call_with_connection: connect: {connection_made}, condition: {condition_met}')
                    if condition_met:
                        break
                except OSError as ce:
                    logger.warn(f'error {ce} while connecting with {remote_address}')
                except Exception as e:
                    logger.error(f'unexpected error {e} while executing {condition_and_results}')
                    traceback.print_exc()
                    self._disconnect()
                    raise e
                self._disconnect()
            success = connection_made and condition_met
            if not connection_made:
                logger.warn(f'no suitable connection for client {self.remote_id}')
            elif not condition_met:
                logger.warn(f'condition not met {condition_and_results}')
            return success, results
        finally:
            lock.release()

    def update_addresses(self, addresses: {str: str}):
        raise NotImplementedError()

    def call_with_proxy(self, action: Callable) -> (bool, Optional[List]):
        raise NotImplementedError()

    def close(self):
        self._disconnect()


class ClientPeer(Peer):
    def __init__(self, local_id: str, remote_id: str, port: int):
        Peer.__init__(self, local_id, remote_id, port)

    def update_addresses(self, client_addresses: Dict[str, str]):
        logger.debug(f'update_addresses: client addresses {client_addresses}')
        self._update_addresses(client_addresses)

    def call_with_proxy(self, action: Callable) -> (bool, Optional[List]):
        logger.debug(f'call_with_proxy: action {action}, client {self.remote_id}')

        def condition_and_results(connection: IConnection) -> (bool, Optional[List]):
            if logger.get_level() <= LogLevel.DETAIL:
                logger.detail(f'call_with_proxy.condition: action {action}, client {self.remote_id}')
            return True, action(connection.get_proxy())

        return self._call_with_connection(condition_and_results)


class ServerPeer(Peer):
    def __init__(self, local_id: str, remote_id: str, port: int):
        Peer.__init__(self, local_id, remote_id, port)
        self._registered = False

    def update_addresses(self, server_addresses: Dict[str, str]):
        logger.debug(f'update_addresses: server addresses {server_addresses}')
        current_remote_addresses = self._get_remote_address_set()
        connection = self._get_connection()
        if connection is None:
            register = True
        else:
            register = False
            new_server_addresses = server_addresses.keys() - current_remote_addresses
            removed_server_addresses = current_remote_addresses - server_addresses.keys()
            if len(new_server_addresses) + len(removed_server_addresses) > 0 and len(server_addresses) > 0:
                register = True
            if not any([connection.valid_for(remote_address) for remote_address in server_addresses.keys()]):
                register = True
        self._update_addresses(server_addresses)
        if register:
            self.__register_client()

    def __register_client(self) -> bool:
        connected, registered = self.call_with_proxy(lambda proxy: True)
        self._registered = connected and registered
        logger.info(f'registration: connected: {connected}, registered: {registered}')
        return self._registered

    def __unregister_client(self):
        connection = self._get_connection()
        if connection is None:
            logger.info(f'no connection to {self.remote_id}, cant unregister')
            return
        if self._registered:
            logger.info(f'unregistering {self.local_id} from server {self.remote_id}')
            try:
                connection.get_proxy().unregister_client(self.local_id)
            except (OSError, HTTPException):
                logger.info(f'connection lost while unregistering from {self.remote_id}')
            except Exception as e:
                logger.error(f'error {e} while unregistering from {self.remote_id}')
                traceback.print_exc()
                raise e
            finally:
                self._registered = False
        self._disconnect()

    def call_with_proxy(self, action: Callable) -> (bool, Optional[List]):
        local_addresses = self._get_local_address_list()

        def condition_and_results(connection: IConnection) -> (bool, Optional[List]):
            if not self._registered:
                logger.info(f'registering from {connection.get_local_address()} to {connection.get_remote_address()}')
                if not connection.get_proxy().register_client(self.local_id, local_addresses):
                    logger.error(f'remote service at {connection.get_remote_address()} rejected registration')
                    return False, None
                self._registered = True
                logger.info(f'registration in remote service successful')
            return True, action(connection.get_proxy())

        return self._call_with_connection(condition_and_results)

    def close(self):
        self.__unregister_client()
        super().close()
