from __future__ import annotations

import threading
import time
import traceback
from threading import Condition
from typing import List, Callable, Any, Optional

from rka.components.cleanup import CloseGuard
from rka.components.cleanup import Closeable
from rka.components.concurrency import logger
from rka.components.concurrency.rkathread import RKAThread


class RKAFuture:
    def __init__(self, action: Callable):
        assert action is not None
        self.__action = action
        self.__result = None
        self.__completed = False
        self.__lock = Condition()
        self.__cancel = False
        self.__exception: Optional[Exception] = None
        self.__next_task: Optional[RKAFuture] = None
        self.__external_condition: Optional[Condition] = None
        self.__info: Optional[str] = None

    def __str__(self) -> str:
        if self.__info:
            return f'Future {self.__info}'
        return f'Future of {self.__action}'

    def __call__(self):
        self.complete()

    def set_description(self, info: Any):
        self.__info = info

    def get_description(self) -> Any:
        return self.__info

    def is_completed(self) -> bool:
        with self.__lock:
            return self.__completed

    def is_cancelled(self) -> bool:
        with self.__lock:
            return self.__cancel

    def get_exception(self) -> Optional[Exception]:
        with self.__lock:
            return self.__exception

    def complete(self):
        with self.__lock:
            if self.__cancel:
                return
        try:
            self.__result = self.__action()
        except Exception as e:
            with self.__lock:
                self.__exception = e
            raise e
        finally:
            with self.__lock:
                self.__completed = True
                self.__lock.notify()
                next_task = self.__next_task
                external_condition = self.__external_condition
            if external_condition:
                with external_condition:
                    external_condition.notify_all()
        if next_task:
            next_task.complete()

    def get_result(self, timeout: Optional[float] = None, guard: Optional[CloseGuard] = None) -> Any:
        with self.__lock:
            while not self.__completed and not self.__cancel and (timeout is None or timeout > 0.0):
                if guard is None and (timeout is not None and timeout > 1.0):
                    # this guard will notify the condition and cancel the future only when general cleanup fires
                    guard = CloseGuard(name=self.__str__(), close_callback=self.cancel_future)
                wait_start = time.time()
                self.__lock.wait(timeout=timeout)
                if timeout:
                    timeout -= time.time() - wait_start
            if guard is not None:
                guard.disband()
            return self.__result

    def set_exernal_condition(self, condition: Condition):
        with self.__lock:
            self.__external_condition = condition

    def then(self, next_task: Callable) -> Optional[RKAFuture]:
        with self.__lock:
            if self.__completed:
                return None
            self.__next_task = RKAFuture(next_task)
            return self.__next_task

    def cancel_future(self) -> bool:
        with self.__lock:
            self.__cancel = True
            self.__lock.notify()
            return not self.__completed


class RKAFutureMuxer(Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__futures: List[RKAFuture] = []
        self.__lock = Condition()
        self.__closed = False

    def close(self):
        with self.__lock:
            self.__closed = True
            self.__lock.notify_all()
        Closeable.close(self)

    def add_future(self, future: RKAFuture):
        with self.__lock:
            self.__futures.append(future)
            future.set_exernal_condition(self.__lock)
            self.__lock.notify_all()

    def pop_completed_futures(self) -> List[RKAFuture]:
        completed = []
        with self.__lock:
            for future in self.__futures:
                if future.is_completed():
                    completed.append(future)
            for future in completed:
                self.__futures.remove(future)
        return completed

    def pop_any_completed_future(self) -> Optional[RKAFuture]:
        with self.__lock:
            for future in self.__futures:
                if future.is_completed():
                    self.__futures.remove(future)
                    return future
        return None

    def wait_and_pop(self, timeout: Optional[float] = None) -> Optional[RKAFuture]:
        with self.__lock:
            future = self.pop_any_completed_future()
            if future:
                return future
            while not self.__closed and (timeout is None or timeout > 0.0):
                wait_start = time.time()
                self.__lock.wait(timeout=timeout)
                if timeout:
                    timeout -= time.time() - wait_start
                future = self.pop_any_completed_future()
                if future:
                    return future
        return None

    def wait_for_all(self, timeout: Optional[float] = None) -> List[RKAFuture]:
        with self.__lock:
            completed_futures = []
            while self.__futures:
                wait_start = time.time()
                future = self.wait_and_pop(timeout)
                if timeout:
                    timeout -= time.time() - wait_start
                if future:
                    completed_futures.append(future)
            return completed_futures


class IWorker:
    def push_task(self, callback: Callable) -> Optional[RKAFuture]:
        raise NotImplementedError()

    def print_queue(self):
        raise NotImplementedError()


class RKAWorkerThread(IWorker, Closeable):
    def __init__(self, name: str, queue_limit=-1):
        Closeable.__init__(self, explicit_close=False, description=name)
        self.__name = name
        self.__description = f'RKAWorkerThread [{name}]'
        self.__lock = threading.Condition()
        self.__queue_limit = queue_limit
        self.__queue: List[RKAFuture] = list()
        self.__keep_running = True
        self.__threads = self._create_threads()
        for thread in self.__threads:
            thread.start()

    def __str__(self) -> str:
        return self.__description

    def _create_threads(self) -> List[RKAThread]:
        return [self._create_thread(self.__name)]

    def _create_thread(self, name: str) -> RKAThread:
        return RKAThread(name, target=self.__loop)

    def __loop(self):
        self.__lock.acquire()
        try:
            while self.__keep_running:
                while not self.__queue and self.__keep_running:
                    self.__lock.wait()
                if not self.__keep_running:
                    logger.debug(f'Worker thread {self.__name} exiting')
                    return
                future = self.__queue.pop(0)
                self.__lock.release()
                logger.detail(f'Worker thread {self.__name} executing {future}')
                try:
                    future.complete()
                except Exception as e:
                    logger.warn(f'Exception {e} in workthread {self}, future {future}')
                    traceback.print_exc()
                finally:
                    self.__lock.acquire()
        finally:
            remaining_futures = self.__queue.copy()
            self.__queue.clear()
            self.__lock.release()
            for remaining_future in remaining_futures:
                remaining_future.cancel_future()

    def push_task(self, callback: Callable[[], None]) -> Optional[RKAFuture]:
        with self.__lock:
            if not self.__keep_running:
                return None
            future = RKAFuture(callback)
            logger.detail(f'Worker thread {self.__name} scheduling {callback} as {future}')
            if len(self.__queue) == self.__queue_limit:
                logger.warn(f'Worker thread {self.__name} queue limit reached')
                return None
            self.__queue.append(future)
            self.__lock.notify()
        return future

    def print_queue(self):
        with self.__lock:
            queue_copy = self.__queue.copy()
        print('Queue contents:')
        for i, future in enumerate(queue_copy):
            print(f'{i}. {future}')

    def close(self):
        with self.__lock:
            logger.detail(f'Stopping worker thread {self.__name}')
            self.__keep_running = False
            self.__lock.notify_all()
        join_end = time.time() + 1.0
        for thread in self.__threads:
            join_time_left = join_end - time.time()
            if join_time_left > 0.0:
                thread.join(join_time_left)
            thread.close()
        Closeable.close(self)


class RKAWorkerThreadPool(RKAWorkerThread):
    def __init__(self, name: str, pool_size: int, queue_limit=-1):
        self.__pool_size = pool_size
        self.__name = name
        RKAWorkerThread.__init__(self, name, queue_limit)

    def _create_threads(self):
        return [self._create_thread(f'{self.__name}-1') for _ in range(self.__pool_size)]
