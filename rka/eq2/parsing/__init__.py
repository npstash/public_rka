from __future__ import annotations

from typing import Optional, Tuple, Iterable

from rka.components.io.filemonitor import IFileMonitor
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_PARSING

logger = LogService(LOG_PARSING)


class ILogReader:
    def interrupt(self):
        raise NotImplementedError()

    def read_log_with_timestamp(self) -> Optional[Tuple[Optional[str], float]]:
        raise NotImplementedError()

    def wait_until_empty(self):
        raise NotImplementedError()

    def clear_logs(self):
        raise NotImplementedError()

    def reader_name(self) -> str:
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class ILogInjector:
    def write_log(self, log_line: str):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class ILogParser:
    def subscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        raise NotImplementedError()

    def unsubscribe(self, parse_filter: str, preparsed_logs=False) -> bool:
        raise NotImplementedError()

    def unsubscribe_all(self, parse_filter: str, preparsed_logs=False) -> bool:
        raise NotImplementedError()

    def get_parser_id(self) -> str:
        raise NotImplementedError()

    def iter_filters(self) -> Iterable[str]:
        raise NotImplementedError()

    def cleanup(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class ILogReaderWriter(ILogReader, ILogInjector):
    pass


# noinspection PyAbstractClass
class IMonitoringLogParser(ILogParser, IFileMonitor):
    def set_active(self, active: bool):
        raise NotImplementedError()
