from __future__ import annotations

import enum
from enum import auto, Enum
from typing import Optional

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_PLAYER
from rka.util.util import NameEnum

logger = LogService(LOG_PLAYER)


class ClientFlags(enum.IntFlag):
    Local = 1
    Remote = 2
    Hidden = 4
    Automated = 8
    none = 0

    def __or__(self, other) -> ClientFlags:
        return enum.IntFlag.__or__(self, other)

    def __and__(self, other) -> ClientFlags:
        return enum.IntFlag.__and__(self, other)

    def __xor__(self, other) -> ClientFlags:
        return enum.IntFlag.__xor__(self, other)

    def is_local(self) -> bool:
        return self.value & ClientFlags.Local != 0

    def is_remote(self) -> bool:
        return self.value & ClientFlags.Remote != 0

    def is_hidden(self) -> bool:
        return self.value & ClientFlags.Hidden != 0

    def is_automated(self) -> bool:
        return self.value & ClientFlags.Automated != 0


class GameVersion(NameEnum):
    US = auto()
    EU = auto()


class GameServer(Enum):
    unknown = 'Unknown', None
    majdul = 'Maj\'Dul', GameVersion.US
    isle_of_refuge = 'Isle of Refuge', GameVersion.US
    halls_of_fate = 'Halls of Fate', GameVersion.US
    skyfire = 'Skyfire', GameVersion.US
    kaladim = 'Kaladim', None
    thurgadin = 'Thurgadin', GameVersion.EU
    beta = 'Beta', None

    def __init__(self, *values):
        self._value_: str = values[0]
        self.servername: str = self._value_
        self.gameversion: Optional[GameVersion] = values[1]


class Groups(enum.IntFlag):
    NONE = auto()
    MAIN_1 = auto()
    MAIN_2 = auto()
    MAIN_OTHER = auto()
    RAID_2 = auto()
    RAID_3 = auto()
    RAID_4 = auto()
    # needs to be after all auto() usages
    RAID_1 = MAIN_1
    ANY = MAIN_1 | MAIN_2 | RAID_1 | RAID_2 | RAID_3 | RAID_4
    MAIN = MAIN_1 | MAIN_2 | MAIN_OTHER

    def is_main_group(self) -> bool:
        return bool(self & Groups.MAIN)

    def is_same_group(self, other: Groups) -> bool:
        this = Groups.MAIN if self.is_main_group() else self
        other = Groups.MAIN if other.is_main_group() else other
        return bool(this & other)

    def get_overlay_resolve_priority(self) -> int:
        if self & Groups.MAIN_1:
            return 10
        if self & Groups.MAIN or self & Groups.RAID_1:
            return 9
        if self & Groups.RAID_2 or self & Groups.RAID_3 or self & Groups.RAID_4:
            return 8
        return 0


GROUP_LIST = [Groups.MAIN, Groups.RAID_2, Groups.RAID_3, Groups.RAID_4]


class ClientConfigData:
    __known_client_ids = set()

    def __init__(self, host_id: int, client_id: str, client_flags: ClientFlags, game_server: GameServer, player_name: str,
                 overlay_id: int, group_id: Groups, cred_key: str, alternative_host_id: Optional[int] = None,
                 launcher_batch: Optional[str] = None):
        assert client_id not in ClientConfigData.__known_client_ids, f'Repeated value of client_id: {client_id}'
        assert isinstance(client_flags, ClientFlags) and client_flags & (ClientFlags.Remote | ClientFlags.Local)
        ClientConfigData.__known_client_ids.add(client_id)
        self.host_id = host_id
        self.overlay_id = overlay_id
        self.client_id = client_id
        self.client_flags = client_flags
        self.game_server = game_server
        self.player_name = player_name
        self.player_id = f'{self.game_server.value}.{self.player_name}'
        self.group_id = group_id
        self.default_group_id = group_id
        self.cred_key = cred_key
        self.alternative_host_id = alternative_host_id
        self.launcher_batch = launcher_batch

    def is_resident_at_host(self, host_id: int) -> bool:
        return host_id == self.host_id or (self.alternative_host_id is not None and host_id == self.alternative_host_id)

    def join_to_group(self, new_group: Groups) -> bool:
        if not self.group_id.is_same_group(new_group):
            logger.warn(f'Change player {self.player_name} group to {new_group.name}')
            self.group_id = new_group
            return True
        return False

    def restore_group(self) -> bool:
        if self.group_id != self.default_group_id:
            logger.warn(f'Restore player {self.player_name} group to {self.default_group_id.name}')
            self.group_id = self.default_group_id
            return True
        return False


class ClientRequests:
    COMBAT = 'combat'
    FOLLOW = 'follow'
    STOP_FOLLOW = 'stop_follow'
    GROUP_CURE = 'cure'
    ACCEPT = 'accept'
    CLICK = 'click'
    START_OOZC = 'start_offzone_combat'
    STOP_OOZC = 'stop_offzone_combat'
