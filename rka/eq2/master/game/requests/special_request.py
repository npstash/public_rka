import time
from typing import List, Optional, Dict

from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.eq2.master import RequiresRuntime
from rka.eq2.master.game.ability import HOIcon
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import MonkAbilities, BrawlerAbilities, FighterAbilities
from rka.eq2.master.game.engine import ICombatantFilter
from rka.eq2.master.game.engine.abilitybag import AbilityBag, EMPTY_BAG
from rka.eq2.master.game.engine.request import Request, RotationWithTargetRanking, CastAnyWhenReady, CascadeRequest
from rka.eq2.master.game.engine.resolver import AbilityResolver
from rka.eq2.master.game.engine.resolver import TAbilities
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.interfaces import AbilityRecord, IAbilityRecordFilter, IAbility, IAbilityLocator
from rka.eq2.master.game.requests.ranking import RankingByIncDamage, RankingByHealNeed
from rka.eq2.master.parsing import CombatantType, ICombatantRecord
from rka.log_configs import LOG_SPECIAL_REQUESTS

logger = LogService(LOG_SPECIAL_REQUESTS)


class InterceptRotation(RotationWithTargetRanking, ICombatantFilter, IAbilityRecordFilter):
    def __init__(self, abilities_to_rotate: List[IAbilityLocator], resolver: AbilityResolver,
                 max_targets: int, exclude_self: bool, max_hits: int, threshold: int, duration: float, description: Optional[str] = None):
        RotationWithTargetRanking.__init__(self, abilities_to_rotate=abilities_to_rotate, ranker=RankingByIncDamage(max_targets=max_targets),
                                           exclude_self=exclude_self, combatant_filter=self, ability_record_filter=self,
                                           resolver=resolver, duration=duration, description=description)
        self.__max_hits = max_hits
        self.__threshold = threshold

    def __get_combatant_hits(self, ability: IAbility) -> int:
        target = ability.get_target()
        if target:
            combatant_record = self.get_runtime().current_dps.get_combatant_record(target.get_target_name())
            if combatant_record:
                return combatant_record.get_incoming_hit_counter(threshold=self.__threshold)
        return 0

    def notify_casting_record(self, ability_record: AbilityRecord):
        logger.detail(f'rotation notify casting: {ability_record}')
        if self.__max_hits <= 0:
            return
        current_hits = self.__get_combatant_hits(ability_record.ability)
        ability_record.properties['last_hits'] = current_hits

    def accept_ability_record(self, ability_record: AbilityRecord) -> bool:
        if self.__max_hits <= 0:
            return True
        if ability_record.ability.is_duration_expired():
            return True
        current_hits = self.__get_combatant_hits(ability_record.ability)
        last_hits = ability_record.properties.get('last_hits', current_hits)
        if current_hits >= last_hits + self.__max_hits:
            ability_record.ability.expire_duration()
        return True

    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        combatant_type = combatant.get_combatant_type()
        if not CombatantType.is_nonmain_player(combatant_type):
            return False
        # wont work if the monk is a remote player
        if combatant.get_combatant_name() == self.get_runtime().playerstate.get_main_player_name():
            return False
        return True


class WardRotation(RotationWithTargetRanking, ICombatantFilter, IAbilityRecordFilter):
    def __init__(self, abilities_to_rotate: List[IAbilityLocator], resolver: AbilityResolver,
                 max_targets: int, exclude_self: bool, duration: float, description: Optional[str] = None):
        RotationWithTargetRanking.__init__(self, abilities_to_rotate=abilities_to_rotate, ranker=RankingByIncDamage(max_targets=max_targets),
                                           exclude_self=exclude_self, combatant_filter=self, ability_record_filter=self,
                                           resolver=resolver, duration=duration, description=description)

    def notify_casting_record(self, ability_record: AbilityRecord):
        logger.detail(f'rotation notify casting: {ability_record}')

    def accept_ability_record(self, ability_record: AbilityRecord) -> bool:
        return True

    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        combatant_type = combatant.get_combatant_type()
        if not CombatantType.is_nonmain_player(combatant_type):
            return False
        return True


class HoTRotation(RotationWithTargetRanking, ICombatantFilter, IAbilityRecordFilter):
    def __init__(self, abilities_to_rotate: List[IAbilityLocator], resolver: AbilityResolver,
                 max_targets: int, exclude_self: bool, duration: float, description: Optional[str] = None):
        RotationWithTargetRanking.__init__(self, abilities_to_rotate=abilities_to_rotate, ranker=RankingByHealNeed(max_targets=max_targets),
                                           exclude_self=exclude_self, combatant_filter=self, ability_record_filter=self,
                                           resolver=resolver, duration=duration, description=description)

    def notify_casting_record(self, ability_record: AbilityRecord):
        logger.detail(f'rotation notify casting: {ability_record}')

    def accept_ability_record(self, ability_record: AbilityRecord) -> bool:
        return True

    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        combatant_type = combatant.get_combatant_type()
        if not CombatantType.is_nonmain_player(combatant_type):
            return False
        return True


# must be cached request
class Combination(Request):
    jabs = [MonkAbilities.striking_cobra, MonkAbilities.arctic_talon, MonkAbilities.frozen_palm]
    kicks = [MonkAbilities.rising_phoenix, MonkAbilities.rising_dragon, MonkAbilities.roundhouse_kick]
    punches = [MonkAbilities.silent_palm, MonkAbilities.waking_dragon]
    dont_cast = [MonkAbilities.rising_dragon]
    all_abilities = jabs + kicks + punches

    NONE = 0
    JAB = 1
    KICK = 3
    PUNCH = 7

    MAX_DELAY = 4.0

    next_attack = {
        NONE: PUNCH,
        JAB: PUNCH,
        KICK: PUNCH,
        PUNCH: JAB,
        JAB + JAB: PUNCH,
        JAB + KICK: PUNCH,
        JAB + PUNCH: KICK,
        KICK + KICK: PUNCH,
        KICK + PUNCH: JAB,
        PUNCH + PUNCH: JAB,
    }

    def __init__(self, duration: float):
        Request.__init__(self, abilities=Combination.all_abilities,
                         resolver=AbilityResolver().filtered(AbilityFilter().local_casters()),
                         duration=duration,
                         description='Monk Combination')
        bus = EventSystem.get_main_bus()
        for jab in Combination.jabs:
            bus.subscribe(CombatParserEvents.COMBAT_HIT(ability_name=jab.get_canonical_name(), attacker_type=CombatantType.MAIN_PLAYER,
                                                        is_multi=False, is_dot=False, is_autoattack=False), self.__jab_hit)
        for kick in Combination.kicks:
            bus.subscribe(CombatParserEvents.COMBAT_HIT(ability_name=kick.get_canonical_name(), attacker_type=CombatantType.MAIN_PLAYER,
                                                        is_multi=False, is_dot=False, is_autoattack=False), self.__kick_hit)
        for punch in Combination.punches:
            bus.subscribe(CombatParserEvents.COMBAT_HIT(ability_name=punch.get_canonical_name(), attacker_type=CombatantType.MAIN_PLAYER,
                                                        is_multi=False, is_dot=False, is_autoattack=False), self.__punch_hit)
        self.last_hit = Combination.NONE
        self.last_hit_time = 0.0
        self.previous_hit = Combination.NONE
        self.previous_hit_time = 0.0
        self.request_changed = True
        self.last_bag = EMPTY_BAG
        self.map_name_to_type = {
            ability_loc.get_canonical_name(): Combination.JAB if ability_loc in Combination.jabs
            else Combination.PUNCH if ability_loc in Combination.punches
            else Combination.KICK
            for ability_loc in Combination.all_abilities
        }
        resolved_abilities = self.get_resolved_abilities_map()
        self.map_type_to_abilities = {
            Combination.JAB: [ability for ability in resolved_abilities.values()
                              if ability.locator in Combination.jabs and ability.locator not in Combination.dont_cast],
            Combination.KICK: [ability for ability in resolved_abilities.values()
                               if ability.locator in Combination.kicks and ability.locator not in Combination.dont_cast],
            Combination.PUNCH: [ability for ability in resolved_abilities.values()
                                if ability.locator in Combination.punches and ability.locator not in Combination.dont_cast],
        }

    def _on_expire(self):
        self.last_bag = EMPTY_BAG

    def __update_timers(self, now: float):
        if now - self.previous_hit_time >= Combination.MAX_DELAY:
            if self.previous_hit != Combination.NONE:
                logger.info(f'COMBINATION: previous ({self.previous_hit}) too old {now - self.previous_hit_time}')
                self.previous_hit = Combination.NONE
                self.previous_hit_time = 0.0
                self.request_changed = True
        if now - self.last_hit_time >= Combination.MAX_DELAY:
            if self.last_hit != Combination.NONE:
                logger.info(f'COMBINATION: last ({self.last_hit}) too old {now - self.last_hit_time}')
                self.last_hit = Combination.NONE
                self.last_hit_time = 0.0
                self.request_changed = True

    def __add_hit(self, ability_name: str, timestamp: float):
        if ability_name not in self.map_name_to_type:
            logger.warn(f'invalid ability for combination {ability_name}')
            return
        self.__update_timers(timestamp)
        new_hit = self.map_name_to_type[ability_name]
        self.previous_hit = self.last_hit
        self.previous_hit_time = self.last_hit_time
        self.last_hit = new_hit
        self.last_hit_time = timestamp
        self.request_changed = True
        logger.debug(f'COMBINATION: hit of {ability_name} ({self.previous_hit} -> {self.last_hit})')

    def __jab_hit(self, event: CombatParserEvents.COMBAT_HIT):
        self.__add_hit(event.ability_name, event.timestamp)

    def __kick_hit(self, event: CombatParserEvents.COMBAT_HIT):
        self.__add_hit(event.ability_name, event.timestamp)

    def __punch_hit(self, event: CombatParserEvents.COMBAT_HIT):
        self.__add_hit(event.ability_name, event.timestamp)

    def get_available_ability_bag(self) -> AbilityBag:
        now = time.time()
        self.__update_timers(now)
        if not self.request_changed and not self.last_bag.is_empty():
            return self.last_bag
        next_hit_type = Combination.next_attack[self.last_hit + self.previous_hit]
        next_next_hit_type = Combination.next_attack[self.last_hit + next_hit_type]
        logger.info(f'COMBINATION: after {self.last_hit} and {self.previous_hit} next is {next_hit_type}, then {next_next_hit_type}')
        next_abilities = self._filter_abilities(self.map_type_to_abilities[next_hit_type])
        next_next_abilities = self._filter_abilities(self.map_type_to_abilities[next_next_hit_type])
        if not next_abilities or not next_next_abilities:
            self.last_bag = EMPTY_BAG
        else:
            self.last_bag = AbilityBag(next_abilities)
        self.request_changed = False
        return self.last_bag


class CombinationClosure(CascadeRequest):
    def __init__(self, duration: float):
        combination_request = Combination(duration)
        closure_request = CastAnyWhenReady(
            abilities=[
                BrawlerAbilities.eagle_spin,
                BrawlerAbilities.pressure_point,
                BrawlerAbilities.baton_flurry,
                MonkAbilities.five_rings,
                FighterAbilities.goading_gesture,
                MonkAbilities.silent_threat,
            ],
            resolver=AbilityResolver().filtered(AbilityFilter().local_casters()),
            duration=duration)
        CascadeRequest.__init__(self, 'Combination Closure', [combination_request, closure_request], duration)


# cast all ability in a sequence, skip filtered.
class PeckingOrder(Request):
    def __init__(self, pecking_choices: List[List[IAbility]], resolver: AbilityResolver, rate: float, duration: float):
        Request.__init__(self, abilities=[], resolver=resolver, duration=duration)
        self.__remaining_chocies: List[Dict[str, IAbility]] = []
        self.__rate = rate
        for ability_choices in pecking_choices:
            resolved_ability_choices = AbilityResolver.reduce_variants(resolver.resolve_abilities(ability_choices))
            self.__remaining_chocies.append({ability.ability_variant_key(): ability for ability in resolved_ability_choices})
        self.__current_step = 0
        self.__current_step_start = 0.0

    def _on_expire(self):
        self.__current_step = -1

    def notify_casting(self, ability: IAbility):
        if self.__current_step >= len(self.__remaining_chocies):
            self.expire()
            return
        if ability.ability_variant_key() in self.__remaining_chocies[self.__current_step]:
            now = time.time()
            self.__current_step += 1
            self.__current_step_start = now

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__current_step >= len(self.__remaining_chocies):
            self.expire()
            return EMPTY_BAG
        now = time.time()
        if now - self.__current_step_start < self.__rate:
            return EMPTY_BAG
        current_choices = self._filter_abilities(self.__remaining_chocies[self.__current_step].values())
        if current_choices:
            return AbilityBag(current_choices)
        return EMPTY_BAG


class HeroicOpportunityRequest(Request, RequiresRuntime):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, ho_icon: HOIcon, max_hits: int, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration, description=f'{ho_icon.name} icon')
        RequiresRuntime.__init__(self)
        self.__max_cast = max_hits
        self.__casting_gap = 1.5
        self.__cast_count = 0
        self.__last_cast_time = 0.0

    def _on_expire(self):
        self.__cast_count = 0
        self.__last_cast_time = 0.0

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.__cast_count += 1
            self.__last_cast_time = time.time()
        if self.__cast_count >= self.__max_cast:
            self.expire()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.is_expired():
            return EMPTY_BAG
        if self.__cast_count >= self.__max_cast:
            self.expire()
            return EMPTY_BAG
        if time.time() - self.__last_cast_time < self.__casting_gap:
            return EMPTY_BAG
        available = Request.get_available_ability_bag(self).get_bag_by_reusable()
        return available


# fire a single ability, but do not expire the request, give extra window of casting (reassurance), only for TS reactions
class CastTradeskillReaction(Request):
    def __init__(self, abilities: IAbility, duration=3.0, casting_duration=1.5):
        Request.__init__(self, abilities=abilities, resolver=AbilityResolver(), duration=duration)
        self.__casting_start: Optional[float] = None
        self.__casting_duration = casting_duration
        self.__finished = False

    def _on_start(self):
        self.__finished = False
        self.__casting_start = time.time()

    def extend(self, duration: Optional[float] = None):
        pass

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.__finished = True

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__finished or self.__casting_start is None:
            return EMPTY_BAG
        if time.time() - self.__casting_start > self.__casting_duration:
            return EMPTY_BAG
        return super().get_available_ability_bag()


class Boneshattering(Request, RequiresRuntime):
    CASTAHEAD_TIME = 5.0
    INCREMENTS = 4

    def __init__(self, duration: float):
        resolver = AbilityResolver()
        Request.__init__(self, abilities=[BrawlerAbilities.boneshattering_combination], resolver=resolver, duration=duration, description='Boneshattering')
        self.__recent_hits = [0.0] * 5
        self.__last_hit_index = 0
        self.__last_time_hit = 0.0

    def __multiple_hits_in_row(self, n_hits: int, max_spead: float) -> bool:
        previous_hit = None
        for n in range(n_hits):
            n_index = (self.__last_hit_index - n) % len(self.__recent_hits)
            hit_time = self.__recent_hits[n_index]
            if hit_time == 0.0:
                return False
            if previous_hit is None:
                previous_hit = hit_time
                continue
            spread = previous_hit - hit_time
            if spread > max_spead:
                return False
            previous_hit = hit_time
        return True

    def get_available_ability_bag(self) -> AbilityBag:
        current_dps = self.get_runtime().current_dps
        if not current_dps:
            return EMPTY_BAG
        now = time.time()
        abilities = Request.get_available_ability_bag(self).get_bag_by_reusable()
        result = list()
        for ability in abilities.get_abilities():
            # expect one ability per player
            acr = current_dps.get_ability_combat_record(ability.player.get_player_name(), ability.locator.get_canonical_name())
            if not acr:
                continue
            if acr.last_time != self.__recent_hits[self.__last_hit_index]:
                self.__last_hit_index = (self.__last_hit_index + 1) % len(self.__recent_hits)
                self.__recent_hits[self.__last_hit_index] = acr.last_time
            duration = ability.census.duration
            if duration - Boneshattering.CASTAHEAD_TIME < now - acr.last_time < duration:
                if self.__multiple_hits_in_row(Boneshattering.INCREMENTS, 17.0):
                    continue
                result.append(ability)
        if not result:
            return EMPTY_BAG
        return AbilityBag(result)
