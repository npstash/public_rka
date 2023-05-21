from __future__ import annotations

from typing import Iterable, Optional

DEFAULT_RKARPC_SERVER_PORT = 25510
FIRST_RKARPC_CLIENT_PORT = 25520
DEFAULT_DISCOVERY_PORT = 25500
LOCAL_NETWORK = '127.0.0.1'
KEEPALIVE_PING = True


class NetworkServiceConfig:
    def __init__(self, port: int, filtered_nifs: Optional[Iterable[str]]):
        self.port = port
        self.filtered_nifs = list(filtered_nifs) if filtered_nifs else []


class NetworkConfig:
    def __init__(self,
                 discovery_port=DEFAULT_DISCOVERY_PORT,
                 server_service_port=DEFAULT_RKARPC_SERVER_PORT,
                 client_service_port=FIRST_RKARPC_CLIENT_PORT,
                 keepalive_ping=KEEPALIVE_PING,
                 filtered_server_nifs: Optional[Iterable[str]] = None,
                 filtered_client_nifs: Optional[Iterable[str]] = None):
        self.client_service = NetworkServiceConfig(port=client_service_port, filtered_nifs=filtered_client_nifs)
        self.server_service = NetworkServiceConfig(port=server_service_port, filtered_nifs=filtered_server_nifs)
        self.discovery_port = discovery_port
        self.keepalive_ping = keepalive_ping

    def create_local_client_config(self) -> NetworkConfig:
        return NetworkConfig(discovery_port=self.discovery_port,
                             server_service_port=self.server_service.port,
                             client_service_port=self.client_service.port,
                             filtered_client_nifs=[LOCAL_NETWORK],
                             )
