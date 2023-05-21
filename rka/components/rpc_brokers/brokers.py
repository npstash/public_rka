import threading
from typing import List, Callable, Dict, Any, Set, Tuple, Optional

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogLevel
from rka.components.network.network_config import NetworkConfig
from rka.components.rpc_brokers import logger
from rka.components.rpc_brokers.command_util import is_any_command_sync, is_any_command_blocking, commands_debug_str
from rka.components.rpc_brokers.peers import Peer, ClientPeer, ServerPeer
from rka.components.rpc_brokers.ping import Ping


class RPCCallToken:
    def __init__(self, commands: List[Dict[str, Any]], completion_cb: Optional[Callable[[Optional[List]], None]] = None):
        self.__commands = commands
        self.__sync = is_any_command_sync(self.__commands)
        self.__block = is_any_command_blocking(self.__commands)
        self.__completion_cb = completion_cb
        self.__str = None

    def __str__(self):
        if not self.__str:
            self.__str = f'RPC call:{commands_debug_str(LogLevel.DEBUG, self.__commands)}'
        return self.__str

    def __call__(self, rpc_proxy) -> Optional[List]:
        results = self.call(rpc_proxy, self.__commands)
        if self.__completion_cb is not None:
            self.__completion_cb(results)
        return results

    def call(self, rpc_proxy, commands: List[Dict[str, Any]]) -> Optional[List]:
        raise NotImplementedError()

    def is_sync(self) -> bool:
        return self.__sync

    def is_blocking(self) -> bool:
        return self.__block


class _BrokerBase(Closeable):
    def __init__(self, local_id: str, initial_remote_id: Optional[str] = None):
        Closeable.__init__(self, explicit_close=True)
        self.__local_id = local_id
        self.__closed = False
        self.__initial_remote_id = initial_remote_id
        self.__peer: Optional[Peer] = None
        self.__queue_lock = threading.Condition()
        self.__peer_lock = threading.RLock()
        self.__async_error_observer: Optional[Callable] = None
        self.__command_queue: List[Optional[Callable]] = list()
        RKAThread(name=f'Broker {self} dispatcher at {local_id} for {initial_remote_id}', target=self.__execute_loop).start()

    def get_local_id(self) -> str:
        return self.__local_id

    def get_remote_id(self) -> str:
        with self.__peer_lock:
            if self.__peer is not None:
                return self.__peer.remote_id
            else:
                return self.__initial_remote_id

    def _get_peer(self) -> Peer:
        with self.__peer_lock:
            return self.__peer

    def _set_peer(self, new_peer: Peer):
        with self.__peer_lock:
            self.__peer = new_peer

    def _close_peer(self):
        logger.info(f'_close_peer: {self}.{self.__peer}')
        peer_to_close = None
        with self.__peer_lock:
            if self.__peer is not None:
                peer_to_close = self.__peer
                self.__peer = None
        if peer_to_close is not None:
            peer_to_close.close()

    def has_connection(self) -> bool:
        with self.__peer_lock:
            return self.__peer is not None

    def __str__(self) -> str:
        return f'{self.__class__.__name__} ({self.get_local_id()} -> {self.get_remote_id()})'

    def __execute_loop(self):
        while True:
            with self.__queue_lock:
                while not self.__command_queue:
                    self.__queue_lock.wait(5.0)
                    if self.__closed:
                        return
                task = self.__command_queue[0]
                if task is None:
                    logger.debug(f'Thread {threading.current_thread().name} exiting')
                    self.__command_queue.clear()
                    self.__queue_lock.notify()
                    return
            logger.debug(f'executing command {task} at {self}')
            task()
            with self.__queue_lock:
                self.__command_queue.pop(0)
                if not self.__command_queue:
                    self.__queue_lock.notify()

    def __queue_command(self, task: Optional[Callable]):
        with self.__queue_lock:
            self.__command_queue.append(task)
            self.__queue_lock.notify()

    def _notify_error_async(self):
        # this can be called within critical section of broker. clear nonblocking event queue and post it there to avoid deadlocks
        if self.__async_error_observer is not None:
            with self.__queue_lock:
                logger.info(f'clearing event queue to post error event')
                self.__command_queue.clear()
                self.__queue_command(lambda: self.__async_error_observer())

    def __nonblocking_command(self, rpccall: Callable):
        peer = self._get_peer()
        if peer is None:
            logger.debug(f'__nonblocking_command: no peer found to {self.get_remote_id()}, dropping {rpccall}')
            self._notify_error_async()
            return
        logger.debug(f'sending non-blocking call {rpccall} from {peer.remote_id}')
        connected, results = peer.call_with_proxy(rpccall)
        if not connected:
            logger.warn(f'connection failed during non-blocking command {rpccall} execution')
            self._close_peer()
            self._notify_error_async()
        else:
            logger.debug(f'non-blocking command {rpccall} result {results}')

    def __blocking_command(self, rpc_call_token: RPCCallToken) -> Tuple[bool, Optional[List]]:
        # instead of queueing a future, send from this thread, its much faster
        with self.__queue_lock:
            while self.__command_queue and not self.__closed:
                self.__queue_lock.wait(5.0)
            if self.__closed:
                logger.warn(f'__blocking_command: closed: {self.get_remote_id()}')
                return False, None
        peer = self._get_peer()
        if peer is None:
            logger.warn(f'__blocking_command: peer lost: {self.get_remote_id()}')
            return False, None
        return self.__peer.call_with_proxy(rpc_call_token)

    def observe_async_error(self, callback: Callable):
        self.__async_error_observer = callback

    def send_remote_call(self, rpc_call_token: RPCCallToken) -> Tuple[bool, Optional[List]]:
        if not self.has_connection():
            logger.warn(f'send_remote_call: no peer found to {self.get_remote_id()}')
            return False, None
        if rpc_call_token.is_blocking():
            logger.debug(f'queue&wait for blocking call {rpc_call_token} from {self}')
            return self.__blocking_command(rpc_call_token)
        else:
            logger.debug(f'queueing non-blocking call {rpc_call_token} from {self}')
            self.__queue_command(lambda: self.__nonblocking_command(rpc_call_token))
            return True, None

    def close_connection(self):
        logger.info(f'close_connection: {self.get_remote_id()}')
        self._close_peer()

    def close(self):
        with self.__queue_lock:
            self.__queue_command(None)
            self.__closed = True
        self._close_peer()
        Closeable.close(self)


class ClientBroker(_BrokerBase):
    def __init__(self, server_id: str, client_id: str, client_port: int):
        _BrokerBase.__init__(self, local_id=server_id, initial_remote_id=client_id)
        self.__client_addresses = set()
        self.__client_addresses_lock = threading.RLock()
        self.__client_port = client_port
        self.__ping = None
        self.__ping_rpc_call = None

    def __send_ping(self):
        # potential error will be notified asynchronously and cause error event
        success, _ = self.send_remote_call(self.__ping_rpc_call)
        if not success:
            self._notify_error_async()

    def start_ping(self, ping_rpc_call: Callable):
        assert self.__ping is None
        self.__ping_rpc_call = ping_rpc_call
        self.__ping = Ping(local_id=self.get_local_id(), remote_id=self.get_remote_id(), ping_cb=self.__send_ping)

    def add_client_addresses(self, client_addresses: List[str]):
        with self.__client_addresses_lock:
            self.__client_addresses.update(client_addresses)
            client_addresses = self.__client_addresses.copy()
        peer = self._get_peer()
        if peer is None:
            peer = ClientPeer(self.get_local_id(), self.get_remote_id(), self.__client_port)
            self._set_peer(peer)
        logger.debug(f'add client {peer.remote_id} addresses {client_addresses}')
        peer.update_addresses({remote: '0.0.0.0' for remote in client_addresses})

    def close(self):
        if self.__ping:
            self.__ping.close()
        _BrokerBase.close(self)


class ClientBrokerFactory(object):
    def __init__(self, server_id: str, client_port: int):
        self.__server_id = server_id
        self.__client_port = client_port

    def create_client_broker(self, client_id: str) -> ClientBroker:
        return ClientBroker(self.__server_id, client_id, self.__client_port)


class ServerBroker(_BrokerBase):
    def __init__(self, client_id: str, network_config: NetworkConfig):
        _BrokerBase.__init__(self, local_id=client_id)
        self.__server_service_port = network_config.server_service.port
        self.__past_server_ids: Set[str] = set()
        self.__past_server_ids_lock = threading.RLock()

    def server_addresses_update(self, server_id: str, server_addresses: Dict[str, str]):
        logger.info(f'server list update for {server_id}: {server_addresses}')
        with self.__past_server_ids_lock:
            if server_id in self.__past_server_ids:
                logger.warn(f'found old server {server_id}, rejecting')
                return
            peer = self._get_peer()
            if peer is not None and peer.remote_id != server_id:
                current_id = peer.remote_id
                # do not reconnect to old master in future
                self.__past_server_ids.add(current_id)
        if len(server_addresses) == 0:
            self._close_peer()
            return
        if peer is not None and peer.remote_id != server_id:
            self._close_peer()
            peer = self._get_peer()
        if peer is None:
            peer = ServerPeer(self.get_local_id(), server_id, self.__server_service_port)
            self._set_peer(peer)
        peer.update_addresses(server_addresses)
