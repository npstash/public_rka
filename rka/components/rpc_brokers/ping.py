import time
from threading import Condition
from typing import Callable, Optional

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.impl.alpha.rpc_xmlrpc import XMLRPCConnection
from rka.components.rpc_brokers import logger


class Ping(Closeable):
    PING_PERIOD = 15.0

    def __init__(self, local_id: str, remote_id: str, ping_cb: Callable):
        Closeable.__init__(self, explicit_close=True)
        self.__run_ping = True
        self.__ping_cond = Condition()
        self.__ping_cb = ping_cb
        self.__name = f'Server-side ping from {local_id} to {remote_id}'
        RKAThread(name=self.__name, target=self.__ping_loop).start()

    def __str__(self) -> str:
        return self.__name

    def __ping_loop(self):
        while self.__run_ping:
            with self.__ping_cond:
                self.__ping_cond.wait(timeout=Ping.PING_PERIOD)
            if not self.__run_ping:
                # check again to reduce unnecessary disconnection errors
                break
            # potential error will be notified asynchronously and cause error event
            logger.detail(f'sending ping: {self.__name}')
            self.__ping_cb()

    def close(self):
        self.__run_ping = False
        with self.__ping_cond:
            self.__ping_cond.notify()
        Closeable.close(self)


class Watchdog(Closeable):
    # needs to exceed one ping period + TCP connect timeout (30s) + some extra time for a late ping
    WATCHDOG_PERIOD = Ping.PING_PERIOD + XMLRPCConnection.TIMEOUT + 3.0

    def __init__(self, local_id: str, remote_id: str, ping_not_received_cb: Callable):
        Closeable.__init__(self, explicit_close=False)
        self.__ping_not_received_cb = ping_not_received_cb
        self.__last_feed = time.time()
        self.__lock = Condition()
        self.__keep_running_watchdog = True
        self.__name = f'Client-side watchdog from {local_id} to {remote_id}'
        self.__thread: Optional[RKAThread] = None

    def __str__(self) -> str:
        return self.__name

    def __watchdog_loop(self):
        self.__last_feed = time.time()
        while self.__keep_running_watchdog:
            now = time.time()
            since_last_feed = now - self.__last_feed
            time_left = Watchdog.WATCHDOG_PERIOD - since_last_feed
            if time_left <= 0.0:
                logger.debug(f'WATCHDOG fired for {self.__name}, since last feed:{since_last_feed}')
                self.__ping_not_received_cb()
                time_left = Watchdog.WATCHDOG_PERIOD
            with self.__lock:
                self.__lock.wait(timeout=min(time_left, Watchdog.WATCHDOG_PERIOD))

    def start_watchdog(self):
        if self.__thread:
            with self.__lock:
                self.__lock.notify()
        self.__thread = RKAThread(name=self.__name, target=self.__watchdog_loop)
        self.__thread.start()

    def feed_watchdog(self, hint=None):
        logger.debug(f'WATCHDOG feeding: {self.__name}, hint={hint}')
        self.__last_feed = time.time()

    def close(self):
        self.__keep_running_watchdog = False
        with self.__lock:
            self.__lock.notify()
        Closeable.close(self)
