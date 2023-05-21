from typing import Dict, Callable


class INetworkService:
    def get_id(self) -> str:
        raise NotImplementedError()

    def wait_for_startup(self):
        raise NotImplementedError()

    def is_running(self) -> bool:
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


class INetworkFilter:
    def accept_nifaddr(self, nifaddr: str, network: str) -> bool:
        raise NotImplementedError()


# noinspection PyAbstractClass
class INetworkDiscovery(INetworkService):
    def set_nif_filter(self, nif_configurator: INetworkFilter):
        raise NotImplementedError()

    def get_nifaddrs_to_networks(self) -> Dict[str, str]:
        raise NotImplementedError()

    def add_network_interface(self, nifaddr: str, network: str):
        raise NotImplementedError()

    def remove_network_interface(self, nifaddr: str):
        raise NotImplementedError()

    def add_network_found_observer(self, callback: Callable[[str, str], None]):
        raise NotImplementedError()

    def add_network_lost_observer(self, callback: Callable[[str, str], None]):
        raise NotImplementedError()


# noinspection PyAbstractClass
class INodeDiscovery(INetworkService):
    def add_nifaddr(self, nifaddr: str, network: str) -> bool:
        raise NotImplementedError()

    def remove_nifaddr(self, nifaddr: str):
        raise NotImplementedError()

    def remove_all_nifaddrs(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class INodeDiscoveryServer(INodeDiscovery, INetworkService):
    pass


# noinspection PyAbstractClass
class INodeDiscoveryClient(INodeDiscovery, INetworkService):
    def add_server_observer(self, callback: Callable[[str, Dict[str, str]], None]):
        raise NotImplementedError()

    def clear_server_address_cache(self):
        raise NotImplementedError()
