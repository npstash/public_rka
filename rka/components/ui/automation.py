import enum
from typing import Optional


class MouseCoordMode(enum.IntEnum):
    ABSOLUTE = 0
    RELATIVE_WINDOW = 1
    RELATIVE_CLIENT_AREA = 2


class IAutomation:
    def modifier_down(self, modifier: str):
        raise NotImplementedError()

    def modifier_up(self, modifier: str):
        raise NotImplementedError()

    def send_key(self, key: str, key_type_delay: Optional[float] = None):
        raise NotImplementedError()

    def send_text(self, text: str, key_type_delay: Optional[float] = None):
        raise NotImplementedError()

    def send_key_spec(self, key_spec: str, key_type_delay: Optional[float] = None):
        raise NotImplementedError()

    def mouse_move(self, x: int, y: int, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW):
        raise NotImplementedError()

    def mouse_click(self, button: str, x: Optional[int] = None, y: Optional[int] = None, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW,
                    modifiers: Optional[str] = None):
        raise NotImplementedError()

    def mouse_double_click(self):
        raise NotImplementedError()

    def mouse_down(self, button: str):
        raise NotImplementedError()

    def mouse_up(self, button: str):
        raise NotImplementedError()

    def mouse_drag(self, button: str, x1: int, y1: int, x2: int, y2: int, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW):
        raise NotImplementedError()

    def mouse_scroll(self, scroll_up: bool, clicks: int):
        raise NotImplementedError()

    def get_mouse_pos(self, coord_mode=MouseCoordMode.RELATIVE_WINDOW) -> (int, int):
        raise NotImplementedError()

    def activate_window(self, title: str, win_wait: Optional[float] = None, maximize=False) -> bool:
        raise NotImplementedError()

    def is_window_active(self, title: str) -> bool:
        raise NotImplementedError()
