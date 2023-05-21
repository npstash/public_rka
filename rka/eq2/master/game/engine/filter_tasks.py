from __future__ import annotations

import time
from threading import Condition, RLock
from typing import Optional, Union, List, Set, Dict, Callable

from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityPriority
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import MysticAbilities
from rka.eq2.master.game.effect import EffectType
from rka.eq2.master.game.engine import logger
from rka.eq2.master.game.engine.task import FilterTask, IAbilityCastingObserver
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IPlayer, TOptionalPlayer, TAbilityFilter, IPlayerSelector
from rka.eq2.shared.flags import MutableFlags


class StopCastingFilter(FilterTask):
    def __init__(self, player: TOptionalPlayer, duration: float):
        FilterTask.__init__(self, filter_cb=AbilityFilter().except_caster_or_none(player),
                            description=f'filter: {player} dont cast', duration=duration)


class ControlOnlyFilter(FilterTask):
    def __init__(self, player: Optional[IPlayer], duration: float):
        FilterTask.__init__(self, filter_cb=AbilityFilter().by_min_priority(AbilityPriority.CONTROL, player),
                            description=f'filter: {player} only control', duration=duration)


class AbilityGlobalFlagsFilter(FilterTask):
    def __init__(self):
        FilterTask.__init__(self, filter_cb=AbilityGlobalFlagsFilter.condition, description='filter: exclude by global flags', duration=-1.0)

    @staticmethod
    def condition(ability: IAbility) -> bool:
        if not MutableFlags.ENABLE_MYSTIC_GRP_WARD:
            if ability.locator == MysticAbilities.umbral_barrier:
                return False
        if not MutableFlags.ENABLE_LOCAL_ABILITIES:
            if ability.player.is_local():
                return False
        return True


class GameStateFilter(FilterTask):
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        FilterTask.__init__(self, filter_cb=self.condition, description='filter: check game states', duration=-1.0)

    def condition(self, ability: IAbility) -> bool:
        if not ability.ext.cast_in_combat and self.__runtime.combatstate.is_combat():
            return False
        if ability.shared.enabled_at is None:
            return False
        if ability.shared.enabled_at > 0.0:
            if time.time() < ability.shared.enabled_at:
                return False
        return True


class AbilityCanceller(FilterTask, IAbilityCastingObserver):
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        FilterTask.__init__(self, filter_cb=self.condition, description='filter: expire abilities', duration=-1.0)

    # noinspection PyMethodMayBeStatic
    def condition(self, _ability: IAbility) -> bool:
        return True

    def notify_casting(self, ability: IAbility):
        if not ability.census.beneficial:
            for ability_to_expire in self.__runtime.ability_reg.find_abilities_expire_on_attack(ability.player):
                ability_to_expire.expire_duration()
        has_stealth = self.__runtime.effects_mgr.apply_effects(effect_type=EffectType.STEALTH, apply_target=ability.player.as_effect_target(), base_value=False)
        if has_stealth:
            effects = self.__runtime.effects_mgr.get_effects(apply_target=ability.player.as_effect_target(), effect_type=EffectType.STEALTH)
            for effect in effects:
                stealth_ability = effect.sustain_source().ability()
                if stealth_ability:
                    stealth_ability.expire_duration()
        if ability.ext.move:
            for ability_to_expire in self.__runtime.ability_reg.find_abilities_expire_on_move(ability.player):
                ability_to_expire.expire_duration()
        return True


class ConfirmAbilityCasting(FilterTask, IAbilityCastingObserver):
    def __init__(self, ability: Union[IAbility, IAbilityLocator, TAbilityFilter], duration: float,
                 notify_callback: Optional[TAbilityFilter] = None):
        FilterTask.__init__(self, filter_cb=AbilityFilter(), description='filter: block until ability is cast', duration=duration)
        self.__ability = ability
        self.__condition = Condition()
        self.__last_cast_at = 0.0
        self.__monitoring_started_at = time.time()
        self.__notify_callback = notify_callback

    def __condition_met(self, ability: IAbility) -> bool:
        if isinstance(self.__ability, IAbilityLocator):
            match = self.__ability == ability.locator
        elif isinstance(self.__ability, IAbility):
            match = self.__ability == ability
        elif isinstance(self.__ability, AbilityFilter):
            match = self.__ability.accept_ability(ability)
        elif isinstance(self.__ability, Callable):
            match = self.__ability(ability)
        else:
            assert False, self.__ability
        return match

    def notify_casting(self, ability: IAbility):
        if not self.__condition_met(ability):
            return
        with self.__condition:
            self.__last_cast_at = time.time()
            self.__condition.notify_all()
        if self.__notify_callback:
            keep_notifying = self.__notify_callback(ability)
            if keep_notifying is None:
                logger.error(f'ConfirmAbilityCasting: keep_notifying is None for {self.__ability}')
            if not keep_notifying:
                self.__notify_callback = None

    def start_monitoring_now(self):
        self.__monitoring_started_at = time.time()

    def wait_for_ability(self, timeout: float) -> bool:
        time_left = timeout
        with self.__condition:
            while time_left > 0.0 and self.__last_cast_at < self.__monitoring_started_at and not self.is_expired():
                condition_wait_start = time.time()
                self.__condition.wait(time_left)
                time_left -= (time.time() - condition_wait_start)
            return self.__last_cast_at >= self.__monitoring_started_at


class ProcessorPlayerSwitcher(FilterTask, IPlayerSelector):
    class PlayerAssignment:
        def __init__(self, player: IPlayer, owner: ProcessorPlayerSwitcher):
            self.__player = player
            self.__owner: ProcessorPlayerSwitcher = owner
            self.__borrow_queue: List[ProcessorPlayerSwitcher] = list()

        def __str__(self) -> str:
            holder = self.__borrow_queue[-1] if self.__borrow_queue else self.__owner
            return f'PA:{self.__player}, owner:{self.__owner}, holder:{holder}'

        def is_owner(self, switcher: ProcessorPlayerSwitcher) -> bool:
            return self.__owner == switcher

        def is_holder(self, switcher: ProcessorPlayerSwitcher) -> bool:
            if self.__borrow_queue:
                return self.__borrow_queue[-1] == switcher
            return self.__owner == switcher

        def borrow_for(self, switcher: ProcessorPlayerSwitcher):
            if self in self.__borrow_queue:
                self.__borrow_queue.remove(switcher)
            self.__borrow_queue.append(switcher)

        def return_to_owner(self):
            while self.__borrow_queue:
                self.__borrow_queue[-1].return_player(self.__player)

        def return_to_previous_holder(self):
            if self.__borrow_queue:
                self.__borrow_queue.pop()

    __lock = RLock()
    __n = 0
    __player_assignments: Dict[IPlayer, PlayerAssignment] = dict()

    def __init__(self):
        FilterTask.__init__(self, filter_cb=self.ability_filter_condition, description=f'PlayerSwitcher #{ProcessorPlayerSwitcher.__n}', duration=-1.0)
        ProcessorPlayerSwitcher.__n += 1
        self.__disabled_players: Set[IPlayer] = set()

    def add_player(self, player: IPlayer) -> bool:
        with ProcessorPlayerSwitcher.__lock:
            if player in ProcessorPlayerSwitcher.__player_assignments:
                pa = ProcessorPlayerSwitcher.__player_assignments[player]
                logger.warn(f'Player already assigned: {pa}')
                return False
            logger.info(f'ProcessorPlayerSwitcher.add_player: {player} to {self}')
            ProcessorPlayerSwitcher.__player_assignments[player] = ProcessorPlayerSwitcher.PlayerAssignment(player, self)
            return True

    def remove_player(self, player: IPlayer) -> bool:
        with ProcessorPlayerSwitcher.__lock:
            if player not in ProcessorPlayerSwitcher.__player_assignments:
                logger.warn(f'Player does not exist: {player}')
                return False
            pa = ProcessorPlayerSwitcher.__player_assignments[player]
            if not pa.is_owner(self):
                logger.error(f'Cannot remove from {self}, not owner of {pa}')
                return False
            logger.info(f'ProcessorPlayerSwitcher.remove_player: {player} from {self}')
            pa.return_to_owner()
            if player in self.__disabled_players:
                self.__disabled_players.remove(player)
            del ProcessorPlayerSwitcher.__player_assignments[player]
            return True

    def borrow_player(self, player: IPlayer) -> bool:
        with ProcessorPlayerSwitcher.__lock:
            if player not in ProcessorPlayerSwitcher.__player_assignments:
                logger.warn(f'Player does not exist: {player}')
                return False
            logger.info(f'ProcessorPlayerSwitcher.borrow_player: {player} for {self}')
            pa = ProcessorPlayerSwitcher.__player_assignments[player]
            pa.borrow_for(self)
            return True

    def return_player(self, player: IPlayer) -> bool:
        with ProcessorPlayerSwitcher.__lock:
            if player not in ProcessorPlayerSwitcher.__player_assignments:
                logger.warn(f'Player does not exist: {player}')
                return False
            pa = ProcessorPlayerSwitcher.__player_assignments[player]
            if not pa.is_holder(self):
                logger.error(f'Cannot return from {self}, not holder of {pa}')
                return False
            logger.info(f'ProcessorPlayerSwitcher.return_player: {player} from {self}')
            pa.return_to_previous_holder()
            if player in self.__disabled_players:
                self.__disabled_players.remove(player)
            return True

    def return_all_players(self):
        with ProcessorPlayerSwitcher.__lock:
            for player, pa in ProcessorPlayerSwitcher.__player_assignments.items():
                if pa.is_holder(self):
                    self.return_player(player)

    def remove_all_players(self):
        with ProcessorPlayerSwitcher.__lock:
            assignments_copy = dict(ProcessorPlayerSwitcher.__player_assignments)
            for player, pa in assignments_copy.items():
                if pa.is_owner(self):
                    self.remove_player(player)

    def disable_player(self, player: IPlayer):
        with ProcessorPlayerSwitcher.__lock:
            logger.info(f'ProcessorPlayerSwitcher.disable_player: {player} in {self}')
            self.__disabled_players.add(player)

    def is_holder_of(self, player: IPlayer, include_disabled: bool) -> bool:
        with ProcessorPlayerSwitcher.__lock:
            if player not in ProcessorPlayerSwitcher.__player_assignments:
                return False
            if not include_disabled and player in self.__disabled_players:
                return False
            pa = ProcessorPlayerSwitcher.__player_assignments[player]
            return pa.is_holder(self)

    def get_holding_players(self, include_disabled: bool) -> List[IPlayer]:
        with ProcessorPlayerSwitcher.__lock:
            players = list()
            for player, pa in ProcessorPlayerSwitcher.__player_assignments.items():
                if pa.is_holder(self):
                    if include_disabled or player not in self.__disabled_players:
                        players.append(player)
            return players

    def ability_filter_condition(self, ability: IAbility) -> bool:
        return self.is_holder_of(ability.player, include_disabled=False)

    def close_switcher(self):
        self.return_all_players()
        self.remove_all_players()

    def resolve_players(self) -> List[IPlayer]:
        return self.get_holding_players(include_disabled=False)
