from __future__ import annotations

import enum
from typing import Callable, List, Tuple, Union, Optional

from rka.eq2.master.game.effect import EffectType, EffectScopeType
from rka.eq2.master.game.effect.effect import Effect
from rka.eq2.master.game.interfaces import IAbilityLocator, IEffect, IEffectsManager, IEffectBuilder, TEffectValue, TEffectModifier, EffectTarget, \
    EffectScope


class EffectModType(enum.IntEnum):
    ADD = 1
    MULTIPLY = 2
    SET = 3


class EffectMod:
    def __init__(self, mod_type: EffectModType, mod_value: TEffectModifier):
        self.__mod_type = mod_type
        self.__mod_value = mod_value
        self.__value_is_fn = isinstance(mod_value, Callable)

    def __get_value(self, source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> TEffectValue:
        if self.__value_is_fn:
            return self.__mod_value(source, target, base_value)
        return self.__mod_value

    def modify(self, source: EffectTarget, target: EffectTarget, base_value: TEffectValue, current_value: TEffectValue) -> Tuple[TEffectValue, bool]:
        mod_value = self.__get_value(source, target, base_value)
        if mod_value is None:
            return current_value, False
        if self.__mod_type == EffectModType.ADD:
            return current_value + mod_value, False
        elif self.__mod_type == EffectModType.MULTIPLY:
            return current_value + base_value * mod_value, False
        elif self.__mod_type == EffectModType.SET:
            return mod_value, True
        assert False


class EffectBuilder(IEffectBuilder):
    def __init__(self, effect_scope: Union[EffectScopeType, IAbilityLocator]):
        self.__effect_name: Optional[str] = None
        if isinstance(effect_scope, IAbilityLocator):
            self.__effect_scope = EffectScope(EffectScopeType.ABILITY, specifier=effect_scope)
        else:
            self.__effect_scope = EffectScope(effect_scope, specifier=None)
        self.__effect_mods: List[Tuple[EffectType, EffectMod]] = list()

    def __str__(self) -> str:
        return self.__effect_name

    def get_effect_name(self) -> str:
        return self.__effect_name

    def set_effect_name(self, effect_name: str) -> EffectBuilder:
        self.__effect_name = effect_name
        return self

    # noinspection PyMethodMayBeStatic
    def __apply_limits(self, effect_type: EffectType, base_value: TEffectValue, current_value: TEffectValue) -> TEffectValue:
        if effect_type == EffectType.DURATION:
            if base_value > 0.0:
                # exclude case when effect is actually setting a value that is absent in ability, but given as spell effect (see: tag team)
                current_value = min(current_value, base_value * 2.0)
        elif effect_type == EffectType.CASTING_SPEED or effect_type == EffectType.REUSE_SPEED or effect_type == EffectType.RECOVERY_SPEED:
            current_value = min(max(current_value, -50.0), 100.0)
        elif effect_type == EffectType.BASE_CASTING or effect_type == EffectType.BASE_REUSE:
            current_value = max(current_value, 0.0)
        return current_value

    def __apply_mods_fn(self, effect_type: EffectType, source: EffectTarget, target: EffectTarget,
                        base_value: TEffectValue, current_value: TEffectValue) -> Tuple[TEffectValue, bool]:
        if base_value < 0.0:
            return base_value, True
        for i_effect_type, modifier in self.__effect_mods:
            if i_effect_type != effect_type:
                continue
            current_value, final = modifier.modify(source, target, base_value, current_value)
            if final:
                return current_value, final
        return self.__apply_limits(effect_type, base_value, current_value), False

    def mul(self, effect_type: EffectType, value: TEffectModifier) -> EffectBuilder:
        self.__effect_mods.append((effect_type, EffectMod(EffectModType.MULTIPLY, value)))
        return self

    def add(self, effect_type: EffectType, value: TEffectModifier) -> EffectBuilder:
        self.__effect_mods.append((effect_type, EffectMod(EffectModType.ADD, value)))
        return self

    def set(self, effect_type: EffectType, value: TEffectModifier) -> EffectBuilder:
        self.__effect_mods.append((effect_type, EffectMod(EffectModType.SET, value)))
        return self

    def build_effect(self, effect_mgr: IEffectsManager, sustain_target: Optional[EffectTarget], sustain_source: EffectTarget, duration=-1.0) -> IEffect:
        assert self.__effect_name
        assert self.__effect_mods
        assert sustain_source
        effect_types = {effect_mod[0] for effect_mod in self.__effect_mods}
        effect = Effect(effect_mgr=effect_mgr, effect_name=self.__effect_name,
                        effect_types=effect_types, effect_scope=self.__effect_scope,
                        sustain_target=sustain_target, sustain_source=sustain_source, effect_cb=self.__apply_mods_fn, duration=duration)
        return effect
