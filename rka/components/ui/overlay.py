from __future__ import annotations

import enum
from enum import auto
from typing import List, Callable, Any, Optional, Union

from rka.components.concurrency.workthread import RKAWorkerThread
from rka.components.ui.capture import Rect


class Severity(enum.IntEnum):
    Low = 0
    Normal = 1
    High = 2
    Critical = 3


class OvTimerStage(enum.IntEnum):
    Ready = 0
    Casting = 1
    Duration = 2
    Reuse = 3
    Expire = 4
    Expired = 5

    @staticmethod
    def get_case_insensitive(name: Union[str, int]) -> OvTimerStage:
        if isinstance(name, str):
            return OvTimerStage[name.capitalize()]
        elif isinstance(name, int):
            return OvTimerStage(name)
        assert False, name


class OvWarning:
    def __init__(self, stage: OvTimerStage, offset: float, action: Callable[[], None], user_object: Any = None):
        self.stage = stage
        self.offset = offset
        self.action = action
        self.user_object = user_object
        self.__fired = False

    def fire_warning(self, worker: RKAWorkerThread):
        worker.push_task(self.action)
        self.__fired = True

    def has_fired(self) -> bool:
        return self.__fired

    def reset(self):
        self.__fired = False


class OvPlotHandlerResult(enum.IntEnum):
    Continue = auto()
    Refresh = auto()
    Close = auto()


class OvPlotHandler:
    def plot(self, axes):
        raise NotImplementedError()

    def on_mouse_double_click(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
        raise NotImplementedError()

    def on_mouse_button_press(self, loc_x: float, loc_y: float, button) -> OvPlotHandlerResult:
        raise NotImplementedError()

    def on_mouse_button_release(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
        raise NotImplementedError()

    def on_mouse_move(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
        raise NotImplementedError()

    def on_close(self):
        raise NotImplementedError()


class IOverlay:
    def runloop(self):
        raise NotImplementedError()

    def queue_event(self, callback: Callable):
        raise NotImplementedError()

    def show(self):
        raise NotImplementedError()

    def hide(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def set_status(self, selection_id: int, status_name: str, severity: Severity):
        raise NotImplementedError()

    def get_selection_id(self) -> int:
        raise NotImplementedError()

    def get_max_selection_id(self) -> int:
        raise NotImplementedError()

    def set_selection_id(self, selection_id: int):
        raise NotImplementedError()

    def start_timer(self, name: str, duration: float, casting: Optional[float] = None, reuse: Optional[float] = None,
                    expire: Optional[float] = None, direction=-1, severity=Severity.Low, warnings: Optional[List[OvWarning]] = None,
                    replace_stage=OvTimerStage.Ready):
        raise NotImplementedError()

    def del_timer(self, name: str):
        raise NotImplementedError()

    def log_event(self, event_text: Optional[str], severity: Severity = Severity.Low, event_id: Optional[str] = None):
        raise NotImplementedError()

    def display_warning(self, warning_text: str, duration: Optional[float] = None, conditional_text: Optional[str] = None):
        raise NotImplementedError()

    def display_dialog(self, title: str, options: List[Any], result_cb: Callable[[Any], None]):
        raise NotImplementedError()

    def display_plot(self, title: str, handler: OvPlotHandler):
        raise NotImplementedError()

    def get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        raise NotImplementedError()

    def get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        raise NotImplementedError()

    def update_parse_window(self, parse: str):
        raise NotImplementedError()

    def set_screen_tint(self, r: int, g: int, b: int, a: int, duration: float):
        raise NotImplementedError()

    def get_window_rect(self) -> Rect:
        raise NotImplementedError()

    def is_capture_safe(self, capture_rect: Rect) -> bool:
        raise NotImplementedError()
