from __future__ import annotations

import datetime
import os
import tempfile
import time
from threading import RLock
from typing import Dict, Generator, Iterable, Optional, List, FrozenSet, Set, Callable, Tuple

from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogLevel
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.interfaces import IPlayer, IAbility
from rka.eq2.master.parsing import CTConfirmRule
from rka.eq2.master.parsing import logger, IDPSParser, CombatantType, ICombatantRecord, get_dps_str, AbilityCombatRecord, DpsMeasure, \
    SHORTTERM_MEASURE_DURATION, INSTANT_MEASURE_DURATION, CRITICAL_STONESKIN_HP_RATIO, ShortTermDpsMeasure, IDPSParserHook
from rka.eq2.parsing import ILogReader
from rka.eq2.parsing.combat_logparser import CombatLogParser, DamageType
from rka.eq2.parsing.parsing_util import ParsingHelpers
from rka.eq2.shared.flags import MutableFlags


class IncomingRecords:
    def __init__(self, runtime: IRuntime, combatant_name: str, initial_combatant_type: CombatantType):
        self.__runtime = runtime
        self.__combatant_name = combatant_name
        self.__combatant_type = initial_combatant_type
        self.__approximate_hitpoints = 1  # unknown
        self.max_stoneskin_hit = 0
        self.max_incoming_hit: Dict[str, int] = dict()  # damage type -> max damage
        self.total_incoming_damage: Dict[str, int] = dict()  # damage type -> total damage
        self.total_remaining_wards: Dict[str, int] = dict()  # ward name -> approx remaining ward
        self.total_received_heal = 0
        self.recent_hitpoints_damage = ShortTermDpsMeasure(SHORTTERM_MEASURE_DURATION, f'inc DPS4 {combatant_name}')
        self.recent_consumed_wards = ShortTermDpsMeasure(SHORTTERM_MEASURE_DURATION, f'inc WPS4 {combatant_name}')
        self.recent_received_heal = ShortTermDpsMeasure(SHORTTERM_MEASURE_DURATION, f'inc HPS4 {combatant_name}')
        self.instant_hitpoints_damage = ShortTermDpsMeasure(INSTANT_MEASURE_DURATION, f'inc DPS1 {combatant_name}')
        self.instant_consumed_wards = ShortTermDpsMeasure(INSTANT_MEASURE_DURATION, f'inc WPS1 {combatant_name}')
        self.incoming_dmg_hit_counter: Dict[int, int] = dict()
        self.incoming_dmg_hit_counter_in_current_combat: Dict[int, int] = dict()
        self.__threshold_step = 20
        self.__thresholds = [i * self.__threshold_step for i in range(int(100 // self.__threshold_step))]
        for t in self.__thresholds:
            self.incoming_dmg_hit_counter[t] = 0
            self.incoming_dmg_hit_counter_in_current_combat[t] = 0
        self.update_combatant_type(initial_combatant_type)

    def update_combatant_type(self, combatant_type: CombatantType):
        if CombatantType.is_my_player(combatant_type):
            player = self.__runtime.player_mgr.get_player_by_name(self.__combatant_name)
            hp = player.get_player_info().health
        elif combatant_type == CombatantType.OTHER_PLAYER:
            hp = self.__runtime.census_cache.get_max_known_player_hitpoints()
        else:
            hp = 1  # unknown
        self.__combatant_type = combatant_type
        self.__approximate_hitpoints = hp

    def reset_incoming(self):
        self.max_stoneskin_hit = 0
        self.max_incoming_hit = dict()
        self.total_incoming_damage = dict()
        self.total_remaining_wards = dict()
        self.total_received_heal = 0
        self.recent_hitpoints_damage.reset_measure()
        self.recent_consumed_wards.reset_measure()
        self.recent_received_heal.reset_measure()
        self.instant_hitpoints_damage.reset_measure()
        self.instant_consumed_wards.reset_measure()
        for t in self.__thresholds:
            self.incoming_dmg_hit_counter_in_current_combat[t] = 0

    def get_nearest_threshold(self, threshold: int) -> int:
        t = int(threshold // self.__threshold_step * self.__threshold_step)
        return min(t, max(self.__thresholds))

    def get_threshold_from_damage(self, damage: int) -> int:
        return self.get_nearest_threshold(int(damage / self.__approximate_hitpoints * 100))

    def get_hits_stronger_or_equal_to_threshold(self, threshold: int, hits_dict: Dict[int, int]) -> int:
        threshold = self.get_nearest_threshold(threshold)
        hits = 0
        for t in self.__thresholds:
            if t < threshold:
                continue
            hits += hits_dict[t]
        return hits

    def get_incoming_dps_str(self, _duration: float) -> str:
        s = ''
        all_inc_dmg = 0
        for damage_type, damage in self.total_incoming_damage.items():
            all_inc_dmg += damage
        if all_inc_dmg > 0:
            max1_type, max1_max = max(self.max_incoming_hit.items(), key=lambda item: item[1])
            max2_type, max2_max = max(self.max_incoming_hit.items(), key=lambda item: item[1] if item[0] != max1_type else 0)
            warded_dps = self.recent_consumed_wards.get_dps()
            incoming_dps = self.recent_hitpoints_damage.get_dps() + warded_dps
            remaining_wards = self.get_remaining_wards()
            s += f'max: {get_dps_str(max1_max)} {max1_type[:5]}/{max2_type[:5]}\n'
            s += f'inc: {get_dps_str(incoming_dps)}\n'
            s += f'wps: {get_dps_str(warded_dps)}\n'
            s += f'wrd: {get_dps_str(remaining_wards)}\n'
        return s

    def __record_total_incoming_dmg(self, damage: int, damage_type: str):
        if damage_type not in self.max_incoming_hit.keys():
            self.max_incoming_hit[damage_type] = 0
            self.total_incoming_damage[damage_type] = 0
        if damage > self.max_incoming_hit[damage_type]:
            self.max_incoming_hit[damage_type] = damage
        self.total_incoming_damage[damage_type] += damage
        threshold = self.get_threshold_from_damage(damage)
        self.incoming_dmg_hit_counter[threshold] += 1
        self.incoming_dmg_hit_counter_in_current_combat[threshold] += 1

    def add_incoming_dmg(self, damage: int, damage_type: str, timestamp: float):
        self.__record_total_incoming_dmg(damage, damage_type)
        self.recent_hitpoints_damage.add_hit(damage, timestamp)
        self.instant_hitpoints_damage.add_hit(damage, timestamp)

    def add_consumed_ward(self, ability_name: str, ward_amount: int, remaining_ward: int, timestamp: float):
        self.__record_total_incoming_dmg(ward_amount, 'warded')
        self.recent_consumed_wards.add_hit(ward_amount, timestamp)
        self.instant_consumed_wards.add_hit(ward_amount, timestamp)
        self.total_remaining_wards[ability_name] = remaining_ward

    def add_received_heal(self, _ability_name: str, heal_amount: int, timestamp: float):
        self.recent_received_heal.add_hit(heal_amount, timestamp)
        self.total_received_heal += heal_amount

    def add_stoneskin(self, stoneskin_amount: int):
        self.max_stoneskin_hit = max(self.max_stoneskin_hit, stoneskin_amount)
        if stoneskin_amount >= self.__approximate_hitpoints * CRITICAL_STONESKIN_HP_RATIO:
            amount_str = get_dps_str(stoneskin_amount)
            event = CombatParserEvents.CRITICAL_STONESKIN(amount=stoneskin_amount, amount_readable=amount_str)
            EventSystem.get_main_bus().post(event)

    def get_remaining_wards(self) -> int:
        if not self.total_remaining_wards:
            return 0
        return sum(self.total_remaining_wards.values())


class OutgoingRecords:
    def __init__(self, runtime: IRuntime, combatant_name: str, initial_combatant_type: CombatantType):
        self.__runtime = runtime
        self.__combatant_name = combatant_name
        self.__combatant_type = initial_combatant_type
        self.ability_records: Dict[str, AbilityCombatRecord] = dict()  # ability name -> record
        self.total_outgoing_damage = 0
        self.recent_outgoing_damage = ShortTermDpsMeasure(SHORTTERM_MEASURE_DURATION, f'ROUT {combatant_name}')
        self.recent_wards_expired: Dict[str, float] = dict()
        self.aoe_targets: Set[str] = set()
        self.update_combatant_type(initial_combatant_type)

    def update_combatant_type(self, combatant_type: CombatantType):
        self.__combatant_type = combatant_type

    def reset_outgoing(self):
        for combat_record in self.ability_records.values():
            combat_record.restart()
        self.total_outgoing_damage = 0
        self.recent_outgoing_damage.reset_measure()

    def get_all_abilities_parse_str(self) -> str:
        s = f'All ability info for {self.__combatant_name}:\n'
        combat_records = list(self.ability_records.values())
        combat_records.sort(key=lambda ch: ch.total_damage, reverse=True)
        for i, combat_record in enumerate(combat_records):
            assert isinstance(combat_record, AbilityCombatRecord)
            if combat_record.total_damage == 0.0:
                continue
            total = get_dps_str(combat_record.total_damage)
            avg = get_dps_str(combat_record.get_average_hit())
            max_hit = get_dps_str(combat_record.max)
            pct = combat_record.total_damage * 100 / self.total_outgoing_damage
            s += f'{i:2}. {combat_record.ability_name}: hits {combat_record.hits}, damage {total}, avg {avg}, max {max_hit}, pct {pct:.2f}%\n'
        return s

    def get_top_abilities_parse_str(self, duration: float) -> str:
        s = f'Top ability parse for {self.__combatant_name}:\n'
        combat_records = list(self.ability_records.values())
        combat_records.sort(key=lambda ch: ch.total_damage, reverse=True)
        total_dmg = 0
        for combat_record in combat_records:
            total_dmg += combat_record.total_damage
        for i, combat_record in enumerate(combat_records[:10]):
            assert isinstance(combat_record, AbilityCombatRecord)
            if combat_record.total_damage == 0.0:
                continue
            dps = get_dps_str(int(combat_record.total_damage / duration))
            if total_dmg > 0:
                pct = combat_record.total_damage / total_dmg * 100
            else:
                pct = 0.0
            s += f'{i:2}. {combat_record.ability_name}: {dps} ({pct:2.0f}%)\n'
        return s

    def get_encounter_dps_str(self, duration: float, position: int, add_damage_spike: bool) -> str:
        now = 0.0
        if add_damage_spike:
            now = time.time()
        if duration < 3.0:
            return ''
        dps = int(self.total_outgoing_damage / duration)
        total_dmg_str = ''
        spike_dmg_str = ''
        if add_damage_spike and position <= 6:
            spike = self.recent_outgoing_damage.get_dps(now)
            if MutableFlags.ALWAYS_SHOW_IMMEDIATE_DPS or spike > dps * 1.2:
                spike_dmg_str = f' ^ {get_dps_str(spike)}'
        combatant_name_short_str = self.__combatant_name[:5]
        if len(combatant_name_short_str) < 5:
            combatant_name_short_str += ' ' * (5 - len(combatant_name_short_str))
        s = f'{combatant_name_short_str} | {get_dps_str(dps)}{spike_dmg_str}{total_dmg_str}\n'
        return s

    def iter_ability_combat_records(self) -> Generator[AbilityCombatRecord, None, None]:
        for ability_combat_record in self.ability_records.values():
            yield ability_combat_record

    def get_ability_combat_record(self, ability_name) -> AbilityCombatRecord:
        if ability_name not in self.ability_records:
            ability_record = AbilityCombatRecord(ability_name)
            # premade poster for autoattack hits
            autoattack_hit_template = CombatParserEvents.COMBAT_HIT(attacker_name=self.__combatant_name, attacker_type=self.__combatant_type,
                                                                    ability_name=ability_name, is_autoattack=True, is_drain=False)
            ability_record.autoattack_poster = EventSystem.get_main_bus().get_poster(autoattack_hit_template)
            # premade poster for non-drain ability hits
            ability_hit_template = CombatParserEvents.COMBAT_HIT(attacker_name=self.__combatant_name, attacker_type=self.__combatant_type,
                                                                 ability_name=ability_name, is_autoattack=False, is_drain=False)
            ability_record.ability_poster = EventSystem.get_main_bus().get_poster(ability_hit_template)
            # premade poster for drain ability hits
            drain_hit_template = CombatParserEvents.COMBAT_HIT(attacker_name=self.__combatant_name, attacker_type=self.__combatant_type,
                                                               ability_name=ability_name, is_autoattack=False, is_drain=True)
            ability_record.drain_poster = EventSystem.get_main_bus().get_poster(drain_hit_template)
            self.ability_records[ability_name] = ability_record
        else:
            ability_record = self.ability_records[ability_name]
        return ability_record

    def add_encounter_dmg(self, damage: int, timestamp: float):
        self.total_outgoing_damage += damage
        self.recent_outgoing_damage.add_hit(damage, timestamp)

    def add_combat_hit(self, target_name: str, target_combatant_type: Optional[CombatantType], ability_name: str, damage: int, damage_type: str,
                       is_autoattack: bool, is_drain: bool, dot_duration: Optional[float], timestamp: float):
        ability_record = self.get_ability_combat_record(ability_name)
        is_multi, is_dot = ability_record.record_hit(damage, not is_drain, dot_duration, timestamp)
        if is_multi:
            # another target had been just hit, which makes is_multi True
            if target_name not in self.aoe_targets:
                is_multi = False
        else:
            # new hit (possibly a DoT, but that flag is not valid for NPCs), collect AOE targets again
            self.aoe_targets.clear()
        self.aoe_targets.add(target_name)
        is_aoe = len(self.aoe_targets) > 1
        if damage <= 0:
            return
        if is_autoattack:
            poster = ability_record.autoattack_poster
        elif is_drain:
            poster = ability_record.drain_poster
        else:
            poster = ability_record.ability_poster
        if target_combatant_type is not None:
            event = CombatParserEvents.COMBAT_HIT(target_name=target_name, target_type=target_combatant_type,
                                                  damage=damage, damage_type=damage_type, is_multi=is_multi, is_dot=is_dot, is_aoe=is_aoe,
                                                  timestamp=timestamp)
        else:
            # value of target_type is unset
            event = CombatParserEvents.COMBAT_HIT(target_name=target_name, damage=damage, damage_type=damage_type,
                                                  is_multi=is_multi, is_dot=is_dot, is_aoe=is_aoe,
                                                  timestamp=timestamp)
        poster.post(event)

    def add_remaining_ward(self, target_name: str, target_combatant_type: Optional[CombatantType], ability_name: str, remaining_ward: int,
                           timestamp: float):
        if remaining_ward != 0:
            return
        recent_expiration = self.recent_wards_expired.setdefault(ability_name, 0.0)
        self.recent_wards_expired[ability_name] = timestamp
        # 0 remaining ward (grp ward) may show for every group member within shor amount of time
        if timestamp - recent_expiration < 1.5:
            logger.debug(f'Skip excessive expiration for {ability_name}')
            return
        ability_locator = self.__runtime.ability_reg.get_ability_locator_by_name(ability_name)
        if ability_locator and ability_locator.get_ext_object().ward_expires:
            if target_combatant_type is not None:
                event = CombatParserEvents.WARD_EXPIRED(caster_name=self.__combatant_name, caster_type=self.__combatant_type,
                                                        target_name=target_name, target_type=target_combatant_type,
                                                        ability_name=ability_name, timestamp=timestamp)
            else:
                # target type is unset
                event = CombatParserEvents.WARD_EXPIRED(caster_name=self.__combatant_name, caster_type=self.__combatant_type,
                                                        target_name=target_name, ability_name=ability_name, timestamp=timestamp)
            EventSystem.get_main_bus().post(event)


class CombatantRecord(ICombatantRecord):
    def __init__(self, runtime: IRuntime, combatant_name: str, combatant_type: CombatantType, initial_type_confirmed: bool):
        self.__runtime = runtime
        self.__combatant_name = combatant_name
        self.__combatant_type = combatant_type
        self.confirmed_combatant_type = False
        self.record_damage_out = False
        self.measure_damage_in = False
        self.record_wards_out = False
        self.measure_wards_in = False
        self.measure_heals_in = False
        self.incoming = IncomingRecords(self.__runtime, combatant_name, combatant_type)
        self.outgoing = OutgoingRecords(self.__runtime, combatant_name, combatant_type)
        self.abilities: Dict[str, IAbility] = dict()
        self.set_combatant_type(combatant_type, initial_type_confirmed)

    def __str__(self) -> str:
        return f'Combatant record of {self.__combatant_name}'

    def reset_record(self):
        self.incoming.reset_incoming()
        self.outgoing.reset_outgoing()
        # allow generating new combatant confirmation event
        self.confirmed_combatant_type = False

    def set_combatant_type(self, new_combatant_type: CombatantType, initial_type_confirmed: bool):
        if self.confirmed_combatant_type:
            if new_combatant_type != self.__combatant_type:
                logger.warn(f'Combatant type of {self.__combatant_name} is fixed as {self.__combatant_type}')
            return
        logger.debug(f'Set combatant {self.__combatant_name} flags by type: {self.__combatant_type}')
        self.incoming.update_combatant_type(new_combatant_type)
        self.outgoing.update_combatant_type(new_combatant_type)
        self.__combatant_type = new_combatant_type
        if self.__combatant_type == CombatantType.MAIN_PLAYER:
            self.record_damage_out = True
            self.measure_damage_in = True
            self.record_wards_out = True
            self.measure_wards_in = True
            self.measure_heals_in = True
        elif self.__combatant_type == CombatantType.MY_PLAYER:
            self.record_damage_out = True
            self.measure_damage_in = True
            self.record_wards_out = True
            self.measure_wards_in = True
            self.measure_heals_in = True
        elif self.__combatant_type == CombatantType.OTHER_PLAYER:
            self.record_damage_out = True
            self.measure_damage_in = True
            self.record_wards_out = False
            self.measure_wards_in = True
            self.measure_heals_in = True
        elif self.__combatant_type == CombatantType.NPC:
            self.record_damage_out = True
            self.measure_damage_in = True
            self.record_wards_out = False
            self.measure_wards_in = False
            self.measure_heals_in = False
        elif self.__combatant_type == CombatantType.PLAYER_DUMBFIRE_PET:
            self.record_damage_out = False
            self.measure_damage_in = False
            self.record_wards_out = False
            self.measure_wards_in = False
            self.measure_heals_in = False
        else:
            assert False, f'{self.__combatant_type} not supported ({self.__combatant_name})'
        if initial_type_confirmed:
            self.__confirm_combatant_type(CTConfirmRule.INITIAL)
        if CombatantType.is_my_player(new_combatant_type):
            self.abilities = self.__runtime.ability_reg.find_ability_map_for_player_name(self.__combatant_name)
        else:
            self.abilities = dict()

    def __confirm_combatant_type(self, confirm_rule: CTConfirmRule):
        self.confirmed_combatant_type = True
        event = CombatParserEvents.COMBATANT_CONFIRMED(combatant_name=self.__combatant_name, combatant_type=self.__combatant_type, confirm_rule=confirm_rule)
        EventSystem.get_main_bus().post(event)

    def __set_confirmed_combatant_type(self, new_combatant_type: CombatantType, confirm_rule: CTConfirmRule):
        if self.__combatant_type != new_combatant_type:
            self.set_combatant_type(new_combatant_type, False)
        self.__confirm_combatant_type(confirm_rule)

    def set_abilities(self, abilities: Dict[str, IAbility]):
        self.abilities = abilities

    def deduct_type_by_hostile(self, other_combatant_record: CombatantRecord):
        if self.confirmed_combatant_type or not other_combatant_record.confirmed_combatant_type:
            return
        if CombatantType.is_allied(other_combatant_record.__combatant_type):
            self.__set_confirmed_combatant_type(CombatantType.NPC, CTConfirmRule.ATTK_BY_PLAYER)
        elif CombatantType.is_npc(other_combatant_record.__combatant_type):
            # at this stage only non-my players can be unconfirmed
            if ParsingHelpers.is_pet(self.__combatant_name):
                self.__set_confirmed_combatant_type(CombatantType.PLAYER_DUMBFIRE_PET, CTConfirmRule.ATTK_BY_NPC)
            else:
                self.__set_confirmed_combatant_type(CombatantType.OTHER_PLAYER, CTConfirmRule.ATTK_BY_NPC)

    def deduct_type_by_beneficial(self, other_combatant_record: CombatantRecord):
        if self.confirmed_combatant_type or not other_combatant_record.confirmed_combatant_type:
            return
        if CombatantType.is_allied(other_combatant_record.__combatant_type):
            # at this stage only non-my players can be unconfirmed
            if ParsingHelpers.is_pet(self.__combatant_name):
                self.__set_confirmed_combatant_type(CombatantType.PLAYER_DUMBFIRE_PET, CTConfirmRule.BENEFICIAL_ACTION)
            else:
                self.__set_confirmed_combatant_type(CombatantType.OTHER_PLAYER, CTConfirmRule.BENEFICIAL_ACTION)

    def get_ability_duration(self, ability_name: str) -> Optional[float]:
        abilities = self.abilities
        if ability_name in abilities:
            dot_duration = abilities[ability_name].get_duration_secs()
            if not dot_duration or dot_duration < 0:
                return None
            return dot_duration
        return None

    def get_ability_combat_record(self, ability_name: str) -> AbilityCombatRecord:
        return self.outgoing.get_ability_combat_record(ability_name)

    def get_all_ability_names(self) -> List[str]:
        return list(self.outgoing.ability_records.keys())

    # override ICombatantRecord
    def get_combatant_name(self) -> str:
        return self.__combatant_name

    # override ICombatantRecord
    def get_combatant_type(self) -> CombatantType:
        return self.__combatant_type

    # override ICombatantRecord
    def get_outgoing_damage(self, dps_measure: DpsMeasure) -> int:
        if dps_measure == DpsMeasure.TOTAL:
            return self.outgoing.total_outgoing_damage
        if dps_measure == DpsMeasure.MAX:
            return max([cr.max for cr in self.outgoing.ability_records.values()])
        if dps_measure == DpsMeasure.RECENT:
            return self.outgoing.recent_outgoing_damage.get_dps()
        # instance outgoing dps is not supported
        raise ValueError(f'Unsupported measure: {dps_measure}')

    # override ICombatantRecord
    def get_incoming_damage(self, dps_measure: DpsMeasure) -> int:
        if dps_measure == DpsMeasure.TOTAL:
            return sum(self.incoming.total_incoming_damage.values())
        if dps_measure == DpsMeasure.MAX:
            return max(self.incoming.max_incoming_hit.values())
        if dps_measure == DpsMeasure.RECENT or dps_measure == DpsMeasure.INSTANT:
            return self.get_hitpoints_damage(dps_measure) + self.get_consumed_wards(dps_measure)
        raise ValueError(f'Unsupported measure: {dps_measure}')

    # override ICombatantRecord
    def get_hitpoints_damage(self, dps_measure: DpsMeasure) -> int:
        if dps_measure == DpsMeasure.RECENT:
            return self.incoming.recent_hitpoints_damage.get_dps()
        if dps_measure == DpsMeasure.INSTANT:
            return self.incoming.instant_hitpoints_damage.get_dps()
        raise ValueError(f'Unsupported measure: {dps_measure}')

    # override ICombatantRecord
    def get_consumed_wards(self, dps_measure: DpsMeasure) -> int:
        if dps_measure == DpsMeasure.RECENT:
            return self.incoming.recent_consumed_wards.get_dps()
        if dps_measure == DpsMeasure.INSTANT:
            return self.incoming.instant_consumed_wards.get_dps()
        raise ValueError(f'Unsupported measure: {dps_measure}')

    # override ICombatantRecord
    def get_received_heals(self, dps_measure: DpsMeasure) -> int:
        if dps_measure == DpsMeasure.TOTAL:
            return self.incoming.total_received_heal
        if dps_measure == DpsMeasure.RECENT:
            return self.incoming.recent_received_heal.get_dps()
        raise ValueError(f'Unsupported measure: {dps_measure}')

    # override ICombatantRecord
    def get_approx_remaining_wards(self) -> int:
        return self.incoming.get_remaining_wards()

    # override ICombatantRecord
    def get_incoming_hit_counter(self, threshold=0) -> int:
        hits_dict = self.incoming.incoming_dmg_hit_counter
        return self.incoming.get_hits_stronger_or_equal_to_threshold(threshold, hits_dict)

    # override ICombatantRecord
    def get_incoming_hit_counter_in_current_combat(self, threshold=0) -> int:
        hits_dict = self.incoming.incoming_dmg_hit_counter_in_current_combat
        return self.incoming.get_hits_stronger_or_equal_to_threshold(threshold, hits_dict)


class DpsLogParser(CombatLogParser, IDPSParser):
    def __init__(self, runtime: IRuntime, player: IPlayer, log_reader: ILogReader, event_system: EventSystem):
        CombatLogParser.__init__(self, player.get_client_id(), player.get_player_name(), log_reader, event_system)
        self.player = player
        self.__runtime = runtime
        self.__combatant_records: Dict[str, CombatantRecord] = dict()
        self.__lock = RLock()
        self.__parser_closed = False
        self.__log_debug_file = None
        self.__bus = EventSystem.get_main_bus()
        self.__installed_hooks: FrozenSet[IDPSParserHook] = frozenset()

    def __get_combatants_sorted_by_dps(self) -> Iterable[str]:
        with self.__lock:
            sorted_combatant_names = list(self.__combatant_records.keys())
            sorted_combatant_names.sort(key=lambda p: self.__combatant_records[p].get_outgoing_damage(DpsMeasure.TOTAL), reverse=True)
            return sorted_combatant_names

    def __get_combat_parse_str(self, combatant_limit: int, add_inc_dps: bool, add_combat_duration: bool, add_inc_spike: bool) -> str:
        with self.__lock:
            sorted_combatant_names = self.__get_combatants_sorted_by_dps()
            duration = self.get_combat_duration()
            if duration < 1.0:
                return 'N/A'
            s = ''
            if add_inc_dps:
                if self.player_name in self.__combatant_records.keys():
                    main_player_name_record = self.__combatant_records[self.player_name]
                    s += main_player_name_record.incoming.get_incoming_dps_str(duration)
                    s += '------------------\n'
            if add_combat_duration:
                duration_sec = int(duration)
                duration_frac = round((duration - duration_sec) * 10)
                duration_min = int(duration_sec / 60)
                duration_sec %= 60
                s += f'({duration_min:02}:{duration_sec:02}.{duration_frac})\n'
            for i, combatant_name in enumerate(sorted_combatant_names[:combatant_limit]):
                combatant_record = self.__combatant_records[combatant_name]
                if combatant_record.get_outgoing_damage(DpsMeasure.TOTAL) == 0:
                    break
                s += combatant_record.outgoing.get_encounter_dps_str(duration, i, add_inc_spike)
        return s

    def __get_top_abilities_parse_str(self, combatant_name: str, duration: float) -> str:
        if combatant_name is None:
            return 'Unknown'
        if duration < 1.0:
            return 'N/A'
        with self.__lock:
            if combatant_name not in self.__combatant_records.keys():
                return 'Error'
            combatant_record = self.__combatant_records[combatant_name]
            return combatant_record.outgoing.get_top_abilities_parse_str(duration)

    def __get_all_abilities_parse_str(self, combatant_name: str) -> str:
        if combatant_name is None:
            return 'Unknown'
        with self.__lock:
            if combatant_name not in self.__combatant_records.keys():
                return 'Error'
            combatant_record = self.__combatant_records[combatant_name]
            return combatant_record.outgoing.get_all_abilities_parse_str()

    def __get_heals_parse_str(self) -> str:
        s = 'Incoming heals:\n'
        duration = self.get_duration()
        if duration < 3.0:
            return s + 'N/A'
        for combatant in self.__combatant_records.values():
            total_heals = combatant.incoming.total_received_heal
            hps = int(total_heals / duration)
            s += f'{combatant.get_combatant_name()}: {get_dps_str(total_heals)} / {get_dps_str(hps)}\n'
        return s

    def __get_player_combatant_type(self, combatant_name: str) -> Optional[CombatantType]:
        combatant_player = self.__runtime.player_mgr.get_player_by_name(combatant_name)
        if combatant_player:
            if combatant_name == self.player_name:
                return CombatantType.MAIN_PLAYER
            return CombatantType.MY_PLAYER
        elif self.__runtime.zonestate.is_player_in_zone(combatant_name):
            return CombatantType.OTHER_PLAYER
        return None

    # combatant type and confirmation
    def __get_combatant_type(self, combatant_name: str) -> Tuple[CombatantType, bool]:
        is_pet = False
        pet_owner = ParsingHelpers.get_pets_owner(combatant_name)
        if pet_owner:
            player_combatant_type = self.__get_player_combatant_type(pet_owner)
            is_pet = True
        else:
            player_combatant_type = self.__get_player_combatant_type(combatant_name)
        if player_combatant_type:
            return player_combatant_type if not is_pet else CombatantType.PLAYER_DUMBFIRE_PET, True
        # enemies
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'Classify {combatant_name} as NPC; Zoned players: {self.__runtime.zonestate.get_players_in_zone()}')
        # NPC combatant type is not confirmed when creating combatant record
        return CombatantType.NPC, False

    def __get_combatant_record(self, combatant_name: str) -> CombatantRecord:
        with self.__lock:
            if combatant_name not in self.__combatant_records.keys():
                combatant_type, type_confirmed = self.__get_combatant_type(combatant_name)
                combatant_record = CombatantRecord(self.__runtime, combatant_name, combatant_type, type_confirmed)
                self.__combatant_records[combatant_name] = combatant_record
            else:
                combatant_record = self.__combatant_records[combatant_name]
            return combatant_record

    def __reset_combatant_records(self):
        with self.__lock:
            my_player_names = self.__runtime.player_mgr.get_player_names()
            self.__combatant_records = {name: self.__combatant_records[name] for name in my_player_names if name in self.__combatant_records}
            for combatant_record in self.__combatant_records.values():
                combatant_record.reset_record()
                new_combatant_type, type_confirmed = self.__get_combatant_type(combatant_record.get_combatant_name())
                combatant_record.set_combatant_type(new_combatant_type, type_confirmed)

    # override CombatLogParser
    def _get_canonical_ability_name(self, effect_name: str) -> str:
        ability_name = self.__runtime.ability_reg.get_ability_name_by_effect_name(effect_name.lower())
        if not ability_name:
            ability_name = effect_name
        return CombatLogParser._get_canonical_ability_name(self, ability_name)

    # override CombatLogParser
    def _on_combat_start(self, attacker_name: str, target_name: str, timestamp: float):
        with self.__lock:
            # dont clear on on-end, to keep the parse info up
            logger.info('Starting new parse')
            self.__reset_combatant_records()
        CombatLogParser._on_combat_start(self, attacker_name, target_name, timestamp)
        self.__bus.post(CombatParserEvents.DPS_PARSE_START(attacker_name=attacker_name, target_name=target_name, timestamp=timestamp))

    # override CombatLogParser
    def _on_combat_tick(self, combatflag: bool, timestamp: float):
        CombatLogParser._on_combat_tick(self, combatflag, timestamp)
        self.__bus.post(CombatParserEvents.DPS_PARSE_TICK(combat_flag=combatflag))

    # override CombatLogParser
    def _on_combat_end(self, timestamp: float):
        CombatLogParser._on_combat_end(self, timestamp)
        self.__bus.post(CombatParserEvents.DPS_PARSE_END(timestamp=timestamp))
        if MutableFlags.PRINT_INC_HPS_LOG:
            print(self.__get_heals_parse_str())
        if MutableFlags.PRINT_FULL_DPS_ABILITY_LOG:
            main_player_name = self.__runtime.playerstate.get_main_player_name()
            print(self.__get_all_abilities_parse_str(main_player_name))
        elif MutableFlags.PRINT_TOP_DPS_ABILITY_LOG:
            main_player_name = self.__runtime.playerstate.get_main_player_name()
            print(self.__get_top_abilities_parse_str(main_player_name, self.get_duration()))

    # override CombatLogParser
    def _record_combat_hit(self, attacker_name: Optional[str], target_name: Optional[str], ability_name: str,
                           damage: int, damage_type: str, is_autoattack: bool, timestamp: float):
        CombatLogParser._record_combat_hit(self, attacker_name, target_name, ability_name, damage, damage_type, is_autoattack, timestamp)
        attacker_name, attacker_is_you = self._get_canonical_combatant_name(attacker_name)
        target_name, target_is_you = self._get_canonical_combatant_name(target_name)
        with self.__lock:
            target_record = None
            attacker_record = None
            target_combatant_type = None
            attacker_combatant_type = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                target_combatant_type = target_record.get_combatant_type()
                if target_record.measure_damage_in:
                    target_record.incoming.add_incoming_dmg(damage, damage_type, timestamp)
            if attacker_name is not None:
                attacker_record = self.__get_combatant_record(attacker_name)
                attacker_combatant_type = attacker_record.get_combatant_type()
                attacker_record.outgoing.add_encounter_dmg(damage, timestamp)
                if attacker_record.record_damage_out:
                    dot_duration = attacker_record.get_ability_duration(ability_name)
                    attacker_record.outgoing.add_combat_hit(target_name, target_combatant_type, ability_name, damage, damage_type,
                                                            is_autoattack, False, dot_duration, timestamp)
            if attacker_record and target_record:
                target_record.deduct_type_by_hostile(attacker_record)
                attacker_record.deduct_type_by_hostile(target_record)
        for hook in self.__installed_hooks:
            hook.record_damage(attacker_name, attacker_combatant_type, target_name, target_combatant_type, ability_name,
                               damage, damage_type, is_autoattack, timestamp)

    def _record_threat(self, attacker_name: str, target_name: str, ability_name: str, threat: int, is_positions: bool, timestamp: float):
        CombatLogParser._record_threat(self, attacker_name, target_name, ability_name, threat, is_positions, timestamp)
        attacker_name, attacker_is_you = self._get_canonical_combatant_name(attacker_name)
        target_name, target_is_you = self._get_canonical_combatant_name(target_name)
        with self.__lock:
            if attacker_name is not None:
                attacker_record = self.__get_combatant_record(attacker_name)
                if attacker_record.record_damage_out:
                    dot_duration = attacker_record.get_ability_duration(ability_name)
                    damage_type = DamageType.positions if is_positions else DamageType.threat
                    threat_amount = threat if is_positions else 1
                    attacker_record.outgoing.add_combat_hit(target_name, None, ability_name, threat_amount,
                                                            damage_type.name, False, False, dot_duration, timestamp)

    # override CombatLogParser
    def _record_power_drained(self, attacker_name: str, target_name: str, ability_name: str, power_amount: int, drain_type: str, timestamp: float):
        CombatLogParser._record_power_drained(self, attacker_name, target_name, ability_name, power_amount, drain_type, timestamp)
        attacker_name, attacker_is_you = self._get_canonical_combatant_name(attacker_name)
        target_name, target_is_you = self._get_canonical_combatant_name(target_name)
        with self.__lock:
            target_record = None
            attacker_record = None
            target_combatant_type = None
            attacker_combatant_type = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                target_combatant_type = target_record.get_combatant_type()
            if attacker_name is not None:
                attacker_record = self.__get_combatant_record(attacker_name)
                attacker_combatant_type = attacker_record.get_combatant_type()
                if attacker_record.record_damage_out:
                    dot_duration = attacker_record.get_ability_duration(ability_name)
                    attacker_record.outgoing.add_combat_hit(target_name, target_combatant_type, ability_name, power_amount, drain_type,
                                                            False, True, dot_duration, timestamp)
            if attacker_record and target_record:
                target_record.deduct_type_by_hostile(attacker_record)
                attacker_record.deduct_type_by_hostile(target_record)
        for hook in self.__installed_hooks:
            hook.record_drain(attacker_name, attacker_combatant_type, target_name, target_combatant_type, ability_name,
                              power_amount, drain_type, timestamp)

    # override CombatLogParser
    def _record_damage_healed(self, caster_name: str, target_name: str, ability_name: str, heal_amount: int, timestamp: float):
        CombatLogParser._record_damage_healed(self, caster_name, target_name, ability_name, heal_amount, timestamp)
        caster_name, caster_is_you = self._get_canonical_combatant_name(caster_name)
        target_name, target_is_you = self._get_canonical_combatant_name(target_name)
        with self.__lock:
            target_record = None
            caster_record = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                if target_record.measure_heals_in:
                    target_record.incoming.add_received_heal(ability_name, heal_amount, timestamp)
            if caster_name is not None:
                caster_record = self.__get_combatant_record(caster_name)
            if caster_record and target_record:
                target_record.deduct_type_by_beneficial(caster_record)
                caster_record.deduct_type_by_beneficial(target_record)

    # override CombatLogParser
    def _record_damage_warded(self, caster_name: str, target_name: str, ability_name: str, ward_amount: int, remaining_ward: int, timestamp: float):
        CombatLogParser._record_damage_warded(self, caster_name, target_name, ability_name, ward_amount, remaining_ward, timestamp)
        caster_name, caster_is_you = self._get_canonical_combatant_name(caster_name)
        target_name, target_is_you = self._get_canonical_combatant_name(target_name)
        with self.__lock:
            target_record = None
            caster_record = None
            target_combatant_type = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                target_combatant_type = target_record.get_combatant_type()
                if target_record.measure_wards_in:
                    target_record.incoming.add_consumed_ward(ability_name, ward_amount, remaining_ward, timestamp)
            if caster_name is not None:
                caster_record = self.__get_combatant_record(caster_name)
                if caster_record.record_wards_out:
                    caster_record.outgoing.add_remaining_ward(target_name, target_combatant_type, ability_name, remaining_ward, timestamp)
            if caster_record and target_record:
                target_record.deduct_type_by_beneficial(caster_record)
                caster_record.deduct_type_by_beneficial(target_record)

    # override CombatLogParser
    def _record_cure(self, caster_name: str, cured_target_name: str, ability_name: str, cured_effect_name: str, timestamp: float):
        CombatLogParser._record_cure(self, caster_name, cured_target_name, ability_name, cured_effect_name, timestamp)
        caster_name, caster_is_you = self._get_canonical_combatant_name(caster_name)
        target_name, target_is_you = self._get_canonical_combatant_name(cured_target_name)
        is_curse = 'curse' in ability_name.lower()
        with self.__lock:
            target_combatant_type = None
            caster_combatant_type = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                target_combatant_type = target_record.get_combatant_type()
            if caster_name is not None:
                caster_record = self.__get_combatant_record(caster_name)
                caster_combatant_type = caster_record.get_combatant_type()
            self.__bus.post(CombatParserEvents.DETRIMENT_RELIEVED(by_combatant=caster_name, by_combatant_type=caster_combatant_type,
                                                                  from_combatant=target_name, from_combatant_type=target_combatant_type,
                                                                  ability_name=ability_name, detriment_name=cured_effect_name, is_curse=is_curse))

    # override CombatLogParser
    def _record_dispel(self, caster_name: str, dispelled_target_name: str, ability_name: str, dispelled_effect_name: str, timestamp: float):
        CombatLogParser._record_dispel(self, caster_name, dispelled_target_name, ability_name, dispelled_effect_name, timestamp)
        caster_name, caster_is_you = self._get_canonical_combatant_name(caster_name)
        target_name, target_is_you = self._get_canonical_combatant_name(dispelled_target_name)
        with self.__lock:
            target_combatant_type = None
            if target_name is not None:
                target_record = self.__get_combatant_record(target_name)
                target_combatant_type = target_record.get_combatant_type()
            caster_combatant_type = None
            if caster_name is not None:
                caster_record = self.__get_combatant_record(caster_name)
                caster_combatant_type = caster_record.get_combatant_type()
            self.__bus.post(CombatParserEvents.EFFECT_DISPELLED(by_combatant=caster_name, by_combatant_type=caster_combatant_type,
                                                                from_combatant=target_name, from_combatant_type=target_combatant_type,
                                                                ability_name=ability_name, effect_name=dispelled_effect_name))

    # override CombatLogParser
    def _record_stoneskin(self, stoneskin_amount: int, timestamp: float):
        CombatLogParser._record_stoneskin(self, stoneskin_amount, timestamp)
        with self.__lock:
            target_record = self.__get_combatant_record(self.player_name)
            if target_record.measure_damage_in:
                target_record.incoming.add_stoneskin(stoneskin_amount)

    # override CombatLogParser
    def _record_interrupt(self, interrupted_player_name: str, timestamp: float):
        CombatLogParser._record_interrupt(self, interrupted_player_name, timestamp)
        player_name, player_is_you = self._get_canonical_combatant_name(interrupted_player_name)
        with self.__lock:
            if player_name is not None:
                player_record = self.__get_combatant_record(player_name)
                if player_record.get_combatant_type() == CombatantType.MY_PLAYER:
                    self.__bus.post(CombatParserEvents.PLAYER_INTERRUPTED(player_name=player_name))

    def __save_nondps_log(self, log_line: str):
        try:
            if not self.__log_debug_file:
                filename = os.path.join(tempfile.gettempdir(), 'rka_noncombat_logs.txt')
                self.__log_debug_file = open(filename, 'a', encoding='utf-8', buffering=1024)
                self.__log_debug_file.write(f'\nOPENED at {datetime.datetime.now()}\n')
                self.__log_debug_file.flush()
            self.__log_debug_file.write(log_line)
            self.__log_debug_file.write('\n')
        except Exception as e:
            logger.warn(f'Exception while saving debug logs {e}')
            MutableFlags.SAVE_NONDPS_LOGS.false()

    # override CombatLogParser
    def _preparse_noncombat_log_line(self, log_line: str, timestamp: float) -> bool:
        if MutableFlags.SAVE_NONDPS_LOGS:
            self.__save_nondps_log(log_line)
        return False

    # override LogParser
    def _on_activated(self):
        CombatLogParser._on_activated(self)

    # override LogParser
    def _on_deactivated(self):
        CombatLogParser._on_deactivated(self)
        self.__installed_hooks = frozenset()

    # override IDPSParser
    def get_parse_info_str(self, combatant_limit: int, add_inc_dps: bool, add_combat_duration: bool, add_inc_spike: bool):
        return self.__get_combat_parse_str(combatant_limit=combatant_limit, add_inc_dps=add_inc_dps,
                                           add_combat_duration=add_combat_duration, add_inc_spike=add_inc_spike)

    # override IDPSParser
    def install_parser_hook(self, hook: IDPSParserHook):
        with self.__lock:
            new_set = set(self.__installed_hooks)
            new_set.add(hook)
            self.__installed_hooks = frozenset(new_set)

    # override IDPSParser
    def uninstall_parser_hook(self, hook: IDPSParserHook):
        if hook in self.__installed_hooks:
            new_set = set(self.__installed_hooks)
            new_set.remove(hook)
            self.__installed_hooks = frozenset(new_set)
        else:
            logger.warn(f'uninstall_parser_hook: not installed: {hook}')

    # override IDPSParser
    def get_start_time(self) -> float:
        start_time = self.get_combat_start_time()
        return start_time if start_time else 0.0

    # override IDPSParser
    def get_duration(self) -> float:
        return self.get_combat_duration()

    # override IDPSParser
    def get_combatant_record(self, combatant_name: str) -> Optional[ICombatantRecord]:
        with self.__lock:
            if combatant_name in self.__combatant_records.keys():
                return self.__combatant_records[combatant_name]
        return None

    # override IDPSParser
    def get_combatant_names(self, combatant_filter: Optional[Callable[[ICombatantRecord], bool]] = None) -> List[str]:
        with self.__lock:
            if not combatant_filter:
                return list(self.__combatant_records.keys())
            else:
                records = filter(combatant_filter, self.__combatant_records.values())
                return [combatant_record.get_combatant_name() for combatant_record in records]

    # override IDPSParser
    def iter_combatant_records(self) -> Generator[ICombatantRecord, None, None]:
        with self.__lock:
            for combatant_record in self.__combatant_records.values():
                yield combatant_record

    # override IDPSParser
    def get_ability_combat_record(self, combatant_name: str, ability_name: str) -> Optional[AbilityCombatRecord]:
        with self.__lock:
            if combatant_name in self.__combatant_records.keys():
                return self.__combatant_records[combatant_name].get_ability_combat_record(ability_name)
        return None

    # override IDPSParser
    def get_all_ability_names(self, combatant_name: str) -> List[str]:
        with self.__lock:
            if combatant_name in self.__combatant_records.keys():
                return self.__combatant_records[combatant_name].get_all_ability_names()
        return []

    # override IDPSParser
    def iter_ability_combat_records(self, combatant_name: str) -> Generator[AbilityCombatRecord, None, None]:
        with self.__lock:
            if combatant_name in self.__combatant_records.keys():
                combatant_record = self.__combatant_records[combatant_name]
                for ability_combat_record in combatant_record.outgoing.iter_ability_combat_records():
                    yield ability_combat_record

    # override IDPSParser
    def recheck_combatant_type(self, player_name: Optional[str] = None):
        with self.__lock:
            if player_name in self.__combatant_records.keys():
                combatant_record = self.__combatant_records[player_name]
                new_combatant_type, type_confirmed = self.__get_combatant_type(player_name)
                combatant_record.set_combatant_type(new_combatant_type, type_confirmed)

    # override Closeable
    def close(self):
        self.__installed_hooks = frozenset()
        if self.__log_debug_file:
            self.__log_debug_file.close()
        CombatLogParser.close(self)
