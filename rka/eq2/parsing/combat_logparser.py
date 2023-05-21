from __future__ import annotations

import time
import traceback
from enum import auto
from typing import Match, Optional, Tuple, Set

import regex as re

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogLevel
from rka.eq2.configs.shared.rka_constants import DPSPARSE_NEW_ENCOUNTER_GAP
from rka.eq2.parsing import ILogReader, logger
from rka.eq2.parsing.logparser import LogParser
from rka.eq2.parsing.parsing_util import ANY_ABILITY_L, ANY_PET_OR_ABILITY_L, ANY_PLAYER_INCL_YOU_G, ANY_PLAYERS_INCL_YOUR, ANY_ENEMY_L, ANY_COMBATANT_L, \
    ANY_COMBATANTS, ANY_COMBATANT_G, ANY_PLAYER_INCL_YOU_L, ParsingHelpers, S_POSTFIX
from rka.eq2.shared.client_combat import ClientCombatParserEvents
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.util.util import NameEnum


class DamageType(NameEnum):
    # existing in-game
    poison = auto()
    disease = auto()
    divine = auto()
    mental = auto()
    magic = auto()
    focus = auto()
    heat = auto()
    cold = auto()
    slashing = auto()
    crushing = auto()
    piercing = auto()
    # virtual
    positions = auto()
    threat = auto()
    unknown = auto()


class _CommonRE:
    formatted_number = r'[\d,]+(?:.\d[BMTKQ])?'
    damage_number = formatted_number
    threat_number = formatted_number
    ward_number = formatted_number
    heal_number = formatted_number
    drain_number = formatted_number
    power_number = formatted_number
    critical = r'(?:a (?:(?:Fabled|Legendary|Mythical) )?critical of )'

    @staticmethod
    def parse_int(text: str) -> int:
        multiplier = 1
        multiplier_2 = 0
        last_char = text[-1]
        text = text.replace(',', '')
        if last_char == 'B':
            multiplier = 1000000000
            multiplier_2 = 100000000
        elif last_char == 'T':
            multiplier = 1000000000000
            multiplier_2 = 100000000000
        elif last_char == 'M':
            multiplier = 1000000
            multiplier_2 = 100000
        elif last_char == 'K':
            multiplier = 1000
            multiplier_2 = 100
        elif last_char == 'Q':
            multiplier = 1000000000000000
            multiplier_2 = 100000000000000
        if multiplier != 1:
            number = int(text[:-3]) * multiplier
            number += int(text[-2]) * multiplier_2
        else:
            number = int(text)
        return number


class CombatLogParser(LogParser):
    @staticmethod
    def compile_combat_hit_re():
        # Entire RE: https://regex101.com/r/D9jECg/1
        damage = rf'({_CommonRE.damage_number}) ([a-z]+)'
        critical_damage = fr'{_CommonRE.critical}?{damage}'
        for_double_damage = fr'for {critical_damage}(?: and {damage})? damage'
        damage_fail = r'but fails? to inflict any damage'
        term = r'[\.!]'
        # ability hit: https://regex101.com/r/VLJNU0/1
        hits = '(?:hits|multi attacks)'
        ability_re = f'({ANY_COMBATANTS}) ({ANY_PET_OR_ABILITY_L}) {hits} ({ANY_COMBATANT_L}) (?:{for_double_damage}|{damage_fail}){term}'
        # autoattack
        autoattack = r'(?:hit|flurry|multi attack|aoe attack)'
        autoattacks = r'(?:hits|flurries|multi attacks|aoe attacks)'
        pc_autoattack = fr'YOU {autoattack}'
        npc_autoattacks = fr'({ANY_ENEMY_L}) {autoattacks}'
        autoattack_re = f'(?:{pc_autoattack}|{npc_autoattacks}) ({ANY_COMBATANT_L}) (?:{for_double_damage}|{damage_fail}){term}'
        # unknown hit
        hit = '(?:hit|multi attack)'
        pc_unknown_hit = f'YOU are'
        npc_unknown_hit = f'({ANY_ENEMY_L}) is'
        unknown_hit_re = fr'(?:{pc_unknown_hit}|{npc_unknown_hit}) {hit} by ({ANY_PET_OR_ABILITY_L})(?:{term}| {for_double_damage}{term})'
        # failed attempts
        trying = '(?:try|tries|attempt|attempts)'
        any_attack = '[a-zA-Z]+'
        failed_ability = fr'({ANY_COMBATANTS}) ({ANY_PET_OR_ABILITY_L}) {trying} to {any_attack} ({ANY_COMBATANT_L})(?: with {ANY_PET_OR_ABILITY_L})?, but .*'
        failed_with_ability = fr'({ANY_COMBATANT_L}) {trying} to {any_attack} ({ANY_COMBATANT_L})(?: with ({ANY_PET_OR_ABILITY_L}))?, but .*'
        # complete RE
        combat_re = rf'({ability_re})|({autoattack_re})|({unknown_hit_re})|({failed_ability})|({failed_with_ability})'
        return re.compile(combat_re)

    @staticmethod
    def compile_ability_effect_re():
        # Entire RE: https://regex101.com/r/H2DYET/1
        # 1. ward
        absorbtion = rf'({_CommonRE.ward_number}) points of damage from being done to'
        bleedthrough = rf'(?: with {_CommonRE.damage_number} points of damage bleeding through)'
        ward_remaining = rf'\(({_CommonRE.ward_number}) points remaining\)'
        warded = rf'absorbs {absorbtion} (YOURSELF|{ANY_PLAYER_INCL_YOU_G}){bleedthrough}?\. {ward_remaining}'
        # 2. heal
        hitpoints = fr'{_CommonRE.critical}?({_CommonRE.heal_number}) hit points?'
        heal = rf'(?:heals|repairs) ({ANY_PLAYER_INCL_YOU_G}) for {hitpoints}\.'
        # 3. power
        mana = fr'{_CommonRE.critical}?({_CommonRE.power_number}) mana points?'
        power = rf'refreshes ({ANY_PLAYER_INCL_YOU_G}) for {mana}\.'
        # 4. regeneration
        regenerate = rf'regenerates ({_CommonRE.ward_number}) points? of absorption\.'
        # 5. cure
        cure = rf'relieves ({ANY_ABILITY_L}) from ({ANY_PLAYER_INCL_YOU_G})\.'
        # complete RE
        effect_re = rf'({ANY_PLAYERS_INCL_YOUR}) ({ANY_PET_OR_ABILITY_L}) (?:({warded})|({heal})|({power})|({regenerate})|({cure}))'
        return re.compile(effect_re)

    @staticmethod
    def compile_effect_dispel_re():
        effect_re = rf'({ANY_COMBATANTS}) ({ANY_ABILITY_L}) dispels ({ANY_ABILITY_L}) from ({ANY_COMBATANT_G})\.'
        return re.compile(effect_re)

    @staticmethod
    def compile_power_drain_re():
        # Entire RE: https://regex101.com/r/nzW9md/1
        hit_types = '(?:zaps?|confounds?|smites?|diseases?|poisons?|burns?|freezes?|crushe?s?|pierces?|slashe?s?)'
        drain_re = rf'({ANY_COMBATANT_L})(?:{S_POSTFIX} ({ANY_PET_OR_ABILITY_L}))? {hit_types} ({ANY_COMBATANT_L}) draining ({_CommonRE.drain_number}) ([a-z]+) points of power\.'
        return re.compile(drain_re)

    @staticmethod
    def compile_threat_re():
        # Entire RE: https://regex101.com/r/ZPg8lO/2
        increase = '(reduces|increases)'
        aggro_owner = r'(?:YOUR|THEIR)'
        hate = r'hate( position)?'
        threat = rf'{_CommonRE.critical}?({_CommonRE.threat_number}) (?:threat|positions?)'
        threat_re = rf'({ANY_PLAYERS_INCL_YOUR}) ({ANY_PET_OR_ABILITY_L}) {increase} {aggro_owner} {hate} with ({ANY_COMBATANT_L}) for {threat}\.'
        return re.compile(threat_re)

    @staticmethod
    def compile_damage_reduction_re():
        reduction_re = rf'({ANY_PLAYER_INCL_YOU_G}) reduces the damage from ({ANY_COMBATANT_L}) to ({ANY_PLAYER_INCL_YOU_L}) by ({_CommonRE.heal_number})\.'
        return re.compile(reduction_re)

    @staticmethod
    def compile_apply_ward_re():
        ward = rf'(YOUR) ({ANY_ABILITY_L}) has applied to (YOU) as a ward for ({_CommonRE.ward_number})\.'
        return re.compile(ward)

    @staticmethod
    def compile_stoneskin_re():
        stoneskin_re = rf'Your stoneskin absorbed ({_CommonRE.ward_number}) points of damage!'
        return re.compile(stoneskin_re)

    @staticmethod
    def compile_interrupt_re():
        interrupt_re = f'(Your|{ANY_COMBATANT_L}) (?:was|were|(?:ability|spell) has been) interrupted!'
        return re.compile(interrupt_re)

    @staticmethod
    def compile_ignored_logs_re():
        # Entire RE: https://regex101.com/r/mXAGmn/1
        ignored_res = list()
        effects1 = 'struck|swiped|smashed|mauled|outraged|painfully hit|protected|wracked|blasted|enraged|drained|affected'
        effects2 = 'filled|guarded|imbued|infuriated as they are struck|numbed|no longer filled'
        affecting = f'(?:(?:is|are) (?:{effects1}|{effects2}) (?:with|by) )'
        feeling = f'(?:feels? )'
        ignored_res.append(rf'{ANY_COMBATANT_L} (?:{affecting}|{feeling})')
        ignored_res.append('Your target is too')
        ignored_res.append('This (?:art|spell) cannot be')
        ignored_res.append('There is no eligible target for')
        ignored_res.append('You must be behind')
        ignored_res.append('An augmentation')
        ignored_baracketed_res = [f'(?:{ignored_re})' for ignored_re in ignored_res]
        complete_re = '(?:' + '|'.join(ignored_baracketed_res) + ')'
        return re.compile(complete_re)

    def __init__(self, client_id: str, player_name: str, log_reader: ILogReader, event_system: EventSystem):
        LogParser.__init__(self, client_id, log_reader, event_system)
        self.player_name = player_name
        self.__event_system = event_system
        self.__start_time = 0.0
        self.__last_time = 0.0
        self.__parser_closed = False
        self.__compiled_combat_hit_re = CombatLogParser.compile_combat_hit_re()
        self.__compiled_ability_effect_re = CombatLogParser.compile_ability_effect_re()
        self.__compiled_effect_dispel_re = CombatLogParser.compile_effect_dispel_re()
        self.__compiled_power_drain_re = CombatLogParser.compile_power_drain_re()
        self.__compiled_threat_re = CombatLogParser.compile_threat_re()
        self.__compiled_damage_reduction_re = CombatLogParser.compile_damage_reduction_re()
        self.__compiled_applied_ward_re = CombatLogParser.compile_apply_ward_re()
        self.__compiled_stoneskin_re = CombatLogParser.compile_stoneskin_re()
        self.__compiled_interrupt_re = CombatLogParser.compile_interrupt_re()
        self.__compiled_ignored_logs_re = CombatLogParser.compile_ignored_logs_re()
        self.__combat_ticker: RKAFuture = shared_scheduler.schedule(self.__update_combat_status, 3.0)
        self.__combat_ongoing = False
        self.__known_combatants: Set[str] = set()

    def __update_combat_status(self):
        if self.__parser_closed:
            return
        if not self.__combat_ongoing:
            self.__combat_ticker = shared_scheduler.schedule(self.__update_combat_status, 3.0)
            return
        else:
            self.__combat_ticker = shared_scheduler.schedule(self.__update_combat_status, 0.5)
        timestamp = time.time()
        if timestamp - self.__last_time >= DPSPARSE_NEW_ENCOUNTER_GAP:
            self._on_combat_end(timestamp)
        else:
            combatflag = timestamp - self.__last_time < 2.0
            self._on_combat_tick(combatflag, timestamp)

    def __check_combat_start(self, attacker_name: str, target_name: str, timestamp: float):
        if timestamp - self.__last_time >= DPSPARSE_NEW_ENCOUNTER_GAP:
            self._on_combat_start(attacker_name, target_name, timestamp)
        self.__last_time = timestamp

    def _on_combat_start(self, attacker_name: str, target_name: str, timestamp: float):
        self.__start_time = timestamp
        self.__combat_ongoing = True
        bus = self.__event_system.get_bus(self.get_parser_id())
        if bus:
            bus.post(ClientCombatParserEvents.COMBAT_PARSE_START(client_id=self.get_parser_id(), timestamp=timestamp))

    def _on_combat_end(self, timestamp: float):
        self.__combat_ongoing = False
        self.__known_combatants.clear()
        bus = self.__event_system.get_bus(self.get_parser_id())
        bus.post(ClientCombatParserEvents.COMBAT_PARSE_END(client_id=self.get_parser_id(), timestamp=timestamp))

    def _on_combat_tick(self, combatflag: bool, timestamp: float):
        bus = self.__event_system.get_bus(self.get_parser_id())
        bus.post(ClientCombatParserEvents.COMBAT_PARSE_TICK(client_id=self.get_parser_id(), combat_flag=combatflag, timestamp=timestamp))

    def _get_canonical_combatant_name(self, combatant_name: Optional[str]) -> Tuple[Optional[str], bool]:
        return ParsingHelpers.get_canonical_combatant_name(self.player_name, combatant_name)

    # noinspection PyMethodMayBeStatic
    def _get_canonical_ability_name(self, effect_name: str) -> str:
        return ParsingHelpers.get_canonical_ability_name(effect_name)

    def __add_combatant(self, combatant_name: str, timestamp: float):
        if combatant_name not in self.__known_combatants:
            self.__known_combatants.add(combatant_name)
            bus = self.__event_system.get_bus(self.get_parser_id())
            if bus:
                bus.post(ClientCombatParserEvents.COMBATANT_JOINED(client_id=self.get_parser_id(), combatant_name=combatant_name, timestamp=timestamp))

    def __combat_sustaining_log(self, attacker_name: Optional[str], target_name: Optional[str], ability_name: str, timestamp: float):
        if not attacker_name or not target_name:
            return
        attacker_name, attacker_is_main_player = self._get_canonical_combatant_name(attacker_name)
        target_name, target_is_main_player = self._get_canonical_combatant_name(target_name)
        # do not maintain combat timers for self-incurred damage
        if attacker_is_main_player and target_is_main_player:
            return
        if target_name == attacker_name:
            return
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'Combat is sustained with: {attacker_name}:{ability_name} -> {target_name}')
        self.__check_combat_start(attacker_name, target_name, timestamp)
        self.__add_combatant(attacker_name, timestamp)
        self.__add_combatant(target_name, timestamp)

    def _record_combat_hit(self, attacker_name: Optional[str], target_name: Optional[str], ability_name: str,
                           _damage: int, _damage_type: str, is_autoattack: bool, timestamp: float):
        self.__combat_sustaining_log(attacker_name, target_name, ability_name, timestamp)

    def _record_damage_warded(self, caster_name: str, target_name: str, ability_name: str, ward_amount: int, remaining: int, timestamp: float):
        pass

    def _record_damage_healed(self, caster_name: str, target_name: str, ability_name: str, heal_amount: int, timestamp: float):
        pass

    def _record_power_refreshed(self, caster_name: str, target_name: str, ability_name: str, power_amount: int, timestamp: float):
        pass

    def _record_regeneration(self, caster_name: str, ability_name: str, regenerate_amount: int, timestamp: float):
        pass

    def _record_cure(self, caster_name: str, cured_target_name: str, ability_name: str, cured_effect_name: str, timestamp: float):
        pass

    def _record_dispel(self, caster_name: str, dispelled_target_name: str, ability_name: str, dispelled_effect_name: str, timestamp: float):
        pass

    def _record_power_drained(self, attacker_name: str, target_name: str, ability_name: str, _power_amount: int, _drain_type: str, timestamp: float):
        self.__combat_sustaining_log(attacker_name, target_name, ability_name, timestamp)

    def _record_threat(self, attacker_name: str, target_name: str, ability_name: str, _threat: int, _is_positions: bool, timestamp: float):
        self.__combat_sustaining_log(attacker_name, target_name, ability_name, timestamp)

    def _record_applied_ward(self, caster_name: str, target_name: str, ability_name: str, ward_amount: int, timestamp: float):
        pass

    def _record_stoneskin(self, stoneskin_amount: int, timestamp: float):
        pass

    def _record_interrupt(self, interrupted_player_name: str, timestamp: float):
        pass

    def __parse_combat_hit_match(self, match: Match, timestamp: float):
        attacker_name = None
        ability_name = None
        damage = None
        damage_type = None
        damage_2 = None
        damage_type_2 = None
        is_autoattack = False
        if match.group(1) is not None:
            # ability hit
            attacker_name = match.group(2)
            ability_name = match.group(3)
            target_name = match.group(4)
            damage = match.group(5)
            damage_type = match.group(6)
            if match.group(7):
                damage_2 = match.group(7)
                damage_type_2 = match.group(8)
        elif match.group(9) is not None:
            # autoattack
            attacker_name = match.group(10)
            if attacker_name is None:
                attacker_name = 'YOU'
            target_name = match.group(11)
            damage = match.group(12)
            damage_type = match.group(13)
            if match.group(14):
                damage_2 = match.group(14)
                damage_type_2 = match.group(15)
        elif match.group(16) is not None:
            # unknown hit
            target_name = match.group(17)
            ability_name = match.group(18)
            damage = match.group(19)
            damage_type = match.group(20)
            if match.group(21):
                damage_2 = match.group(21)
                damage_type_2 = match.group(22)
        elif match.group(23) is not None:
            # failed ability hit
            attacker_name = match.group(24)
            ability_name = match.group(25)
            target_name = match.group(26)
        elif match.group(27) is not None:
            # failed with ability
            attacker_name = match.group(28)
            target_name = match.group(29)
            ability_name = match.group(30)
        else:
            logger.warn(f'Did not match autoattack nor ability: {match.group(0)}')
            return
        if damage_type is None:
            damage_type = DamageType.unknown.name
        if damage_type not in DamageType.__members__:
            logger.warn(f'Unknown damage type: {damage_type}')
        if ability_name is None:
            ability_name = damage_type
            is_autoattack = True
        else:
            ability_name = self._get_canonical_ability_name(ability_name)
        if damage is None:
            damage = 0
        else:
            damage = _CommonRE.parse_int(damage)
        self._record_combat_hit(attacker_name, target_name, ability_name, damage, damage_type, is_autoattack, timestamp)
        if damage_2 is not None:
            damage_2 = _CommonRE.parse_int(damage_2)
            if damage_2 > 0:
                self._record_combat_hit(attacker_name, target_name, ability_name, damage_2, damage_type_2, is_autoattack, timestamp)

    def __parse_ability_effect_match(self, match: Match, timestamp: float):
        caster_name = match.group(1)
        ability_name = match.group(2)
        ability_name = self._get_canonical_ability_name(ability_name)
        if match.group(3) is not None:
            ward_amount = _CommonRE.parse_int(match.group(4))
            ward_target = match.group(5)
            ward_remain = _CommonRE.parse_int(match.group(6))
            self._record_damage_warded(caster_name, ward_target, ability_name, ward_amount, ward_remain, timestamp)
            return
        if match.group(7) is not None:
            heal_target = match.group(8)
            heal_amount = _CommonRE.parse_int(match.group(9))
            self._record_damage_healed(caster_name, heal_target, ability_name, heal_amount, timestamp)
            return
        if match.group(10) is not None:
            feed_target = match.group(11)
            power_amount = _CommonRE.parse_int(match.group(12))
            self._record_power_refreshed(caster_name, feed_target, ability_name, power_amount, timestamp)
            return
        if match.group(13) is not None:
            regenerate_amount = _CommonRE.parse_int(match.group(14))
            self._record_regeneration(caster_name, ability_name, regenerate_amount, timestamp)
            return
        if match.group(15) is not None:
            removed_effect_name = match.group(16)
            removed_effect_name = self._get_canonical_ability_name(removed_effect_name)
            target_name = match.group(17)
            self._record_cure(caster_name, target_name, ability_name, removed_effect_name, timestamp)
            return
        assert False, match.group(0)

    def __parse_effect_dispel_match(self, match: Match, timestamp: float):
        caster_name = match.group(1)
        ability_name = match.group(2)
        ability_name = self._get_canonical_ability_name(ability_name)
        removed_effect_name = match.group(3)
        removed_effect_name = self._get_canonical_ability_name(removed_effect_name)
        target_name = match.group(4)
        self._record_dispel(caster_name, target_name, ability_name, removed_effect_name, timestamp)

    def __parse_power_drain_match(self, match: Match, timestamp: float):
        caster_name = match.group(1)
        ability_name = match.group(2)
        drain_target = match.group(3)
        power_amount = _CommonRE.parse_int(match.group(4))
        drain_type = match.group(5)
        if ability_name:
            ability_name = self._get_canonical_ability_name(ability_name)
        else:
            ability_name = drain_type
        self._record_power_drained(caster_name, drain_target, ability_name, power_amount, drain_type, timestamp)

    def __parse_threat_match(self, match: Match, timestamp: float):
        attacker_name = match.group(1)
        ability_name = match.group(2)
        ability_name = self._get_canonical_ability_name(ability_name)
        increase = match.group(3)
        is_positions = match.group(4) is not None
        target_name = match.group(5)
        threat = _CommonRE.parse_int(match.group(6))
        if increase == 'reduces':
            threat = -threat
        self._record_threat(attacker_name, target_name, ability_name, threat, is_positions, timestamp)

    def __parse_damage_reduction_match(self, match: Match, timestamp: float):
        healer_name = match.group(1)
        _attacker_name = match.group(2)
        target_name = match.group(3)
        reduced_amount = _CommonRE.parse_int(match.group(4))
        self._record_damage_healed(healer_name, target_name, 'reduction', reduced_amount, timestamp)

    def __parse_applied_ward_match(self, match: Match, timestamp: float):
        caster_name = match.group(1)
        ability_name = match.group(2)
        ability_name = self._get_canonical_ability_name(ability_name)
        target_name = match.group(3)
        ward_amount = _CommonRE.parse_int(match.group(4))
        self._record_applied_ward(caster_name, target_name, ability_name, ward_amount, timestamp)

    def __parse_stoneskin_match(self, match: Match, timestamp: float):
        stoneskin_amount = _CommonRE.parse_int(match.group(1))
        self._record_stoneskin(stoneskin_amount, timestamp)

    def __parse_interrupt_match(self, match: Match, timestamp: float):
        interrupted_player = match.group(1)
        self._record_interrupt(interrupted_player, timestamp)

    def _preparse_noncombat_log_line(self, log_line: str, timestamp: float) -> bool:
        return False

    # override LogParser
    def _preparse_log_line(self, log_line: str, timestamp: float) -> bool:
        # noinspection PyBroadException
        try:
            # all combat damage hits
            match = self.__compiled_combat_hit_re.match(log_line)
            if match is not None:
                self.__parse_combat_hit_match(match, timestamp)
                return True
            # ability effects such as healing, warding, curing, regeneration, power
            match = self.__compiled_ability_effect_re.match(log_line)
            if match is not None:
                self.__parse_ability_effect_match(match, timestamp)
                return True
            # power drain
            match = self.__compiled_power_drain_re.match(log_line)
            if match is not None:
                self.__parse_power_drain_match(match, timestamp)
                return True
            # taunts and positions
            match = self.__compiled_threat_re.match(log_line)
            if match is not None:
                self.__parse_threat_match(match, timestamp)
                return True
            # damage reductions/intercepts
            match = self.__compiled_damage_reduction_re.match(log_line)
            if match is not None:
                self.__parse_damage_reduction_match(match, timestamp)
                return True
            # new wards
            match = self.__compiled_applied_ward_re.match(log_line)
            if match is not None:
                self.__parse_applied_ward_match(match, timestamp)
                return True
            # stoneskins triggering
            match = self.__compiled_stoneskin_re.match(log_line)
            if match is not None:
                self.__parse_stoneskin_match(match, timestamp)
                return True
            # dispels
            match = self.__compiled_effect_dispel_re.match(log_line)
            if match is not None:
                self.__parse_effect_dispel_match(match, timestamp)
                return True
            # interrupted casting
            match = self.__compiled_interrupt_re.match(log_line)
            if match is not None:
                self.__parse_interrupt_match(match, timestamp)
                return True
            # ignored combat logs
            match = self.__compiled_ignored_logs_re.match(log_line)
            if match is not None:
                return True
            # non-combat logs - open for all triggers
            if self._preparse_noncombat_log_line(log_line, timestamp):
                return True
        except Exception as e:
            traceback.print_exc()
            logger.error(f'Logger error when parsing dps line: {e}')
            logger.error(f'{log_line}')
            traceback.print_exc()
        return False

    def get_combat_start_time(self) -> Optional[float]:
        return self.__start_time

    def get_combat_duration(self) -> float:
        start_time = self.__start_time
        last_time = self.__last_time
        if not start_time or not last_time:
            return 0.0
        d = last_time - start_time
        if last_time - time.time() >= DPSPARSE_NEW_ENCOUNTER_GAP:
            return d - DPSPARSE_NEW_ENCOUNTER_GAP
        return d

    # override LogParser
    def close(self):
        self.__parser_closed = True
        LogParser.close(self)
        self.__combat_ticker.cancel_future()


if __name__ == '__main__':
    print(CombatLogParser.compile_combat_hit_re())
