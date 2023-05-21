from __future__ import annotations

import enum
import inspect
import logging
import os
import sys
import threading
import time
import traceback
from typing import Dict, Callable, Optional


class LogLevel(enum.IntEnum):
    DETAIL = 0
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4
    FATAL = 5


class LogService:
    loggers: Dict[str, LogService] = dict()
    __loggers_lock = threading.Lock()
    __log_listener: Optional[Callable[[str, LogLevel], None]] = None
    __log_listener_level = LogLevel.ERROR
    __level_mapping = [
        (logging.Logger.debug, logging.DEBUG),
        (logging.Logger.debug, logging.DEBUG),
        (logging.Logger.info, logging.INFO),
        (logging.Logger.warning, logging.WARNING),
        (logging.Logger.error, logging.ERROR),
        (logging.Logger.fatal, logging.FATAL),
    ]
    __name = None

    @staticmethod
    def set_log_listener(listener: Callable[[str, LogLevel], None], level=LogLevel.ERROR):
        LogService.__log_listener = listener
        LogService.__log_listener_level = level

    # noinspection PyTypeChecker
    @staticmethod
    def __get_caller(depth: int):
        stack = inspect.stack()
        caller_filename: str = stack[depth + 1].filename
        filename_split = os.path.normpath(caller_filename).split(os.path.sep)
        caller = filename_split[-1].split('.')[0]
        if caller == '__init__' and len(filename_split) > 1:
            caller = filename_split[-2].split('.')[0]
        return caller

    def __init__(self, log_level=LogLevel.INFO):
        caller = LogService.__get_caller(1)
        self.__name = caller
        self.__level = log_level
        self.__initial_level = log_level
        self.__logger = logging.Logger(self.__name)
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(name)s [%(threadName)s, %(thread)d]: %(message)s', "%H:%M:%S")
        self.__handler_stdout = logging.StreamHandler(sys.stdout)
        self.__handler_stdout.setFormatter(formatter)
        self.__logger.addHandler(self.__handler_stdout)
        self.__handler_stderr = logging.StreamHandler(sys.stderr)
        self.__handler_stderr.setLevel(logging.ERROR)
        self.__handler_stderr.setFormatter(formatter)
        self.__logger.addHandler(self.__handler_stderr)
        with LogService.__loggers_lock:
            LogService.loggers[self.__name] = self

    def reset_level(self):
        self.__level = self.__initial_level

    def set_level(self, new_level: LogLevel):
        self.__level = new_level

    def set_stderr_level(self, new_error_level: LogLevel):
        level = LogService.__level_mapping[new_error_level][1]
        self.__handler_stderr.setLevel(level)

    def get_level(self) -> LogLevel:
        return self.__level

    def __log(self, msg: str, level: LogLevel):
        LogService.__level_mapping[level][0](self.__logger, msg)
        if LogService.__log_listener is not None and LogService.__log_listener_level <= level:
            LogService.__log_listener(msg, level)

    def log(self, msg: str, level=LogLevel.INFO):
        if level >= self.__level:
            self.__log(msg, level)

    def detail(self, msg: str):
        if self.__level <= LogLevel.DETAIL:
            self.__log(msg, LogLevel.DETAIL)

    def debug(self, msg: str):
        if self.__level <= LogLevel.DEBUG:
            self.__log(msg, LogLevel.DEBUG)

    def info(self, msg: str):
        if self.__level <= LogLevel.INFO:
            self.__log(msg, LogLevel.INFO)

    def warn(self, msg: str):
        if self.__level <= LogLevel.WARN:
            self.__log(msg, LogLevel.WARN)

    def error(self, msg: str):
        if self.__level <= LogLevel.ERROR:
            self.__log(msg, LogLevel.ERROR)

    def fatal(self, msg: str):
        if self.__level <= LogLevel.FATAL:
            self.__log(msg, LogLevel.FATAL)
            traceback.print_stack()

    def mandatory_log(self, msg: str):
        self.__log(msg, LogLevel.DETAIL)


class Trace:
    def __init__(self, trace_id: str):
        self.__trace_id = trace_id
        self.__stamp = time.time()

    def mark(self):
        self.__stamp = time.time()

    def trace(self, text: str):
        now = time.time()
        print(f'trace {now - self.__stamp} [{self.__trace_id}:{text}]')
        self.__stamp = now
