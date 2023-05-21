import threading
import time
from collections import deque
from typing import Optional, Tuple

import regex as re

from rka.components.cleanup import Closeable
from rka.eq2.parsing import ILogReader, ILogInjector, ILogReaderWriter, logger


class FileLogReader(ILogReader, Closeable):
    ACTIVE_CHECK_TIME = 0.05
    INACTIVE_CHECK_TIME = 2.0

    def __init__(self, log_filename: str, encoding='utf-8', file_not_found_retry=600.0, io_error_retry=5.0):
        Closeable.__init__(self, explicit_close=True)
        self.__log_filename = log_filename
        self.__name = log_filename[log_filename.rfind('\\') + 1:]
        self.__file = None
        self.__wait_lock = threading.Condition()
        self.__encoding = encoding
        self.__interrupted = False
        self.__file_not_found_retry = file_not_found_retry
        self.__io_error_retry = io_error_retry
        self.__io_error_count = 0
        self.__encoding_error_count = 0

    def interrupt(self):
        with self.__wait_lock:
            self.__interrupted = True
            if self.__file:
                self.__file.close()
            self.__wait_lock.notify_all()

    def __wait_until_interrupted(self, remaining_duration: float) -> bool:
        with self.__wait_lock:
            while not self.__interrupted and remaining_duration > 0:
                start = time.time()
                self.__wait_lock.wait(remaining_duration)
                remaining_duration -= time.time() - start
            return self.__interrupted

    def read_log_with_timestamp(self) -> Optional[Tuple[Optional[str], float]]:
        while not self.__interrupted:
            try:
                if self.__file is None:
                    self.__file = open(self.__log_filename, mode='rt', encoding=self.__encoding)
                    self.__file.seek(0, 2)
                log_line = self.__file.readline()
                if not log_line:
                    return None
                self.__io_error_count = 0
                return log_line, time.time()
            except FileNotFoundError as e:
                logger.info(f'file not found {self}: {e}')
                if self.__wait_until_interrupted(self.__file_not_found_retry):
                    break
                continue
            except (ValueError, IOError) as e:
                logger.warn(f'error reading log file in {self}: {e}')
                self.__io_error_count += 1
                if self.__io_error_count > 10:
                    if self.__wait_until_interrupted(5.0):
                        break
                continue
            except UnicodeDecodeError as e:
                logger.warn(f'encoding error with log file in {self}: {e}')
                self.__encoding_error_count += 1
                self.__file.seek(0, whence=2)
                if self.__encoding_error_count > 5:
                    self.__file.close()
                    self.__file = None
                    self.__encoding = 'latin-1'
                continue
        return None

    def wait_until_empty(self):
        return

    def clear_logs(self):
        try:
            f = open(self.__log_filename, 'w+')
            f.truncate(0)
            f.close()
        except FileNotFoundError:
            pass
        except IOError as e:
            logger.warn(f'problem clearing log file {self.__log_filename} {e}')
        if self.__file:
            self.__file.close()
            self.__file = None
        with self.__wait_lock:
            self.__wait_lock.notify_all()

    def reader_name(self) -> str:
        return self.__name

    def close(self):
        self.interrupt()
        Closeable.close(self)


class FileLogInjector(ILogInjector, Closeable):
    def __init__(self, log_filename: str, encoding='utf-8'):
        Closeable.__init__(self, explicit_close=False)
        self.__log_filename = log_filename
        self.__name = log_filename[log_filename.rfind('\\') + 1:]
        self.__file = None
        self.__encoding = encoding

    def write_log(self, log_line: str):
        if self.__file is None:
            self.__file = open(self.__log_filename, mode='a', encoding=self.__encoding)
        self.__file.write(f'{log_line.strip()}\n')
        self.__file.flush()

    def close(self):
        if self.__file:
            self.__file.close()
        Closeable.close(self)


class QueueLogReader(ILogReaderWriter):
    def __init__(self):
        self.__queue_lock = threading.Condition()
        self.__log_queue = deque()
        self.__closed = False

    def interrupt(self):
        self.write_log(None)

    def read_log_with_timestamp(self) -> Optional[Tuple[Optional[str], float]]:
        with self.__queue_lock:
            while not self.__log_queue and not self.__closed:
                self.__queue_lock.notify_all()
                self.__queue_lock.wait()
            if self.__closed:
                return None
            log = self.__log_queue.popleft()
            return log

    def write_log(self, log_line: Optional[str]):
        with self.__queue_lock:
            if self.__closed:
                return
            was_empty = True if not self.__log_queue else False
            self.__log_queue.append((log_line, time.time()))
            if was_empty:
                self.__queue_lock.notify_all()

    def wait_until_empty(self):
        with self.__queue_lock:
            while self.__log_queue:
                self.__queue_lock.wait()

    def clear_logs(self):
        with self.__queue_lock:
            self.__log_queue.clear()
            self.__queue_lock.notify_all()

    def reader_name(self) -> str:
        return str(self)

    def close(self):
        with self.__queue_lock:
            self.__closed = True
            self.__log_queue.clear()
            self.__queue_lock.notify_all()


class TruncateLogHeader(ILogReader):
    def __init__(self, delegate: ILogReader, skip_chars: int):
        self.__delegate = delegate
        self.__skip_chars = skip_chars

    def interrupt(self):
        self.__delegate.interrupt()

    def read_log_with_timestamp(self) -> Optional[Tuple[Optional[str], float]]:
        log = self.__delegate.read_log_with_timestamp()
        if not log:
            return None
        log_line, timestamp = log
        if len(log_line) < self.__skip_chars:
            return None, timestamp
        log_line = log_line[self.__skip_chars:]
        log_line = log_line.strip()
        return log_line, timestamp

    def wait_until_empty(self):
        self.__delegate.wait_until_empty()

    def clear_logs(self):
        self.__delegate.clear_logs()

    def reader_name(self) -> str:
        return self.__delegate.reader_name()

    def close(self):
        self.__delegate.close()


class LogReaderWriter(ILogReaderWriter):
    def __init__(self, reader: ILogReader, injector: ILogInjector):
        self.__reader = reader
        self.__injector = injector

    def interrupt(self):
        self.__reader.interrupt()

    def read_log_with_timestamp(self) -> Optional[Tuple[Optional[str], float]]:
        return self.__reader.read_log_with_timestamp()

    def wait_until_empty(self):
        self.__reader.wait_until_empty()

    def clear_logs(self):
        self.__reader.clear_logs()

    def reader_name(self) -> str:
        return self.__reader.reader_name()

    def close(self):
        self.__injector.close()
        self.__reader.close()

    def write_log(self, log_line: str):
        self.__injector.write_log(log_line)


class LogReaderFactory:
    @staticmethod
    def create_file_logreader(filename: str) -> ILogReader:
        return FileLogReader(filename)

    @staticmethod
    def create_file_loginjector(filename: str) -> ILogInjector:
        return FileLogInjector(filename)

    @staticmethod
    def create_file_logio(reader, injector) -> ILogReaderWriter:
        return LogReaderWriter(reader, injector)

    @staticmethod
    def create_queue_logreader() -> ILogReaderWriter:
        return QueueLogReader()


class LogUtil:
    @staticmethod
    def inject_gamelog_from_text(loginjector: ILogInjector, logline: str):
        if not re.match(r'\(\d{10}\)\[[\p{L}0-9: ]{24}\] ', logline):
            logline = '(0124567890)[Thu Jan  1  0:00:00 1970] ' + logline
        loginjector.write_log(logline)

    @staticmethod
    def inject_gamelog_from_file(loginjector: ILogInjector, logfile: str):
        f = open(logfile, mode='rt', encoding='utf-8')
        for line in f:
            if not line:
                continue
            LogUtil.inject_gamelog_from_text(loginjector, line)
        f.close()
