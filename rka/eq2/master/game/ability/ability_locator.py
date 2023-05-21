from __future__ import annotations

from typing import List, Callable, Optional

from rka.eq2.master.game.ability import AbilityPriority
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.ability.ability_data import AbilityExtConsts, AbilityCensusConsts
from rka.eq2.master.game.ability.ability_ext_reg import AbilityExtConstsRegistry
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.census.census_bridge import ICensusBridge
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IPlayer, TOptionalPlayer, IAbilityRegistry


class AbilityLocator(IAbilityLocator):
    def __init__(self, ability_reg: IAbilityRegistry, census_cache: ICensusBridge, ext_consts_reg: AbilityExtConstsRegistry,
                 game_class: GameClass, ability_id: str, canonical_ability_name: str, shared_name: str):
        self.__ability_reg = ability_reg
        self.__census_cache = census_cache
        self.__ext_consts_reg = ext_consts_reg
        self.__gameclass = game_class
        self.__ability_id = ability_id
        self.__canonical_ability_name = canonical_ability_name
        self.__shared_name = shared_name
        self.__cached_abilities: Optional[List[IAbility]] = None
        self.__locator_key: Optional[str] = None
        self.__hash: Optional[int] = None

    def __str__(self) -> str:
        return self.locator_key()

    def __hash__(self) -> int:
        if self.__hash is None:
            self.__hash = self.__str__().__hash__()
        return self.__hash

    def get_gameclass(self) -> GameClass:
        return self.__gameclass

    def get_ability_id(self) -> str:
        return self.__ability_id

    def get_canonical_name(self) -> str:
        return self.__canonical_ability_name

    def get_shared_name(self) -> str:
        return self.__shared_name

    def locator_key(self) -> str:
        if not self.__locator_key:
            self.__locator_key = f'{self.__gameclass.name}.{self.__ability_id}'
        return self.__locator_key

    def get_census_object_by_tier(self, player_level: int, ability_tier: AbilityTier) -> Optional[AbilityCensusConsts]:
        ability_census = self.__census_cache.get_ability_census_data_by_tier(gameclass=self.__gameclass,
                                                                             player_level=player_level,
                                                                             abilityname_lower=self.__canonical_ability_name,
                                                                             ability_tier=ability_tier)
        if not ability_census:
            return None
        ability_census_consts = AbilityCensusConsts()
        ability_census_consts.set_census_data(ability_census)
        return ability_census_consts

    def get_census_object_for_player(self, player: IPlayer) -> Optional[AbilityCensusConsts]:
        ability_census = self.__census_cache.get_ability_census_data_for_player(player, self.__gameclass, self.__canonical_ability_name)
        if not ability_census:
            return None
        ability_census_consts = AbilityCensusConsts()
        ability_census_consts.set_census_data(ability_census)
        return ability_census_consts

    def get_ext_object(self) -> AbilityExtConsts:
        ext_object = self.__ext_consts_reg.get_ability_ext_object(self.__gameclass, self.__ability_id)
        return ext_object

    def match_ability(self, ability: IAbility) -> bool:
        return ability.ext.ability_id == self.__ability_id and ability.ext.classname == self.__gameclass.name

    def __accept(self, ability: IAbility, extra_filter_cb: Optional[Callable[[IAbility], bool]] = None) -> bool:
        matched = self.match_ability(ability)
        if not matched:
            return False
        if extra_filter_cb is not None:
            return extra_filter_cb(ability)
        return True

    def resolve(self, filter_cb: Callable[[IAbility], bool] = None) -> List[IAbility]:
        if not self.__cached_abilities:
            self.__cached_abilities = self.__ability_reg.find_abilities(self.__accept)
        return list(filter(filter_cb, self.__cached_abilities))

    def resolve_for_player(self, player: IPlayer) -> Optional[IAbility]:
        matching_abilities = self.resolve(AbilityFilter().only_caster(player))
        return matching_abilities[0] if matching_abilities else None

    def resolve_for_player_default_all(self, player: TOptionalPlayer = None) -> List[IAbility]:
        matching_abilities = self.resolve(AbilityFilter().only_caster_or_all(player))
        return matching_abilities

    def resolve_for_main_player(self) -> Optional[IAbility]:
        matching_abilities = self.resolve(AbilityFilter().caster_is_main_player())
        return matching_abilities[0] if matching_abilities else None

    def boost_resolved(self, priority: AbilityPriority, priority_adjust: Optional[int] = None) -> List[IAbility]:
        return [ability.prototype(priority=priority, priority_adjust=priority_adjust) for ability in self.resolve()]


class AbilityLocatorFactory:
    __ability_reg: Optional[IAbilityRegistry] = None
    __census_cache: Optional[ICensusBridge] = None
    __ext_consts_reg: Optional[AbilityExtConstsRegistry] = None

    @staticmethod
    def initialize(ability_reg: IAbilityRegistry, census_cache: ICensusBridge, ext_consts_reg: AbilityExtConstsRegistry):
        AbilityLocatorFactory.__ability_reg = ability_reg
        AbilityLocatorFactory.__census_cache = census_cache
        AbilityLocatorFactory.__ext_consts_reg = ext_consts_reg

    @staticmethod
    def create(game_class: GameClass, ability_id: str, canonical_ability_name: str, ability_shared_name: str) -> IAbilityLocator:
        assert AbilityLocatorFactory.__ability_reg
        assert AbilityLocatorFactory.__census_cache
        assert AbilityLocatorFactory.__ext_consts_reg
        return AbilityLocator(AbilityLocatorFactory.__ability_reg, AbilityLocatorFactory.__census_cache, AbilityLocatorFactory.__ext_consts_reg,
                              game_class, ability_id, canonical_ability_name, ability_shared_name)
