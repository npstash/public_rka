from __future__ import annotations

import datetime
from typing import Optional, Iterable, Union, List

from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import HOIcon, AbilityPriority, logger, AbilityEffectTarget, AbilityType, AbilitySpecial, PRIORITY_ADJUSTMENT_MARGIN
from rka.eq2.master.game.gameclass import GameClasses, GameClass
from rka.eq2.master.game.interfaces import IAbility, TAbilityFilter, IPlayer, TValidTarget, TOptionalPlayer, IAbilityLocator
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.shared import Groups, ClientFlags


class AbilityFilter(TAbilityFilter):
    @staticmethod
    def _exclude_one_or_none(player: TOptionalPlayer, ability: IAbility) -> bool:
        if not player:
            return True
        if isinstance(player, IPlayer):
            return player != ability.player
        elif isinstance(player, str):
            return player != ability.player.get_player_name()
        assert False, player

    @staticmethod
    def _exclude_one_or_all(player: TOptionalPlayer, ability: IAbility) -> bool:
        if not player:
            return False
        if isinstance(player, IPlayer):
            return player != ability.player
        elif isinstance(player, str):
            return player != ability.player.get_player_name()
        assert False, player

    @staticmethod
    def _allow_one_or_all(player: TOptionalPlayer, ability: IAbility) -> bool:
        if not player:
            return True
        if isinstance(player, IPlayer):
            return player == ability.player
        elif isinstance(player, str):
            return player == ability.player.get_player_name()
        assert False, player

    @staticmethod
    def _allow_one_or_none(player: TOptionalPlayer, ability: IAbility) -> bool:
        if not player:
            return False
        if isinstance(player, IPlayer):
            return player == ability.player
        elif isinstance(player, str):
            return player == ability.player.get_player_name()
        assert False, player

    def __init__(self, filter_cb: Optional[TAbilityFilter] = None):
        self._filter_cb = filter_cb

    def _add_filter(self, filter_cb: TAbilityFilter) -> AbilityFilter:
        if self._filter_cb is None:
            self._filter_cb = filter_cb
            return self
        maf = MultipleAbilityFilter(self._filter_cb)
        maf.op_and(filter_cb)
        return maf

    def __call__(self, ability: IAbility) -> bool:
        if self._filter_cb:
            return self._filter_cb(ability)
        return True

    def accept_ability(self, ability: IAbility) -> bool:
        if self._filter_cb:
            return self._filter_cb(ability)
        return True

    def apply(self, abilities: Iterable[IAbility]) -> List[IAbility]:
        return list(filter(self.accept_ability, abilities))

    def print_debug(self, ability: IAbility):
        for flt in self._filters:
            accepted = flt(ability)
            logger.debug(f'testing {ability}, filter: {flt}, result {accepted}')

    # ==================================== Generic Filter builders ====================================
    def op_nand(self, nand_filter: TAbilityFilter) -> AbilityFilter:
        return self._add_filter(lambda ability: not nand_filter(ability))

    def op_and(self, and_filter: TAbilityFilter) -> AbilityFilter:
        return self._add_filter(and_filter)

    def op_or(self, or_filter: TAbilityFilter) -> AbilityFilter:
        and_af = AbilityFilter(or_filter)
        or_af = AbilityFilter(lambda ability: self(ability) or and_af(ability))
        return or_af

    def op_and_all(self, and_filters: Iterable[TAbilityFilter]) -> AbilityFilter:
        af = self
        for flt in and_filters:
            af = af._add_filter(flt)
        return af

    # ==================================== Specialized Filter builders ====================================
    def by_all_client_flags(self, flags: ClientFlags) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_client_flags() & flags == flags)

    def by_some_client_flags(self, flags: ClientFlags) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_client_flags() & flags != 0)

    def local_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_local())

    def remote_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_remote())

    def hidden_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_hidden())

    def automated_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_automated())

    def online_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_status() >= PlayerStatus.Online)

    def zoned_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_status() >= PlayerStatus.Zoned)

    def alive_casters(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_alive())

    def caster_is(self, player: IPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player == player)

    def caster_is_one_of(self, players: List[IPlayer]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player in players)

    def caster_is_main_player(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_main_player())

    def casters_by_class(self, game_class: GameClass) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_class(game_class))

    def casters_by_group(self, group_id: Groups) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_client_config_data().group_id.is_same_group(group_id))

    def remote_casters_by_group(self, group_id: Groups) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_remote() and ability.player.get_client_config_data().group_id.is_same_group(group_id))

    def automated_casters_by_group(self, group_id: Groups) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_automated() and ability.player.get_client_config_data().group_id.is_same_group(group_id))

    def local_allowed_for_HO(self) -> AbilityFilter:
        from rka.eq2.master.game.ability.generated_abilities import MonkAbilities, FighterAbilities
        allowed = [
            # sword
            MonkAbilities.waking_dragon,
            MonkAbilities.striking_cobra,
            # boot
            MonkAbilities.rising_phoenix,
            MonkAbilities.mountain_stance,
            MonkAbilities.body_like_mountain,
            # horn
            MonkAbilities.challenge,
            MonkAbilities.silent_threat,
            # arm
            MonkAbilities.lightning_palm,
            MonkAbilities.mend,
            MonkAbilities.arctic_talon,
            # fist
            MonkAbilities.charging_tiger,
            MonkAbilities.five_rings,
            MonkAbilities.frozen_palm,
            MonkAbilities.silent_palm,
            # starter
            FighterAbilities.fighting_chance,
        ]
        return self._add_filter(lambda ability: ability.locator in allowed if ability.player.is_local() and ability.player.is_class(GameClasses.Monk) else True)

    def only_caster(self, player: IPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player is player)

    def only_caster_or_all(self, player: TOptionalPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: AbilityFilter._allow_one_or_all(player, ability))

    def except_caster_or_none(self, player: TOptionalPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: AbilityFilter._exclude_one_or_all(player, ability))

    def is_sustained_by(self, sustainer: Optional[IPlayer], target: Optional[IPlayer]) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            sustainer_match = ability.is_sustained_by(sustainer) if sustainer else False
            target_match = ability.is_sustained_for(target) if target else False
            return sustainer_match or target_match

        return self._add_filter(condition)

    def is_sustained_to_group(self, player: IPlayer) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            is_sustainer = ability.is_sustained_by(player)
            is_target = ability.is_sustained_for(player)
            if is_sustainer and is_target:
                return False
            if not is_sustainer and not is_target:
                return False
            # accept abilities sustained by the player to other player, or vice versa
            return True

        return self._add_filter(condition)

    def heroic_op(self, icon_heroic_op: HOIcon) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.icon_heroic_op == icon_heroic_op)

    def not_heroic_op(self, icon_heroic_op: HOIcon) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.icon_heroic_op != icon_heroic_op)

    def casting_or_in_duration(self, now: Optional[datetime.datetime] = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_casting(now) or not ability.is_duration_expired(now))

    def in_duration(self, now: Optional[datetime.datetime] = None) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.is_duration_expired(now))

    def reusable(self, now: Optional[datetime.datetime] = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_reusable(now))

    def expired(self, now: Optional[datetime.datetime] = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_duration_expired(now))

    def maintained(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.maintained)

    def not_maintained(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.maintained)

    def persistent_passive_buffs(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.is_dispelable_maintained_buff())

    def resets_on_zone_change(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.expire_on_zone)

    def resets_on_death(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.expire_on_death)

    def is_deathsave(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.deathsave)

    def can_override(self, test_ability: IAbility) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_overriding(test_ability))

    def ability_type(self, ability_type: AbilityType) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.type == ability_type)

    def ability_special(self, control_effect=AbilitySpecial.Control) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.has_special_effect(control_effect))

    def non_move(self, player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.move or AbilityFilter._exclude_one_or_all(player, ability))

    def non_combat(self, except_player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.beneficial or AbilityFilter._exclude_one_or_all(except_player, ability))

    def non_hostile_ca(self, except_player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.type != AbilityType.arts or ability.census.beneficial
                                                or AbilityFilter._allow_one_or_none(except_player, ability))

    def non_hostile_aoe(self, except_player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.effect_target != AbilityEffectTarget.AOE
                                                or AbilityFilter._allow_one_or_none(except_player, ability))

    def non_combat_for(self, players: List[IPlayer]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.beneficial or ability.player not in players)

    def non_combat_except(self, players: List[IPlayer]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.beneficial or ability.player in players)

    def no_ascensions_for(self, players: List[IPlayer]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.type != AbilityType.ascension or ability.player not in players)

    def no_ascensions_except(self, players: List[IPlayer]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.census.type != AbilityType.ascension or ability.player in players)

    def no_group_cures(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.cure
                                                or ability.ext.effect_target == AbilityEffectTarget.Ally
                                                or ability.ext.effect_target == AbilityEffectTarget.GroupMember)

    def no_automatic_cures(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.cure or ability.ext.is_essential())

    def no_priest_cures(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.cure or not ability.player.is_class(GameClasses.Priest))

    def dont_cure_player(self, target_name: str) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            if not ability.ext.cure:
                return True
            return not ability.can_affect_target(target_name)

        return self._add_filter(condition)

    def no_automatic_dispels(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.dispel or ability.ext.is_essential())

    def only_mage_dispels(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.is_class(GameClasses.Mage) or not ability.ext.dispel)

    def dont_cast_abilities(self, abilities: List[IAbilityLocator]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.locator not in abilities)

    def only_allow_abilities(self, abilities: List[IAbilityLocator]) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.locator in abilities)

    def dont_powerfeed(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.ext.power or ability.get_priority() >= AbilityPriority.MANUAL_REQUEST)

    def dont_powerfeed_player(self, target_name: str) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            if not ability.ext.power:
                return True
            return not ability.can_affect_target(target_name)

        return self._add_filter(condition)

    def no_priest_beneficials(self) -> AbilityFilter:
        return self._add_filter(lambda ability: not ability.census.beneficial or not ability.ext.has_census or not ability.player.is_class(GameClasses.Priest))

    def no_beneficials(self, player: IPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player != player or not ability.ext.has_census or not ability.census.beneficial)

    def by_min_priority(self, priority: Union[AbilityPriority, int], player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.get_priority() >= priority - PRIORITY_ADJUSTMENT_MARGIN or AbilityFilter._exclude_one_or_all(player, ability))

    def by_max_priority(self, priority: Union[AbilityPriority, int], player: TOptionalPlayer = None) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.get_priority() <= priority + PRIORITY_ADJUSTMENT_MARGIN or AbilityFilter._exclude_one_or_all(player, ability))

    def permitted_caster_zone(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.player.get_status() >= ability.ext.cast_min_state)

    def permitted_caster_state(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_permitted_in_caster_state())

    def permitted_target_state(self) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.is_permitted_in_target_state())

    def can_affect_target_player(self, player: IPlayer) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.can_affect_target(player))

    def can_affect_main_player(self) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            if ability.player.get_client_config_data().group_id.is_main_group():
                return True
            return ability.ext.effect_target in [AbilityEffectTarget.Ally, AbilityEffectTarget.Any, AbilityEffectTarget.Raid]

        return self._add_filter(condition)

    def can_affect_ally_target(self, runtime: IRuntime, target: TValidTarget) -> AbilityFilter:
        def condition(ability: IAbility) -> bool:
            target_player = runtime.player_mgr.resolve_player(target)
            if target_player and target_player.get_zone() != ability.player.get_zone():
                return False
            if ability.ext.effect_target in (AbilityEffectTarget.Ally, AbilityEffectTarget.Any, AbilityEffectTarget.Raid):
                return True
            if ability.ext.effect_target not in (AbilityEffectTarget.GroupMember, AbilityEffectTarget.Group):
                return False
            if not target_player:
                # other player
                return True
            return ability.player.is_in_group_with(target_player)

        return self._add_filter(condition)

    def target_type(self, target_type: AbilityEffectTarget) -> AbilityFilter:
        return self._add_filter(lambda ability: ability.ext.effect_target == target_type)


class MultipleAbilityFilter(AbilityFilter):
    def __init__(self, filter_cb: Optional[TAbilityFilter] = None):
        AbilityFilter.__init__(self, None)
        self._filters = list()
        if filter_cb:
            self._filters.append(filter_cb)

    # Override
    def _add_filter(self, filter_cb: TAbilityFilter) -> AbilityFilter:
        self._filters.append(filter_cb)
        return self

    # Override
    def __call__(self, ability: IAbility) -> bool:
        for flt in self._filters:
            if not flt(ability):
                return False
        return True

    # Override
    def accept_ability(self, ability: IAbility) -> bool:
        for flt in self._filters:
            if not flt(ability):
                return False
        return True
