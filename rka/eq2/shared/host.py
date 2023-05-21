import enum
import os
from typing import Optional

from rka.eq2.configs.shared.clients import client_config_data
from rka.eq2.configs.shared.game_constants import EQ2_LOG_FILE_TEMPLATE
from rka.eq2.shared import GameServer


class HostRole(enum.IntEnum):
    Slave = 1
    Master = 2


class InputType(enum.IntEnum):
    CONFIG_1920 = 1
    CONFIG_1280 = 2


class HostConfig:
    def __init__(self, host_id: int, host_role: HostRole, input_type: InputType, eq2_path: str,
                 beta_path: Optional[str] = None, local_window_title: Optional[str] = None, secure=False):
        self.host_id = host_id
        self.host_role = host_role
        self.input_type = input_type
        self.maximized_window = input_type == InputType.CONFIG_1920
        self.input_config = None
        self.secure = secure
        self.local_window_title = local_window_title
        self.local_client_config_data = [data for data in client_config_data if data.is_resident_at_host(host_id)]
        self.client_ids = [data.client_id for data in self.local_client_config_data]
        self.player_names = {data.client_id: data.player_name for data in self.local_client_config_data}
        self.__eq2_path = os.path.normpath(eq2_path) if eq2_path else None
        self.__beta_path = os.path.normpath(beta_path) if beta_path else None

    def __str__(self):
        return f'Host id {self.host_id}, type {self.host_role}'

    def get_input_config(self):
        if self.input_config is None:
            # Host is a shared class, and this function can be only called in Master
            from rka.eq2.master.control.input_configs import InputConfigFactory
            self.input_config = InputConfigFactory.get_input_config(self.host_role, self.input_type)
        return self.input_config

    def get_eq2_path(self, game_server: Optional[GameServer] = None) -> str:
        if game_server == GameServer.beta:
            if self.__beta_path:
                return self.__beta_path
            return f'{self.__eq2_path}{os.sep}BetaServer'
        return self.__eq2_path

    def get_log_filename(self, client_id: str) -> str:
        game_server = None
        player_name = None
        for client_data in self.local_client_config_data:
            if client_data.client_id == client_id:
                game_server = client_data.game_server
                player_name = client_data.player_name
                break
        assert game_server is not None
        assert player_name is not None
        eq2path = self.get_eq2_path(game_server)
        return EQ2_LOG_FILE_TEMPLATE.format(eq2path, game_server.servername, player_name)

    def get_recent_log_filenames_client(self) -> str:
        latest_mtime = None
        latest_client_id = None
        for client_id in self.client_ids:
            log_filename = self.get_log_filename(client_id)
            try:
                mtime = os.path.getmtime(log_filename)
            except OSError:
                continue
            if not latest_mtime or mtime > latest_mtime:
                latest_mtime = mtime
                latest_client_id = client_id
        if not latest_client_id:
            latest_client_id = self.client_ids[0]
        return latest_client_id
