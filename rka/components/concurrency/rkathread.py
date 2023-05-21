import faulthandler
import sys
import threading
from threading import Thread
from typing import Dict, Optional, Callable

from rka.components.cleanup import Closeable
from rka.components.concurrency import logger


class RKAThread(Thread, Closeable):
    __next_thread_num = 0
    __thread_names: Dict[int, Optional[str]] = dict()

    @staticmethod
    def dump_threads(stderr=False):
        f = sys.stderr if stderr else sys.stdout
        faulthandler.dump_traceback(file=f)
        for th_id, th_name in RKAThread.__thread_names.items():
            print(f'Thread ID=0x{th_id:08x} - {th_name}', file=f)

    def __init__(self, name: str, target: Callable[[], None]):
        assert callable(target)
        Closeable.__init__(self, explicit_close=False, description=name)
        Thread.__init__(self, name=f'{name}-{RKAThread.__next_thread_num}', target=self.__target_wrapper)
        RKAThread.__next_thread_num += 1
        self.__target = target
        self.__completed = False

    def __str__(self):
        name = self.name
        ident = self.ident
        return f'Thread [{name}] ID {ident}'

    def __target_wrapper(self):
        logger.debug(f'{self} starting')
        RKAThread.__thread_names[threading.get_ident()] = f'Started thread: {self.name}'
        try:
            self.__target()
        finally:
            logger.debug(f'{self} exiting')
            RKAThread.__thread_names[threading.get_ident()] = f'Completed thread: {self.name}'
            self.__completed = True
            Closeable.close(self)

    def close_resource(self):
        logger.info(f'{self} no longer managed as resource. completed flag is: {self.__completed}')
        Closeable.close(self)

    def close(self):
        if not self.__completed:
            logger.debug(f'{self} not completed before calling close()')
        else:
            Closeable.close(self)
