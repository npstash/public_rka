from typing import Optional

from rka.components.network.network_config import NetworkConfig
from rka.eq2.master import logger
from rka.eq2.master.runtime import Runtime
from rka.eq2.shared.host import HostConfig

__runtime: Optional[Runtime] = None


def handle_extra_command(cmd: str) -> bool:
    if __runtime is None:
        return False
    if cmd == 'parser':
        from rka.eq2.master.ui import debug_helpers
        debug_helpers.print_parser_data(__runtime)
        return True
    elif cmd == 'ability':
        from rka.eq2.master.ui import debug_helpers
        debug_helpers.print_ability_data(__runtime)
        return True
    return False


def run_master(host_config: HostConfig, network_config: NetworkConfig, server_id: str):
    logger.info(f'starting master {server_id}')
    global __runtime
    __runtime = Runtime(host_config, network_config, server_id)
    __runtime.run_blocking()
    logger.mandatory_log('EXIT MAIN')
