from __future__ import annotations

from rka.components.cleanup import cleanup_manager
from rka.components.concurrency.rkathread import RKAThread
from rka.components.events.event_system import EventSystem
from rka.components.impl.factories import HotkeyServiceFactory
from rka.components.ui.hotkeys import IHotkeyFilter, IHotkeyService, HotkeyEventPumpType
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.hosts import is_slave_window, is_master_window
from rka.eq2.configs.shared.rka_constants import KEY_REPEAT
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IHotkeySpec, logger
from rka.eq2.master.control.hotkey_bus_events import HotkeyEvents
from rka.eq2.master.ui import PermanentUIEvents
from rka.eq2.master.ui.control_menu_ui import ControlMenuUIType
from rka.eq2.master.ui.debug_helpers import print_mouse_info


class EmptyHotkeySpec(IHotkeySpec):
    def get_spec_count(self) -> int:
        return 1

    def register_keys(self, runtime: IRuntime, spec_id: int, keyfilter: IHotkeyFilter) -> str:
        return 'None'


class KeySpecManager:
    def __register_permanent_control_keys(self, keyfilter: IHotkeyFilter):
        # master control
        keyfilter.add_keys('consume alt control q', self.__server_cleanup_start)
        keyfilter.add_keys(['consume alt oem_4', 'consume alt f'], self.resume)
        keyfilter.add_keys('consume alt oem_6', lambda: self.pause(True))
        keyfilter.add_keys('consume alt oem_5', self.cycle_hotkeys)
        keyfilter.add_keys('escape', self.__runtime.control_menu.cancel_script_start)
        # panic stop
        keyfilter.add_keys(['consume control escape', 'consume alt escape', 'consume shift escape',
                            'consume control alt escape', 'consume control shift escape', 'consume alt shift escape',
                            'consume control alt shift escape'], lambda: self.__runtime.control_menu.stop_scripts())
        # menus
        keyfilter.add_keys('consume F11', lambda: self.__runtime.control_menu.select_menu(ControlMenuUIType.OVERLAY))
        keyfilter.add_keys('consume control F11', lambda: self.__runtime.control_menu.select_flag(ControlMenuUIType.OVERLAY))
        keyfilter.add_keys('consume F12', lambda: self.__runtime.control_menu.select_script(ControlMenuUIType.OVERLAY))
        keyfilter.add_keys('consume control F12', lambda: self.__runtime.control_menu.control_scripts(ControlMenuUIType.OVERLAY))
        # selecting character for script use
        keyfilter.add_keys(f'consume control oem_4', lambda: self.cycle_selection_id(-1))
        keyfilter.add_keys(f'consume control oem_6', lambda: self.cycle_selection_id(1))
        # utility
        keyfilter.add_keys('consume shift alt control k', self.__runtime.request_ctrl.request_toggle_keep_clicking)
        keyfilter.add_keys('consume shift alt control m', print_mouse_info)
        keyfilter.add_keys('consume shift alt control l', self.__runtime.zonemaps.save_location)

    def __register_running_control_keys(self, keyfilter: IHotkeyFilter):
        # automatic clicking
        keyfilter.add_keys('repeat 1', lambda: self.__runtime.automation.autocombat.sustain_clicking())
        # utility
        keyfilter.add_keys('control space', self.__runtime.overlay_controller.start_timer)
        # pausing
        keyfilter.add_keys(['r', 'oem_2', 'return'], lambda: self.pause(False))

    # noinspection PyMethodMayBeStatic
    def __register_programmable_event_hotkeys(self, keyfilter: IHotkeyFilter):
        bus = EventSystem.get_main_bus()
        keyfilter.add_keys('consume F1', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=1)))
        keyfilter.add_keys('consume F2', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=2)))
        keyfilter.add_keys('consume F3', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=3)))
        keyfilter.add_keys('consume F4', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=4)))
        keyfilter.add_keys('consume F5', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=5)))
        keyfilter.add_keys('consume F6', lambda: bus.post(HotkeyEvents.FUNCTION_KEY(function_num=6)))

    # noinspection PyMethodMayBeStatic
    def __register_blocked_keys_in_remote(self, keyfilter: IHotkeyFilter):
        keyfilter.add_keys('consume alt F4', lambda: True)

    # noinspection PyMethodMayBeStatic
    def __register_window_switching_keys_in_remote(self, keyfilter: IHotkeyFilter):
        local_player = self.__runtime.playerselectors.local_online()
        keyfilter.add_keys('consume alt tab', lambda: self.__runtime.master_bridge.send_switch_to_client_window(local_player.resolve_first_player()))

    @staticmethod
    def __new_nonslave_window_filter() -> IHotkeyFilter:
        new_filter = HotkeyServiceFactory.create_filter()
        new_filter.set_window_name_filter(lambda win_title: not win_title or not is_slave_window(win_title))
        new_filter.set_repetition_delay(KEY_REPEAT)
        return new_filter

    @staticmethod
    def __new_slave_window_filter() -> IHotkeyFilter:
        new_filter = HotkeyServiceFactory.create_filter()
        new_filter.set_window_name_filter(is_slave_window)
        new_filter.set_repetition_delay(KEY_REPEAT)
        return new_filter

    @staticmethod
    def __new_master_or_slave_window_filter() -> IHotkeyFilter:
        new_filter = HotkeyServiceFactory.create_filter()
        new_filter.set_description('Window switching hotkeys')
        new_filter.set_window_name_filter(lambda win_title: is_slave_window(win_title) or is_master_window(win_title))
        new_filter.set_repetition_delay(KEY_REPEAT)
        return new_filter

    def __new_running_filters(self) -> [IHotkeyFilter]:
        nonslave_filter = KeySpecManager.__new_nonslave_window_filter()
        nonslave_filter.set_description('Playing state hotkeys')
        self.__register_permanent_control_keys(nonslave_filter)
        self.__register_running_control_keys(nonslave_filter)
        gameonly_filter = KeySpecManager.__new_master_or_slave_window_filter()
        self.__register_programmable_event_hotkeys(gameonly_filter)
        slaveonly_filter = KeySpecManager.__new_slave_window_filter()
        self.__register_blocked_keys_in_remote(slaveonly_filter)
        self.__register_window_switching_keys_in_remote(slaveonly_filter)
        return [nonslave_filter, gameonly_filter, slaveonly_filter]

    def __new_paused_filters(self) -> [IHotkeyFilter]:
        nonslave_filter = KeySpecManager.__new_nonslave_window_filter()
        nonslave_filter.set_description('Paused state hotkeys')
        self.__register_permanent_control_keys(nonslave_filter)
        slaveonly_filter = KeySpecManager.__new_slave_window_filter()
        self.__register_blocked_keys_in_remote(slaveonly_filter)
        self.__register_window_switching_keys_in_remote(slaveonly_filter)
        return [nonslave_filter, slaveonly_filter]

    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__hotkey_spec: IHotkeySpec = EmptyHotkeySpec()
        self.__current_spec_id = 0
        self.__current_spec_name = ''
        self.hotkey_service = HotkeyServiceFactory.create_service(service_type=HotkeyEventPumpType.SERVICE_TYPE_CURRENT_THREAD_PUMP)
        # this key filter is added when game hotkeys are active
        self.running_keyfilters = self.__new_running_filters()
        # this key filter is always active
        self.paused_keyfilters = self.__new_paused_filters()

    def __server_cleanup(self):
        logger.info('cleanup start')
        self.__runtime.close()
        cleanup_manager.close_all()

    def __server_cleanup_start(self):
        close_thread = RKAThread('Cleanup thread', target=self.__server_cleanup)
        # remove from resource list to prevent cleanup manager from waiting for it
        close_thread.close_resource()
        close_thread.start()

    def __update_status_info(self):
        status_info = f'Hotkeys: {self.__current_spec_name} {"PAUSED" if self.__runtime.processor.is_paused() else "ON"}'
        self.__runtime.overlay.log_event(status_info, Severity.Critical, event_id=PermanentUIEvents.HOTKEYS.str())

    def pause(self, clear_processor: bool):
        logger.debug(f'pausing hotkeys {clear_processor}')
        self.hotkey_service.clear_filters()
        self.hotkey_service.add_filters(self.paused_keyfilters)
        if self.__runtime.processor.pause():
            if self.__runtime.combatstate.is_combat():
                self.__runtime.tts.say('keys off')
        elif clear_processor:
            self.__runtime.processor.clear_processor()
            self.__runtime.overlay.log_event('Processor pruned', Severity.Normal)
        self.__update_status_info()

    def resume(self):
        logger.debug(f'resuming hotkeys')
        self.hotkey_service.clear_filters()
        self.hotkey_service.add_filters(self.running_keyfilters)
        if self.__runtime.processor.resume():
            if self.__runtime.combatstate.is_combat():
                self.__runtime.tts.say('keys on')
        self.__update_status_info()

    def set_hotkey_spec(self, hotkey_spec: IHotkeySpec):
        logger.debug(f'setting hotkey spec {hotkey_spec}')
        self.__hotkey_spec = hotkey_spec
        self.__current_spec_id = None
        self.cycle_hotkeys(None, self.hotkey_service)

    def unset_hotkey_spec(self):
        self.set_hotkey_spec(EmptyHotkeySpec())

    def cycle_hotkeys(self, _, hotkey_service: IHotkeyService):
        # get next keyspec ID
        if self.__current_spec_id is None:
            self.__current_spec_id = 0
        else:
            self.__current_spec_id = (self.__current_spec_id + 1) % (self.__hotkey_spec.get_spec_count() + 1)
        # get keyspec name and keys
        self.running_keyfilters = self.__new_running_filters()
        if self.__current_spec_id < self.__hotkey_spec.get_spec_count():
            new_keyspec_filter = KeySpecManager.__new_nonslave_window_filter()
            self.__current_spec_name = self.__hotkey_spec.register_keys(self.__runtime, self.__current_spec_id, new_keyspec_filter)
            self.running_keyfilters.append(new_keyspec_filter)
        else:
            self.__current_spec_name = 'Control & scripts only'
        # store new hotkey filters
        logger.info(f'rotating hotkey specification to {self.__current_spec_name}')
        # apply new hotkey filters
        hotkey_service.clear_filters()
        if self.__runtime.processor.is_paused():
            hotkey_service.add_filters(self.paused_keyfilters)
        else:
            hotkey_service.add_filters(self.running_keyfilters)
        self.__update_status_info()

    def cycle_selection_id(self, increment: int):
        current_selection_id = self.__runtime.overlay.get_selection_id()
        max_selection_id = self.__runtime.overlay.get_max_selection_id()
        new_selection_id = (current_selection_id + increment) % max_selection_id
        self.__runtime.overlay.set_selection_id(new_selection_id)

    def run_blocking(self):
        self.hotkey_service.start(self.running_keyfilters)
