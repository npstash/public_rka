from __future__ import annotations

import time
from threading import RLock
from typing import Dict, List, Optional, Iterable, Tuple, Callable, Union

from rka.components.events.event_system import EventSystem, CloseableSubscriber
from rka.eq2.configs.shared.rka_constants import ABILITY_GRANT_DELAY
from rka.eq2.master.game.effect import EffectType, logger, EffectScopeType
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.interfaces import IEffect, IEffectsManager, IPlayer, IAbilityLocator, TEffectValue, EffectTarget
from rka.eq2.master.game.player import PlayerStatus


class SpecialEffectsHandler(CloseableSubscriber):
    def __init__(self):
        bus = EventSystem.get_main_bus()
        CloseableSubscriber.__init__(self, bus)
        self.subscribe(ObjectStateEvents.EFFECT_STARTED(effect_type=EffectType.RESET_ABILITY), self.__reset_ability)
        self.subscribe(ObjectStateEvents.EFFECT_STARTED(effect_type=EffectType.GRANT_ABILITY), self.__grant_ability)
        self.subscribe(ObjectStateEvents.EFFECT_CANCELLED(effect_type=EffectType.GRANT_ABILITY), self.__grant_ability)

    # noinspection PyMethodMayBeStatic
    def __reset_ability(self, event: ObjectStateEvents.EFFECT_STARTED):
        ability_causing_reset = event.effect.sustain_source().ability()
        player_having_reset = ability_causing_reset.player
        ability_descr_to_reset, _ = event.effect.apply_effect(effect_type=EffectType.RESET_ABILITY,
                                                              apply_target=EffectTarget(ability=ability_causing_reset),
                                                              base_value=0.0,
                                                              current_value=0.0)
        assert isinstance(ability_descr_to_reset, IAbilityLocator)
        ability_to_reset = ability_descr_to_reset.resolve_for_player(player_having_reset)
        if ability_to_reset:
            ability_to_reset.reset_reuse()

    # noinspection PyMethodMayBeStatic
    def __grant_ability(self, event: Union[ObjectStateEvents.EFFECT_STARTED, ObjectStateEvents.EFFECT_CANCELLED]):
        ability_causing_grant = event.effect.sustain_source().ability()
        player_having_grant = event.effect.sustain_target().player()
        ability_descr_to_grant, _ = event.effect.apply_effect(effect_type=EffectType.GRANT_ABILITY,
                                                              apply_target=EffectTarget(ability=ability_causing_grant),
                                                              base_value=0.0,
                                                              current_value=0.0)
        assert isinstance(ability_descr_to_grant, IAbilityLocator)
        ability_to_grant = ability_descr_to_grant.resolve_for_player(player_having_grant)
        if ability_to_grant:
            grant = isinstance(event, ObjectStateEvents.EFFECT_STARTED)
            if grant:
                ability_to_grant.shared.enabled_at = time.time() + ABILITY_GRANT_DELAY
            else:
                ability_to_grant.shared.enabled_at = None


class EffectsManager(IEffectsManager):
    def __init__(self):
        self.__lock = RLock()
        # {effect_type: {effect_key: effect}}
        self.__group_effects: Dict[str, Dict[str, IEffect]] = dict()
        self.__raid_effects: Dict[str, Dict[str, IEffect]] = dict()
        # {effect_type: {effect_key: {target_key: effect}}}
        self.__target_effects: Dict[str, Dict[str, Dict[str, IEffect]]] = dict()
        # {effect_type: {effect_key: {target_key: {ability_key: effect}}}}
        self.__ability_effects: Dict[str, Dict[str, Dict[str, Dict[str, IEffect]]]] = dict()
        for effect_type in EffectType:
            self.__group_effects[effect_type.name] = dict()
            self.__raid_effects[effect_type.name] = dict()
            self.__target_effects[effect_type.name] = dict()
            self.__ability_effects[effect_type.name] = dict()
        self.__setup_event_listenters()
        self.__special_effects = SpecialEffectsHandler()
        self.__empty_dict = dict()

    def __setup_event_listenters(self):
        bus = EventSystem.get_main_bus()
        bus.subscribe(CombatEvents.PLAYER_DIED(), self.__player_died)
        bus.subscribe(CombatEvents.PLAYER_REVIVED(), self.__player_revived)

    # noinspection PyMethodMayBeStatic
    def __stop_effects_by_scope(self, effect: IEffect, player: IPlayer, scope: EffectScopeType) -> bool:
        if effect.sustain_source() is not player:
            return False
        return effect.effect_scope().scope_type() == scope

    def __player_died(self, event: CombatEvents.PLAYER_DIED):
        self.cancel_effects(lambda effect: self.__stop_effects_by_scope(effect, event.player, EffectScopeType.RAID))
        self.cancel_effects(lambda effect: self.__stop_effects_by_scope(effect, event.player, EffectScopeType.GROUP))

    # noinspection PyMethodMayBeStatic
    def __player_revived(self, event: CombatEvents.PLAYER_REVIVED):
        if event.player.get_status() >= PlayerStatus.Zoned:
            event.player.effects.start_effects_by_scope(EffectScopeType.RAID)
            event.player.effects.start_effects_by_scope(EffectScopeType.GROUP)

    def __get_effects(self, effect_type_key: str, effect_scope_type: EffectScopeType, write_keys: bool,
                      target_key: Optional[str] = None, ability_key: Optional[str] = None) -> Dict[str, IEffect]:
        if effect_scope_type == EffectScopeType.GROUP:
            return self.__group_effects[effect_type_key]
        elif effect_scope_type == EffectScopeType.RAID:
            return self.__raid_effects[effect_type_key]
        elif effect_scope_type == EffectScopeType.PLAYER or effect_scope_type == EffectScopeType.NON_PLAYER:
            assert target_key, effect_type_key
            if target_key not in self.__target_effects[effect_type_key].keys():
                if write_keys:
                    self.__target_effects[effect_type_key][target_key] = dict()
                else:
                    return self.__empty_dict
            return self.__target_effects[effect_type_key][target_key]
        elif effect_scope_type == EffectScopeType.ABILITY:
            assert target_key, effect_type_key
            if target_key not in self.__ability_effects[effect_type_key].keys():
                if write_keys:
                    self.__ability_effects[effect_type_key][target_key] = dict()
                else:
                    return self.__empty_dict
            assert ability_key, effect_type_key
            if ability_key not in self.__ability_effects[effect_type_key][target_key].keys():
                if write_keys:
                    self.__ability_effects[effect_type_key][target_key][ability_key] = dict()
                else:
                    return self.__empty_dict
            return self.__ability_effects[effect_type_key][target_key][ability_key]
        assert False, effect_scope_type

    def add_effect(self, effect: IEffect):
        effect_key = effect.effect_key()
        with self.__lock:
            for effect_type in effect.effect_types():
                effect_type_key = effect_type.name
                target_key = effect.sustain_target().key() if effect.sustain_target() else None
                scope_key = effect.effect_scope().key()
                effects = self.__get_effects(effect_type_key=effect_type_key,
                                             effect_scope_type=effect.effect_scope().scope_type(),
                                             write_keys=True,
                                             target_key=target_key,
                                             ability_key=scope_key)
                if effect_key in effects.keys():
                    effects[effect_key].cancel_effect()
                effects[effect_key] = effect
        logger.info(f'add_effect: {effect}')

    def remove_effect(self, effect: IEffect):
        effect_key = effect.effect_key()
        removed = False
        with self.__lock:
            for effect_type in effect.effect_types():
                effect_type_key = effect_type.name
                target_key = effect.sustain_target().key() if effect.sustain_target() else None
                scope_key = effect.effect_scope().key()
                effects = self.__get_effects(effect_type_key=effect_type_key,
                                             effect_scope_type=effect.effect_scope().scope_type(),
                                             write_keys=True,
                                             target_key=target_key,
                                             ability_key=scope_key)
                if effect_key in effects.keys():
                    del effects[effect_key]
                    removed = True
        if removed:
            logger.debug(f'remove_effect: removed effect {effect.effect_key()}')

    def cancel_effects(self, effect_filter: Callable[[IEffect], bool]):
        with self.__lock:
            effect_to_cancel: List[IEffect] = list()
            for effect_type in EffectType:
                effect_type_key = effect_type.name
                for effect_key, effect in self.__raid_effects[effect_type_key].items():
                    if effect_filter(effect):
                        effect_to_cancel.append(effect)
                for effect_key, effect in self.__group_effects[effect_type_key].items():
                    if effect_filter(effect):
                        effect_to_cancel.append(effect)
                for target_key, effects in self.__target_effects[effect_type_key].items():
                    for effect_key, effect in effects.items():
                        if effect_filter(effect):
                            effect_to_cancel.append(effect)
                for target_key, abilities in self.__ability_effects[effect_type_key].items():
                    for ability_key, effects in abilities.items():
                        for effect_key, effect in effects.items():
                            if effect_filter(effect):
                                effect_to_cancel.append(effect)
            for effect in effect_to_cancel:
                effect.cancel_effect()
            logger.debug(f'remove_effects: removed {len(effect_to_cancel)}')

    # noinspection PyMethodMayBeStatic
    def __apply_effects(self, effect_type: EffectType, apply_target: EffectTarget, effects: Iterable[IEffect],
                        base_value: TEffectValue, current_value: TEffectValue) -> Tuple[TEffectValue, bool]:
        result_value = current_value
        for effect in effects:
            if effect.applies_to(apply_target):
                new_result_value, final = effect.apply_effect(effect_type, apply_target, base_value, result_value)
                if new_result_value != result_value:
                    logger.detail(f'applied: {effect.effect_name()}, target {apply_target}, base/result {base_value}/{new_result_value}, final {final}')
                    result_value = new_result_value
                if final:
                    return result_value, True
        return result_value, False

    def __iter_effect_groups(self, effect_type: EffectType, apply_target: EffectTarget) -> Iterable[Iterable[IEffect]]:
        effect_type_key = effect_type.name
        target_key = apply_target.key()
        with self.__lock:
            # NPC target
            if apply_target.scope().scope_type() == EffectScopeType.NON_PLAYER:
                npc_effects = self.__get_effects(effect_type_key=effect_type_key,
                                                 effect_scope_type=EffectScopeType.NON_PLAYER,
                                                 write_keys=True,
                                                 target_key=apply_target.npc_name())
                yield npc_effects.values()
                return
            # target is Player or Ability
            ability = apply_target.ability()
            cannot_modify_except_directly = ability and ability.ext.cannot_modify
            if not cannot_modify_except_directly:
                # Raid & Group effects
                raid_effects = self.__get_effects(effect_type_key=effect_type_key,
                                                  effect_scope_type=EffectScopeType.RAID,
                                                  write_keys=False)
                yield raid_effects.values()
                group_effects = self.__get_effects(effect_type_key=effect_type_key,
                                                   effect_scope_type=EffectScopeType.GROUP,
                                                   write_keys=False)
                yield group_effects.values()
                # Player target
                player_effects = self.__get_effects(effect_type_key=effect_type_key,
                                                    effect_scope_type=EffectScopeType.PLAYER,
                                                    write_keys=False,
                                                    target_key=target_key)
                yield player_effects.values()
            if ability:
                # Ability target
                scope_key = apply_target.scope().key()
                ability_effects = self.__get_effects(effect_type_key=effect_type_key,
                                                     effect_scope_type=EffectScopeType.ABILITY,
                                                     write_keys=False,
                                                     target_key=target_key,
                                                     ability_key=scope_key)
                yield ability_effects.values()
        return

    def get_effects(self, apply_target: EffectTarget, effect_type: Optional[EffectType] = None) -> List[IEffect]:
        effect_types = [effect_type] if effect_type else list(EffectType)
        all_effects = list()
        for effect_type in effect_types:
            for effects in self.__iter_effect_groups(effect_type, apply_target):
                all_effects.extend(effects)
        return list(dict.fromkeys(all_effects))

    def apply_effects(self, effect_type: EffectType, apply_target: EffectTarget, base_value: TEffectValue) -> TEffectValue:
        result_value = base_value
        final = False
        for effects in self.__iter_effect_groups(effect_type, apply_target):
            if effects:
                result_value, final = self.__apply_effects(effect_type, apply_target, effects, base_value, result_value)
            if final:
                break
        return result_value
