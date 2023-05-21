from __future__ import annotations

from threading import RLock
from typing import Dict, Optional

from rka.components.cleanup import Closeable
from rka.components.io.filemonitor import IActiveFileMonitorObserver, FileMonitorManager, IFileMonitor
from rka.eq2.parsing import ILogInjector, ILogParser, IMonitoringLogParser, logger
from rka.eq2.shared.host import HostConfig


class IParserManager:
    def get_parser(self, client_id: str) -> ILogParser:
        raise NotImplementedError()

    def get_loginjector(self, client_id: str) -> ILogInjector:
        raise NotImplementedError()


class ParserManager(IParserManager, Closeable, IActiveFileMonitorObserver):
    def __init__(self, host_config: HostConfig):
        Closeable.__init__(self, explicit_close=False)
        self.__lock = RLock()
        self.__parsers: Dict[str, IMonitoringLogParser] = dict()
        self.__loginjectors: Dict[str, ILogInjector] = dict()
        self.__host_config = host_config
        self.__monitor_mgr = FileMonitorManager(self)
        self.__delegated_observer: Optional[IActiveFileMonitorObserver] = None

    def set_file_obeserver(self, file_observer: IActiveFileMonitorObserver):
        self.__delegated_observer = file_observer

    def file_activated(self, deactivated_monitor: IFileMonitor, activated_monitor: IFileMonitor):
        if self.__delegated_observer is not None:
            self.__delegated_observer.file_activated(deactivated_monitor, activated_monitor)

    def get_parser(self, client_id: str) -> IMonitoringLogParser:
        with self.__lock:
            return self.__parsers[client_id]

    def get_loginjector(self, client_id: str) -> ILogInjector:
        with self.__lock:
            return self.__loginjectors[client_id]

    def register_parser(self, log_parser: IMonitoringLogParser, log_injector: ILogInjector):
        client_id = log_parser.get_parser_id()
        parser_to_close = None
        injector_to_close = None
        with self.__lock:
            if client_id in self.__parsers:
                logger.error(f'register_parser: parser already registered for {client_id}')
                parser_to_close = self.__parsers[client_id]
            if client_id in self.__parsers:
                logger.error(f'register_parser: injector already registered for {client_id}')
                injector_to_close = self.__loginjectors[client_id]
            self.__parsers[client_id] = log_parser
            self.__loginjectors[client_id] = log_injector
        self.__monitor_mgr.add_monitor(log_parser)
        if parser_to_close:
            parser_to_close.close()
        if injector_to_close:
            injector_to_close.close()

    def unregister_parser(self, client_id: str):
        with self.__lock:
            if client_id in self.__parsers:
                log_parser = self.__parsers[client_id]
                del self.__parsers[client_id]
            else:
                logger.error(f'unregister_parser: log parser not found for {client_id}')
                log_parser = None
            if client_id in self.__loginjectors:
                log_injector = self.__loginjectors[client_id]
                del self.__loginjectors[client_id]
            else:
                logger.error(f'unregister_parser: log injector not found for {client_id}')
                log_injector = None
        if log_parser:
            log_parser.close()
        if log_injector:
            log_injector.close()
        self.__monitor_mgr.remove_monitor(log_parser)

    def close(self):
        self.__monitor_mgr.close()
        Closeable.close(self)
