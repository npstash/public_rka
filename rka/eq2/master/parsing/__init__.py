from __future__ import annotations

import enum
import time
from enum import auto, Enum
from typing import Optional, List, Generator, Tuple, Callable

from rka.components.events.event_system import IEventPoster
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_PARSING

logger = LogService(LOG_PARSING)

SHORTTERM_MEASURE_DURATION = 4.0
INSTANT_MEASURE_DURATION = 1.0
CRITICAL_STONESKIN_HP_RATIO = 0.7


class CombatantType(enum.IntEnum):
    MAIN_PLAYER = 1
    MY_PLAYER = 2
    OTHER_PLAYER = 3
    NPC = 4
    PLAYER_DUMBFIRE_PET = 5
    OTHER = 6

    @staticmethod
    def is_player(c_type_id: int) -> bool:
        return c_type_id == CombatantType.MY_PLAYER or c_type_id == CombatantType.MAIN_PLAYER or c_type_id == CombatantType.OTHER_PLAYER

    @staticmethod
    def is_allied(c_type_id: int) -> bool:
        return c_type_id == CombatantType.MY_PLAYER or c_type_id == CombatantType.MAIN_PLAYER \
               or c_type_id == CombatantType.OTHER_PLAYER or c_type_id == CombatantType.PLAYER_DUMBFIRE_PET

    @staticmethod
    def is_my_player(ct: int) -> bool:
        return ct == CombatantType.MY_PLAYER or ct == CombatantType.MAIN_PLAYER

    @staticmethod
    def is_nonmain_player(ct: int) -> bool:
        return ct == CombatantType.MY_PLAYER or ct == CombatantType.OTHER_PLAYER

    @staticmethod
    def is_other_player(ct: int) -> bool:
        return ct == CombatantType.OTHER_PLAYER

    @staticmethod
    def is_npc(ct: int) -> bool:
        return ct == CombatantType.NPC or ct == CombatantType.OTHER


class CTConfirmRule(enum.IntEnum):
    INITIAL = auto()
    ATTK_BY_PLAYER = auto()
    ATTK_BY_NPC = auto()
    BENEFICIAL_ACTION = auto()


class DpsMeasure(Enum):
    TOTAL = auto()
    MAX = auto()
    RECENT = auto()
    INSTANT = auto()


class ICombatantRecord:
    def get_combatant_name(self) -> str:
        raise NotImplementedError()

    def get_combatant_type(self) -> CombatantType:
        raise NotImplementedError()

    def get_outgoing_damage(self, dps_measure: DpsMeasure) -> int:
        raise NotImplementedError()

    def get_incoming_damage(self, dps_measure: DpsMeasure) -> int:
        raise NotImplementedError()

    def get_hitpoints_damage(self, dps_measure: DpsMeasure) -> int:
        raise NotImplementedError()

    def get_consumed_wards(self, dps_measure: DpsMeasure) -> int:
        raise NotImplementedError()

    def get_received_heals(self, dps_measure: DpsMeasure) -> int:
        raise NotImplementedError()

    def get_approx_remaining_wards(self) -> int:
        raise NotImplementedError()

    def get_incoming_hit_counter(self, threshold=0) -> int:
        raise NotImplementedError()

    def get_incoming_hit_counter_in_current_combat(self, threshold=0) -> int:
        raise NotImplementedError()


class AbilityCombatRecord:
    def __init__(self, ability_name: str):
        self.ability_name = ability_name
        self.last_time = 0.0
        self.dot_start_time = 0.0
        self.hits = 0
        self.max = 0
        self.total_damage = 0
        self.autoattack_poster: Optional[IEventPoster] = None
        self.ability_poster: Optional[IEventPoster] = None
        self.drain_poster: Optional[IEventPoster] = None

    def __str__(self) -> str:
        return f'Ability record of {self.ability_name}'

    def record_hit(self, damage: int, is_damage: bool, dot_duration: Optional[float], timestamp: float) -> Tuple[bool, bool]:
        is_dot = False
        if dot_duration:
            if timestamp - self.dot_start_time >= dot_duration:
                self.dot_start_time = timestamp
            else:
                is_dot = True
        is_multi = timestamp - self.last_time < 1.0
        self.last_time = timestamp
        if is_damage:
            self.hits += 1
            self.total_damage += damage
            if damage > self.max:
                self.max = damage
        return is_multi, is_dot

    def restart(self):
        self.hits = 0
        self.max = 0
        self.total_damage = 0

    def get_average_hit(self) -> int:
        if self.hits == 0:
            return 0
        return int(self.total_damage / self.hits)


class ShortTermDpsMeasure:
    def __init__(self, period: float, description=''):
        self.__bin_count = max(10, int(period))
        self.__bin_timespan = period / self.__bin_count
        self.__duration = self.__bin_count * self.__bin_timespan
        # current timestamp-bin - bin calculated using timestamp as if there was no limit of bins and bin 0 is at time 0
        self.__current_ts_bin: Optional[int] = None
        # the actually written bin in the ring of bins
        self.__current_bin: Optional[int] = None
        self.__bins = [0] * self.__bin_count
        self.__start_new = True
        self.description = description

    def reset_measure(self):
        self.__current_ts_bin = None
        self.__current_bin = None
        self.__bins = [0] * self.__bin_count
        self.__start_new = True

    def get_dps(self, now: Optional[float] = None) -> int:
        now = now if now else time.time()
        self.add_hit(0, now)
        return self.__get_dps()

    def __get_dps(self) -> int:
        total = sum(self.__bins)
        return int(total / self.__duration)

    def add_hit(self, damage: int, timestamp: float):
        ts_bin = int(timestamp // self.__bin_timespan)
        current_ts_bin = self.__current_ts_bin
        current_bin = self.__current_bin
        bins = self.__bins
        if self.__start_new:
            self.__current_ts_bin = ts_bin
            self.__current_bin = 0
            current_ts_bin = self.__current_ts_bin
            current_bin = self.__current_bin
            self.__start_new = False
        if current_ts_bin == ts_bin:
            bins[current_bin] += damage
            return
        diff_bins = ts_bin - current_ts_bin
        for i in range(1, diff_bins):
            b = (current_bin + i) % self.__bin_count
            bins[b] = 0
        current_bin = (current_bin + diff_bins) % self.__bin_count
        self.__current_ts_bin = ts_bin
        self.__current_bin = current_bin
        bins[current_bin] = damage

    def _print_debug(self):
        print(f'DPS: {self.description}: dps:{self.get_dps()} cbin:{self.__current_bin} bins:{self.__bins}')


class IDPSParserHook:
    def record_damage(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                      ability_name: str, damage: int, damage_type: str, is_autoattack: bool, timestamp: float):
        pass

    def record_drain(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                     ability_name: str, power_amount: int, drain_type: str, timestamp: float):
        pass


class IDPSParser:
    def get_parse_info_str(self, combatant_limit: int, add_inc_dps: bool, add_combat_duration: bool, add_inc_spike: bool):
        raise NotImplementedError()

    def install_parser_hook(self, hook: IDPSParserHook):
        raise NotImplementedError()

    def uninstall_parser_hook(self, hook: IDPSParserHook):
        raise NotImplementedError()

    def get_start_time(self) -> float:
        raise NotImplementedError()

    def get_duration(self) -> float:
        raise NotImplementedError()

    def get_combatant_record(self, combatant_name: str) -> Optional[ICombatantRecord]:
        raise NotImplementedError()

    def get_combatant_names(self, combatant_filter: Optional[Callable[[ICombatantRecord], bool]] = None) -> List[str]:
        raise NotImplementedError()

    def iter_combatant_records(self) -> Generator[ICombatantRecord, None, None]:
        raise NotImplementedError()

    def get_ability_combat_record(self, combatant_name: str, ability_name: str) -> Optional[AbilityCombatRecord]:
        raise NotImplementedError()

    def get_all_ability_names(self, combatant_name: str) -> List[str]:
        raise NotImplementedError()

    def iter_ability_combat_records(self, combatant_name: str) -> Generator[AbilityCombatRecord, None, None]:
        raise NotImplementedError()

    def recheck_combatant_type(self, player_name: Optional[str] = None):
        raise NotImplementedError()


def get_dps_str(dps_i: int) -> str:
    suffix = ' kmbtzp'
    expk = 0
    dps = float(dps_i)
    while dps >= 1000.0:
        dps /= 1000.0
        expk += 1
    if expk >= len(suffix):
        suffix_ = '?'
    else:
        suffix_ = suffix[expk]
    frac = 2
    dpstmp = dps
    while dpstmp >= 10.0:
        dpstmp /= 10.0
        frac -= 1
    fill = ' ' if frac == 0 else ''
    if frac == 2:
        return f'{dps:.2f}{suffix_}{fill}'
    elif frac == 1:
        return f'{dps:.1f}{suffix_}{fill}'
    elif frac == 0:
        return f'{dps:.0f}{suffix_}{fill}'
    assert False
