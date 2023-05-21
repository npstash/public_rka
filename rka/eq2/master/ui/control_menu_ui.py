from __future__ import annotations

from enum import auto, Enum
from typing import Any, Iterable, Callable, Optional

from rka.components.ui.notification import INotificationService
from rka.components.ui.overlay import Severity, IOverlay
from rka.eq2.master import IRuntime


class ControlMenuUIType(Enum):
    OVERLAY = auto()
    NOTIFICATION = auto()

    def produce_ui(self, runtime: IRuntime) -> ControlMenuUI:
        if self is ControlMenuUIType.OVERLAY:
            return CMOverlayUI(runtime.overlay)
        if self is ControlMenuUIType.NOTIFICATION:
            return CMNotificationUI(runtime.notification_service)
        assert False, self


class ControlMenuUI(object):
    def select_option(self, title: str, options: Iterable[Any], result_cb: Callable[[Any], None]):
        raise NotImplementedError()

    def get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        raise NotImplementedError()

    def get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        raise NotImplementedError()

    def show_timer(self, name: str, duration: float, severity: Severity):
        raise NotImplementedError()

    def hide_timer(self, name: str):
        raise NotImplementedError()

    def log_event(self, event_str: str, severity: Severity):
        raise NotImplementedError()

    def is_onscreen(self) -> bool:
        raise NotImplementedError()


class CMOverlayUI(ControlMenuUI):
    def __init__(self, overlay: IOverlay):
        self.__overlay = overlay

    def select_option(self, title: str, options: Iterable[Any], result_cb: Callable[[Any], None]):
        self.__overlay.display_dialog(title=title, options=list(options), result_cb=result_cb)

    def get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        self.__overlay.get_text(title=title, result_cb=result_cb)

    def get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        self.__overlay.get_confirm(title=title, result_cb=result_cb)

    def show_timer(self, name: str, duration: float, severity: Severity):
        self.__overlay.start_timer(name=name, duration=duration, expire=0.0, severity=severity)

    def hide_timer(self, name: str):
        self.__overlay.del_timer(name=name)

    def log_event(self, event_str: str, severity: Severity):
        self.__overlay.log_event(event_text=event_str, severity=severity)

    def is_onscreen(self) -> bool:
        return True


class CMNotificationUI(ControlMenuUI):
    def __init__(self, notification: INotificationService):
        self.__notification = notification
        self.__pending_options = None
        self.__pending_query = None
        self.__pending_callback = None
        notification.set_callback_for_unmatched_commands(self.__notification_cb)

    def __reset(self):
        self.__pending_options = None
        self.__pending_query = None
        self.__pending_callback = None

    def __notification_cb(self, service: INotificationService, command: str):
        pending_options = self.__pending_options
        pending_query = self.__pending_query
        pending_callback = self.__pending_callback
        self.__reset()
        if pending_options:
            if command.isdecimal():
                option_num = int(command) - 1
                if option_num >= len(pending_options) or option_num < 0:
                    return
                option = pending_options[option_num]
                pending_callback(option)
            elif command in pending_options:
                pending_callback(command)
            else:
                service.post_notification(f'Unknown option, state is reset')
        elif pending_query:
            pending_callback(command)

    def select_option(self, title: str, options: Iterable[Any], result_cb: Callable[[Any], None]):
        self.__reset()
        self.__pending_options = list(options)
        self.__pending_callback = result_cb
        message = ''
        for i, option in enumerate(self.__pending_options):
            message += f'{i + 1}. {option}\n'
        self.__notification.post_notification(message)

    def get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        self.__reset()
        self.__pending_query = title
        self.__pending_callback = result_cb
        self.__notification.post_notification(f'Input data for "{title}":')

    def get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        self.__reset()
        self.__pending_query = title
        self.__pending_callback = lambda answer: result_cb('yes' in answer.lower() or 'ok' in answer.lower())
        self.__notification.post_notification(f'Question "{title}":')

    def show_timer(self, name: str, duration: float, severity: Severity):
        self.__notification.post_notification(f'Wait {duration} sec for {name}')

    def hide_timer(self, name: str):
        self.__notification.post_notification(f'Waiting for {name} interrupted')

    def log_event(self, event_str: str, severity: Severity):
        self.__notification.post_notification(event_str)

    def is_onscreen(self) -> bool:
        return False
