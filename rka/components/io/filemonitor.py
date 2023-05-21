from __future__ import annotations

from typing import Dict, Optional

from rka.components.cleanup import Closeable


class IActiveFileMonitorBroker(object):
    def file_activated(self, activated_monitor: IFileMonitor):
        raise NotImplementedError


class IActiveFileMonitorObserver(object):
    def file_activated(self, deactivated_monitor: IFileMonitor, activated_monitor: IFileMonitor):
        raise NotImplementedError


class IFileMonitor(object):
    def get_monitor_id(self) -> str:
        raise NotImplementedError

    def set_broker(self, manager: IActiveFileMonitorBroker):
        raise NotImplementedError

    def another_file_activated(self):
        raise NotImplementedError


class FileMonitorManager(IActiveFileMonitorBroker, Closeable):
    def __init__(self, file_changed_cb: IActiveFileMonitorObserver):
        Closeable.__init__(self, explicit_close=False)
        self.__file_changed_cb = file_changed_cb
        self.__file_monitors: Dict[str, IFileMonitor] = dict()
        self.__current_monitor: Optional[IFileMonitor] = None

    def add_monitor(self, file_monitor: IFileMonitor):
        monitor_id = file_monitor.get_monitor_id()
        self.__file_monitors[monitor_id] = file_monitor
        file_monitor.set_broker(self)

    def remove_monitor(self, file_monitor: IFileMonitor):
        if self.__current_monitor == file_monitor:
            self.__current_monitor = None
        monitor_id = file_monitor.get_monitor_id()
        del self.__file_monitors[monitor_id]

    def file_activated(self, activated_monitor: IFileMonitor):
        self.__file_changed_cb.file_activated(self.__current_monitor, activated_monitor)
        self.__current_monitor = activated_monitor
        for other_file_monitor in self.__file_monitors.values():
            if activated_monitor != other_file_monitor:
                other_file_monitor.another_file_activated()

    def get_monitor(self, monitor_id: str) -> IFileMonitor:
        return self.__file_monitors[monitor_id] if monitor_id is not None else None

    def close(self):
        for file_monitor in self.__file_monitors.values():
            if isinstance(file_monitor, Closeable):
                file_monitor.close()
        Closeable.close(self)
