import threading
import time
import traceback
from time import sleep
from typing import List, Callable

from rka.components.concurrency import logger
from rka.components.concurrency.rkathread import RKAThread


class RKAClock(RKAThread):
    def __init__(self, name: str, tick_duration: float):
        RKAThread.__init__(self, 'RT timer', target=self.__ticker)
        self.__name = name
        self.__tick_duration = tick_duration
        self.__listeners: List[Callable] = list()
        self.__keep_running = True
        self.__paused = False
        self.__lock = threading.Condition()
        self.start()

    def __ticker(self):
        started_at = 0.0
        last_slack_notify = None
        ticks = 0
        next_wait = self.__tick_duration
        while True:
            with self.__lock:
                while self.__paused and self.__keep_running:
                    self.__lock.wait(4.0)
                    if not self.__paused:
                        started_at = 0.0
                if not self.__keep_running:
                    break
                if not started_at:
                    started_at = time.time()
                    last_slack_notify = started_at
                    ticks = 0
            sleep(next_wait)
            remove_listeners: List[Callable] = list()
            for listener_cb in self.__listeners:
                # noinspection PyBroadException
                try:
                    listener_cb()
                    pass
                except Exception as e:
                    logger.error(f'scheduler ticker listener {listener_cb} cause exception {e}')
                    traceback.print_exc()
                    remove_listeners.append(listener_cb)
            for listener_cb in remove_listeners:
                self.__listeners.remove(listener_cb)
            ticks += 1
            clock_time = self.__tick_duration * ticks
            now = time.time()
            actual_time = now - started_at
            diff_time = actual_time - clock_time
            next_wait = self.__tick_duration - diff_time
            if next_wait < 0.0:
                next_wait = 0.0
            if diff_time > 2 * self.__tick_duration and now > last_slack_notify + 10.0:
                logger.warn(f'clock "{self.__name}" delaying, current slack {diff_time:0.4f}')
                last_slack_notify = now
            if diff_time > 20 * self.__tick_duration:
                logger.warn(f'clock "{self.__name}" delaying too much {diff_time:0.4f}, restarting')
                started_at = now
                ticks = 0
                last_slack_notify = now
                next_wait = self.__tick_duration
        with self.__lock:
            self.__lock.notify()

    def add_listener(self, listener_cb):
        self.__listeners.append(listener_cb)

    def remove_listener(self, listener_cb) -> bool:
        if listener_cb not in self.__listeners:
            logger.warn(f'cant remove listener, not in in list: {listener_cb}')
            return False
        self.__listeners.remove(listener_cb)
        return True

    def pause(self):
        with self.__lock:
            self.__paused = True

    def resume(self):
        with self.__lock:
            self.__paused = False
            self.__lock.notify()

    def close(self):
        with self.__lock:
            self.__keep_running = False
            self.__lock.wait(2 * self.__tick_duration)
        super().close()
