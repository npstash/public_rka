from __future__ import annotations

from typing import Callable, Union, Set, Tuple, Optional

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem
from rka.eq2.master.game.effect import EffectType, EffectScopeType
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.interfaces import IEffect, IEffectsManager, TEffectValue, EffectTarget, EffectScope
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.shared.shared_workers import shared_scheduler

TEffectFn = Callable[[EffectType, EffectTarget, EffectTarget, TEffectValue, TEffectValue], Tuple[TEffectValue, bool]]


class Effect(IEffect):
    def __init__(self, effect_mgr: IEffectsManager, effect_name: str, effect_types: Union[EffectType, Set[EffectType]],
                 effect_scope: EffectScope, sustain_target: Optional[EffectTarget], sustain_source: EffectTarget,
                 duration: float, effect_cb: TEffectFn):
        if isinstance(effect_types, EffectType):
            effect_types = {effect_types}
        assert isinstance(effect_types, Set)
        self.__effect_mgr = effect_mgr
        self.__effect_types = effect_types
        self.__effect_name = effect_name
        self.__effect_scope = effect_scope
        self.__sustain_target = sustain_target
        self.__sustain_source = sustain_source
        self.__duration = duration
        self.__effect_cb = effect_cb
        self.__cancel_effect_future: Optional[RKAFuture] = None
        self.__is_active = False
        self.__cached_str = f'{self.__effect_name}[{",".join((et.name for et in self.__effect_types))}] on {self.__sustain_target} from {self.__sustain_source}'

    def __str__(self):
        return self.__cached_str

    def effect_key(self) -> str:
        return f'{self}-{id(self)}'

    def effect_name(self) -> str:
        return self.__effect_name

    def effect_scope(self) -> EffectScope:
        return self.__effect_scope

    def effect_types(self) -> Set[EffectType]:
        return self.__effect_types

    def sustain_target(self) -> Optional[EffectTarget]:
        return self.__sustain_target

    def sustain_source(self) -> EffectTarget:
        return self.__sustain_source

    def start_effect(self):
        self.cancel_effect()
        if self.__duration > 0.0:
            self.__cancel_effect_future = shared_scheduler.schedule(action=lambda: self.cancel_effect(), delay=self.__duration)
        self.__is_active = True
        self.__effect_mgr.add_effect(self)
        for effect_type in self.__effect_types:
            EventSystem.get_main_bus().post(ObjectStateEvents.EFFECT_STARTED(effect=self, effect_type=effect_type, effect_scope_type=self.__effect_scope.scope_type()))

    def cancel_effect(self):
        if not self.__is_active:
            return
        if self.__cancel_effect_future is not None:
            self.__cancel_effect_future.cancel_future()
            self.__cancel_effect_future = None
        self.__effect_mgr.remove_effect(self)
        self.__is_active = False
        for effect_type in self.__effect_types:
            EventSystem.get_main_bus().post(ObjectStateEvents.EFFECT_CANCELLED(effect=self, effect_type=effect_type,
                                                                               effect_scope_type=self.__effect_scope.scope_type()))

    def applies_to(self, apply_target: EffectTarget) -> bool:
        assert apply_target, self
        # test if ability is modified *directly*
        effect_scope_type = self.__effect_scope.scope_type()
        if effect_scope_type != EffectScopeType.ABILITY and apply_target.ability() is not None and apply_target.ability().ext.cannot_modify:
            return False
        if effect_scope_type == EffectScopeType.ABILITY:
            assert apply_target.ability() is not None, self
            assert self.__effect_scope.ability_locator() is not None, self
            return self.__effect_scope.ability_locator() == apply_target.ability().locator
        elif effect_scope_type == EffectScopeType.PLAYER:
            assert apply_target.player() is not None, self
            return apply_target.player() is self.__sustain_target.player()
        elif effect_scope_type == EffectScopeType.GROUP:
            assert apply_target.player() is not None, self
            apply_player_zoned = apply_target.player().get_status() >= PlayerStatus.Zoned
            if self.__sustain_source.npc_name():
                return apply_player_zoned
            caster = self.__sustain_source.player()
            both_zoned = apply_player_zoned and caster.get_status() >= PlayerStatus.Zoned
            same_group = apply_target.player().is_in_group_with(caster)
            return both_zoned and same_group
        elif effect_scope_type == EffectScopeType.RAID:
            assert apply_target.player() is not None, self
            caster = self.__sustain_source.player()
            both_zoned = apply_target.player().get_status() >= PlayerStatus.Zoned and caster.get_status() >= PlayerStatus.Zoned
            return both_zoned
        elif effect_scope_type == EffectScopeType.NON_PLAYER:
            assert apply_target.player() is None, self
            assert apply_target.npc_name() is not None, self
            return self.__sustain_target is None or self.__sustain_target.npc_name() == apply_target.npc_name()
        assert False, self

    def apply_effect(self, effect_type: EffectType, apply_target: EffectTarget,
                     base_value: TEffectValue, current_value: TEffectValue) -> Tuple[TEffectValue, bool]:
        return self.__effect_cb(effect_type, self.__sustain_source, apply_target, base_value, current_value)
