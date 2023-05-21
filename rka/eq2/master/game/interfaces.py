from __future__ import annotations

import datetime
from typing import Optional, List, Union, Callable, Set, Tuple, Dict, Iterable

from rka.eq2.master.control import IAction, IClientConfig, InputConfig, IHasClient
from rka.eq2.master.game.ability import AbilityPriority, AbilityTier, AbilityEffectTarget
from rka.eq2.master.game.ability.ability_data import AbilityExtConsts, AbilityCensusConsts, AbilitySharedVars
from rka.eq2.master.game.effect import EffectType, EffectScopeType
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.player import PlayerStatus, PlayerInfo, PlayerAspects
from rka.eq2.shared import GameServer, ClientFlags, ClientConfigData


class IRunningAbilityMonitor:
    def stop_monitoring(self):
        raise NotImplementedError()

    def start_for_clone(self, ability: IAbility) -> IRunningAbilityMonitor:
        raise NotImplementedError()


class IAbilityMonitor:
    def start_monitoring(self, ability: IAbility) -> IRunningAbilityMonitor:
        raise NotImplementedError()


class IAbilityMonitorConfigurator:
    def configure_monitor(self, ability: IAbility, ability_monitor: IAbilityMonitor):
        raise NotImplementedError()


class AbilityKey:
    SHARED = 0
    UNIQUE = 1
    VARIANT = 2

    def __init__(self, ability: IAbility, key_type: int):
        self.ability = ability
        self.__key = None
        if key_type == AbilityKey.VARIANT:
            self.__key = ability.ability_variant_key()
        elif key_type == AbilityKey.UNIQUE:
            self.__key = ability.ability_unique_key()
        elif key_type == AbilityKey.SHARED:
            self.__key = ability.ability_shared_key()
        else:
            assert False, key_type
        self.__hash = self.__key.__hash__()
        self.__str = '#' + str(ability)

    def __eq__(self, other) -> bool:
        assert isinstance(other, AbilityKey)
        return self.__key == other.__key

    def __hash__(self) -> int:
        return self.__hash

    def __str__(self) -> str:
        return self.__str


class AbilityVariantKey(AbilityKey):
    def __init__(self, ability: IAbility):
        AbilityKey.__init__(self, ability, AbilityKey.VARIANT)


class AbilitySharedKey(AbilityKey):
    def __init__(self, ability: IAbility):
        AbilityKey.__init__(self, ability, AbilityKey.SHARED)


class AbilityUniqueKey(AbilityKey):
    def __init__(self, ability: IAbility):
        AbilityKey.__init__(self, ability, AbilityKey.UNIQUE)


class IAbility:
    @staticmethod
    def make_ability_shared_key(player_id: str, ability_shared_name: str) -> str:
        return f'{player_id}.{ability_shared_name}'

    @staticmethod
    def make_ability_unique_key(player_id: str, ability_id: str) -> str:
        return f'{player_id}.{ability_id}'

    @staticmethod
    def make_ability_variant_key(player_id: str, ability_id: str, variant_name: Optional[str]) -> str:
        if variant_name:
            return f'{player_id}.{ability_id}->{variant_name}'
        return f'{player_id}.{ability_id}'

    def __init__(self):
        self.locator: Optional[IAbilityLocator] = None
        self.player: Optional[IPlayer] = None
        self.shared: Optional[AbilitySharedVars] = None
        self.ext: Optional[AbilityExtConsts] = None
        self.census: Optional[AbilityCensusConsts] = None

    def debug_str(self) -> str:
        raise NotImplementedError()

    def ability_variant_display_name(self) -> str:
        raise NotImplementedError()

    def ability_variant_key(self) -> str:
        raise NotImplementedError()

    def ability_shared_key(self) -> str:
        raise NotImplementedError()

    def ability_unique_key(self) -> str:
        raise NotImplementedError()

    def get_action(self) -> IAction:
        raise NotImplementedError()

    def set_action(self, action: IAction) -> IAbility:
        raise NotImplementedError()

    def set_alternative_action(self, action: IAction) -> IAbility:
        raise NotImplementedError()

    def use_alternative_action(self, use: bool):
        raise NotImplementedError()

    def set_effect_builder(self, effect_builder: IEffectBuilder) -> IAbility:
        raise NotImplementedError()

    def set_monitors(self, monitors: List[IAbilityMonitor]) -> IAbility:
        raise NotImplementedError()

    def set_target(self, target: TValidTarget) -> IAbility:
        raise NotImplementedError()

    def get_target(self) -> Optional[AbilityTarget]:
        raise NotImplementedError()

    def get_priority(self) -> int:
        raise NotImplementedError()

    def prototype(self, action: Optional[IAction] = None, target: TOptionalTarget = None,
                  priority: Optional[AbilityPriority] = None, priority_adjust: Optional[int] = None) -> IAbility:
        raise NotImplementedError()

    def get_casting_secs(self) -> float:
        raise NotImplementedError()

    def get_recovery_secs(self) -> float:
        raise NotImplementedError()

    def get_casting_with_recovery_secs(self) -> float:
        raise NotImplementedError()

    def get_reuse_secs(self) -> float:
        raise NotImplementedError()

    def get_duration_secs(self) -> float:
        raise NotImplementedError()

    def get_remaining_reuse_wait_td(self, now: Optional[datetime.datetime] = None) -> datetime.timedelta:
        raise NotImplementedError()

    def get_remaining_duration_sec(self, now: Optional[datetime.datetime] = None) -> float:
        raise NotImplementedError()

    def is_casting(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_recovering(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_after_recovery(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_reuse_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_reusable(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_permanent(self) -> bool:
        raise NotImplementedError()

    def is_duration_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def can_affect_target(self, target: TValidTarget) -> bool:
        raise NotImplementedError()

    def is_sustained_for(self, target: TValidTarget) -> bool:
        raise NotImplementedError()

    def is_sustained_by(self, player: TValidPlayer) -> bool:
        raise NotImplementedError()

    def is_reusable_and_duration_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        raise NotImplementedError()

    def is_permitted_in_caster_state(self) -> bool:
        raise NotImplementedError()

    def is_permitted_in_target_state(self) -> bool:
        raise NotImplementedError()

    def is_overriding(self, test_ability: IAbility) -> bool:
        raise NotImplementedError()

    def interrupted(self):
        raise NotImplementedError()

    def reset_reuse(self):
        raise NotImplementedError()

    def expire_duration(self, when: Union[datetime.datetime, float, None] = None):
        raise NotImplementedError()

    def confirm_casting_started(self, cancel_action: bool, casting_overhead=0.0, when: Union[datetime.datetime, float, None] = None,
                                player_busy: Optional[bool] = None):
        raise NotImplementedError()

    def confirm_casting_completed(self, cancel_action: bool, when: Union[datetime.datetime, float, None]):
        raise NotImplementedError()

    def withdraw_casting_action(self) -> bool:
        raise NotImplementedError()

    def revoke_last_cast_if_not_confirmed(self, max_confirm_delay: float, now: Union[datetime.datetime, float, None] = None) -> bool:
        raise NotImplementedError()

    def cast(self) -> bool:
        raise NotImplementedError()

    def start_ability_monitoring(self, configurator: IAbilityMonitorConfigurator):
        raise NotImplementedError()

    def stop_ability_monitoring(self):
        raise NotImplementedError()


class IAbilityLocator:
    def get_gameclass(self) -> GameClass:
        raise NotImplementedError()

    def get_ability_id(self) -> str:
        raise NotImplementedError()

    def get_canonical_name(self) -> str:
        raise NotImplementedError()

    def get_shared_name(self) -> str:
        raise NotImplementedError()

    def locator_key(self) -> str:
        raise NotImplementedError()

    def get_census_object_by_tier(self, player_level: int, ability_tier: AbilityTier) -> Optional[AbilityCensusConsts]:
        raise NotImplementedError()

    def get_census_object_for_player(self, player: IPlayer) -> Optional[AbilityCensusConsts]:
        raise NotImplementedError()

    def get_ext_object(self) -> AbilityExtConsts:
        raise NotImplementedError()

    def match_ability(self, ability: IAbility) -> bool:
        raise NotImplementedError()

    def resolve(self, filter_cb: Optional[TAbilityFilter] = None) -> List[IAbility]:
        raise NotImplementedError()

    def resolve_for_player(self, player: IPlayer) -> Optional[IAbility]:
        raise NotImplementedError()

    def resolve_for_player_default_all(self, player: TOptionalPlayer = None) -> List[IAbility]:
        raise NotImplementedError()

    def resolve_for_main_player(self) -> Optional[IAbility]:
        raise NotImplementedError()

    def boost_resolved(self, priority: AbilityPriority, priority_adjust: Optional[int] = None) -> List[IAbility]:
        raise NotImplementedError()


TAbilityFilter = Callable[[IAbility], bool]


class IAbilityFactory:
    def create_ability(self, locator: IAbilityLocator, player: IPlayer,
                       census_consts: AbilityCensusConsts, ext_consts: Optional[AbilityExtConsts] = None) -> IAbility:
        raise NotImplementedError()


class IAbilityRegistry:
    def register_ability(self, ability: IAbility):
        raise NotImplementedError()

    def find_abilities(self, condition: TAbilityFilter) -> List[IAbility]:
        raise NotImplementedError()

    def find_first_ability(self, condition: TAbilityFilter) -> Optional[IAbility]:
        raise NotImplementedError()

    def find_ability_map_for_player_name(self, player_name: str) -> Dict[str, IAbility]:
        raise NotImplementedError()

    def find_abilities_expire_on_attack(self, player: IPlayer) -> List[IAbility]:
        raise NotImplementedError()

    def find_abilities_expire_on_move(self, player: IPlayer) -> List[IAbility]:
        raise NotImplementedError()

    def get_all_ability_names(self) -> Set[str]:
        raise NotImplementedError()

    def get_ability_shared_vars(self, player_name: str, ability_shared_name: str):
        raise NotImplementedError()

    def get_ability_name_by_effect_name(self, effect_name_lower: str) -> Optional[str]:
        raise NotImplementedError()

    def get_ability_locator_by_name(self, ability_name_lower: str) -> Optional[IAbilityLocator]:
        raise NotImplementedError()


class AbilityRecord:
    def __init__(self, ability: IAbility):
        self.ability = ability
        self.properties = dict()

    def __str__(self):
        return f'{self.ability}, props={self.properties}'


class IAbilityRecordFilter:
    def accept_ability_record(self, ability_record: AbilityRecord) -> bool:
        raise NotImplementedError()

    def notify_casting_record(self, ability_record: AbilityRecord):
        raise NotImplementedError()


class IEffectBuilder:
    def get_effect_name(self) -> str:
        raise NotImplementedError()

    def build_effect(self, effect_mgr: IEffectsManager, sustain_target: Optional[EffectTarget], sustain_source: EffectTarget, duration=-1.0) -> IEffect:
        raise NotImplementedError()


class EffectTarget:
    def __init__(self, player: Optional[IPlayer] = None, npc_name: Optional[str] = None, ability: Optional[IAbility] = None):
        assert player or npc_name or ability
        self.__player = player
        self.__ability = ability
        self.__npc_name = npc_name
        self.__scope = EffectScope(EffectScopeType.PLAYER) if player else EffectScope(EffectScopeType.NON_PLAYER) if npc_name else EffectScope(
            EffectScopeType.ABILITY, specifier=ability.locator)
        self.__key = self.__npc_name if self.__scope.scope_type() == EffectScopeType.NON_PLAYER else self.player().get_player_name()

    def __str__(self) -> str:
        return self.__key

    def key(self) -> str:
        return self.__key

    def player(self) -> Optional[IPlayer]:
        return self.__ability.player if self.__ability else self.__player

    def ability(self) -> Optional[IAbility]:
        return self.__ability

    def npc_name(self) -> Optional[str]:
        return self.__npc_name

    def scope(self) -> EffectScope:
        return self.__scope


class EffectScope:
    def __init__(self, scope_type: EffectScopeType, specifier: Union[None, IAbilityLocator] = None):
        self.__scope_type = scope_type
        self.__specifier = specifier
        self.__key = scope_type.name
        if scope_type == EffectScopeType.ABILITY and isinstance(specifier, IAbilityLocator):
            self.__key += ':' + specifier.locator_key()
        else:
            assert specifier is None, specifier

    def scope_type(self) -> EffectScopeType:
        return self.__scope_type

    def ability_locator(self) -> Optional[IAbilityLocator]:
        return self.__specifier

    def key(self) -> str:
        return self.__key


class IEffect:
    def effect_key(self) -> str:
        raise NotImplementedError()

    def effect_name(self) -> str:
        raise NotImplementedError()

    def effect_scope(self) -> EffectScope:
        raise NotImplementedError()

    def effect_types(self) -> Set[EffectType]:
        raise NotImplementedError()

    def sustain_target(self) -> Optional[EffectTarget]:
        raise NotImplementedError()

    def sustain_source(self) -> EffectTarget:
        raise NotImplementedError()

    def start_effect(self):
        raise NotImplementedError()

    def cancel_effect(self):
        raise NotImplementedError()

    def applies_to(self, apply_target: EffectTarget) -> bool:
        raise NotImplementedError()

    def apply_effect(self, effect_type: EffectType, apply_target: EffectTarget,
                     base_value: TEffectValue, current_value: TEffectValue) -> Tuple[TEffectValue, bool]:
        raise NotImplementedError()


class EffectsBag:
    def __init__(self):
        self.__effects: List[IEffect] = list()

    def add_effect(self, effect: IEffect):
        self.__effects.append(effect)

    def start_effects(self):
        for effect in self.__effects:
            effect.start_effect()

    def start_effects_by_scope(self, scope_type: EffectScopeType):
        for effect in self.__effects:
            if effect.effect_scope().scope_type() == scope_type:
                effect.start_effect()

    def cancel_effects_by_scope(self, scope_type: EffectScopeType):
        for effect in self.__effects:
            if effect.effect_scope().scope_type() == scope_type:
                effect.cancel_effect()


class IEffectsManager:
    def add_effect(self, effect: IEffect):
        raise NotImplementedError()

    def remove_effect(self, effect: IEffect):
        raise NotImplementedError()

    def apply_effects(self, effect_type: EffectType, apply_target: EffectTarget, base_value: TEffectValue) -> TEffectValue:
        raise NotImplementedError()

    def get_effects(self, apply_target: EffectTarget, effect_type: Optional[EffectType] = None) -> List[IEffect]:
        raise NotImplementedError()

    def cancel_effects(self, effect_filter: Callable[[IEffect], bool]):
        raise NotImplementedError()


class AbilityTarget:
    @staticmethod
    def get_opt_target_name(target: TOptionalTarget) -> Optional[str]:
        return target.get_player_name() if isinstance(target, IPlayer) else target if isinstance(target, str) else None

    @staticmethod
    def match_targets(target: TValidTarget, other: TValidTarget) -> bool:
        assert is_valid_ability_target(target), target
        assert is_valid_ability_target(other), other
        if isinstance(target, str):
            if isinstance(other, str):
                return target == other
            return other.get_player_name() == target
        if isinstance(other, str):
            return target.get_player_name() == other
        return target == other

    def __init__(self, target: TValidTarget, player_mgr: IPlayerManager):
        assert is_valid_ability_target(target), target
        self.__target_player = target if isinstance(target, IPlayer) else player_mgr.resolve_player(target)
        self.__target_name = target.get_player_name() if isinstance(target, IPlayer) else target

    def __str__(self) -> str:
        return self.get_target_name()

    def get_target_name(self) -> str:
        return self.__target_name

    def get_target_player(self) -> Optional[IPlayer]:
        return self.__target_player

    def get_target(self) -> TValidTarget:
        return self.__target_player if self.__target_player else self.__target_name

    def get_effect_target(self) -> EffectTarget:
        if self.__target_player:
            return self.__target_player.as_effect_target()
        else:
            return EffectTarget(npc_name=self.__target_name)

    def match_target(self, other: TValidTarget) -> bool:
        return AbilityTarget.match_targets(self.__target_player if self.__target_player else self.__target_name, other)

    def can_be_affected_by(self, ability: IAbility) -> bool:
        if ability.ext.effect_target == AbilityEffectTarget.Self:
            assert self.__target_player, f'{ability} vs {self.__target_name}'
            return ability.player == self.__target_player
        if ability.ext.effect_target == AbilityEffectTarget.Raid:
            if self.__target_player:
                if self.__target_player.get_zone() != ability.player.get_zone():
                    return False
            return True
        if ability.ext.effect_target == AbilityEffectTarget.Group:
            if self.__target_player:
                if self.__target_player.get_zone() != ability.player.get_zone():
                    return False
                if not self.__target_player.is_in_group_with(ability.player):
                    return False
            return True
        if ability.ext.effect_target == AbilityEffectTarget.Ally:
            if self.__target_player:
                if self.__target_player.get_zone() != ability.player.get_zone():
                    return False
            return self.__target_name == ability.get_target().get_target_name()
        if ability.ext.effect_target == AbilityEffectTarget.GroupMember:
            if self.__target_player:
                if self.__target_player.get_zone() != ability.player.get_zone():
                    return False
                if not self.__target_player.is_in_group_with(ability.player):
                    return False
            return self.__target_name == ability.get_target().get_target_name()
        # Any / any other
        return self.__target_name == ability.get_target().get_target_name()


class IPlayerSelector:
    def resolve_players(self) -> List[IPlayer]:
        raise NotImplementedError()

    def resolve_first_player(self) -> Optional[IPlayer]:
        resolved = self.resolve_players()
        return resolved[0] if resolved else None

    def __iter__(self) -> Iterable[IPlayer]:
        return self.resolve_players().__iter__()


class IPlayer(IPlayerSelector, IHasClient):
    def __init__(self):
        self.effects = EffectsBag()
        self.aspects = PlayerAspects()
        self.__as_effect_target: Optional[EffectTarget] = None

    def as_effect_target(self) -> EffectTarget:
        if not self.__as_effect_target:
            self.__as_effect_target = EffectTarget(player=self)
        return self.__as_effect_target

    # from IPlayerSelector
    def resolve_players(self) -> List[IPlayer]:
        return [self]

    # from IHasClient
    def get_client_id(self) -> str:
        raise NotImplementedError()

    def get_host_id(self) -> Optional[int]:
        raise NotImplementedError()

    def get_client_config(self) -> IClientConfig:
        raise NotImplementedError()

    def get_client_config_data(self) -> ClientConfigData:
        raise NotImplementedError()

    def get_client_flags(self) -> ClientFlags:
        raise NotImplementedError()

    # convenience function
    def is_local(self) -> bool:
        return self.get_client_flags().is_local()

    # convenience function
    def is_remote(self) -> bool:
        return self.get_client_flags().is_remote()

    # convenience function
    def is_hidden(self) -> bool:
        return self.get_client_flags().is_hidden()

    # convenience function
    def is_automated(self) -> bool:
        return self.get_client_flags().is_automated()

    def get_player_manager(self) -> IPlayerManager:
        raise NotImplementedError()

    def get_server(self) -> GameServer:
        raise NotImplementedError()

    def get_inputs(self) -> InputConfig:
        raise NotImplementedError()

    def get_command_injector_name(self) -> str:
        raise NotImplementedError()

    def get_ability_injector_name(self) -> str:
        raise NotImplementedError()

    def get_player_name(self) -> str:
        raise NotImplementedError()

    def get_player_id(self) -> str:
        raise NotImplementedError()

    def get_player_info(self) -> PlayerInfo:
        raise NotImplementedError()

    def interrupted(self):
        raise NotImplementedError()

    def is_busy(self) -> bool:
        raise NotImplementedError()

    def is_busier_than(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def get_last_cast_ability(self) -> Optional[IAbility]:
        raise NotImplementedError()

    def set_last_cast_ability(self, ability: Optional[IAbility]):
        raise NotImplementedError()

    def is_class(self, game_class: GameClass) -> bool:
        raise NotImplementedError()

    def get_adventure_class(self) -> Optional[GameClass]:
        raise NotImplementedError()

    def get_crafter_class(self) -> Optional[GameClass]:
        raise NotImplementedError()

    def get_ascension_class(self) -> Optional[GameClass]:
        raise NotImplementedError()

    def get_level(self, game_class: GameClass) -> Optional[int]:
        raise NotImplementedError()

    def is_main_player(self) -> bool:
        raise NotImplementedError()

    def is_alive(self) -> bool:
        raise NotImplementedError()

    def set_alive(self, alive: bool):
        raise NotImplementedError()

    def get_status(self) -> PlayerStatus:
        raise NotImplementedError()

    def set_status(self, status: PlayerStatus):
        raise NotImplementedError()

    # convenience function
    def is_offline(self) -> bool:
        return self.get_status() <= PlayerStatus.Offline

    # convenience function
    def is_online(self) -> bool:
        return self.get_status() >= PlayerStatus.Online

    # convenience function
    def is_logged(self) -> bool:
        return self.get_status() >= PlayerStatus.Logged

    # convenience function
    def is_zoned(self) -> bool:
        return self.get_status() >= PlayerStatus.Zoned

    def get_zone(self) -> str:
        raise NotImplementedError()

    def set_zone(self, zone: str):
        raise NotImplementedError()

    def is_in_group_with(self, player: IPlayer) -> bool:
        raise NotImplementedError()


TValidPlayer = Union[IPlayer, str]
TOptionalPlayer = Union[TValidPlayer, None]
TValidTarget = Union[IPlayer, str]
TOptionalTarget = Union[TValidTarget, None]
TAbilityBuildTarget = Union[TOptionalTarget, GameClass, List[Union[GameClass, TValidTarget]]]

TEffectValue = Union[float, bool]
TEffectModFn = Callable[[EffectTarget, EffectTarget, TEffectValue], Optional[TEffectValue]]
TEffectModifier = Union[float, bool, TEffectModFn, IAbilityLocator]


def is_valid_ability_target(obj) -> bool:
    return isinstance(obj, IPlayer) or isinstance(obj, str)


def is_ability_build_target(obj) -> bool:
    if isinstance(obj, IPlayer) or isinstance(obj, str) or isinstance(obj, GameClass) or obj is None:
        return True
    if isinstance(obj, list):
        for subobj in obj:
            if is_ability_build_target(subobj):
                return True
    return False


DEFAULT_MIN_STATUS = PlayerStatus.Online
DEFAULT_MAX_STATUS = PlayerStatus.Zoned
DEFAULT_AND_FLAGS = ClientFlags.none
DEFAULT_OR_FLAGS = ClientFlags.Remote | ClientFlags.Local
DEFAULT_NOR_FLAGS = ClientFlags.none


class IPlayerManager:
    def get_player_by_client_id(self, client_id) -> Optional[IPlayer]:
        raise NotImplementedError()

    def get_player_by_name(self, player_name: str) -> Optional[IPlayer]:
        raise NotImplementedError()

    def get_online_player_by_overlay_id(self, status_overlay_id: int) -> Optional[IPlayer]:
        raise NotImplementedError()

    def find_first_player(self, fn: Callable[[IPlayer], bool]) -> Optional[IPlayer]:
        raise NotImplementedError()

    def find_best_player(self, fn: Callable[[IPlayer], int]) -> Optional[IPlayer]:
        raise NotImplementedError()

    def find_players(self, fn: Optional[Callable[[IPlayer], bool]] = None) -> List[IPlayer]:
        raise NotImplementedError()

    def get_players(self, and_flags=DEFAULT_AND_FLAGS, or_flags=DEFAULT_OR_FLAGS, nor_flags=DEFAULT_NOR_FLAGS,
                    min_status=DEFAULT_MIN_STATUS, max_status=DEFAULT_MAX_STATUS) -> List[IPlayer]:
        raise NotImplementedError()

    def get_player_names(self, and_flags=DEFAULT_AND_FLAGS, or_flags=DEFAULT_OR_FLAGS, nor_flags=DEFAULT_NOR_FLAGS,
                         min_status=DEFAULT_MIN_STATUS, max_status=DEFAULT_MAX_STATUS) -> List[str]:
        players = self.get_players(and_flags=and_flags, or_flags=or_flags, nor_flags=nor_flags, min_status=min_status, max_status=max_status)
        return [p.get_player_name() for p in players]

    def resolve_player(self, player: TOptionalPlayer, min_status=DEFAULT_MIN_STATUS, max_status=DEFAULT_MAX_STATUS) -> Optional[IPlayer]:
        raise NotImplementedError()

    def resolve_targets(self, target: TAbilityBuildTarget, player_filter: Callable[[IPlayer], bool] = None) -> List[TValidTarget]:
        raise NotImplementedError()

    def create_dummy_player(self, player_name: str) -> IPlayer:
        raise NotImplementedError()
