import threading
from typing import Dict, List, Callable, Set, Optional

import netifaces

from rka.components.impl.alpha.discovery_service import NetworkEvent, NetworkService
from rka.components.io.log_service import LogService
from rka.components.network.discovery import INetworkDiscovery, INetworkFilter
from rka.log_configs import LOG_DISCOVERY

NIFDISCO_RETRY_SEC = 30.0

logger = LogService(LOG_DISCOVERY)


class NetifacesNetworkDiscovery(INetworkDiscovery, NetworkService):
    def __init__(self, service_id: str, filtered_nifaddrs: List[str] = None):
        NetworkService.__init__(self, service_id)
        self.__nifs_lock = threading.Condition()
        self.__nif_filter: Optional[INetworkFilter] = None
        self.__nifaddr_to_network: Dict[str, str] = dict()  # NIF_addr -> network
        self.__filtered_nifaddrs = filtered_nifaddrs

    @staticmethod
    def __get_nifaddrs_to_networks() -> Dict[str, str]:  # NIF_addr -> network
        nifs = netifaces.interfaces()
        networks: Dict[str, str] = dict()
        for nif in nifs:
            addresses = netifaces.ifaddresses(nif)
            if netifaces.AF_INET not in addresses:
                continue
            inet_addr = addresses[netifaces.AF_INET][0]
            if 'broadcast' not in inet_addr or 'addr' not in inet_addr:
                continue
            nif_address = inet_addr['addr']
            network = inet_addr['broadcast']
            networks[nif_address] = network
        return networks

    def __detect_nifs(self):
        logger.detail(f'refreshing NIF list, service {self.get_id()}')
        all_nifaddrs_to_networks = NetifacesNetworkDiscovery.__get_nifaddrs_to_networks()
        logger.detail(f'found {len(all_nifaddrs_to_networks)} NIFs {all_nifaddrs_to_networks}')
        new_nifaddrs = set(all_nifaddrs_to_networks.keys())
        disappeared_nifaddrs: Set[str] = set()
        with self.__nifs_lock:
            # find which interface is already configured and remove from the list of new NIFs
            for nifaddr, nifnetw in all_nifaddrs_to_networks.items():
                if nifaddr in self.__nifaddr_to_network.keys():
                    new_nifaddrs.remove(nifaddr)
                # also remove NIFs that are not in the accepting filter
                if self.__filtered_nifaddrs:
                    if nifnetw not in self.__filtered_nifaddrs and nifaddr not in self.__filtered_nifaddrs:
                        new_nifaddrs.remove(nifaddr)
            # find which already configured interface is no longer on the list
            for nifaddr in self.__nifaddr_to_network.keys():
                if nifaddr not in all_nifaddrs_to_networks.keys():
                    disappeared_nifaddrs.add(nifaddr)
        logger.detail(f'disappeared_nifaddrs {disappeared_nifaddrs}')
        for old_nifaddr in disappeared_nifaddrs:
            self.remove_network_interface(old_nifaddr)
        logger.detail(f'new_nifaddrs {new_nifaddrs}')
        for new_nifaddr in new_nifaddrs:
            new_network = all_nifaddrs_to_networks[new_nifaddr]
            self.add_network_interface(new_nifaddr, new_network)
        self._notify_startup_done()

    def __monitor_nifs(self):
        while True:
            self.__detect_nifs()
            if not self._wait_while_running(NIFDISCO_RETRY_SEC):
                break

    def set_nif_filter(self, nif_filter: INetworkFilter):
        self.__nif_filter = nif_filter

    def add_network_interface(self, nifaddr: str, network: str):
        logger.detail(f'add_network_interface: {nifaddr}/{network}')
        if not self.__nif_filter or self.__nif_filter.accept_nifaddr(nifaddr, network):
            logger.info(f'accepted new nif address {nifaddr}/{network}')
        else:
            logger.info(f'rejected new nif address {nifaddr}/{network}')
            return
        with self.__nifs_lock:
            if nifaddr in self.__nifaddr_to_network.keys():
                logger.warn(f'replacing exisitng NIF {nifaddr} bcast address {network}')
            self.__nifaddr_to_network[nifaddr] = network
        self._fire_event(NetworkEvent.NETWORK_FOUND_EVENT_TYPE, nifaddr, network)

    def remove_network_interface(self, nifaddr: str):
        with self.__nifs_lock:
            network = self.__nifaddr_to_network[nifaddr]
            del self.__nifaddr_to_network[nifaddr]
        logger.info(f'removing address {nifaddr} with broadcast {network}')
        self._fire_event(NetworkEvent.NETWORK_LOST_EVENT_TYPE, nifaddr, network)

    def get_nifaddrs_to_networks(self) -> Dict[str, str]:
        with self.__nifs_lock:
            return self.__nifaddr_to_network.copy()

    def add_network_found_observer(self, callback: Callable[[str, str], None]):
        self._add_observer(NetworkEvent.NETWORK_FOUND_EVENT_TYPE, callback)
        get_nifaddrs_to_networks = self.get_nifaddrs_to_networks()
        for nifaddr, network in get_nifaddrs_to_networks.items():
            self._fire_event(NetworkEvent.NETWORK_FOUND_EVENT_TYPE, nifaddr, network)

    def add_network_lost_observer(self, callback: Callable[[str, str], None]):
        self._add_observer(NetworkEvent.NETWORK_LOST_EVENT_TYPE, callback)

    def start(self):
        NetworkService.start(self)
        self._start_tasks([self.__monitor_nifs])

    def stop(self):
        NetworkService.stop(self)
        nifaddrs = self.get_nifaddrs_to_networks()
        for nifaddr in nifaddrs:
            self.remove_network_interface(nifaddr)
