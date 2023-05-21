from __future__ import annotations

import time
import traceback
from threading import Condition
from time import sleep
from typing import List, Optional, Callable

from rka.components.io.log_service import LogService, LogLevel
from rka.log_configs import LOG_COMMON

logger = LogService(LOG_COMMON)


class CleanupManager:
    MAX_CLEANUP_DURATION = 0.1

    __cleanup_list: List[Closeable] = list()
    __cleanup_stage = 0

    # noinspection PyBroadException
    @staticmethod
    def __safe_close(resource: Closeable):
        assert isinstance(resource, Closeable)
        cleanup_start = time.time()
        try:
            logger.info(f'Closing resource {resource.describe_resource()}')
            if resource.is_explicit():
                logger.warn(f'resource {resource.describe_resource()} not closed explicitly (yet)')
            resource.close()
        except Exception as e:
            logger.error(f'Fatal error while closing {resource.describe_resource()}: {e}')
            traceback.print_exc()
        finally:
            cleanup_duration = time.time() - cleanup_start
            if cleanup_duration > CleanupManager.MAX_CLEANUP_DURATION:
                logger.warn(f'Resource taking too long to close {resource.describe_resource()}: {cleanup_duration}s')

    @staticmethod
    def register(resource: Closeable):
        assert isinstance(resource, Closeable)
        rname = resource.__class__.__name__
        if CleanupManager.__cleanup_stage > 0:
            logger.warn(f'Trying to registere resource {rname} when cleanup is ongoing')
            return
        logger.info(f'Registering resource {rname}')
        assert isinstance(resource, Closeable), f'{rname} not closable class'
        assert resource not in CleanupManager.__cleanup_list, f'{rname} already registered'
        CleanupManager.__cleanup_list.append(resource)

    @staticmethod
    def notify_closed(resource):
        assert isinstance(resource, Closeable)
        logger.mandatory_log(f'Resource close notify: {resource.describe_resource()}')
        if resource not in CleanupManager.__cleanup_list:
            logger.info(f'resource {resource.describe_resource()} already closed')
            return
        try:
            CleanupManager.__cleanup_list.remove(resource)
        except ValueError:
            logger.error(f'Could not remove {resource}')

    @staticmethod
    def is_closed(resource):
        assert isinstance(resource, Closeable)
        return resource not in CleanupManager.__cleanup_list

    @staticmethod
    def is_closing():
        return CleanupManager.__cleanup_stage > 0

    @staticmethod
    def __try_close_all(log_level: int) -> bool:
        implicit_resources = list(filter(Closeable.is_implicit, CleanupManager.__cleanup_list))
        for resource in reversed(implicit_resources):
            CleanupManager.__safe_close(resource)
        remaining_closeables = len(CleanupManager.__cleanup_list)
        if remaining_closeables > 0:
            logger.log(f'There are {remaining_closeables} remaining resources', log_level)
            resource_list_copy = list(CleanupManager.__cleanup_list)
            for i, resource in enumerate(reversed(resource_list_copy)):
                logger.log(f'{i}. closing {resource.describe_resource()}', log_level)
                CleanupManager.__safe_close(resource)
        return len(CleanupManager.__cleanup_list) == 0

    @staticmethod
    def audit_remaining_resources():
        if not CleanupManager.__cleanup_list:
            return
        logger.mandatory_log(f'Cleanup: {len(CleanupManager.__cleanup_list)} unclosed resources remaining')
        from rka.components.concurrency.rkathread import RKAThread
        if CleanupManager.__cleanup_list:
            RKAThread.dump_threads(stderr=True)

    @staticmethod
    def __clear_resource_list() -> bool:
        all_cleared = len(CleanupManager.__cleanup_list) == 0
        CleanupManager.__cleanup_list.clear()
        return all_cleared

    @staticmethod
    def close_all(call_quit=True):
        logger.set_stderr_level(LogLevel.INFO)
        if CleanupManager.__cleanup_stage == 0:
            CleanupManager.__cleanup_stage = 1
            for i in range(10):
                log_level = LogLevel.WARN if i > 0 else LogLevel.INFO
                logger.log(f'cleanup try {i}', log_level)
                if CleanupManager.__try_close_all(log_level):
                    break
                sleep(1.0)
        elif CleanupManager.__cleanup_stage == 1:
            logger.error(f'Cannot start cleanup, because cleanup is already ongoing. Try again for emergency cleanup')
            CleanupManager.__cleanup_stage = 2
            return
        elif CleanupManager.__cleanup_stage == 2:
            logger.error(f'Emergency cleanup')
        CleanupManager.audit_remaining_resources()
        if not CleanupManager.__clear_resource_list() and call_quit:
            quit()


cleanup_manager = CleanupManager()


class Closeable:
    def __init__(self, explicit_close: bool, description: Optional[str] = None):
        self.__explicit_close = explicit_close
        self.__description = description
        CleanupManager.register(self)

    def __str_own(self):
        if self.__description is None:
            return f'[{self.__class__.__name__}]'
        else:
            return f'[{self.__class__.__name__} {self.__description}]'

    def __str__(self):
        return self.__str_own()

    def describe_resource(self) -> str:
        # noinspection PyBroadException
        try:
            if self.__class__.__str__ is not object.__str__:
                rname = self.__class__.__name__
                return f'[{rname} {self}]'
        except Exception:
            traceback.print_exc()
        return self.__str_own()

    def close(self):
        CleanupManager.notify_closed(self)

    def is_closed(self) -> bool:
        return CleanupManager.is_closed(self)

    def is_explicit(self) -> bool:
        return self.__explicit_close

    def is_implicit(self) -> bool:
        return not self.__explicit_close


class CloseGuard(Closeable):
    def __init__(self, name: str, close_callback: Optional[Callable] = None):
        Closeable.__init__(self, explicit_close=False)
        self.__name = f'{self.__class__.__name__} [{name}]'
        self.__condition = Condition()
        self.__close_callback = close_callback

    def __str__(self) -> str:
        return self.__name

    def __enter__(self):
        assert not self.is_closed()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        with self.__condition:
            self.__condition.notify_all()
        if self.__close_callback and not self.is_closed():
            self.__close_callback()
        Closeable.close(self)

    def disband(self):
        Closeable.close(self)

    def sleep(self, timeout: float) -> bool:
        with self.__condition:
            self.__condition.wait(timeout)
            return self.is_closed()

    def meet_condition(self, rule: Callable[[], bool], timeout: Optional[float], period=0.5) -> bool:
        with self.__condition:
            while not self.is_closed():
                if rule():
                    break
                wait_start = time.time()
                wait_time = min(timeout, period) if timeout and timeout > 0.0 else period
                self.__condition.wait(wait_time)
                if timeout:
                    timeout -= time.time() - wait_start
                    if timeout <= 0.0:
                        return False
            return not self.is_closed()
