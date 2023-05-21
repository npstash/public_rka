import ctypes
import threading
import traceback
from typing import Dict, List, Callable, Optional, Iterable, Set

import pyWinhook
import pythoncom
import win32api
import win32con

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogService
from rka.components.ui.hotkey_util import Modifier
from rka.components.ui.hotkeys import IHotkeyHandler, IHotkeyFilter, IHotkeyService, HotkeyEventPumpType
from rka.log_configs import LOG_HOTKEYS

logger = LogService(LOG_HOTKEYS)

STATE_CREATED = 1
STATE_INITIALIZED = 2
STATE_RUNNING = 3
STATE_DESTROYED = 4


# event callback chain
# > HotkeyService.__event_pump (windows message pump)
# -> HotkeyService.__key_event_relay (invoked with event by PyWinHook)
# --> HotkeyFilter.on_key_event (event passing for matching and consuming, creates a lambda with user callback and k33ey)
# ---> HotkeyService.__append_to_taskloop (if matched, pass notification to command queue)
# ----> HotkeyService.__task_dispatch (notification thread loop, pick up from queue)
# -----> HotkeyFilter.lambda (contains a call to user callback with key binding)
# ------> user_event_hanle(key: str, hks: HotkeyService) (callback from user code)
class PyWinHookHotkeys(Closeable, IHotkeyService, IHotkeyHandler):
    __instance = None

    def __init__(self, service_type=HotkeyEventPumpType.SERVICE_TYPE_CURRENT_THREAD_PUMP):
        assert not PyWinHookHotkeys.__instance, 'Multiple instances will not work'
        Closeable.__init__(self, explicit_close=False)
        self.__lock = threading.Condition()
        # service-related
        self.__service_type = service_type
        self.__state = STATE_CREATED
        self.__pump_threadid: Optional[int] = None
        self.__taskloop_lock = threading.Condition()
        self.__task_queue: List[Callable] = list()
        # filter-related
        self.__current_filters: List[IHotkeyFilter] = []
        self.__hook_manager: Optional[pyWinhook.HookManager] = None
        self.__dispatch_thread: Optional[RKAThread] = None
        # tracking keypresses - filters need to be initialized with current state of keypresses
        self.__saved_pressed_keys: Set[str] = set()

    def __is_state(self, state_check) -> bool:
        if state_check == STATE_CREATED:
            return self.__state >= STATE_CREATED
        elif state_check == STATE_INITIALIZED:
            return self.__state >= STATE_INITIALIZED
        elif state_check == STATE_RUNNING:
            return self.__state == STATE_RUNNING
        elif state_check == STATE_DESTROYED:
            return self.__state == STATE_DESTROYED
        raise ValueError(state_check)

    def __set_state(self, new_state):
        assert not self.__is_state(STATE_DESTROYED)
        assert new_state != STATE_CREATED
        if new_state == self.__state:
            return
        if new_state == STATE_INITIALIZED:
            assert self.__state == STATE_CREATED or self.__state == STATE_RUNNING
        elif new_state == STATE_RUNNING:
            assert self.__state == STATE_INITIALIZED
        elif new_state == STATE_DESTROYED:
            assert self.__is_state(STATE_CREATED)
        else:
            raise ValueError(new_state)
        self.__state = new_state

    def __task_dispatch(self):
        while True:
            with self.__lock:
                if self.__is_state(STATE_DESTROYED):
                    break
            with self.__taskloop_lock:
                if len(self.__task_queue) == 0:
                    self.__taskloop_lock.wait(4.0)
                    continue
                task = self.__task_queue.pop(0)
            try:
                logger.detail(f'hotkey dispatching task: {task}')
                if not task:
                    logger.info(f'exiting hotkey dispatching')
                    break
                task()
            except Exception as e:
                logger.error(f'exception occured when calling hotkey callback {task}, {e}')
                traceback.print_exc()

    def __append_to_taskloop(self, user_callback_handler):
        logger.detail(f'adding callback to notification queue: {user_callback_handler}')
        with self.__taskloop_lock:
            self.__task_queue.append(user_callback_handler)
            self.__taskloop_lock.notify()

    @staticmethod
    def __describe_key(event: pyWinhook.KeyboardEvent):
        return f'KeyID:{event.KeyID} ScanCode:{event.ScanCode} Ascii:{event.Ascii} Key:{event.Key} ' \
               f'Extended:{event.Extended} Injected:{event.Injected} Alt:{event.Alt} Transition:{event.Transition}'

    def __common_key_event_relay(self, event_type: str, key: str, key_debug_info: str, modifier_states: Dict[Modifier, bool],
                                 filter_function: Callable[[str, Dict[Modifier, bool], IHotkeyService, Callable[[Callable], None]], bool]) -> bool:
        try:
            logger.debug(f'received event ({event_type}): {key_debug_info}')
            # key = self.get_key(event)
            if key is None:
                logger.debug(f'could not translate event {key_debug_info} to a key')
                return True
            # modifier_states = self.get_modifiers(event)
            pass_event = filter_function(key, modifier_states, self, self.__append_to_taskloop)
            logger.detail(f'pass {key} {event_type} event {pass_event}')
            return pass_event
        except Exception as e:
            logger.error(f'error while handling key event {e}')
            traceback.print_exc()
        return True

    def __key_down_event_relay(self, event: pyWinhook.KeyboardEvent) -> bool:
        key_debug_info = PyWinHookHotkeys.__describe_key(event)
        key = self.get_key(event)
        modifier_states = self.get_modifiers(event)
        pass_event = True
        self.__saved_pressed_keys.add(key)
        for hkfilter in self.__current_filters:
            if not self.__common_key_event_relay('down', key, key_debug_info, modifier_states, hkfilter.on_key_down_event):
                pass_event = False
        return pass_event

    def __key_up_event_relay(self, event: pyWinhook.KeyboardEvent) -> bool:
        key_debug_info = PyWinHookHotkeys.__describe_key(event)
        key = self.get_key(event)
        modifier_states = self.get_modifiers(event)
        pass_event = True
        if key in self.__saved_pressed_keys:
            self.__saved_pressed_keys.remove(key)
        for hkfilter in self.__current_filters:
            if not self.__common_key_event_relay('up', key, key_debug_info, modifier_states, hkfilter.on_key_up_event):
                pass_event = False
        return pass_event

    def __key_char_event_relay(self, event: pyWinhook.KeyboardEvent) -> bool:
        key_debug_info = PyWinHookHotkeys.__describe_key(event)
        key = self.get_key(event)
        modifier_states = self.get_modifiers(event)
        pass_event = True
        for hkfilter in self.__current_filters:
            if not self.__common_key_event_relay('char', key, key_debug_info, modifier_states, hkfilter.on_key_char_event):
                pass_event = False
        return pass_event

    def __add_hotkey_filter(self, hkfilter: IHotkeyFilter):
        if hkfilter in self.__current_filters:
            logger.warn(f'Cannot add new filter, already added: {hkfilter}')
            return
        self.__current_filters.append(hkfilter)
        hkfilter.on_hotkeyfilter_installed(self, set(self.__saved_pressed_keys))
        self.__hook_key_event_relays()

    def __add_multiple_hotkey_filter(self, hkfilters: List[IHotkeyFilter]):
        for hkfilter in hkfilters:
            if hkfilter in self.__current_filters:
                logger.warn(f'Cannot add new filter, already added: {hkfilter}')
                continue
            self.__current_filters.append(hkfilter)
            hkfilter.on_hotkeyfilter_installed(self, set(self.__saved_pressed_keys))
        self.__hook_key_event_relays()

    def __remove_hotkey_filter(self, hkfilter: IHotkeyFilter):
        if hkfilter not in self.__current_filters:
            logger.warn(f'Cannot remove filter, not added: {hkfilter}')
            return
        self.__current_filters.remove(hkfilter)
        hkfilter.on_hotkeyfilter_uninstalled(self)
        self.__hook_key_event_relays()

    def __clear_hotkey_filters(self):
        for hkfilter in self.__current_filters:
            hkfilter.on_hotkeyfilter_uninstalled(self)
        self.__current_filters.clear()
        self.__hook_key_event_relays()

    # noinspection PyArgumentList
    def __hook_key_event_relays(self):
        assert self.__hook_manager
        any_filter_uses_key_down = False
        any_filter_uses_key_up = False
        any_filter_uses_key_char = False
        for hkfilter in self.__current_filters:
            any_filter_uses_key_down = any_filter_uses_key_down or hkfilter.uses_key_down
            any_filter_uses_key_up = any_filter_uses_key_down or hkfilter.uses_key_up
            any_filter_uses_key_char = any_filter_uses_key_down or hkfilter.uses_key_char
        self.__hook_manager.SubscribeKeyDown(self.__key_down_event_relay if any_filter_uses_key_down else None)
        self.__hook_manager.SubscribeKeyUp(self.__key_up_event_relay if any_filter_uses_key_up else None)
        self.__hook_manager.SubscribeKeyChar(self.__key_char_event_relay if any_filter_uses_key_char else None)

    def __initialize(self):
        __pump_thread_started = False
        __pump_thread_lock = threading.Condition()

        def __create_hook_manager():
            assert self.__hook_manager is None
            self.__hook_manager = pyWinhook.HookManager()
            self.__hook_manager.HookKeyboard()
            self.__hook_key_event_relays()
            logger.debug('event pump created')

        def __initialize_pump_thread():
            ct = ctypes.windll.kernel32.GetCurrentThreadId()
            if self.__pump_threadid is not None and self.__pump_threadid != ct:
                raise Exception('reentering event pump in another thread')
            self.__pump_threadid = ct
            # noinspection PyUnresolvedReferences
            pythoncom.EnableQuitMessage(ct)
            logger.debug('event pump initialized')

        def __event_pump_thread():
            __create_hook_manager()
            __initialize_pump_thread()
            nonlocal __pump_thread_lock
            with __pump_thread_lock:
                logger.debug('notifying event pump creation')
                nonlocal __pump_thread_started
                __pump_thread_lock.notify()
                __pump_thread_started = True
            self.__event_pump()

        self.__dispatch_thread = RKAThread(name='Hotkey Dispatcher', target=self.__task_dispatch)
        self.__dispatch_thread.start()
        if self.__service_type == HotkeyEventPumpType.SERVICE_TYPE_NEW_THREAD_PUMP:
            with __pump_thread_lock:
                logger.debug('waiting for event pump thread to start')
                RKAThread(name='Hotkey Pump', target=__event_pump_thread).start()
                while not __pump_thread_started:
                    __pump_thread_lock.wait()
                logger.debug('delegated event pump started in worker thread')
        else:
            __create_hook_manager()
            __initialize_pump_thread()
        self.__set_state(STATE_INITIALIZED)

    def __event_pump(self):
        logger.info(f'event pump loop start')
        while True:
            with self.__lock:
                while not self.__is_state(STATE_RUNNING) and not self.__is_state(STATE_DESTROYED):
                    logger.debug(f'waiting until event pump thread is notified')
                    self.__lock.wait()
                    logger.debug(f'event pump thread unlocked')
                    continue
                if self.__is_state(STATE_DESTROYED):
                    break
            logger.info(f'starting blocking pycomm event pump')
            # noinspection PyUnresolvedReferences
            pythoncom.PumpMessages()
        logger.info(f'event pump loop end')

    __modifier_to_vk = {
        Modifier.lcontrol: 'VK_LCONTROL',
        Modifier.rcontrol: 'VK_RCONTROL',
        Modifier.control: 'VK_CONTROL',
        Modifier.lshift: 'VK_LSHIFT',
        Modifier.rshift: 'VK_RSHIFT',
        Modifier.shift: 'VK_SHIFT',
        Modifier.lalt: 'VK_LMENU',
        Modifier.ralt: 'VK_RMENU',
        Modifier.alt: 'VK_MENU',
    }

    __pywin_modifier_to_modifier = {
        'lcontrol': Modifier.lcontrol,
        'rcontrol': Modifier.rcontrol,
        'lshift': Modifier.lshift,
        'rshift': Modifier.rshift,
        'lmenu': Modifier.lalt,
        'rmenu': Modifier.ralt,
    }

    def __translate_key(self, key: str) -> str:
        pass

    def get_key(self, event: pyWinhook.KeyboardEvent) -> Optional[str]:
        if event is not None and event.Key is not None:
            key = event.Key.lower()
            if key in PyWinHookHotkeys.__pywin_modifier_to_modifier:
                return PyWinHookHotkeys.__pywin_modifier_to_modifier[key].value
            return key
        return None

    def get_modifiers(self, event: pyWinhook.KeyboardEvent) -> Dict[Modifier, bool]:
        all_modifier_states = dict()
        for modifier in PyWinHookHotkeys.__modifier_to_vk.keys():
            vk_code = self.__modifier_to_vk[modifier]
            vk_code_id = pyWinhook.HookConstants.VKeyToID(vk_code)
            state = pyWinhook.GetKeyState(vk_code_id)
            all_modifier_states[modifier] = state > 0
        # unset state if the key is a modifier and it is released. set, if it was pressed
        pressed = event.Transition != 128
        if event.Key:
            key = event.Key.lower()
            if key in PyWinHookHotkeys.__pywin_modifier_to_modifier:
                modifier = PyWinHookHotkeys.__pywin_modifier_to_modifier[key]
                all_modifier_states[modifier] = pressed
                all_modifier_states[modifier.generalize()] = pressed
        return all_modifier_states

    def start(self, key_filters: List[IHotkeyFilter], coroutine: Optional[Callable] = None):
        logger.info(f'hotkey service starting')
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            if not self.__is_state(STATE_INITIALIZED):
                self.__initialize()
            self.stop()
            self.__add_multiple_hotkey_filter(key_filters)
            self.__lock.notify()
            self.__set_state(STATE_RUNNING)
        if self.__service_type == HotkeyEventPumpType.SERVICE_TYPE_CURRENT_THREAD_PUMP:
            if coroutine is not None:
                # return flow to the caller using new thread
                new_thread = RKAThread(name='Hotkey Coroutine', target=coroutine)
                new_thread.start()
            # pump in current thread
            logger.info(f'hotkey pump enter')
            self.__event_pump()
            logger.info(f'hotkey pump left')

    def add_filter(self, hkfilter: IHotkeyFilter):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            self.__add_hotkey_filter(hkfilter)

    def add_filters(self, hkfilters: Iterable[IHotkeyFilter]):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            self.__add_multiple_hotkey_filter(hkfilters)

    def remove_filter(self, hkfilter: IHotkeyFilter):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            self.__remove_hotkey_filter(hkfilter)

    def clear_filters(self):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            self.__clear_hotkey_filters()

    def stop(self):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            if not self.__is_state(STATE_INITIALIZED):
                raise Exception('service not initialized')
            if not self.__is_state(STATE_RUNNING):
                logger.info(f'hotkey service not running, cannot stop')
                return
            win32api.PostThreadMessage(self.__pump_threadid, win32con.WM_QUIT, 0, 0)
            self.__lock.notify()
            self.__set_state(STATE_INITIALIZED)
        logger.info(f'hotkey service stopped')

    def close(self):
        with self.__lock:
            if self.__is_state(STATE_DESTROYED):
                raise Exception('service destroyed')
            self.stop()
            self.__lock.notify()
            self.__set_state(STATE_DESTROYED)
        self.__append_to_taskloop(None)
        logger.info(f'hotkey service destroyed')
        Closeable.close(self)
        PyWinHookHotkeys.__instance = None
