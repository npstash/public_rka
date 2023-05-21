import datetime
import socket
import threading
from _thread import RLock
from typing import Dict, List, Callable, Union, Optional

import select

from rka.components.impl.alpha.discovery_service import NetworkEvent, NetworkService
from rka.components.io.log_service import LogService
from rka.components.network.discovery import INodeDiscoveryServer, INodeDiscoveryClient
from rka.log_configs import LOG_DISCOVERY

SELECT_TIMEOUT = 2.0
ERROR_COUNT_LIMIT = 5
ERROR_RETRY_SEC = 5.0
BCAST_RETRY_SEC = 5.0
SERVER_LOST_SEC = BCAST_RETRY_SEC * 100
DISCOVERY_MAGIC = 'RKA_DISCOVERY'

logger = LogService(LOG_DISCOVERY)


class UDPBCNodeDiscoveryServer(NetworkService, INodeDiscoveryServer):
    def __init__(self, server_id: str, bcast_port: int):
        NetworkService.__init__(self, server_id)
        self.__bcast_sock = None
        self.__bcast_port = bcast_port
        self.__niflist_lock = RLock()
        self.__enabled_nifs: Dict[str, str] = dict()  # nifaddr: network

    def __keep_bcasting(self):
        bcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        bcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.__bcast_sock = bcast_sock
        self._notify_startup_done()
        error_counts: Dict[str, int] = dict()
        while True:
            with self.__niflist_lock:
                nifaddrs = self.__enabled_nifs.copy()
            remove_nifaddrs: List[str] = list()
            for nifaddr, network in nifaddrs.items():
                logger.detail(f'[{self.id}] Ping broadcast {network} from nif {nifaddr}')
                try:
                    # send NIF address as payload in broadcast
                    msg = bytes(f'{DISCOVERY_MAGIC} {nifaddr} {self.get_id()}', 'utf-8')
                    bcast_sock.sendto(msg, (network, self.__bcast_port))
                    error_counts[nifaddr] = 0
                except OSError as e:
                    logger.warn(f'[{self.id}] Error occured during attempt to broadcast {e} from addr {nifaddr}')
                    if nifaddr in error_counts:
                        error_counts[nifaddr] += 1
                    else:
                        error_counts[nifaddr] = 1
                    if error_counts[nifaddr] >= ERROR_COUNT_LIMIT:
                        logger.warn(f'[{self.id}] Stopping discovery service for addr {nifaddr}, error count limit reached')
                        remove_nifaddrs.append(nifaddr)
                        break
            for nifaddr in remove_nifaddrs:
                self.remove_nifaddr(nifaddr)
                del error_counts[nifaddr]
            if not self._wait_while_running(BCAST_RETRY_SEC):
                break
        bcast_sock.close()
        self.__bcast_sock = None

    def __get_extra_discovery_tasks(self) -> List[Callable]:
        return [self.__keep_bcasting]

    def add_nifaddr(self, nifaddr: str, network: str) -> bool:
        with self.__niflist_lock:
            self.__enabled_nifs[nifaddr] = network

    def remove_nifaddr(self, nifaddr: str):
        with self.__niflist_lock:
            if nifaddr in self.__enabled_nifs:
                del self.__enabled_nifs[nifaddr]

    def remove_all_nifaddrs(self):
        with self.__niflist_lock:
            self.__enabled_nifs.clear()

    def start(self):
        NetworkService.start(self)
        logger.info(f'[{self.id}] Discovery server setup')
        self._start_tasks(self.__get_extra_discovery_tasks())

    def stop(self):
        self.remove_all_nifaddrs()
        bcast_sock = self.__bcast_sock
        if bcast_sock:
            bcast_sock.close()
            self.__bcast_sock = None
        NetworkService.stop(self)


class ServerLocator:
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.addresses: Dict[str, Dict[str, Union[str, datetime.datetime]]] = dict()  # address: {'time':timestamp, 'nif':addr}

    def get_addresses(self) -> Dict[str, str]:  # remote: local
        return {remote_addr: self.addresses[remote_addr]['nif'] for remote_addr in self.addresses.keys()}

    def update_addresses(self, nifaddr: Optional[str] = None, new_address: Optional[str] = None) -> bool:  # True if changed
        changed = False
        now = datetime.datetime.now()
        if nifaddr is not None and new_address is not None:
            if new_address not in self.addresses.keys():
                self.addresses[new_address] = dict()
                changed = True
            self.addresses[new_address]['time'] = now
            self.addresses[new_address]['nif'] = nifaddr
        addrs_to_remove: List[str] = list()
        delta = None
        for addr in self.addresses.keys():
            delta = now - self.addresses[addr]['time']
            if delta >= datetime.timedelta(seconds=SERVER_LOST_SEC):
                addrs_to_remove.append(addr)
        for addr in addrs_to_remove:
            nif = self.addresses[addr]['nif']
            logger.warn(f'master {self.server_id}: remote address {addr} with nif {nif} lost due to timeout {delta}')
            del self.addresses[addr]
            changed = True
        return changed


class UDPBCNodeDiscoveryClient(NetworkService, INodeDiscoveryClient):
    def __init__(self, client_id: str, discovery_port: int):
        NetworkService.__init__(self, client_id)
        self.__listen_sockets: Dict[str, socket.socket] = dict()  # NIF_addr -> socket
        self.__listen_port = discovery_port
        self.__server_list_lock = threading.Condition()
        self.__servers: Dict[str, ServerLocator] = dict()  # server_id -> ServerLocator

    def __monitor_servers(self):
        while self.is_running():
            self._wait_while_running(SERVER_LOST_SEC)
            with self.__server_list_lock:
                for server_id in self.__servers.keys():
                    changed = self.__servers[server_id].update_addresses()
                    if changed:
                        server_addresses = self.__servers[server_id].get_addresses()
                        self._fire_event(NetworkEvent.SERVER_UPDATE_EVENT_TYPE, server_id, server_addresses)

    def __keep_listening_for_bcast(self):
        error_counts: Dict[str, int] = dict()
        self._notify_startup_done()
        while self.is_running():
            sockets = self.__listen_sockets.copy()
            if not sockets:
                if not self._wait_while_running(BCAST_RETRY_SEC):
                    logger.warn(f'[{self.id}] No listening sockets available to discover broadcasts, exiting')
                    break
                else:
                    continue
            remove_nifaddrs: List[str] = list()
            fdesc = [sock.fileno() for sock in sockets.values()]
            fdesmap = {sock.fileno(): addr for addr, sock in sockets.items()}
            logger.detail(f'[{self.id}] Select listening sockets, fds = {fdesc}')
            fdr, _, fderr = select.select(fdesc, [], fdesc, SELECT_TIMEOUT)
            for fd in fdr:
                nifaddr = fdesmap[fd]
                sock = sockets[nifaddr]
                error_occured = None
                if fd in fderr:
                    error_occured = f'exceptonal condition occured on fd for nif {nifaddr}'
                else:
                    try:
                        msg, (remote_addr, _) = sock.recvfrom(64)
                        logger.detail(f'[{self.id}] Received data {msg} on nif {nifaddr} from remote {remote_addr}')
                        splits = str(msg, 'utf-8').split()
                        if len(splits) < 3:
                            error_occured = 'message has too few tokens'
                        else:
                            magic, remote_addr_in_payload, server_id = splits[0], splits[1], splits[2]
                            if magic != DISCOVERY_MAGIC:
                                error_occured = f'wrong magic id {magic}'
                            else:
                                if remote_addr != remote_addr_in_payload:
                                    logger.warn(f'[{self.id}] Remote address missmatch {remote_addr}, {remote_addr_in_payload}')
                                self.__server_update(nifaddr, remote_addr_in_payload, server_id)
                    except IOError as e:
                        error_occured = f'exception during reading broadcast {e} from nif addr {nifaddr}'
                if error_occured is not None:
                    logger.warn(f'[{self.id}] Problem when receiving broadcast /{error_occured}/')
                    if nifaddr in error_counts.keys():
                        error_counts[nifaddr] += 1
                    else:
                        error_counts[nifaddr] = 1
                    if error_counts[nifaddr] >= ERROR_COUNT_LIMIT:
                        logger.error(f'[{self.id}] Stopping discovery listen for nif addr {nifaddr}')
                        remove_nifaddrs.append(nifaddr)
                        break
                else:
                    error_counts[nifaddr] = 0
            for nifaddr in remove_nifaddrs:
                self.remove_nifaddr(nifaddr)
                del error_counts[nifaddr]

    def __server_update(self, nifaddr: str, remote_addr: str, server_id: str):
        logger.detail(f'[{self.id}] Received broadcast on {nifaddr} from {remote_addr}, id={server_id}')
        with self.__server_list_lock:
            if server_id not in self.__servers.keys():
                logger.info(f'[{self.id}] New master {server_id} registered')
                self.__servers[server_id] = ServerLocator(server_id)
            changed = self.__servers[server_id].update_addresses(nifaddr, remote_addr)
            if changed:
                server_addresses = self.__servers[server_id].get_addresses()
                self._fire_event(NetworkEvent.SERVER_UPDATE_EVENT_TYPE, server_id, server_addresses)

    def add_nifaddr(self, nifaddr: str, network: str) -> bool:
        sock = None
        port = self.__listen_port
        try:
            logger.info(f'[{self.id}] Creating new listening socket on {nifaddr}:{port}')
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((nifaddr, port))
            logger.debug(f'[{self.id}] Created new listening socket on {nifaddr}:{port}, fd={sock.fileno()}')
        except OSError as e:
            logger.warn(f'[{self.id}] Failed to setup socket on address {nifaddr}:{port} due to {e}')
            if sock is not None:
                sock.close()
                sock = None
        with self.__server_list_lock:
            if nifaddr in self.__listen_sockets.keys():
                logger.warn(f'[{self.id}] add_nifaddr: {nifaddr} was already configured')
            if sock:
                self.__listen_sockets[nifaddr] = sock
        return sock is not None

    def remove_nifaddr(self, nifaddr: str):
        logger.debug(f'[{self.id}] remove_nifaddr: closing listening socket on {nifaddr}')
        with self.__server_list_lock:
            if nifaddr in self.__listen_sockets.keys():
                sock_to_close = self.__listen_sockets[nifaddr]
            else:
                logger.warn(f'[{self.id}] No socket open at nif {nifaddr}')
                return
            del self.__listen_sockets[nifaddr]
        if sock_to_close:
            try:
                sock_to_close.close()
                logger.debug(f'[{self.id}] remove_nifaddr: closed listening socket on {nifaddr}')
            except OSError as e:
                logger.warn(f'[{self.id}] Problem to cleanup socket at nif {nifaddr} due to {e}')

    def remove_all_nifaddrs(self):
        sockets = self.__listen_sockets.copy()
        for nifaddr in sockets.keys():
            self.remove_nifaddr(nifaddr)

    def add_server_observer(self, callback: Callable[[str, Dict[str, str]], None]):
        self._add_observer(NetworkEvent.SERVER_UPDATE_EVENT_TYPE, callback)
        with self.__server_list_lock:
            for server_id in self.__servers.keys():
                server_addresses = self.__servers[server_id].get_addresses()
                self._fire_event(NetworkEvent.SERVER_UPDATE_EVENT_TYPE, server_id, server_addresses)

    def clear_server_address_cache(self):
        with self.__server_list_lock:
            self.__servers.clear()

    def start(self):
        NetworkService.start(self)
        logger.info(f'[{self.id}] Discovery client setup')
        self._start_tasks([self.__keep_listening_for_bcast, self.__monitor_servers])

    def stop(self):
        self.remove_all_nifaddrs()
        NetworkService.stop(self)
