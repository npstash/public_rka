from __future__ import annotations

import datetime
import time
from typing import Optional, Dict, Type, Callable, Tuple

from rka.eq2.master.game.engine import logger
from rka.eq2.master.game.interfaces import IAbility, TAbilityFilter


class Task:
    __descriptions: Dict[str, Tuple[Type, bool]] = dict()

    @staticmethod
    def __assert_unique_description(description: str, clazz: Type):
        if description in Task.__descriptions:
            previous_class, ignore = Task.__descriptions[description]
            if ignore:
                return
            if previous_class is not clazz:
                logger.info(f'Task with same name, new class: {description}, old: {previous_class}, new: {clazz}')
            else:
                logger.info(f'Task with same name: {description}, {clazz}')
            Task.__descriptions[description] = clazz, True
        else:
            Task.__descriptions[description] = clazz, False

    def __init__(self, description: str, duration: float):
        if description:
            Task.__assert_unique_description(description, self.__class__)
            self.__description = description
        else:
            self.__description = None
        self.__default_description = f'{self.__class__.__name__}[{id(self)}]'
        self.__duration = duration
        self.__expires_at = None
        self.__next_delay = 0.0
        self.__delay_until = None
        self.__forced_expire = False
        self.__start_notified = False
        self.__expire_notified = False
        self.__set_timers()
        self.__was_started = False
        self.__hash: Optional[int] = None

    def set_description(self, description: str):
        self.__description = description

    def set_default_description(self, description: str):
        self.__default_description = description

    def get_description(self) -> str:
        if self.__description:
            return self.__description
        return self.__default_description

    def is_persistent(self) -> bool:
        return False

    def __str__(self):
        return self.get_description()

    def __hash__(self) -> int:
        if self.__hash is None:
            self.__hash = self.get_description().__hash__()
        return self.__hash

    def __set_start_flags(self):
        self.__next_delay = 0.0
        self.__forced_expire = False
        if self.__expire_notified:
            self.__start_notified = False
        self.__expire_notified = False

    def __set_timers(self):
        self.__delay_until = datetime.datetime.now() + datetime.timedelta(seconds=self.__next_delay)
        self.__expires_at = datetime.datetime.now() + datetime.timedelta(seconds=self.__duration) + datetime.timedelta(seconds=self.__next_delay)

    def get_duration(self) -> float:
        return self.__duration

    def get_remaining_duration(self) -> Optional[float]:
        if self.is_expired():
            return None
        now = time.time()
        expires_at = self.__expires_at.timestamp()
        if expires_at < now:
            return None
        return expires_at - now

    def set_duration(self, duration: float):
        # this will apply when the duration is started next time
        self.__duration = duration

    def is_in_delay(self) -> bool:
        if self.__delay_until is None:
            return False
        now = datetime.datetime.now()
        return now < self.__delay_until

    def is_expired(self) -> bool:
        if self.__forced_expire:
            return True
        if self.__duration < 0:
            return False
        return datetime.datetime.now() > self.__expires_at

    def get_delay(self) -> Optional[datetime.timedelta]:
        now = datetime.datetime.now()
        if self.__delay_until is None or now >= self.__delay_until:
            return None
        return self.__delay_until - now

    def delay_next_start(self, delay: Optional[float] = None) -> Task:
        self.__next_delay = delay
        return self

    def start(self):
        self.__was_started = True
        self.__set_timers()
        self.__set_start_flags()

    # does not set new delay, clears next delay, but clears expiration and extends duration
    def restart(self):
        self.__set_start_flags()
        self.extend()

    def extend(self, duration: Optional[float] = None):
        if self.is_expired() or self.is_in_delay():
            return
        if not self.__was_started:
            return
        if duration is None:
            duration = self.__duration
        now = datetime.datetime.now()
        new_expiration = now + datetime.timedelta(seconds=duration)
        if self.__expires_at < new_expiration:
            self.__expires_at = new_expiration
            remaining_duration = new_expiration - now
            self._on_extend(remaining_duration.total_seconds())

    def expire(self):
        self.__forced_expire = True

    def notify_expired(self):
        logger.detail(f'notify_expired: {self}')
        if not self.is_expired():
            logger.warn(f'notify_expired failed: is_expired in {self}')
        if self.__expire_notified:
            # situation possible with composite requests
            logger.info(f'notify_expired failed: __expire_notified in {self}')
            return
        if self.__start_notified:
            self._on_expire()
            self.__expire_notified = True

    def notify_started(self):
        if self.is_in_delay():
            logger.warn(f'notify_started: is_in_delay in {self}')
        if self.__start_notified:
            # this is a possible situation if a request is part of multiple composite requets
            # so though that composite request it can started twice, or exist in both running and delayed request lists
            logger.info(f'notify_started: __start_notified in {self}')
            return
        if self.__expire_notified:
            # situation possible with composite requests
            logger.info(f'notify_started: __expire_notified in {self}')
            return
        self._on_start()
        self.__start_notified = True

    def is_running(self) -> bool:
        return self.__start_notified and not self.__expire_notified

    def _on_start(self):
        pass

    def _on_extend(self, remaining_duration: float):
        pass

    def _on_expire(self):
        pass


class IAbilityCastingObserver:
    def notify_casting(self, ability: IAbility):
        pass


class FilterTask(Task, TAbilityFilter):
    def __init__(self, filter_cb: TAbilityFilter, description: str, duration: float):
        Task.__init__(self, description=description, duration=duration)
        self._filter_cb = filter_cb

    def accept(self, ability: IAbility) -> bool:
        return self._filter_cb(ability)

    def __call__(self, ability: IAbility) -> bool:
        return self._filter_cb(ability)


class ExpireHook(Task):
    def __init__(self, hook_cb: Callable, description: str, duration: float):
        Task.__init__(self, description=description, duration=duration)
        self.hook_cb = hook_cb

    def _on_expire(self):
        self.hook_cb()
        super()._on_expire()
