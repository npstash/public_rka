from __future__ import annotations

import enum
import inspect
import time
from typing import Dict, List, Callable, Set, Union, Optional, Iterable

import win32gui

from rka.components.io.log_service import LogService
from rka.components.ui.hotkey_util import Modifier, Binding
from rka.log_configs import LOG_HOTKEYS

logger = LogService(LOG_HOTKEYS)


class HotkeyEventPumpType(enum.IntEnum):
    SERVICE_TYPE_CURRENT_THREAD_PUMP = 1
    SERVICE_TYPE_NEW_THREAD_PUMP = 2


class IHotkeyHandler:
    def get_key(self, event) -> str:
        raise NotImplementedError()

    def get_modifiers(self, event) -> Dict[Modifier, bool]:
        raise NotImplementedError()


class IHotkeyFilter:
    def __init__(self):
        self.uses_key_down = False
        self.uses_key_up = False
        self.uses_key_char = False
        self.description = None

    def __str__(self):
        if self.description:
            return self.description
        return super().__str__()

    def set_repetition_delay(self, repetition_delay: float):
        raise NotImplementedError()

    def set_description(self, description: str):
        self.description = description

    def set_window_name_filter(self, callback: Callable[[Optional[str]], bool]):
        raise NotImplementedError()

    def add_keys(self, keys: Union[List[str], str], callback: Callable[[Optional[str], Optional[IHotkeyService]], None]):
        raise NotImplementedError()

    def on_key_down_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        raise NotImplementedError()

    def on_key_up_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        raise NotImplementedError()

    def on_key_char_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        raise NotImplementedError()

    def on_hotkeyfilter_installed(self, service: IHotkeyService, already_pressed_keys: Set[str]):
        pass

    def on_hotkeyfilter_uninstalled(self, service: IHotkeyService):
        pass


def get_user_callback_handler(binding_key: str, hotkey_service: IHotkeyService, user_callback: Callable) -> Callable:
    arg_count = len(inspect.signature(user_callback).parameters)
    if arg_count == 0:
        return lambda: user_callback()
    if arg_count == 1:
        return lambda: user_callback(binding_key)
    if arg_count == 2:
        return lambda: user_callback(binding_key, hotkey_service)
    assert False


class IHotkeyService:
    def add_filter(self, hkfilter: IHotkeyFilter):
        raise NotImplementedError()

    def add_filters(self, hkfilters: Iterable[IHotkeyFilter]):
        raise NotImplementedError()

    def remove_filter(self, hkfilter: IHotkeyFilter):
        raise NotImplementedError()

    def clear_filters(self):
        raise NotImplementedError()

    def start(self, key_filters: List[IHotkeyFilter], coroutine: Optional[Callable] = None):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


class RKAHotkeyFilter(IHotkeyFilter):
    DEFAULT_KEY_REPEAT_DELAY = 0.1

    @staticmethod
    def __check_modifier_set(mod: Modifier, binding: Binding, all_modifier_states: Dict[Modifier, bool]):
        lmod = mod.lmodifier()
        rmod = mod.rmodifier()
        match = lmod in binding.modifiers or mod in binding.modifiers if all_modifier_states[lmod] else True
        match &= rmod in binding.modifiers or mod in binding.modifiers if all_modifier_states[rmod] else True
        match &= lmod in binding.modifiers or rmod in binding.modifiers or mod in binding.modifiers if all_modifier_states[mod] else True
        match &= all_modifier_states[lmod] if lmod in binding.modifiers else True
        match &= all_modifier_states[rmod] if rmod in binding.modifiers else True
        match &= all_modifier_states[lmod] or all_modifier_states[rmod] or all_modifier_states[mod] if mod in binding.modifiers else True
        return match

    @staticmethod
    def __check_modifier_unset(mod: Modifier, binding: Binding, all_modifier_states: Dict[Modifier, bool]):
        lmod = mod.lmodifier()
        rmod = mod.rmodifier()
        match = not all_modifier_states[lmod] if lmod in binding.modifiers else True
        match &= not all_modifier_states[rmod] if rmod in binding.modifiers else True
        match &= not (all_modifier_states[lmod] or all_modifier_states[rmod] or all_modifier_states[mod]) if mod in binding.modifiers else True
        return match

    __checked_modifiers = [Modifier.alt, Modifier.control, Modifier.shift]

    @staticmethod
    def __check_all_modifiers_set(binding: Binding, all_modifier_states: Dict[Modifier, bool]):
        for mod in RKAHotkeyFilter.__checked_modifiers:
            if not RKAHotkeyFilter.__check_modifier_set(mod, binding, all_modifier_states):
                return False
        return True

    @staticmethod
    def __check_all_modifiers_unset(binding, all_modifier_states):
        for mod in RKAHotkeyFilter.__checked_modifiers:
            if not RKAHotkeyFilter.__check_modifier_unset(mod, binding, all_modifier_states):
                return False
        return True

    def __init__(self, keys: Union[List[str], str] = None, callback: Callable[[Optional[str], Optional[IHotkeyService]], None] = None):
        IHotkeyFilter.__init__(self)
        self.uses_key_down = True
        self.uses_key_up = True
        self.keys_to_bindings: Dict[str, List[Binding]] = dict()
        self.__event_repetition_delay = RKAHotkeyFilter.DEFAULT_KEY_REPEAT_DELAY
        if keys is not None:
            self.add_keys(keys, callback)
        self.__window_name_filter: Optional[Callable[[Optional[str]], bool]] = None
        self.saved_pressed_keys: Set[str] = set()
        self.saved_binding_to_release: Optional[Binding] = None

    def set_repetition_delay(self, repetition_delay: float):
        self.__event_repetition_delay = repetition_delay

    def set_window_name_filter(self, callback: Callable[[Optional[str]], bool]):
        self.__window_name_filter = callback

    def add_keys(self, keys: Union[List[str], str], callback: Callable[[Optional[str], Optional[IHotkeyService]], None]):
        assert callback, keys
        if isinstance(keys, str):
            keys = [keys]
        for keyspec in keys:
            binding = Binding.parse_hotkey_spec(keyspec)
            logger.info(f'adding key binding {keyspec}: key {binding.key} modifiers {binding.raw_modifiers}')
            if binding.key not in self.keys_to_bindings.keys():
                self.keys_to_bindings[binding.key] = list()
            binding.params['callback'] = callback
            self.keys_to_bindings[binding.key].append(binding)

    def __check_last_press(self, binding: Binding):
        now = time.time()
        last_press = None
        if 'last_press' in binding.params:
            last_press = binding.params['last_press']
        if last_press is None or last_press + self.__event_repetition_delay <= now:
            binding.params['last_press'] = now
            return True
        logger.detail(f'skipping {binding.key} due to repetition overflow')
        return False

    @staticmethod
    def __dispatch_key(binding: Binding, hotkey_service: IHotkeyService, dispatching_callback: Callable[[Callable], None]):
        user_callback_handler = get_user_callback_handler(binding.keyspec, hotkey_service, binding.params['callback'])
        dispatching_callback(user_callback_handler)

    @staticmethod
    def __modifiers_str(modifiers: Dict[Modifier, bool]) -> str:
        return str([modifier.value for modifier, enable in modifiers.items() if enable])

    def __check_active_window(self) -> bool:
        if not self.__window_name_filter:
            return True
        fg_wnd = win32gui.GetForegroundWindow()
        if not fg_wnd:
            logger.warn(f'__check_active_window: No active window')
            return False
        fg_wnd_title = win32gui.GetWindowText(fg_wnd)
        filter_result = self.__window_name_filter(fg_wnd_title)
        if not filter_result:
            logger.info(f'__check_active_window: not accepted "{fg_wnd_title}"')
            return False
        return True

    def on_key_down_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        consume = False
        logger.detail(f'on_key_down_event: {key}, mods: {RKAHotkeyFilter.__modifiers_str(modifiers)}')
        logger.detail(f'on_key_down_event: pressed keys state (1): {self.saved_pressed_keys}')
        is_registered = key in self.keys_to_bindings.keys()
        already_pressed = key in self.saved_pressed_keys
        self.saved_pressed_keys.add(key)
        if is_registered:
            for binding in self.keys_to_bindings[key]:
                if not RKAHotkeyFilter.__check_all_modifiers_set(binding, modifiers):
                    logger.detail(f'on_key_down_event: drop DOWN {binding.keyspec}, not all modifiers set')
                    continue
                consume = consume or binding.consume
                if already_pressed and not binding.repeat:
                    logger.detail(f'on_key_down_event: drop DOWN {binding.keyspec}, already pressed')
                    continue
                logger.detail(f'matched new hotkey event {binding.keyspec}')
                if not self.__check_last_press(binding):
                    continue
                if binding.release or (binding.up and not binding.down):
                    logger.debug(f'waiting for release of {binding.keyspec}')
                    self.saved_binding_to_release = binding
                    continue
                if not binding.down:
                    logger.detail(f'on_key_down_event: drop DOWN {binding.keyspec}, binding only UP')
                    continue
                if not self.__check_active_window():
                    # dont consume, but dont fire the hotkey either
                    return True
                RKAHotkeyFilter.__dispatch_key(binding, service, dispatching_callback)
        logger.detail(f'on_key_down_event: pressed keys state (2): {self.saved_pressed_keys}')
        return not consume

    def on_key_up_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        consume = False
        logger.detail(f'on_key_up_event: {key}, mods: {RKAHotkeyFilter.__modifiers_str(modifiers)}')
        logger.detail(f'on_key_up_event: pressed keys state (1): {self.saved_pressed_keys}')
        already_pressed = key in self.saved_pressed_keys
        # situation: key was registered in previous spec, when key is released (up), it needs to be removed from pressed_keys
        if not already_pressed:
            logger.detail(f'on_key_up_event: drop UP {key}, not pressed')
            return True
        self.saved_pressed_keys.remove(key)
        binding = self.saved_binding_to_release
        if binding is not None:
            if binding.key != key:
                # this not a modifier and not the key being released
                logger.detail(f'on_key_up_event: drop UP {binding.keyspec}, not the awaited key')
                return not consume
            if not RKAHotkeyFilter.__check_all_modifiers_unset(binding, modifiers):
                # event UP of a modifier means the state is already OFF
                logger.detail(f'on_key_up_event: drop UP {binding.keyspec}, modifiers not set')
                return not consume
            logger.debug(f'matched key waiting for release: {binding.keyspec}')
            consume = consume or binding.consume
            self.saved_binding_to_release = None
            if not self.__check_active_window():
                # dont consume, but dont fire the hotkey either
                return True
            RKAHotkeyFilter.__dispatch_key(binding, service, dispatching_callback)
        logger.detail(f'on_key_up_event: pressed keys state (2): {self.saved_pressed_keys}')
        return not consume

    def on_key_char_event(self, key: str, modifiers: Dict[Modifier, bool], service: IHotkeyService, dispatching_callback: Callable[[Callable], None]) -> bool:
        raise NotImplementedError()

    def on_hotkeyfilter_installed(self, service: IHotkeyService, already_pressed_keys: Set[str]):
        self.saved_pressed_keys = already_pressed_keys
