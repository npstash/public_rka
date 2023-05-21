from __future__ import annotations

import enum
from typing import Tuple, Optional

from rka.components.io.log_service import LogService
from rka.components.ui.capture import Rect
from rka.eq2.master import IRuntime
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IPlayer
from rka.log_configs import LOG_SCRIPTING_FRAMEWORK

logger = LogService(LOG_SCRIPTING_FRAMEWORK)


class BagLocation:
    def __init__(self, player: IPlayer, bag_n: int, slot_n: int):
        assert 1 <= bag_n <= 6
        assert 1 <= slot_n
        self.player = player
        self.bag_n = bag_n
        self.slot_n = slot_n

    def __str__(self):
        return f'Bag {self.bag_n} slot {self.slot_n} of {self.player.get_player_name()}'

    def is_same(self, other: BagLocation) -> bool:
        if other is None:
            return False
        if self.bag_n != other.bag_n:
            return False
        if self.slot_n != other.slot_n:
            return False
        if self.player is not other.player:
            return False
        return True

    def get_item_screen_coords(self) -> Tuple[int, int]:
        inputs = self.player.get_inputs()
        sx, sy = inputs.screen.bags_item_1[self.bag_n - 1]
        slot_h = (self.slot_n - 1) // inputs.screen.bags_width[self.bag_n - 1]
        slot_w = (self.slot_n - 1) % inputs.screen.bags_width[self.bag_n - 1]
        return sx + slot_w * inputs.screen.bag_slot_size, sy + slot_h * inputs.screen.bag_slot_size


class MovePrecision:
    HIGH = 0.8
    NORMAL = 1.8
    COARSE = 2.8


class RotatePrecision:
    HIGH = 9.0
    NORMAL = 14.0
    COARSE = 20.0


class MovementParams:
    MAX_MOVE_ATTEMPTS = 10
    MAX_TURN_ATTEMPTS = 5

    def __init__(self):
        # boundaries
        self.max_rotation_angle = 120.0
        self.max_movement_distance = 40.0
        self.default_rotation_precision = RotatePrecision.NORMAL
        self.default_movement_precision = MovePrecision.NORMAL
        # default movement type
        self.movement_speed = 30.0
        self.default_min_movement_duration = 0.013
        self.min_movement_duration = self.default_min_movement_duration
        self.max_movement_duration = 3.5
        # non-adapdative rotation
        self.default_rotation_duration_at_3 = 0.02
        self.rotation_duration_at_3 = self.default_rotation_duration_at_3
        self.rotation_duration_at_90 = 0.45
        # adaptive rotation
        self.rotation_speed = 150.0
        self.default_min_rotation_duration = 0.05
        self.min_rotation_duration = self.default_min_rotation_duration

    def precision_movement_speed(self, movement_distance: float, is_combat: bool) -> float:
        speed = self.movement_speed
        # for combat, actual speed is reduced so movement duration should be extended
        if is_combat:
            speed = speed * 0.6
        # speed needs to be increased for a precise movement -> to decrease movement duration
        if movement_distance <= 2.0:
            speed = speed * 1.5
        elif movement_distance <= 5.0:
            speed = speed * 1.2
        return speed


class RepeatMode(enum.IntEnum):
    DONT_REPEAT = 0
    REPEAT_ON_FAIL = 1
    REPEAT_ON_SUCCESS = 2
    REPEAT_ON_BOTH = 3
    TRY_ALL_ACCESS = 1


class ScriptException(Exception):
    def __init__(self, reason: str):
        self.reason = reason

    def __str__(self) -> str:
        return f'ScriptException: {self.reason}'


class ScriptGuard:
    def is_script_action_allowed(self) -> bool:
        raise NotImplementedError()


class RaidSlotInfo:
    @staticmethod
    def get_slot_number(raid_window: Rect, icon_rect: Rect) -> int:
        return round((icon_rect.y1 - raid_window.y1) / raid_window.height() * 24)

    def __init__(self, gameclass: GameClass, ord_num: int, slot_num: int):
        self.gameclass = gameclass
        self.ord_num = ord_num
        self.slot_num = slot_num
        self.__cached_raid_member: Optional[str] = None

    def __str__(self) -> str:
        return f'slot={self.slot_num} (ord={self.ord_num}): {self.gameclass} ({self.__cached_raid_member})'

    def get_raid_member_name(self, runtime: IRuntime) -> Optional[str]:
        if not self.__cached_raid_member:
            raiders = runtime.zonestate.get_players_in_raid()
            if raiders and self.ord_num < len(raiders):
                self.__cached_raid_member = raiders[self.ord_num]
        return self.__cached_raid_member
