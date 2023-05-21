from time import sleep
from typing import Tuple, Optional

import autoit
import win32api
import win32con
import win32gui
import win32process
from autoit import AutoItError

from rka.components.io.log_service import LogService
from rka.components.ui.automation import IAutomation, MouseCoordMode
from rka.components.ui.hotkey_util import Binding
from rka.log_configs import LOG_INPUT_EVENTS

logger = LogService(LOG_INPUT_EVENTS)

_autoit_modifiers_down = {'alt': '{ALTDOWN}',
                          'control': '{CTRLDOWN}',
                          'shift': '{SHIFTDOWN}',
                          'win': '{LWINDOWN}',
                          }

_autoit_modifiers_up = {'alt': '{ALTUP}',
                        'control': '{CTRLUP}',
                        'shift': '{SHIFTUP}',
                        'win': '{LWINUP}',
                        }

_SLEEP_BEFORE_MODIFIER_DOWN = 0.2
_SLEEP_AFTER_MODIFIER_DOWN = 0.1
_SLEEP_BEFORE_MODIFIER_UP = 0.5
_SLEEP_AFTER_KEYTYPE = 0.05
_SLEEP_AFTER_MOUSE_DOWN = 0.15
_SLEEP_AFTER_MOUSE_MOVE = 0.15
_SLEEP_AFTER_MOUSE_CLICK = 0.1
_SLEEP_DOUBLECLICK_GAP = 0.1

_special_autoit_key_mapping = {
    'numpad1': 'NUMPAD1',
    'numpad2': 'NUMPAD2',
    'numpad3': 'NUMPAD3',
    'numpad4': 'NUMPAD4',
    'numpad5': 'NUMPAD5',
    'numpad6': 'NUMPAD6',
    'numpad7': 'NUMPAD7',
    'numpad8': 'NUMPAD8',
    'numpad9': 'NUMPAD9',
    'numpad0': 'NUMPAD0',
    'divide': 'NUMPADDIV',
    'multiply': 'NUMPADMULT',
    'substract': 'NUMPADSUB',
    'add': 'NUMPADADD',
    'space': 'SPACE',
    'backspace': 'BACKSPACE',
    'delete': 'DELETE',
    'enter': 'ENTER',
    'escape': 'ESC',
    'tab': 'TAB',
    'F1': 'F1',
    'F2': 'F2',
    'F3': 'F3',
    'F4': 'F4',
    'F5': 'F5',
    'F6': 'F6',
    'F7': 'F7',
    'F8': 'F8',
    'F9': 'F9',
    'F10': 'F10',
    'F11': 'F11',
    'F12': 'F12',
}


def _get_autoit_key(key: str) -> Tuple[bool, str]:
    if key.lower() in _special_autoit_key_mapping.keys():
        return True, _special_autoit_key_mapping[key]
    return False, key


def _autoit_error_consume(func):
    def consume_exceptions(*_args, **_kwargs):
        # noinspection PyBroadException
        try:
            return func(*_args, **_kwargs)
        except AutoItError as e:
            logger.error(f'error processing autoit command {e}')
        return None

    return consume_exceptions


def _autoit_mouse_coord_mode(coord_mode: MouseCoordMode) -> int:
    if coord_mode == MouseCoordMode.ABSOLUTE:
        return 1
    if coord_mode == MouseCoordMode.RELATIVE_CLIENT_AREA:
        return 2
    return 0


class AutoitWin32GuiAutomation(IAutomation):
    @_autoit_error_consume
    def modifier_down(self, modifier: str):
        autoit.send(_autoit_modifiers_down[modifier.lower()])
        sleep(0.1)

    @_autoit_error_consume
    def modifier_up(self, modifier: str):
        sleep(0.1)
        autoit.send(_autoit_modifiers_up[modifier.lower()])

    @_autoit_error_consume
    def send_key(self, key: str, key_type_delay: Optional[float] = None):
        special, autoit_key = _get_autoit_key(key)
        if special:
            autoit.send(f'{{{autoit_key}}}')
        else:
            autoit.send(key)
        if key_type_delay:
            sleep(key_type_delay)
        else:
            sleep(_SLEEP_AFTER_KEYTYPE)

    _characters_with_shift = {
        '!': '1',
        '@': '2',
        '#': '3',
        '$': '4',
        '%': '5',
        '^': '6',
        '&': '7',
        '*': '8',
        '(': '9',
        ')': '0',
        '_': '-',
        '+': '=',
        '{': '[',
        '}': ']',
        ':': ';',
        '"': '\'',
        '<': ',',
        '>': '.',
        '?': '/',
        '|': '\\',
        '~': '`',
    }

    def send_text(self, text: str, key_type_delay: Optional[float] = None):
        logger.debug(f'send_text: {text} {key_type_delay}')
        for c in text:
            if c.isupper() or c in AutoitWin32GuiAutomation._characters_with_shift.keys():
                sleep(_SLEEP_BEFORE_MODIFIER_DOWN)
                autoit.send(_autoit_modifiers_down['shift'])
                sleep(_SLEEP_AFTER_MODIFIER_DOWN)
                if c.isupper():
                    send_c = c.lower()
                else:
                    send_c = AutoitWin32GuiAutomation._characters_with_shift[c]
                self.send_key(send_c, key_type_delay)
                sleep(_SLEEP_BEFORE_MODIFIER_UP)
                autoit.send(_autoit_modifiers_up['shift'])
            else:
                self.send_key(c, key_type_delay)

    @_autoit_error_consume
    def send_key_spec(self, key_spec: str, key_type_delay: Optional[float] = None):
        logger.debug(f'send_key_spec: {key_spec} {key_type_delay}')
        binding = Binding.parse_hotkey_spec(key_spec)
        any_modifier = binding.control or binding.alt or binding.shift or binding.win
        if binding.down:
            if any_modifier:
                sleep(_SLEEP_BEFORE_MODIFIER_DOWN)
            if binding.alt:
                autoit.send(_autoit_modifiers_down['alt'])
            if binding.control:
                autoit.send(_autoit_modifiers_down['control'])
            if binding.shift:
                autoit.send(_autoit_modifiers_down['shift'])
            if binding.win:
                autoit.send(_autoit_modifiers_down['win'])
            if any_modifier:
                sleep(_SLEEP_AFTER_MODIFIER_DOWN)
        special, autoit_key = _get_autoit_key(binding.key)
        if binding.down and binding.up:
            if key_type_delay is None:
                self.send_key(binding.key)
                sleep(_SLEEP_AFTER_KEYTYPE)
            else:
                self.send_key(f'{{{autoit_key} down}}')
                sleep(key_type_delay)
                self.send_key(f'{{{autoit_key} up}}')
        elif binding.down:
            self.send_key(f'{{{autoit_key} down}}')
        elif binding.up:
            self.send_key(f'{{{autoit_key} up}}')
        if binding.up:
            if any_modifier:
                sleep(_SLEEP_BEFORE_MODIFIER_UP)
            if binding.win:
                autoit.send(_autoit_modifiers_up['win'])
            if binding.shift:
                autoit.send(_autoit_modifiers_up['shift'])
            if binding.control:
                autoit.send(_autoit_modifiers_up['control'])
            if binding.alt:
                autoit.send(_autoit_modifiers_up['alt'])

    @_autoit_error_consume
    def mouse_move(self, x: int, y: int, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW):
        speed = speed if speed is not None else 2
        logger.debug(f'mouse_move: {x} {y} {speed} {coord_mode}')
        autoit.opt('MouseCoordMode', _autoit_mouse_coord_mode(coord_mode))
        autoit.mouse_move(x, y, speed=speed)
        sleep(_SLEEP_AFTER_MOUSE_DOWN)

    @_autoit_error_consume
    def mouse_click(self, button: str, x: Optional[int] = None, y: Optional[int] = None, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW,
                    modifiers: Optional[str] = None):
        speed = speed if speed is not None else 2
        logger.debug(f'mouse_click: {button} {x} {y} {speed} {coord_mode} {modifiers}')
        autoit.opt('MouseCoordMode', _autoit_mouse_coord_mode(coord_mode))
        if modifiers:
            modifiers = modifiers.replace(';', ',')
            modifiers = modifiers.replace(' ', ',')
            split_modifiers = modifiers.split(',')
            if split_modifiers:
                sleep(_SLEEP_BEFORE_MODIFIER_DOWN)
            for modifier in split_modifiers:
                if modifier not in _autoit_modifiers_down.keys():
                    logger.warn(f'Unknown modifier for mouse click: {modifier}')
                    continue
                logger.debug(f'Pressing modifier for mouse clock: {modifier}')
                autoit.send(_autoit_modifiers_up[modifier])
                sleep(0.05)
                autoit.send(_autoit_modifiers_down[modifier])
            if split_modifiers:
                sleep(_SLEEP_AFTER_MODIFIER_DOWN * 4)
        if x is not None and y is not None:
            autoit.mouse_move(x, y, speed=speed)
            sleep(_SLEEP_AFTER_MOUSE_MOVE)
        autoit.mouse_down(button)
        sleep(_SLEEP_AFTER_MOUSE_CLICK)
        autoit.mouse_up(button)
        if modifiers:
            sleep(_SLEEP_BEFORE_MODIFIER_UP)
            for modifier in modifiers:
                if modifier not in _autoit_modifiers_down.keys():
                    continue
                autoit.send(_autoit_modifiers_up[modifier])
                sleep(0.05)

    @_autoit_error_consume
    def mouse_double_click(self):
        logger.detail('mouse_double_click')
        autoit.mouse_click(button='left')
        sleep(_SLEEP_DOUBLECLICK_GAP)
        autoit.mouse_click(button='left')

    @_autoit_error_consume
    def mouse_down(self, button: str):
        logger.detail(f'mouse_down: {button}')
        autoit.mouse_down(button)
        sleep(_SLEEP_AFTER_MOUSE_DOWN)

    @_autoit_error_consume
    def mouse_up(self, button: str):
        logger.detail(f'mouse_up: {button}')
        autoit.mouse_up(button)

    @_autoit_error_consume
    def mouse_drag(self, button: str, x1, y1, x2, y2, speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW):
        logger.detail(f'mouse_drag: {x1}, {y1}, {x2}, {y2}, {speed}, {coord_mode}')
        autoit.opt('MouseCoordMode', _autoit_mouse_coord_mode(coord_mode))
        autoit.mouse_click_drag(x1, y1, x2, y2, button, speed)
        sleep(_SLEEP_AFTER_MOUSE_DOWN)

    @_autoit_error_consume
    def mouse_scroll(self, scroll_up: bool, clicks: int):
        logger.detail(f'mouse_scroll: {scroll_up}, {clicks}')
        autoit.mouse_wheel('up' if scroll_up else 'down', clicks)

    @_autoit_error_consume
    def get_mouse_pos(self, coord_mode=MouseCoordMode.RELATIVE_WINDOW) -> (int, int):
        autoit.opt('MouseCoordMode', _autoit_mouse_coord_mode(coord_mode))
        return autoit.mouse_get_pos()

    @staticmethod
    def __match_window(wintitle: str, all_windows, at_start_only: bool, lowercase: bool):
        mypid = win32api.GetCurrentProcessId()
        if lowercase:
            wintitle = wintitle.lower()
        for hwnd in all_windows:
            threadid, procid = win32process.GetWindowThreadProcessId(hwnd)
            if procid == mypid:
                logger.debug(f'skip own process\' window: hwnd:{hwnd:#010x} pid:{procid:#010x} tid:{threadid:#010x}')
                continue
            iter_title = win32gui.GetWindowText(hwnd)
            if not iter_title or not wintitle:
                continue
            if lowercase:
                iter_title = iter_title.lower()
            if at_start_only:
                present = iter_title.startswith(wintitle)
            else:
                present = wintitle in iter_title
            if present:
                return hwnd
        return None

    @staticmethod
    def __find_window(wintitle: str) -> object:
        all_windows = list()
        win32gui.EnumWindows(lambda _hwnd, _: all_windows.append(_hwnd), None)
        hwnd = AutoitWin32GuiAutomation.__match_window(wintitle, all_windows, True, False)
        if not hwnd:
            hwnd = AutoitWin32GuiAutomation.__match_window(wintitle, all_windows, True, True)
        if not hwnd:
            hwnd = AutoitWin32GuiAutomation.__match_window(wintitle, all_windows, False, False)
        if not hwnd:
            hwnd = AutoitWin32GuiAutomation.__match_window(wintitle, all_windows, False, True)
        return hwnd

    @staticmethod
    def __is_minimized(hwnd):
        p = win32gui.GetWindowPlacement(hwnd)
        if p is None:
            return False
        return p[1] == win32con.SW_SHOWMINIMIZED

    def activate_window(self, title: str, win_wait: Optional[float] = None, maximize=False) -> bool:
        if self.is_window_active(title):
            return True
        if win_wait is None:
            win_wait = 0.2
        hwnd = AutoitWin32GuiAutomation.__find_window(title)
        if hwnd is None:
            logger.warn(f'could not find window for title \'{title}\'')
            return False
        logger.info(f'activate window \'{title}\' hwnd:{hwnd:#010x} with wait {win_wait}')
        if AutoitWin32GuiAutomation.__is_minimized(hwnd):
            logger.detail(f'window \'{title}\' hwnd:{hwnd:#010x} is minimized')
            mode = win32con.SW_MAXIMIZE if maximize else win32con.SW_NORMAL
            win32gui.ShowWindow(hwnd, mode)
            win_wait += 0.5
        set_active_success = False
        for _ in range(3):
            # noinspection PyBroadException
            try:
                win32gui.SetForegroundWindow(hwnd)
                set_active_success = True
                break
            except Exception as e:
                logger.warn(f'SetForegroundWindow for {title} fails with {e}')
                sleep(0.2)
                continue
        if not set_active_success:
            return False
        for i in range(int(win_wait / 0.1)):
            sleep(0.1)
            if self.is_window_active(title):
                return True
        return False

    def is_window_active(self, title: str) -> bool:
        logger.detail(f'is_window_active 1 {title}')
        active_hwnd = win32gui.GetForegroundWindow()
        logger.detail(f'is_window_active 2 {active_hwnd}')
        if active_hwnd is None:
            return False
        mypid = win32api.GetCurrentProcessId()
        logger.detail(f'is_window_active 3 {mypid}')
        _, procid = win32process.GetWindowThreadProcessId(active_hwnd)
        logger.detail(f'is_window_active 4 {procid}')
        if mypid == procid:
            # dont check text, it might lockup. assuming its not the RKA window we're looking for
            return False
        active_title = win32gui.GetWindowText(active_hwnd)
        logger.detail(f'is_window_active 5 {active_title}')
        if active_title is None:
            return False
        return title.lower() in active_title.lower()
