import threading
import traceback
from time import sleep, time
from typing import List, Optional

import win32file
import win32pipe

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.injector import IInjector
from rka.components.io.log_service import LogService, LogLevel
from rka.log_configs import LOG_INJECTIONS

logger = LogService(LOG_INJECTIONS)


class InjectedCommand:
    def __init__(self, command: str, once: bool, passthrough: bool, duration: Optional[float], command_id: str):
        self.command = command
        self.once = once
        self.passthrough = passthrough
        self.duration = duration
        self.command_id = command_id
        self.last_inject_time: Optional[float] = None
        self.__timestamp = time()

    def expired(self) -> bool:
        if self.duration is None:
            return False
        return time() > self.__timestamp + self.duration

    def describe(self):
        return f'"{self.command}"'.replace('\n', ';')


class NamedPipeInjector(Closeable, IInjector):
    __current_injectros = set()

    def __init__(self, path_name: str, prefix: str, postfix: str, injectionwait=0.0, singleusedelay=0.0):
        assert path_name not in NamedPipeInjector.__current_injectros
        Closeable.__init__(self, explicit_close=False)
        self.__pipe_name = path_name
        self.__injection_wait = injectionwait
        self.__singleuse_delay = singleusedelay
        self.__last_singleuse_time = time()
        self.__running = False
        self.__error_count = 0
        self.__data_lock = threading.Condition()
        self.__commands: List[InjectedCommand] = list()
        self.__injection_prefix: Optional[List[str]] = None
        self.__injection_postfix: Optional[List[str]] = None
        logger.info(f'creating injector pipe at {path_name}')
        try:
            self.__pipe = win32pipe.CreateNamedPipe(
                path_name,
                win32pipe.PIPE_ACCESS_OUTBOUND, win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 1024, 1024, 0, None)
        except Exception as e:
            logger.error(f'error while creating pipe {e}')
            raise e
        RKAThread(name=f'Named pipe injector {path_name}', target=self.__accept_loop).start()
        self.set_injection_prefix(prefix)
        self.set_injection_postfix(postfix)
        NamedPipeInjector.__current_injectros.add(self.__pipe_name)

    def __get_data_for_next_write(self) -> Optional[str]:
        now = time()
        diff = now - self.__last_singleuse_time
        if diff < self.__singleuse_delay:
            logger.info(f'Skip data feed, too early. Diff={diff}, min. {self.__singleuse_delay}')
            return None
        with self.__data_lock:
            logger.detail(f'preparing data for response')
            if self.__injection_wait > 0.0:
                self.__data_lock.wait(self.__injection_wait)
            result = ''
            if self.__injection_prefix is not None:
                for line in self.__injection_prefix:
                    result += line.strip() + '\n'
            blocking_injection = False
            remove_commands: List[InjectedCommand] = list()
            # single commands first, until a blocking one is found
            for inj_cmd in self.__commands:
                if inj_cmd.expired():
                    remove_commands.append(inj_cmd)
                    continue
                if blocking_injection:
                    # do not break, allow adding other cmds to remove_commands
                    continue
                result += inj_cmd.command.strip() + '\n'
                if inj_cmd.once:
                    remove_commands.append(inj_cmd)
                    logger.debug(f'one-shot injection: {inj_cmd.describe()}')
                    if self.__singleuse_delay:
                        self.__last_singleuse_time = now
                if not inj_cmd.passthrough:
                    blocking_injection = True
                    logger.debug(f'blocking injection: {inj_cmd.describe()}')
            # remove all singles, which were before the blocking one (incluside)
            for inj_cmd in remove_commands:
                logger.debug(f'removing command: "{inj_cmd.describe()}"')
                self.__commands.remove(inj_cmd)
            # append postfix
            if not blocking_injection:
                if self.__injection_postfix is not None:
                    logger.detail(f'appending injection postfix')
                    for line in self.__injection_postfix:
                        result += line.strip() + '\n'
        return result

    def __accept_loop(self):
        self.__running = True
        while self.__running:
            try:
                logger.detail(f'waiting for connection on pipe')
                r = win32pipe.ConnectNamedPipe(self.__pipe, None)
                if r != 0:
                    logger.warn(f'ConnectNamedPipe returns error {r}')
                    raise IOError()
                if not self.__running:
                    logger.info(f'writing cancelled, exiting')
                    break
                logger.detail(f'client connected on pipe, building response')
                data = self.__get_data_for_next_write()
                if data:
                    win32file.WriteFile(self.__pipe, str.encode(data))
                    if logger.get_level() <= LogLevel.DETAIL:
                        logger.detail(f'Data written to pipe:\n"{data}"')
                win32pipe.DisconnectNamedPipe(self.__pipe)
            except Exception as e:
                if not isinstance(e, IOError):
                    traceback.print_exc()
                if not self.__running:
                    break
                logger.error(f'error while communicating with client {e}')
                if self.__error_count >= 3:
                    logger.error(f'bailing out')
                    self.__running = False
                    raise e
                sleep(3.0)
                self.__error_count += 1

    def __disconnect(self):
        # noinspection PyBroadException
        try:
            handle = win32file.CreateFile(self.__pipe_name, win32file.GENERIC_READ, 0, None, win32file.OPEN_EXISTING, 0, None)
            win32file.CloseHandle(handle)
        except Exception:
            pass

    def get_name(self) -> str:
        return self.__pipe_name

    def set_injection_prefix(self, injection_prefix):
        with self.__data_lock:
            injection_prefix_str = str(injection_prefix).replace('\n', ';')
            logger.detail(f'set_injection_prefix: {self.__pipe_name} PRE-fix set {injection_prefix_str}')
            if isinstance(injection_prefix, str):
                self.__injection_prefix = [injection_prefix]
            elif isinstance(injection_prefix, list):
                self.__injection_prefix = injection_prefix.copy()
            else:
                self.__injection_prefix = None
            self.__data_lock.notify()

    def set_injection_postfix(self, injection_postfix):
        with self.__data_lock:
            injection_postfix_str = str(injection_postfix).replace('\n', ';')
            logger.detail(f'set_injection_postfix: {self.__pipe_name} POST-fix set {injection_postfix_str}')
            if isinstance(injection_postfix, str):
                self.__injection_postfix = [injection_postfix]
            elif isinstance(injection_postfix, list):
                self.__injection_postfix = injection_postfix.copy()
            else:
                self.__injection_postfix = None
            self.__data_lock.notify()

    def inject_command(self, command: str, command_id: str, once: bool, pass_through: bool, duration: Optional[float] = None) -> bool:
        if duration is None:
            duration = 15.0
        replaced = False
        with self.__data_lock:
            for ic in self.__commands:
                if ic.command_id == command_id:
                    self.__commands.remove(ic)
                    replaced = True
                    break
            command_str = str(command).replace('\n', ';')
            logger.info(f'inject_command: once: {once}, pass: {pass_through}, duration: {duration}, replaced: {replaced}, cmd: {command_str}')
            ic = InjectedCommand(command=command, once=once, passthrough=pass_through, duration=duration, command_id=command_id)
            self.__commands.append(ic)
            self.__data_lock.notify()
        return True

    def remove_command(self, command_id) -> bool:
        with self.__data_lock:
            for ic in self.__commands:
                if ic.command_id == command_id:
                    self.__commands.remove(ic)
                    ic_str = str(ic).replace('\n', ';')
                    logger.info(f'remove_command: cmd {ic_str}')
                    return True
        logger.info(f'remove_command: could not remove {command_id}')
        return False

    def close(self):
        # noinspection PyBroadException
        try:
            logger.info(f'closing injection pipe')
            self.__running = False
            with self.__data_lock:
                self.__data_lock.notify()
            self.__disconnect()
            win32file.CloseHandle(self.__pipe)
            logger.info(f'closed injection pipe')
        except Exception as e:
            logger.error(f'error while closing pipe {e}')
        if self.__pipe_name in NamedPipeInjector.__current_injectros:
            NamedPipeInjector.__current_injectros.remove(self.__pipe_name)
        else:
            logger.info(f'injector already removed {self}')
        Closeable.close(self)
