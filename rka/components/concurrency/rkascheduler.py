from __future__ import annotations

import heapq
import time
import traceback
from threading import Condition
from typing import List, Callable

from rka.components.cleanup import Closeable
from rka.components.concurrency import logger
from rka.components.concurrency.rkathread import RKAThread
from rka.components.concurrency.workthread import RKAFuture


class RKASchedulerFuture(RKAFuture):
    def __init__(self, action, scheduler: RKAScheduler, item_id: int, run_at: float):
        RKAFuture.__init__(self, action)
        self.__scheduler = scheduler
        self.item_id = item_id
        self.run_at = run_at

    def __lt__(self, other):
        return self.run_at < other.run_at

    def __gt__(self, other):
        return self.run_at > other.run_at

    def __le__(self, other):
        return self.run_at <= other.run_at

    def __ge__(self, other):
        return self.run_at >= other.run_at

    def cancel_future(self) -> bool:
        super().cancel_future()
        return self.__scheduler.cancel_future_by_id(self.item_id)


class RKAScheduler(Closeable):
    def __init__(self, name):
        Closeable.__init__(self, explicit_close=False)
        self.__task_queue: List[RKASchedulerFuture] = list()
        self.__next_id = 1
        self.__lock = Condition()
        self.__running = True
        RKAThread(name=name, target=self.__main_loop).start()

    def __main_loop(self):
        error_safety_wait = 2.0
        # loop executing ready tasks
        while self.__running:
            task = None
            with self.__lock:
                # loop until a ready task is found
                while self.__running:
                    # loop until there is any task
                    while not self.__task_queue and self.__running:
                        # wakeup periodically for error safety
                        self.__lock.wait(error_safety_wait)
                    if not self.__running:
                        break
                    # task found on heap
                    _task = self.__task_queue[0]
                    run_at_time = _task.run_at
                    now = time.time()
                    if run_at_time <= now:
                        heapq.heappop(self.__task_queue)
                        # let the task complete in the outer loop and outside crit section
                        task = _task
                        break
                    # task is not ready, wait until it is
                    wait_time = min(error_safety_wait, max(0.0, run_at_time - now))
                    self.__lock.wait(wait_time)
            if not self.__running:
                break
            # task can be none if the loop is being terminated
            if task is not None:
                try:
                    task.complete()
                except Exception as e:
                    logger.warn(f'scheduler job error: {e}')
                    traceback.print_exc()

    def cancel_future_by_id(self, item_id: int) -> bool:
        with self.__lock:
            for i, item in enumerate(self.__task_queue):
                future = item
                if future.item_id == item_id:
                    self.__task_queue.pop(i)
                    return True
        return False

    def schedule(self, action: Callable, delay: float) -> RKASchedulerFuture:
        with self.__lock:
            run_at_time = time.time() + delay
            future = RKASchedulerFuture(action, self, self.__next_id, run_at_time)
            heapq.heappush(self.__task_queue, future)
            self.__next_id += 1
            self.__lock.notify()
            return future

    def close(self):
        with self.__lock:
            self.__running = False
            self.__lock.notify_all()
        super().close()
