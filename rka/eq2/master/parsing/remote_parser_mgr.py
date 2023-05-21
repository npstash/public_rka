from __future__ import annotations

import threading
from threading import RLock
from typing import Dict, Iterable

from rka.components.cleanup import Closeable
from rka.eq2.master import IRuntime
from rka.eq2.master.control.master_bridge import MasterBridge
from rka.eq2.master.parsing import logger
from rka.eq2.parsing import ILogInjector, ILogParser
from rka.eq2.parsing.logparser import ParserSubscription
from rka.eq2.parsing.parser_mgr import IParserManager


class RemoteParserProxy(ILogParser):
    def __init__(self, master_bridge: MasterBridge, client_id: str):
        self.__master_bridge = master_bridge
        self.__client_id = client_id
        self.__parse_filters_lock = threading.RLock()
        self.__parse_filters: Dict[str, ParserSubscription] = dict()

    def __str__(self) -> str:
        return f'Remote parser proxy {self.__client_id}'

    def __send_remote_subsribe(self, parse_filter: str, preparsed_logs: bool) -> bool:
        connected, result = self.__master_bridge.send_parser_subscribe(self.__client_id, parse_filter, preparsed_logs)
        if not connected or not result or not result[0]:
            logger.info(f'subscribe for {parse_filter}, {preparsed_logs} failed in {self}: {connected}, {result}')
            return False
        logger.info(f'subscribed remotely \'{parse_filter}\', {preparsed_logs} in {self}: {connected}, {result}')
        return True

    def __send_remote_unsubsribe(self, parse_filter: str, preparsed_logs: bool) -> bool:
        connected = self.__master_bridge.send_parser_unsubscribe(self.__client_id, parse_filter, preparsed_logs)
        if not connected:
            logger.info(f'unsubscribe for {parse_filter}, {preparsed_logs} failed in {self}: {connected}')
            return False
        logger.info(f'unsubscribed remotely \'{parse_filter}\', {preparsed_logs} in {self}: {connected}')
        return True

    def subscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter not in self.__parse_filters:
                self.__parse_filters[parse_filter] = ParserSubscription(parse_filter)
            subscription = self.__parse_filters[parse_filter]
            is_empty = not subscription.has_increments()
            if is_empty:
                if not self.__send_remote_subsribe(parse_filter, preparsed_logs):
                    return False
            subscription.increment(preparsed_logs)
        logger.info(f'subscribed locally \'{parse_filter}\', {preparsed_logs} in {self}')
        return True

    def unsubscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter not in self.__parse_filters:
                return False
            subscription = self.__parse_filters[parse_filter]
            subscription.decrement(preparsed_logs)
            is_empty = not subscription.has_increments()
        logger.info(f'unsubscribed locally \'{parse_filter}\', {preparsed_logs} in {self}')
        if is_empty:
            if not self.__send_remote_unsubsribe(parse_filter, preparsed_logs):
                return False
        return True

    def unsubscribe_all(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter not in self.__parse_filters:
                return False
            subscription = self.__parse_filters[parse_filter]
            subscription.clear_increments(preparsed_logs)
            is_empty = not subscription.has_increments()
        logger.info(f'unsubscribed all locally \'{parse_filter}\', {preparsed_logs} in {self}')
        if is_empty:
            if not self.__send_remote_unsubsribe(parse_filter, preparsed_logs):
                return False
        return True

    def iter_filters(self) -> Iterable[str]:
        with self.__parse_filters_lock:
            for parse_filter, subscription in self.__parse_filters.items():
                yield parse_filter

    def get_parser_id(self) -> str:
        return self.__client_id

    def cleanup(self):
        pass

    def close(self):
        pass


class RemoteLogInjectorProxy(ILogInjector):
    def __init__(self, master_bridge: MasterBridge, client_id: str):
        self.__master_bridge = master_bridge
        self.__client_id = client_id

    def __str__(self) -> str:
        return f'Remote log injector proxy {self.__client_id}'

    def write_log(self, log_line: str):
        self.__master_bridge.send_testlog_inject(self.__client_id, log_line)

    def close(self):
        pass


class RemoteParserManager(Closeable, IParserManager):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=True)
        self.__runtime = runtime
        self.__lock = RLock()
        self.__parsers: Dict[str, RemoteParserProxy] = dict()
        self.__loginjectors: Dict[str, RemoteLogInjectorProxy] = dict()

    def __clients_debug_str(self) -> str:
        return ','.join((p.get_parser_id() for p in self.__parsers.values()))

    def get_parser(self, client_id: str) -> ILogParser:
        with self.__lock:
            if client_id not in self.__parsers:
                logger.fatal(f'Missing parser for {client_id}. Have parsers for: {self.__clients_debug_str()}')
            return self.__parsers[client_id]

    def get_loginjector(self, client_id: str) -> ILogInjector:
        with self.__lock:
            return self.__loginjectors[client_id]

    def register_remote_parser(self, client_id: str):
        logger.info(f'register_remote_parser: {client_id}. Have: {self.__clients_debug_str()}')
        with self.__lock:
            assert client_id not in self.__parsers.keys()
            assert client_id not in self.__loginjectors.keys()
            self.__parsers[client_id] = RemoteParserProxy(self.__runtime.master_bridge, client_id)
            self.__loginjectors[client_id] = RemoteLogInjectorProxy(self.__runtime.master_bridge, client_id)

    def unregister_remote_parser(self, client_id: str):
        logger.info(f'unregister_remote_parser: {client_id}. Have: {self.__clients_debug_str()}')
        with self.__lock:
            assert client_id in self.__parsers.keys()
            assert client_id in self.__loginjectors.keys()
            self.__parsers[client_id].close()
            self.__loginjectors[client_id].close()
            del self.__parsers[client_id]
            del self.__loginjectors[client_id]

    def close(self):
        with self.__lock:
            for parser in self.__parsers.values():
                parser.close()
            self.__parsers.clear()
            for loginjector in self.__loginjectors.values():
                loginjector.close()
            self.__loginjectors.clear()
        Closeable.close(self)
