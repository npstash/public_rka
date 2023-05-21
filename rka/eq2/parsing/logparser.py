from __future__ import annotations

import threading
import time
from typing import Dict, Match, Optional, Iterable

import regex as re

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.events.event_system import EventSystem
from rka.components.io.filemonitor import IActiveFileMonitorBroker
from rka.components.io.log_service import LogLevel
from rka.eq2.parsing import ILogReader, IMonitoringLogParser, logger
from rka.eq2.shared.client_events import ClientEvents


class ParserSubscription:
    def __init__(self, parse_filter: str):
        self.parse_filter = parse_filter
        self.subscriber_count_for_preparsed_logs = 0
        self.subscriber_count_for_not_preparsed_logs = 0
        try:
            self.regex = re.compile(parse_filter)
        except re.error:
            logger.error(f'Error compiling: {parse_filter}')
            raise

    def increment(self, parse_preparsed_logs: bool):
        if parse_preparsed_logs:
            self.subscriber_count_for_preparsed_logs += 1
        else:
            self.subscriber_count_for_not_preparsed_logs += 1

    def decrement(self, parse_preparsed_logs: bool):
        if parse_preparsed_logs:
            self.subscriber_count_for_preparsed_logs -= 1
        else:
            self.subscriber_count_for_not_preparsed_logs -= 1

    def has_increments(self) -> bool:
        return self.subscriber_count_for_not_preparsed_logs > 0 or self.subscriber_count_for_preparsed_logs > 0

    def clear_increments(self, parse_preparsed_logs: bool):
        if parse_preparsed_logs:
            self.subscriber_count_for_preparsed_logs = 0
        else:
            self.subscriber_count_for_not_preparsed_logs = 0

    def match(self, log_line: str, preparsed_log: bool) -> Optional[Match]:
        if preparsed_log:
            if self.subscriber_count_for_preparsed_logs > 0:
                return self.regex.match(log_line)
        # preparsed log subscribers - means they match both preparesed and non-preparsed
        else:
            if self.subscriber_count_for_not_preparsed_logs > 0 or self.subscriber_count_for_preparsed_logs > 0:
                return self.regex.match(log_line)
        return None


class LogParser(Closeable, IMonitoringLogParser):
    ACTIVE_CHECK_TIME = 0.05
    INACTIVE_CHECK_TIME = 2.0

    def __init__(self, parser_id: str, log_reader: ILogReader, event_system: EventSystem):
        Closeable.__init__(self, explicit_close=True)
        self.__parser_id = parser_id
        self.__event_system = event_system
        self.__keep_running = True
        self.__parse_filters_lock = threading.RLock()
        self.__parse_filters: Dict[str, ParserSubscription] = dict()
        self.__active = False
        self.__check_time = LogParser.INACTIVE_CHECK_TIME
        self.__monitor_manager = None
        self.__log_reader = log_reader
        RKAThread(name=f'Parse thread of {self}', target=self.__main_loop).start()

    def __str__(self) -> str:
        return f'LogParser[{self.__parser_id}] on [{self.__log_reader.reader_name()}]'

    def _on_activated(self):
        pass

    def _on_deactivated(self):
        pass

    def set_active(self, active: bool):
        old_active = self.__active
        logger.debug(f'changing active state from {old_active} to {active} in {self}')
        if active == self.__active:
            return
        self.__active = active
        if active:
            self.__check_time = self.ACTIVE_CHECK_TIME
            if self.__monitor_manager is not None:
                self.__monitor_manager.file_activated(self)
            self._on_activated()
        else:
            self.__check_time = self.INACTIVE_CHECK_TIME
            self._on_deactivated()

    # noinspection PyMethodMayBeStatic
    def _preparse_log_line(self, log_line: str, timestamp: float) -> bool:
        # for overriding
        return False

    def __parse_log_line(self, log_line: str, timestamp: float) -> bool:
        preparsed_log = self._preparse_log_line(log_line, timestamp)
        subscriptions_to_notify = list()
        with self.__parse_filters_lock:
            for subscription in self.__parse_filters.values():
                match = subscription.match(log_line, preparsed_log)
                if match:
                    if logger.get_level() <= LogLevel.DETAIL:
                        count_1 = subscription.subscriber_count_for_preparsed_logs
                        count_2 = subscription.subscriber_count_for_not_preparsed_logs
                        logger.detail(f'Parser matched "{subscription.parse_filter}", #prep: {count_1}, #non-prep: {count_2} in {self}')
                    subscriptions_to_notify.append((match, subscription.parse_filter))
        event_bus = None
        if subscriptions_to_notify:
            event_bus = self.__event_system.get_bus(self.__parser_id)
        for match, parse_filter in subscriptions_to_notify:
            event = ClientEvents.PARSER_MATCH(client_id=self.__parser_id, parse_filter=parse_filter, preparsed_log=preparsed_log,
                                              matched_text=log_line, timestamp=timestamp)
            if not event_bus:
                logger.warn(f'No bus available to post parser match: "{parse_filter}" in "{log_line}"')
                continue
            event_bus.post(event)
        return bool(subscriptions_to_notify)

    def __main_loop(self):
        while self.__keep_running:
            log = self.__log_reader.read_log_with_timestamp()
            if not log:
                time.sleep(self.__check_time)
                continue
            log_text, log_timestamp = log
            if not self.__active:
                self.set_active(True)
            if log_text:
                self.__parse_log_line(log_text, log_timestamp)
        self.__log_reader.close()

    def subscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter not in self.__parse_filters:
                logger.info(f'Adding filter \'{parse_filter}\', {preparsed_logs} to {self}')
                self.__parse_filters[parse_filter] = ParserSubscription(parse_filter)
            else:
                logger.info(f'Incrementing filter \'{parse_filter}\', {preparsed_logs} to {self}')
            subscription = self.__parse_filters[parse_filter]
            subscription.increment(preparsed_logs)
            total_count = subscription.subscriber_count_for_not_preparsed_logs + subscription.subscriber_count_for_preparsed_logs
            logger.detail(f'Total increments {total_count} for \'{parse_filter}\', {preparsed_logs}')
        return True

    def unsubscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter in self.__parse_filters:
                subscription = self.__parse_filters[parse_filter]
                subscription.decrement(preparsed_logs)
                total_count = subscription.subscriber_count_for_not_preparsed_logs + subscription.subscriber_count_for_preparsed_logs
                logger.detail(f'Total increments {total_count} for \'{parse_filter}\', {preparsed_logs}')
                if subscription.has_increments():
                    logger.info(f'Decrementing filter \'{parse_filter}\', {preparsed_logs} from {self}')
                else:
                    logger.info(f'Removing filter \'{parse_filter}\', {preparsed_logs} from {self}')
                    del self.__parse_filters[parse_filter]
                return True
            else:
                logger.info(f'Cannot remove, filter not found \'{parse_filter}\', {preparsed_logs} from {self}')
        return False

    def unsubscribe_all(self, parse_filter: str, preparsed_logs=False) -> bool:
        with self.__parse_filters_lock:
            if parse_filter in self.__parse_filters:
                logger.info(f'Removing all filter \'{parse_filter}\', {preparsed_logs} from {self}')
                subscription = self.__parse_filters[parse_filter]
                subscription.clear_increments(preparsed_logs)
                del self.__parse_filters[parse_filter]
                return True
            else:
                logger.info(f'Cannot remove all, filter not found \'{parse_filter}\', {preparsed_logs} from {self}')
        return False

    def iter_filters(self) -> Iterable[str]:
        with self.__parse_filters_lock:
            for parse_filter, subscription in self.__parse_filters.items():
                yield parse_filter

    def get_monitor_id(self) -> str:
        return self.__parser_id

    def get_parser_id(self) -> str:
        return self.__parser_id

    def set_broker(self, manager: IActiveFileMonitorBroker):
        assert self.__monitor_manager is None
        self.__monitor_manager = manager
        if self.__active:
            self.__monitor_manager.file_activated(self)

    def another_file_activated(self):
        self.set_active(False)
        self.cleanup()

    def cleanup(self):
        with self.__parse_filters_lock:
            for subscriber in self.__parse_filters.values():
                subscriber.clear_increments(False)
                subscriber.clear_increments(True)

    def close(self):
        self.__monitor_manager = None
        self.__keep_running = False
        self.__log_reader.close()
        self.cleanup()
        Closeable.close(self)
