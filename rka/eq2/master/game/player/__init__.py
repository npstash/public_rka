from __future__ import annotations

import enum
from enum import Enum, auto
from typing import Dict, Optional

from rka.components.io.log_service import LogService
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import DEFAULT_PLAYER_HEALTH, DEFAULT_PLAYER_POWER
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.location import Location
from rka.log_configs import LOG_PLAYER
from rka.services.api.census import TCensusStruct
from rka.util.util import NameEnum

logger = LogService(LOG_PLAYER)


class HomeCityNames(NameEnum):
    qeynos = 'Qeynos'
    freeport = 'Freeport'
    unknown = '<unknown>'

    def get_call_to_home_ability_crc(self) -> int:
        if self is HomeCityNames.freeport:
            return 4122759557
        elif self is HomeCityNames.qeynos:
            return 408478600
        assert False, f'{self} has no home city ability CRC'


class GuildHallInfo:
    def __init__(self,
                 guildhall_name: str,
                 taskboard_location: Location,
                 recipe_merchant_location: Location,
                 recipe_merchant_name: str,
                 writ_agent_location: Location,
                 writ_agent_name: str,
                 private_guild: bool,
                 workstation_locations: Dict[GameClass, Location],
                 housing: bool):
        self.guildhall_name = guildhall_name
        self.taskboard_location = taskboard_location
        self.recipe_merchant_location = recipe_merchant_location
        self.recipe_merchant_name = recipe_merchant_name
        self.writ_agent_location = writ_agent_location
        self.writ_agent_name = writ_agent_name
        self.private_guild = private_guild
        self.workstation_locations = workstation_locations
        self.housing = housing


class PlayerStatus(enum.IntEnum):
    Offline = 0
    Online = 1
    Logged = 2
    Zoned = 3

    def __str__(self):
        return super().name

    def next(self) -> PlayerStatus:
        return PlayerStatus(self.value + 1) if self < PlayerStatus.Zoned else self

    def previous(self) -> PlayerStatus:
        return PlayerStatus(self.value - 1) if self > PlayerStatus.Offline else self

    def get_display_severity(self):
        if self.value == PlayerStatus.Zoned:
            return Severity.Critical
        if self.value == PlayerStatus.Logged:
            return Severity.High
        if self.value == PlayerStatus.Online:
            return Severity.Normal
        return Severity.Low


class PlayerInfo:
    def __init__(self):
        self.home_city = HomeCityNames.unknown
        self.health = DEFAULT_PLAYER_HEALTH
        self.power = DEFAULT_PLAYER_POWER
        self.base_casting_speed = 100.0
        self.base_reuse_speed = 100.0
        self.base_recovery_speed = 0.0
        self.guildhall_config: Optional[GuildHallInfo] = None
        self.run_overseer_missions = False
        self.buy_overseer_missions = False
        self.keep_overseers_for_alt = False
        self.membership = False

    def fill_from_census(self, player_census_data: TCensusStruct):
        self.health = player_census_data['stats']['health']['max']
        self.power = player_census_data['stats']['power']['max']
        self.base_casting_speed = player_census_data['stats']['ability']['spelltimecastpct']
        self.base_reuse_speed = player_census_data['stats']['ability']['spelltimereusepct']
        self.base_recovery_speed = player_census_data['stats']['ability']['spelltimerecoverypct']


class CharacterGearSlots(Enum):
    # slot#, column, row
    head = (2, 1, 1)
    shoulder = (4, 1, 2)
    chest = (3, 1, 3)
    forearms = (5, 1, 4)
    hands = (6, 1, 5)
    legs = (7, 1, 6)
    feet = (8, 1, 7)
    cloak = (19, 2, 1)
    charm_left = (20, 3, 1)
    charm_right = (21, 4, 1)
    ear_left = (11, 5, 1)
    ear_right = (12, 6, 1)
    neck = (13, 6, 2)
    ring_left = (9, 6, 3)
    ring_right = (10, 6, 4)
    wrist_right = (15, 6, 5)
    wrist_left = (14, 6, 6)
    waist = (18, 6, 7)
    primary = (0, 3, 8)
    secondary = (1, 4, 8)
    ranged = (16, 5, 8)
    ammo = (17, 6, 8)

    def slot_num(self) -> int:
        return self.value[0]

    def column(self) -> int:
        return self.value[1] - 1

    def row(self) -> int:
        return self.value[2] - 1


class PlayerAspects:
    last_readyup_time = 0.0
    last_cure_curse_time = 0.0
    last_cure_detriment_time = 0.0
    last_detriment_time = 0.0
    all_last_detriments_times: Dict[str, float] = dict()
    default_target_name: Optional[str] = None
    default_follow_target: Optional[str] = None


class AutoattackMode:
    AUTO = 0
    MEELEE = 1
    RANGED = 2
    OFF = 3


class TellType(NameEnum):
    tell = auto()
    say = auto()
    shout = auto()
    ooc = auto()
    group = auto()
    raid = auto()
    guild = auto()
    general = auto()
    auction = auto()
    lfg = auto()
    custom = auto()
    unknown = auto()
