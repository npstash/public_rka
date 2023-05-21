from __future__ import annotations

import copy
import datetime
import time
import weakref
from typing import Union, List, Optional, Callable

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogLevel, LogService
from rka.eq2.configs.shared.rka_constants import ABILITY_RECOVERY_SAFETY, ABILITY_REUSE_SAFETY, ABILITY_CASTING_SAFETY
from rka.eq2.master.control import IAction
from rka.eq2.master.game.ability import AbilityEffectTarget, AbilityPriority, logger
from rka.eq2.master.game.ability.ability_data import AbilityExtConsts, AbilityCensusConsts, AbilitySharedVars
from rka.eq2.master.game.effect import EffectType
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.interfaces import IAbilityMonitor, IAbility, IAbilityLocator, IEffectsManager, IPlayer, IEffectBuilder, TValidPlayer, \
    TOptionalTarget, TValidTarget, AbilityTarget, EffectTarget, IRunningAbilityMonitor, IAbilityMonitorConfigurator
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.log_configs import LOG_ABILITY_CASTING

NO_DELAY = datetime.timedelta(seconds=0)

casting_logger = LogService(LOG_ABILITY_CASTING)


class Ability(IAbility):
    @staticmethod
    def get_dt(when: Union[datetime.datetime, float, None] = None) -> datetime.datetime:
        if when is None:
            return datetime.datetime.now()
        elif isinstance(when, float):
            return datetime.datetime.fromtimestamp(when)
        assert isinstance(when, datetime.datetime)
        return when

    @staticmethod
    def get_ts(when: Union[datetime.datetime, float, None] = None) -> float:
        if when is None:
            return time.time()
        elif isinstance(when, datetime.datetime):
            return when.timestamp()
        assert isinstance(when, float)
        return when

    def __init__(self, locator: IAbilityLocator, player: IPlayer, effects_mgr: IEffectsManager,
                 shared_vars: AbilitySharedVars, ext_consts: AbilityExtConsts, census_consts: AbilityCensusConsts):
        IAbility.__init__(self)
        self.locator = locator
        self.player = player
        self.shared = shared_vars
        self.ext = ext_consts
        self.census = census_consts
        self.__default_target = AbilityTarget(self.player, self.player.get_player_manager())
        self.__target: Optional[AbilityTarget] = None
        if self.ext.effect_target == AbilityEffectTarget.Self:
            self.__target = self.__default_target
        self.__action: Optional[IAction] = None
        self.__alternative_action: Optional[IAction] = None
        self.__use_alternative_action = False
        self.__last_action_withdraw = time.time()
        self.__effects_mgr = effects_mgr
        self.__effect_builder: Optional[IEffectBuilder] = None
        self.__effect_source = EffectTarget(ability=self)
        self.__prototype: Optional[Ability] = None  # parent ability, which is registered in AbilityRegistry
        self.__clones: List[Callable[[], Ability]] = list()  # weak references
        self.__monitors: List[IAbilityMonitor] = []
        self.__running_monitors: List[IRunningAbilityMonitor] = []
        self.__monitoring_running = False
        self.__last_cast_time_for_target: Optional[datetime.datetime] = None
        self.__expired_time_for_target: Optional[datetime.datetime] = None
        self.__effect_start_future: Optional[RKAFuture] = None
        self.__target_key: Optional[str] = None
        self.__shared_key: Optional[str] = None
        self.__unique_key: Optional[str] = None
        self.__display_id: Optional[str] = None

    def __str__(self) -> str:
        return self.ability_variant_display_name()

    def __get_target_str(self) -> Optional[str]:
        if not self.__target:
            return None
        return self.__target.get_target_name()

    def ability_variant_display_name(self) -> str:
        if not self.__display_id:
            if not self.__target:
                target_name = None
            elif self.__target.get_target_name() == self.player.get_player_name():
                target_name = None
            else:
                target_name = self.__target.get_target_name()
            self.__display_id = IAbility.make_ability_variant_key(self.player.get_player_name(), self.ext.ability_id, target_name)
        return self.__display_id

    def ability_shared_key(self) -> str:
        if not self.__shared_key:
            self.__shared_key = IAbility.make_ability_shared_key(self.player.get_player_id(), self.ext.shared_name)
        return self.__shared_key

    def ability_unique_key(self) -> str:
        if not self.__unique_key:
            self.__unique_key = IAbility.make_ability_unique_key(self.player.get_player_id(), self.ext.ability_id)
        return self.__unique_key

    def ability_variant_key(self) -> str:
        if not self.__target_key:
            target_name = self.__target.get_target_name() if self.__target else None
            self.__target_key = IAbility.make_ability_variant_key(self.player.get_player_id(), self.ext.ability_id, target_name)
        return self.__target_key

    def __create_clone(self) -> Ability:
        clone = Ability(locator=self.locator, player=self.player, effects_mgr=self.__effects_mgr,
                        shared_vars=self.shared, ext_consts=self.ext, census_consts=self.census)
        clone.set_action(self.__action)
        clone.set_alternative_action(self.__action)
        clone.set_effect_builder(self.__effect_builder)
        # monitors are not set into clones - its not necessary
        if self.__target:
            clone.__target = self.__target
        # flat prototype hierarchy
        prototype = self.__prototype if self.__prototype else self
        clone.__prototype = prototype
        prototype.__clones.append(weakref.ref(clone))
        return clone

    def __get_clones(self) -> List[Ability]:
        clone_refs_to_remove = list()
        clones = list()
        for clone_ref in self.__clones:
            clone = clone_ref()
            if clone:
                clones.append(clone)
            else:
                clone_refs_to_remove.append(clone_ref)
        for clone_ref in clone_refs_to_remove:
            self.__clones.remove(clone_ref)
        return clones

    def prototype(self, action: Optional[IAction] = None, target: TOptionalTarget = None,
                  priority: Optional[AbilityPriority] = None, priority_adjust: Optional[int] = None) -> IAbility:
        new_ability = self.__create_clone()
        if priority is not None or priority_adjust is not None:
            new_ability.ext = copy.copy(self.ext)
        if action is not None:
            new_ability.__action = new_ability.__alternative_action = action
        if target is not None:
            new_ability.set_target(target)
            if action is None:
                new_ability.__action = new_ability.__alternative_action = self.__action.prototype(target=new_ability.get_target().get_target_name())
        if priority is not None:
            new_ability.ext.priority = priority
        if priority_adjust is not None:
            new_ability.ext.priority_adjust = priority_adjust
        if self.__monitoring_running:
            new_ability.__start_clone_ability_monitoring(self.__running_monitors)
        return new_ability

    def debug_str(self) -> str:
        duration = self.__calc_effective_duration()
        casting = self.__calc_effective_casting(0.0) - ABILITY_CASTING_SAFETY
        recovery = self.__calc_effective_recovery() - ABILITY_RECOVERY_SAFETY
        reuse = self.__calc_effective_reuse() - ABILITY_REUSE_SAFETY
        duration_str = f'{duration:.3f}'.rstrip('0')
        if duration_str[-1] == '.':
            duration_str += '0'
        casting_str = f'{casting:.3f}'.rstrip('0')
        if casting_str[-1] == '.':
            casting_str += '0'
        recovery_str = f'{recovery:.3f}'.rstrip('0')
        if recovery_str[-1] == '.':
            recovery_str += '0'
        reuse_str = f'{reuse:.3f}'.rstrip('0')
        if reuse_str[-1] == '.':
            reuse_str += '0'
        timers_str = f'dur={duration_str}, cas={casting_str}, rec={recovery_str}, reu={reuse_str}'
        target = f'target={self.__get_target_str()}'
        line = f'{self.player}, {self.ext.classname}, {self.ext.ability_id}, {target}, {self.census.type}, {timers_str}, tier={self.census.tier_int}'
        return line

    def get_action(self) -> IAction:
        use_alternative = self.__use_alternative_action if self.__prototype is None else self.__prototype.__use_alternative_action
        return self.__alternative_action if use_alternative else self.__action

    def set_action(self, action: IAction) -> IAbility:
        if self.__action is not None:
            logger.warn(f'Redefining action for {self} from {self.__action} to {action}')
        assert action is not None
        self.__action = action
        return self

    def set_alternative_action(self, action: IAction) -> IAbility:
        self.__alternative_action = action
        return self

    def use_alternative_action(self, use: bool):
        self.__use_alternative_action = use

    def set_effect_builder(self, effect_builder: IEffectBuilder) -> IAbility:
        self.__effect_builder = effect_builder
        return self

    def set_monitors(self, monitors: List[IAbilityMonitor]) -> IAbility:
        assert not self.__monitors
        self.__monitors = monitors
        return self

    def set_target(self, target: TValidTarget) -> IAbility:
        self.__target = AbilityTarget(target, self.player.get_player_manager())
        # reset debug str, it uses target value
        assert self.__target_key is None, f'Target key already set, before target {target}'
        self.__display_id = None
        return self

    def get_target(self) -> Optional[AbilityTarget]:
        return self.__target

    def get_priority(self) -> int:
        base_priority = self.ext.priority + self.ext.priority_adjust
        priority = self.__effects_mgr.apply_effects(effect_type=EffectType.PRIORITY, apply_target=self.__effect_source, base_value=base_priority)
        return priority

    def __calc_effective_casting_with_base(self, base_casting: float, casting_overhead: float) -> float:
        casting = self.__effects_mgr.apply_effects(effect_type=EffectType.BASE_CASTING, apply_target=self.__effect_source, base_value=base_casting)
        if not self.ext.cannot_modify:
            casting_speed = self.__effects_mgr.apply_effects(effect_type=EffectType.CASTING_SPEED, apply_target=self.__effect_source, base_value=0.0)
            casting /= 1 + casting_speed / 100.0
        return casting + casting_overhead + ABILITY_CASTING_SAFETY

    def __calc_effective_reuse_with_base(self, base_reuse: float) -> float:
        reuse = self.__effects_mgr.apply_effects(effect_type=EffectType.BASE_REUSE, apply_target=self.__effect_source, base_value=base_reuse)
        if not self.ext.cannot_modify:
            reuse_speed = self.__effects_mgr.apply_effects(effect_type=EffectType.REUSE_SPEED, apply_target=self.__effect_source, base_value=0.0)
            reuse /= 1 + reuse_speed / 100.0
        return reuse + ABILITY_REUSE_SAFETY

    def __calc_effective_recovery_with_base(self, base_recovery: float) -> float:
        recovery = base_recovery
        if not self.ext.cannot_modify:
            recovery_speed = self.__effects_mgr.apply_effects(effect_type=EffectType.RECOVERY_SPEED, apply_target=self.__effect_source, base_value=0.0)
            recovery /= 1 + recovery_speed / 100.0
        return recovery + ABILITY_RECOVERY_SAFETY

    def __calc_effective_casting(self, casting_overhead: float) -> float:
        return self.__calc_effective_casting_with_base(self.census.casting, casting_overhead)

    def __calc_effective_reuse(self) -> float:
        return self.__calc_effective_reuse_with_base(self.census.reuse)

    def __calc_effective_recovery(self) -> float:
        return self.__calc_effective_recovery_with_base(self.census.recovery)

    def __calc_effective_duration(self) -> float:
        duration = self.__effects_mgr.apply_effects(effect_type=EffectType.DURATION, apply_target=self.__effect_source, base_value=self.census.duration)
        return duration

    def __set_casting_timers(self, now: datetime.datetime, casting_overhead: float):
        now = Ability.get_dt(now)
        self.__set_last_cast_time(now)
        self.__set_expired_time(None)
        self.shared.last_target_name = self.__get_target_str()
        self.shared.last_effective_casting = self.__calc_effective_casting(casting_overhead)
        self.shared.last_effective_reuse = self.__calc_effective_reuse()
        self.shared.last_effective_recovery = self.__calc_effective_recovery()
        self.shared.last_effective_duration = self.__calc_effective_duration()

    def __get_casting_td(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.get_casting_secs())

    def __get_recovery_td(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.get_recovery_secs())

    def __get_casting_with_recovery_td(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.get_casting_with_recovery_secs())

    def __get_reuse_td_from_cast(self) -> datetime.timedelta:
        assert self.__has_been_cast()
        reuse_td = datetime.timedelta(seconds=self.get_reuse_secs())
        if self.ext.maintained:
            if self.shared.last_expired_time is None:
                duration_td = self.__get_duration_td()
            else:
                duration_td = self.shared.last_expired_time - self.shared.last_cast_time
            return reuse_td + self.__get_casting_td() + duration_td
        else:
            return reuse_td + self.__get_casting_td()

    def __get_duration_td(self) -> datetime.timedelta:
        if not self.__has_been_cast():
            return datetime.timedelta(seconds=self.__calc_effective_duration())
        return datetime.timedelta(seconds=self.shared.last_effective_duration)

    def __has_been_cast(self) -> bool:
        return self.shared.last_cast_time is not None

    def __set_last_cast_time(self, last_cast_time: datetime.datetime):
        self.shared.previous_last_cast_time = self.shared.last_cast_time
        self.__last_cast_time_for_target = last_cast_time
        self.shared.last_cast_time = last_cast_time

    def __revert_last_cast_time(self):
        self.__last_cast_time_for_target = self.shared.previous_last_cast_time
        self.shared.last_cast_time = self.shared.previous_last_cast_time

    def __get_last_cast_time_for_target(self) -> Optional[datetime.datetime]:
        if self.shared.last_target_name == self.__get_target_str():
            return self.shared.last_cast_time
        return self.__last_cast_time_for_target

    def __set_expired_time(self, expired_time: Optional[datetime.datetime]):
        self.__expired_time_for_target = expired_time
        self.shared.last_expired_time = expired_time

    def __get_expired_time_for_target(self) -> Optional[datetime.datetime]:
        if self.shared.last_target_name == self.__get_target_str():
            return self.shared.last_expired_time
        return self.__expired_time_for_target

    def __is_being_maintained(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.ext.maintained:
            return False
        return not self.__is_maintained_duration_expired(now)

    def __has_duration_running_since(self, cast_time: datetime.datetime, now: Optional[datetime.datetime] = None) -> bool:
        if self.is_permanent():
            return True
        casting_ends_at = cast_time + self.__get_casting_td()
        still_running = cast_time <= Ability.get_dt(now) < casting_ends_at + self.__get_duration_td()
        return still_running

    def __is_maintained_duration_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        assert self.ext.maintained
        last_cast = self.shared.last_cast_time
        if not last_cast:
            return True
        if self.shared.last_expired_time:
            return True
        if self.is_permanent():
            return False
        return not self.__has_duration_running_since(last_cast, now)

    def get_casting_secs(self) -> float:
        if not self.__has_been_cast():
            return self.__calc_effective_casting(0.0)
        return self.shared.last_effective_casting

    def get_recovery_secs(self) -> float:
        if not self.__has_been_cast():
            return self.__calc_effective_recovery()
        return self.shared.last_effective_recovery

    def get_casting_with_recovery_secs(self) -> float:
        if not self.__has_been_cast():
            return self.__calc_effective_casting(0.0) + self.__calc_effective_recovery()
        return self.shared.last_effective_casting + self.shared.last_effective_recovery

    def get_reuse_secs(self) -> float:
        if not self.__has_been_cast():
            return self.__calc_effective_reuse()
        return self.shared.last_effective_reuse

    def get_duration_secs(self) -> float:
        duration_td = self.__get_duration_td()
        return duration_td.total_seconds()

    def get_remaining_reuse_wait_td(self, now: Optional[datetime.datetime] = None) -> datetime.timedelta:
        if self.is_reuse_expired(now):
            return NO_DELAY
        assert self.__has_been_cast()
        now = Ability.get_dt(now)
        recast_possible_at = self.shared.last_cast_time + self.__get_reuse_td_from_cast()
        return recast_possible_at - now

    def get_remaining_duration_sec(self, now: Optional[datetime.datetime] = None) -> float:
        if not self.__has_been_cast():
            return -1.0
        if not self.__get_last_cast_time_for_target():
            return -1.0
        if self.is_permanent():
            return -1.0
        now = Ability.get_dt(now)
        casting_ends_at = self.__get_last_cast_time_for_target() + self.__get_casting_td()
        duration_ends_at = casting_ends_at + self.__get_duration_td()
        remaining_duration_td = duration_ends_at - now
        return remaining_duration_td.total_seconds()

    def is_casting(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return False
        now = Ability.get_dt(now)
        return now <= self.shared.last_cast_time + self.__get_casting_td()

    def is_recovering(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return False
        now = Ability.get_dt(now)
        casting_end = self.shared.last_cast_time + self.__get_casting_td()
        recovery_end = casting_end + self.__get_recovery_td()
        return casting_end < now <= recovery_end

    def is_after_recovery(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return True
        now = Ability.get_dt(now)
        return now > self.shared.last_cast_time + self.__get_casting_with_recovery_td()

    def is_reuse_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return True
        now = Ability.get_dt(now)
        recast_possible_at = self.shared.last_cast_time + self.__get_reuse_td_from_cast()
        return now > recast_possible_at

    def is_reusable(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return True
        now = Ability.get_dt(now)
        if self.ext.cast_when_reusing:
            return self.is_after_recovery(now)
        return self.is_reuse_expired(now)

    def is_permanent(self) -> bool:
        return self.census.duration < 0 or self.census.does_not_expire

    def is_duration_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        if not self.__has_been_cast():
            return True
        last_cast = self.__get_last_cast_time_for_target()
        if not last_cast:
            return True
        if self.__get_expired_time_for_target():
            return True
        if self.is_permanent():
            return False
        return not self.__has_duration_running_since(last_cast, now)

    def can_affect_target(self, target: TValidTarget) -> bool:
        check_target = AbilityTarget(target, self.player.get_player_manager())
        return check_target.can_be_affected_by(self)

    def is_sustained_for(self, target: TValidTarget) -> bool:
        if self.is_duration_expired():
            return False
        if not target:
            logger.warn(f'is_sustained_for: incorrect target {target}, self={self}')
            return False
        if not self.__target:
            # no target - comparing to ability owner
            return AbilityTarget.match_targets(self.player, target)
        return self.__target.match_target(target)

    def is_sustained_by(self, player: TValidPlayer) -> bool:
        assert player, f'is_sustained_by: {self}, checked player is {player}'
        if self.is_duration_expired():
            return False
        return AbilityTarget.match_targets(self.player, player)

    def is_reusable_and_duration_expired(self, now: Optional[datetime.datetime] = None) -> bool:
        now = Ability.get_dt(now)
        return self.is_reusable(now) and self.is_duration_expired(now)

    def is_permitted_in_caster_state(self) -> bool:
        if self.player.get_status() <= PlayerStatus.Offline:
            return False
        if self.player.is_alive():
            return self.ext.cast_when_alive
        # not alive
        if not self.ext.resurrect:
            return self.ext.cast_when_dead
        return self.ext.cast_when_dead and MutableFlags.AUTO_SELF_REZ

    def is_permitted_in_target_state(self) -> bool:
        if not self.__target:
            return True
        target_player = self.__target.get_target_player()
        if not target_player:
            # assuming its another player or NPC
            return True
        if not target_player.is_online():
            return False
        if not target_player.is_alive():
            return self.ext.resurrect
        if target_player.get_zone() != self.player.get_zone():
            return False
        return True

    def is_overriding(self, test_ability: IAbility) -> bool:
        # can always override a None ability
        if test_ability is None:
            return True
        assert self.player is test_ability.player
        # can always override if the player is not casting
        if not self.player.is_busy():
            return True
        # still can cast any ability than can be cast anytime, as long as they dont interrupt
        if not self.ext.cancel_spellcast and self.ext.cast_when_casting:
            return True
        # can cast higher priority if it interrupts
        if self.ext.cancel_spellcast and self.get_priority() > test_ability.get_priority():
            return True
        return False

    def interrupted(self):
        if not self.__has_been_cast():
            return
        now = datetime.datetime.now()
        # only apply the interrupt if the ability has been cast below a threshold (prevent race condition)
        reduced_casting_ts = self.__get_casting_td() * 0.8
        if now <= self.shared.last_cast_time + reduced_casting_ts:
            self.__cancel_ability_effect_start()
            self.__revert_last_cast_time()

    def reset_reuse(self):
        if self.__is_being_maintained():
            logger.info(f'cannot reset reuse {self.ext.ability_name}, is being maintained')
            return
        logger.info(f'reset reuse {self.ext.ability_name}')
        self.shared.last_effective_reuse = 0.0

    def __cancel_ability_effect_start(self):
        effect_future = self.__effect_start_future
        if effect_future:
            self.__effect_start_future = None
            if not effect_future.cancel_future():
                self.__stop_ability_effect()

    def __start_ability_effect(self):
        if self.__effect_builder:
            effect_target = self.__target.get_effect_target() if self.__target else self.__default_target.get_effect_target()
            self.__cancel_ability_effect_start()
            effect = self.__effect_builder.build_effect(self.__effects_mgr, sustain_target=effect_target, sustain_source=self.__effect_source,
                                                        duration=self.get_duration_secs())
            casting = self.get_casting_secs()
            if casting > 0.0:
                self.__effect_start_future = shared_scheduler.schedule(lambda: effect.start_effect(), delay=casting)
            else:
                effect.start_effect()

    def __stop_ability_effect(self):
        self.__effects_mgr.cancel_effects(lambda effect: effect.sustain_source().ability() is self)

    def expire_duration(self, when: Union[datetime.datetime, float, None] = None):
        when = Ability.get_dt(when)
        if self.is_duration_expired(when):
            return
        casting_logger.info(f'expired {self.ext.ability_name} at {when}')
        self.__set_expired_time(when)
        EventSystem.get_main_bus().post(ObjectStateEvents.ABILITY_EXPIRED(ability=self,
                                                                          ability_name=self.locator.get_canonical_name(),
                                                                          ability_shared_key=self.ability_shared_key(),
                                                                          ability_unique_key=self.ability_unique_key(),
                                                                          ability_variant_key=self.ability_variant_key()))
        self.__stop_ability_effect()

    def __log_casting(self, casting_overhead: float):
        debug_str = ''
        if casting_logger.get_level() <= LogLevel.INFO:
            debug_str += f'*** Casting {self.ability_variant_display_name()}'
        if casting_logger.get_level() <= LogLevel.DEBUG:
            debug_str += f', priority: {self.get_priority()}'
            debug_str += f', duration: {self.get_duration_secs():.2f}'
            debug_str += f', casting: {self.get_casting_secs():.2f} ovh:{casting_overhead:.2f}'
            debug_str += f', reuse: {self.get_reuse_secs():.2f}'
            debug_str += f', recovery: {self.get_recovery_secs():.2f}'
        if casting_logger.get_level() <= LogLevel.DETAIL:
            debug_str += f', action: {self.get_action()}'
        if debug_str:
            casting_logger.info(debug_str)

    def __log_confirm_casting(self):
        if casting_logger.get_level() <= LogLevel.INFO:
            debug_str = f'* Confirm casting {self.ability_variant_display_name()}'
            casting_logger.info(debug_str)

    def __casting_started(self, cancel_action: bool, casting_overhead: float, when: datetime.datetime, player_busy: bool):
        self.__set_casting_timers(when, casting_overhead)
        if not player_busy or self.ext.cancel_spellcast or not self.ext.cast_when_casting:
            self.player.set_last_cast_ability(self)
        self.__start_ability_effect()
        if cancel_action:
            if not self.withdraw_casting_action():
                logger.warn(f'ability action cancel failed: {self.get_action()}')

    def confirm_casting_started(self, cancel_action: bool, casting_overhead=0.0, when: Union[datetime.datetime, float, None] = None,
                                player_busy: Optional[bool] = None):
        casting_logger.detail(f'confirm_casting_started: {self} at {when}')
        when_ts = Ability.get_ts(when)
        last_cast_ts = self.shared.last_cast_time.timestamp() if self.shared.last_cast_time else 0.0
        since_last_confirm = when_ts - self.shared.last_confirm_time
        # handle two casting modes:
        # 1. by confirming (confirm and cast times were set)
        # 2. by invoking (casting time was set, but confirm time was not
        if since_last_confirm >= self.get_reuse_secs() or when_ts > last_cast_ts > self.shared.last_confirm_time:
            self.shared.last_confirm_time = when_ts
            self.__casting_started(cancel_action, casting_overhead, when, player_busy if player_busy is not None else self.player.is_busy())
            self.__log_confirm_casting()
            EventSystem.get_main_bus().post(ObjectStateEvents.ABILITY_CASTING_CONFIRMED(ability=self,
                                                                                        ability_name=self.locator.get_canonical_name(),
                                                                                        ability_shared_key=self.ability_shared_key(),
                                                                                        ability_unique_key=self.ability_unique_key(),
                                                                                        ability_variant_key=self.ability_variant_key()))

    def confirm_casting_completed(self, cancel_action: bool, when: Union[datetime.datetime, float, None]):
        when = Ability.get_dt(when)
        casting_logger.debug(f'confirm_casting_completed: {self} at {when}')
        when = when - self.__get_casting_td()
        self.confirm_casting_started(cancel_action=cancel_action, casting_overhead=0.0, when=when, player_busy=False)

    def withdraw_casting_action(self) -> bool:
        if self.shared.last_cast_time is None:
            logger.warn(f'nothing to withdraw, ability not cast: {self}')
            return False
        if not self.get_action().is_cancellable():
            logger.error(f'ability is not cancellable: {self}')
            return False
        now = time.time()
        if now - self.__last_action_withdraw < 1.0:
            # ignore rapid withdrawals (multiple events for example)
            return True
        self.__last_action_withdraw = now
        casting_logger.debug(f'withdraw ability casting action: {self.get_action()}')
        return self.get_action().post_async_cancel(self.player.get_client_id())

    def revoke_last_cast_if_not_confirmed(self, max_confirm_delay: float, now: Union[datetime.datetime, float, None] = None) -> bool:
        if not self.__has_been_cast():
            return False
        last_cast_ts = self.shared.last_cast_time.timestamp() if self.shared.last_cast_time else 0.0
        if self.shared.last_confirm_time >= last_cast_ts:
            return False
        now_ts = Ability.get_ts(now)
        if now_ts <= last_cast_ts + max_confirm_delay:
            return False
        self.__revert_last_cast_time()
        return True

    def cast(self) -> bool:
        now = datetime.datetime.now()
        reuse_expired = self.is_reuse_expired(now)
        if not self.ext.cast_when_reusing and not reuse_expired:
            recast_possible_at = self.shared.last_cast_time + self.__get_reuse_td_from_cast()
            tstr1 = f'cast_at:{self.shared.last_cast_time.time()}'
            tstr2 = f'casting:{self.shared.last_effective_casting}/{self.census.casting}'
            tstr3 = f'reuse:{self.shared.last_effective_reuse}/{self.census.reuse}/{recast_possible_at.time()}'
            tstr = f'now:{datetime.datetime.now().time()}, {tstr1}, {tstr2}, {tstr3}'
            logger.warn(f'casting ability too early {self}. {tstr}')
            return False
        busy = self.player.is_busy()
        if busy and not self.ext.cast_when_casting and not self.ext.cancel_spellcast:
            logger.warn(f'trying to cast when player is busy {self} {self.ext.cast_when_casting} {self.ext.cancel_spellcast} {busy}')
            return False
        if self.__is_being_maintained(now):
            if self.shared.last_target_name == self.__get_target_str():
                logger.warn(f'trying to dispel a maintained spell {self}, previously cast on the same target {self.__get_target_str()}')
                return False
        if busy and self.ext.cancel_spellcast:
            logger.debug(f'interrupting a spellcast in progress {self}')
            self.player.interrupted()
        client_id = self.player.get_client_id()
        sent = self.get_action().post_auto(client_id)
        if sent:
            casting_overhead = self.get_action().get_average_delay(client_id)
            self.__casting_started(cancel_action=False, casting_overhead=casting_overhead, when=now, player_busy=busy)
            self.__log_casting(casting_overhead)
        else:
            logger.warn(f'failed to cast spell {self}')
        return sent

    def __expire_ward_event(self, event: CombatParserEvents.WARD_EXPIRED):
        if not self.__target or self.is_sustained_for(event.target_name):
            logger.info(f'ward {self} expired on {event.target_name}')
            self.expire_duration(event.timestamp)

    def __start_ability_monitoring(self, configurator: IAbilityMonitorConfigurator):
        if self.__running_monitors:
            logger.warn(f'ability {self} running monitors not cleared')
            self.__running_monitors.clear()
        for monitor in self.__monitors:
            configurator.configure_monitor(self, monitor)
            running_monitor = monitor.start_monitoring(self)
            self.__running_monitors.append(running_monitor)
        if not self.is_duration_expired():
            self.__start_ability_effect()

    def __start_clone_ability_monitoring(self, prototype_running_monitors: List[IRunningAbilityMonitor]):
        if self.__running_monitors:
            logger.warn(f'ability clone {self} running monitors not cleared')
            self.__running_monitors.clear()
        for prototype_running_monitor in prototype_running_monitors:
            running_monitor = prototype_running_monitor.start_for_clone(self)
            self.__running_monitors.append(running_monitor)
        if not self.is_duration_expired():
            self.__start_ability_effect()

    def __stop_ability_monitoring(self):
        for running_monitor in self.__running_monitors:
            running_monitor.stop_monitoring()
        self.__running_monitors.clear()
        self.__stop_ability_effect()

    def start_ability_monitoring(self, configurator: IAbilityMonitorConfigurator):
        if self.__monitoring_running:
            logger.warn(f'ability {self} already monitoring')
            return
        self.__monitoring_running = True
        self.__start_ability_monitoring(configurator)
        for clone in self.__get_clones():
            clone.__start_clone_ability_monitoring(self.__running_monitors)

    def stop_ability_monitoring(self):
        if not self.__monitoring_running:
            logger.warn(f'ability {self} not monitoring')
            return
        self.__monitoring_running = False
        self.__stop_ability_monitoring()
        for clone in self.__get_clones():
            clone.__stop_ability_monitoring()
        self.__clones.clear()
