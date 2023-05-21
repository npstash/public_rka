import os
import random
import socket
import sys
import threading
import time
from typing import Callable, Optional

from rka.app.app_info import AppInfo
from rka.app.reloader import reload_modules
from rka.components.cleanup import CleanupManager
from rka.components.concurrency.rkathread import RKAThread
from rka.components.network.network_config import NetworkConfig, LOCAL_NETWORK
from rka.eq2.configs.shared.hosts import host_configs
from rka.eq2.shared.host import HostConfig, HostRole, InputType


class Starter:
    def __init__(self):
        self.hostname: Optional[str] = None
        self.host_config: Optional[HostConfig] = None
        self.extra_command_handler: Optional[Callable[[str], bool]] = None

    def run_command_console(self):
        while not CleanupManager.is_closing():
            try:
                time.sleep(4.0)
            except KeyboardInterrupt:
                print('commands: dump, parser, ability, exit, quit, ver, reload', file=sys.stderr)
                print('?>', file=sys.stderr)
                line = input()
                cmd = line.strip()
                if not cmd:
                    continue
                if self.handle_common_command(cmd):
                    continue
                self.get_extra_command_handler()(cmd)

    # noinspection PyMethodMayBeStatic
    def handle_common_command(self, cmd: str) -> bool:
        if cmd == 'dump' or cmd == 'd':
            RKAThread.dump_threads(stderr=True)
            return True
        if cmd == 'reload' or cmd == 'r':
            CleanupManager.close_all(call_quit=False)
            reload_modules()
            return True
        elif cmd == 'exit' or cmd == 'e':
            # noinspection PyProtectedMember,PyUnresolvedReferences
            os._exit(1)
            return True
        elif cmd == 'quit' or cmd == 'q':
            CleanupManager.close_all()
            return True
        elif cmd == 'ver' or cmd == 'v':
            print(AppInfo.get_host_config(), file=sys.stderr)
            return True
        return False

    def launch_application(self):
        if len(sys.argv) < 2:
            print('usage: <module_name> [NIFADDR_1 NIFADDR_2 ...]')
        argc = len(sys.argv)
        self.hostname = socket.gethostname()
        AppInfo.set_hostname(self.hostname)
        filtered_nifs = set()
        args_start = 1
        if argc > 1 and (sys.argv[1].lower() == 'master' or sys.argv[1].lower() == 'slave'):
            forced_role = HostRole.Master if sys.argv[1].lower() == 'master' else HostRole.Slave
            forced_id = int(sys.argv[2])
            forced_input = InputType.CONFIG_1920 if sys.argv[3].lower() == 'native' else InputType.CONFIG_1280
            tmp_host_config = host_configs[self.hostname]
            host_configs[self.hostname] = HostConfig(host_id=forced_id, host_role=forced_role, input_type=forced_input, eq2_path=tmp_host_config.get_eq2_path())
            args_start += 3
        if argc > args_start:
            filtered_nifs = set(sys.argv[args_start:])
        self.host_config = host_configs[self.hostname]
        AppInfo.set_host_config(self.host_config)
        if self.host_config.host_role == HostRole.Master:
            if filtered_nifs:
                filtered_nifs.add(LOCAL_NETWORK)
            server_network_config = NetworkConfig(filtered_client_nifs=[LOCAL_NETWORK], filtered_server_nifs=filtered_nifs)
            # randomize the ID, otherwise restarting master immediately after closing does not make clients update themselves
            random.seed()
            from rka.eq2.master.starter import run_master
            server_name = f'SERVER-{random.randint(0, 100000)}'
            threading.Thread(name='Master App Thread', target=lambda: run_master(self.host_config, server_network_config, server_name)).start()
        elif self.host_config.host_role == HostRole.Slave:
            client_network_config = NetworkConfig(filtered_client_nifs=filtered_nifs)
            from rka.eq2.slave.starter import run_slave
            threading.Thread(name='Slave App Thread', target=lambda: run_slave(self.host_config, client_network_config)).start()
        else:
            assert False, self.host_config.host_role

    def get_extra_command_handler(self) -> Callable[[str], bool]:
        if self.extra_command_handler is not None:
            return self.extra_command_handler
        if self.host_config.host_role == HostRole.Master:
            from rka.eq2.master.starter import handle_extra_command
            self.extra_command_handler = handle_extra_command
        elif self.host_config.host_role == HostRole.Slave:
            from rka.eq2.slave.starter import handle_extra_command
            self.extra_command_handler = handle_extra_command
        else:
            assert False, self.host_config.host_role
        return self.extra_command_handler


if __name__ == '__main__':
    starter = Starter()
    starter.launch_application()
    starter.run_command_console()
