from typing import Optional

from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.shared.host import HostRole, HostConfig, InputType

host_configs = {
    # real PC's ONLY, dont add VMs
    'HOSTNAME': HostConfig(host_id=0,
                           host_role=HostRole.Master,
                           input_type=InputType.CONFIG_1920,
                           eq2_path='',
                           beta_path='',
                           local_window_title=EQ2_WINDOW_NAME,
                           secure=True
                           ),
}

hostid_to_hostname = {
    host.host_id: hostname for hostname, host in host_configs.items()
}

hostid_to_hostconfig = {
    host.host_id: host for host in host_configs.values()
}

__local_window_title_roles = {
    host_config.local_window_title.lower(): host_config.host_role for host_config in host_configs.values() if host_config.local_window_title
}


def __get_window_role_by_tile(wintitle: Optional[str]) -> Optional[HostRole]:
    if not wintitle:
        return None
    wintitle = wintitle.lower()
    for local_window_title, role in __local_window_title_roles.items():
        if local_window_title in wintitle:
            return role
    return None


def is_slave_window(wintitle: Optional[str]) -> bool:
    return __get_window_role_by_tile(wintitle) == HostRole.Slave


def is_master_window(wintitle: Optional[str]) -> bool:
    return __get_window_role_by_tile(wintitle) == HostRole.Master
