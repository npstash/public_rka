import copy
from typing import Optional

from rka.eq2.master.game.ability.ability_data import AbilityCensusConsts, AbilitySharedVars, AbilityExtConsts
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IEffectsManager, IPlayer, IAbilityRegistry, IAbilityFactory


class AbilityFactory(IAbilityFactory):
    def __init__(self, effects_mgr: IEffectsManager, ability_reg: IAbilityRegistry):
        self.__effects_mgr = effects_mgr
        self.__ability_reg = ability_reg

    def create_ability(self, locator: IAbilityLocator, player: IPlayer,
                       census_consts: AbilityCensusConsts, ext_consts: Optional[AbilityExtConsts] = None) -> IAbility:
        shared_vars = self.__ability_reg.get_ability_shared_vars(player.get_player_id(), locator.get_shared_name())
        if not ext_consts:
            # make a copy to allow modifications for different players
            ext_consts = copy.copy(locator.get_ext_object())
        from rka.eq2.master.game.ability.ability import Ability
        ability = Ability(locator=locator, player=player, effects_mgr=self.__effects_mgr,
                          shared_vars=shared_vars, ext_consts=ext_consts, census_consts=census_consts)
        return ability


class CustomAbilityFactory(IAbilityFactory):
    def __init__(self, effects_mgr: IEffectsManager):
        self.__effects_mgr = effects_mgr

    def create_ability(self, locator: IAbilityLocator, player: IPlayer,
                       census_consts: AbilityCensusConsts, ext_consts: Optional[AbilityExtConsts] = None) -> IAbility:
        shared_vars = AbilitySharedVars()
        if not ext_consts:
            # make a copy to allow modifications without affecting original
            ext_consts = copy.copy(locator.get_ext_object())
        from rka.eq2.master.game.ability.ability import Ability
        ability = Ability(locator=locator, player=player, effects_mgr=self.__effects_mgr,
                          shared_vars=shared_vars, ext_consts=ext_consts, census_consts=census_consts)
        return ability
