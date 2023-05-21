import random
import threading
import time
import traceback
from typing import Dict, List, Callable

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogService
from rka.components.network.discovery import INetworkService
from rka.log_configs import LOG_DISCOVERY

logger = LogService(LOG_DISCOVERY)


class NetworkEvent:
    NETWORK_FOUND_EVENT_TYPE = 'nif_found'
    NETWORK_LOST_EVENT_TYPE = 'nif_lost'
    SERVER_UPDATE_EVENT_TYPE = 'server_found'

    def __init__(self, event_type: str, *args):
        self.event_type = event_type
        self.args = args


class NetworkService(Closeable, INetworkService):
    def __init__(self, service_id: str):
        Closeable.__init__(self, explicit_close=False)
        self.__lock = threading.Condition()
        self.__service_running = True
        self.__startup_done = False
        self.__startup_condition = threading.Condition()
        self.__observers: Dict[str, List[Callable]] = dict()  # type -> list
        self.__pending_events: List[NetworkEvent] = list()
        self.__node_id = random.randint(0, 123456789)
        self.id = service_id

    def __notify_events(self):
        logger.info(f'[{self.id}] Event pump starting in service')
        while True:
            with self.__lock:
                while len(self.__pending_events) == 0 and self.__service_running:
                    self.__lock.wait()
                if not self.__service_running:
                    break
                event = self.__pending_events.pop(0)
            self.__dispatch_event(event.event_type, event.args)
        logger.info(f'[{self.id}] Event pump closing in service')

    def __dispatch_event(self, event_type: str, args):
        with self.__lock:
            if event_type not in self.__observers.keys():
                return
            observers = self.__observers[event_type].copy()
        logger.debug(f'[{self.id}] Dispatching event type {event_type} args {args}, observers {observers}')
        for observer in observers:
            try:
                observer(*args)
            except Exception as e:
                logger.error(f'[{self.id}] Exception occured when calling discovery callback {observer}, {args}, {e}')
                traceback.print_exc()
                return

    def _add_observer(self, event_type: str, callback: Callable):
        logger.debug(f'[{self.id}] Adding event {event_type} observer {callback}')
        with self.__lock:
            if event_type not in self.__observers.keys():
                self.__observers[event_type] = list()
            self.__observers[event_type].append(callback)

    def _remove_observer(self, event_type: str, callback: Callable):
        logger.debug(f'[{self.id}] Removing event {event_type} observer {callback}')
        with self.__lock:
            if event_type not in self.__observers.keys():
                return
            self.__observers[event_type].remove(callback)

    def _fire_event(self, event_type, *args):
        logger.detail(f'[{self.id}] Firing event {event_type} args {args}')
        with self.__lock:
            self.__pending_events.append(NetworkEvent(event_type, *args))
            self.__lock.notify_all()

    def _notify_startup_done(self):
        with self.__startup_condition:
            if not self.__startup_done:
                self.__startup_done = True
                self.__startup_condition.notify_all()
                logger.debug(f'[{self.id}] Service startup done {self}')

    def _wait_while_running(self, timeout: float) -> bool:
        now = time.time()
        finish_at = now + timeout
        with self.__lock:
            while True:
                if self.__service_running and now < finish_at:
                    wait_time = finish_at - now
                    self.__lock.wait(wait_time)
                else:
                    break
                now = time.time()
        return self.__service_running

    def _start_tasks(self, tasks: List[Callable]):
        if not self.is_running():
            logger.warn(f'[{self.id}] Trying to launch task after stopping service: {tasks}')
            return
        for task in tasks:
            RKAThread(name=f'Discovery({task.__name__})-{self.id}', target=task).start()

    def wait_for_startup(self):
        logger.debug(f'[{self.id}] Wait for service startup {self}')
        with self.__startup_condition:
            while not self.__startup_done and self.__service_running:
                self.__startup_condition.wait()

    def is_running(self) -> bool:
        return self.__service_running

    def get_id(self) -> str:
        return str(self.__node_id)

    def start(self):
        logger.info(f'[{self.id}] Starting service {self}')
        assert self.__service_running
        self._start_tasks([self.__notify_events])

    def stop(self):
        logger.info(f'[{self.id}] Stopping service {self}')
        with self.__lock:
            self.__service_running = False
            self.__lock.notify_all()

    def close(self):
        logger.info(f'[{self.id}] Close service {self}')
        with self.__lock:
            if self.__service_running:
                self.stop()
        Closeable.close(self)
