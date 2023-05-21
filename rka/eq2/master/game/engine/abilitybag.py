from __future__ import annotations

import datetime
from random import choice
from typing import Dict, List, Set, Optional, Iterable, Callable, Any

from rka.eq2.configs.shared.game_constants import READYUP_MIN_PERIOD
from rka.eq2.configs.shared.rka_constants import ABILITY_CASTING_SAFETY, ABILITY_REUSE_SAFETY
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.snap import AbilitySnapshot
from rka.eq2.master.game.interfaces import IAbility, IPlayer, TAbilityFilter


def minall(abilities: List[IAbility], key: Callable[[IAbility], Any]) -> List[Any]:
    keyvalues = map(key, abilities)
    extremum = min(keyvalues)
    return [ability for ability in abilities if key(ability) == extremum]


def maxall(abilities: List[IAbility], key: Callable[[IAbility], Any]) -> List[Any]:
    keyvalues = map(key, abilities)
    extremum = max(keyvalues)
    return [ability for ability in abilities if key(ability) == extremum]


class AbilityBag:
    def __init__(self, abilities: Optional[Iterable[IAbility]] = None, readonly=False):
        self.__abilities: List[IAbility] = list(abilities) if abilities is not None else []
        self.__bags: List[AbilityBag] = list()
        self.__filter: Optional[TAbilityFilter] = None
        self.__readonly = readonly

    def __str__(self):
        abilities_str = [str(a) for a in self.__abilities]
        return f'[{len(abilities_str)}] {abilities_str}'

    def add_bag(self, bag: AbilityBag):
        assert not self.__readonly
        self.__bags.append(bag)

    def remove_bag(self, bag: AbilityBag):
        assert not self.__readonly
        self.__bags.remove(bag)

    def snapshot(self) -> AbilityBag:
        abilities = self.get_abilities_unfiltered()
        snapshots = list()
        for ability in abilities:
            snapshots.append(AbilitySnapshot(ability))
        new_bag = AbilityBag(snapshots)
        new_bag.set_filter(self.__filter)
        return new_bag

    def set_filter(self, ability_filter: TAbilityFilter):
        self.__filter = ability_filter

    def filter_abilities(self, abilities: Optional[List[IAbility]]) -> List[IAbility]:
        if abilities is None:
            abilities = self.get_abilities_unfiltered()
        if self.__filter is None:
            return list(abilities)
        accepted: List[IAbility] = list()
        for ability in abilities:
            if self.__filter(ability):
                accepted.append(ability)
        return accepted

    def get_abilities(self) -> List[IAbility]:
        filtered_abilities = self.filter_abilities(self.__abilities)
        for bag in self.__bags:
            filtered_abilities += bag.get_abilities()
        return filtered_abilities

    def get_first_ability(self) -> Optional[IAbility]:
        filtered_abilities = self.filter_abilities(self.__abilities)
        if filtered_abilities:
            return filtered_abilities[0]
        for bag in self.__bags:
            abilities = bag.get_abilities()
            if abilities:
                return abilities[0]
        return None

    def get_abilities_unfiltered(self) -> List[IAbility]:
        unfiltered_abilities = list()
        for bag in self.__bags:
            unfiltered_abilities += bag.get_abilities()
        return unfiltered_abilities

    def get_all_players(self) -> Set[IPlayer]:
        players: Set[IPlayer] = set()
        for ability in self.get_abilities():
            players.add(ability.player)
        return players

    def get_map_by_player(self) -> Dict[IPlayer, AbilityBag]:
        abilities_by_player: Dict[IPlayer, Dict[str, IAbility]] = dict()
        bags_by_player: Dict[IPlayer, AbilityBag] = dict()
        players = self.get_all_players()
        filtered_abilities = self.get_abilities()
        for player in players:
            abilities_by_player[player] = dict()
        for ability in filtered_abilities:
            abilities_by_player[ability.player][ability.ability_variant_key()] = ability
        for player in players:
            bags_by_player[player] = AbilityBag(abilities_by_player[player].values())
        return bags_by_player

    def one_random(self) -> AbilityBag:
        filtered_abilities = self.get_abilities()
        if not filtered_abilities:
            return EMPTY_BAG
        return AbilityBag([choice(filtered_abilities)])

    def one_of_least_busy_player(self) -> AbilityBag:
        filtered_abilities = self.get_abilities()
        best_ability = None
        for ability in filtered_abilities:
            if not best_ability or best_ability.player.is_busier_than(ability.player):
                best_ability = ability
        if not best_ability:
            return EMPTY_BAG
        return AbilityBag([best_ability])

    def get_bag_by_filter(self, condition: TAbilityFilter) -> AbilityBag:
        return AbilityBag(filter(condition, self.get_abilities()))

    def get_bag_by_max_priority(self) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        max_priority_abilities = maxall(abilities, key=lambda ability: ability.get_priority())
        if not max_priority_abilities:
            return EMPTY_BAG
        return AbilityBag(max_priority_abilities)

    def get_bag_by_max_duration(self) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        max_duration_abilities = maxall(abilities, key=lambda ability: ability.census.duration)
        if not max_duration_abilities:
            return EMPTY_BAG
        return AbilityBag(max_duration_abilities)

    def get_bag_by_priority_in_range(self, max_priority: int, priority_range: int) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        abilities_in_range = [ability for ability in abilities if max_priority - priority_range <= ability.get_priority() <= max_priority]
        return AbilityBag(abilities_in_range)

    def get_bag_by_general_preference(self, max_return=1) -> AbilityBag:
        if self.is_empty():
            return EMPTY_BAG
        # assume all abilities are reusable, or its not a factor here
        # 1. dont include abilities already running
        # 2. select abilities with best (duration + reuse)/casting ratio * priority
        ability_bag = self.get_bag_by_duration_expired()
        if ability_bag.is_empty():
            ability_bag = self
        abilities = ability_bag.get_abilities()
        max_priority = max(abilities, key=lambda ability: ability.get_priority()).get_priority()
        min_priority = min(abilities, key=lambda ability: ability.get_priority()).get_priority()
        priority_spread = max_priority - min_priority

        def ranking(ability: IAbility) -> float:
            # normalized priority 0.5 - 0.99
            priority_factor = (ability.get_priority() - min_priority) / (priority_spread + 1)
            priority_factor = priority_factor * 0.5 + 0.5
            # permanent buffs get some duration too
            duration = 50.0 if ability.census.duration < 0.0 else ability.census.duration
            # impose some fixed casting overhead
            casting = ability.census.casting + ABILITY_CASTING_SAFETY
            # set a cap for reuse - due to ReadyUp and Asensions (prevent favorizing them)
            reuse = max(ability.census.reuse + ABILITY_REUSE_SAFETY, READYUP_MIN_PERIOD)
            usefullness_factor = (duration + reuse) / casting
            return usefullness_factor * priority_factor

        sorted_abilities = sorted(abilities, key=ranking, reverse=True)
        return AbilityBag(sorted_abilities[:max_return])

    def get_bag_by_shortest_cast_time(self) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        min_time_to_cast = minall(abilities, key=lambda ability: ability.census.casting)
        if not min_time_to_cast:
            return EMPTY_BAG
        return AbilityBag(min_time_to_cast)

    def get_bag_by_shortest_reuse_time(self) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        min_time_to_reuse = minall(abilities, key=lambda ability: ability.census.reuse)
        if not min_time_to_reuse:
            return EMPTY_BAG
        return AbilityBag(min_time_to_reuse)

    def get_bag_by_shortest_time_to_recast(self, now: Optional[datetime.datetime] = None) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        if not now:
            now = datetime.datetime.now()
        min_time_to_recast = minall(abilities, key=lambda ability: round(ability.get_remaining_reuse_wait_td(now).seconds, 1))
        if not min_time_to_recast:
            return EMPTY_BAG
        return AbilityBag(min_time_to_recast)

    def get_bag_by_reusable(self, now: Optional[datetime.datetime] = None) -> AbilityBag:
        if not now:
            now = datetime.datetime.now()
        return self.get_bag_by_filter(AbilityFilter().reusable(now))

    def get_bag_by_duration_expired(self, now: Optional[datetime.datetime] = None) -> AbilityBag:
        if not now:
            now = datetime.datetime.now()
        return self.get_bag_by_filter(AbilityFilter().expired(now))

    def get_bag_by_in_duration_or_casting(self, now: Optional[datetime.datetime] = None) -> AbilityBag:
        if not now:
            now = datetime.datetime.now()
        return self.get_bag_by_filter(AbilityFilter().casting_or_in_duration(now))

    def get_bag_by_can_override(self, test_ability: IAbility) -> AbilityBag:
        return self.get_bag_by_filter(AbilityFilter().can_override(test_ability))

    def get_bag_by_highest_tier(self) -> AbilityBag:
        abilities = self.get_abilities()
        if not abilities:
            return EMPTY_BAG
        max_tier = maxall(abilities, key=lambda ability: ability.census.tier_int)
        if not max_tier:
            return EMPTY_BAG
        return AbilityBag(max_tier)

    def is_empty(self) -> bool:
        filtered_abilities = self.filter_abilities(self.__abilities)
        if filtered_abilities:
            return False
        for bag in self.__bags:
            if not bag.is_empty():
                return False
        return True


EMPTY_BAG = AbilityBag([], readonly=True)
