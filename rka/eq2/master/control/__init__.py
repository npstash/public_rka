from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional, Iterable, Callable

from rka.components.io.log_service import LogService
from rka.components.ui.automation import MouseCoordMode
from rka.components.ui.capture import MatchPattern, CaptureArea, Capture, Offset, Rect
from rka.components.ui.hotkeys import IHotkeyFilter
from rka.eq2.master import IRuntime
from rka.eq2.shared import ClientConfigData
from rka.eq2.shared.control.action_id import ActionID
from rka.eq2.shared.host import HostConfig
from rka.log_configs import LOG_APPCONTROL

logger = LogService(LOG_APPCONTROL)


class IHotkeySpec:
    def get_spec_count(self) -> int:
        raise NotImplementedError()

    def register_keys(self, runtime: IRuntime, spec_id: int, keyfilter: IHotkeyFilter) -> str:
        raise NotImplementedError()


class ICommandBuilder:
    def key(self, key: str, count=1, key_type_delay: Optional[float] = None) -> IAction:
        raise NotImplementedError()

    def text(self, text: str, key_type_delay: Optional[float] = None) -> IAction:
        raise NotImplementedError()

    def mouse(self, x: int, y: int, button='left', speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW,
              modifiers: Optional[str] = None) -> IAction:
        raise NotImplementedError()

    def double_click(self) -> IAction:
        raise NotImplementedError()

    def mouse_scroll(self, scroll_up: bool, clicks: Optional[int] = None) -> IAction:
        raise NotImplementedError()

    def window_activate(self, window: str, set_default=False, wait_time: Optional[float] = None) -> IAction:
        raise NotImplementedError()

    def window_check(self, window: str) -> IAction:
        raise NotImplementedError()

    def delay(self, delay: float) -> IAction:
        raise NotImplementedError()

    def process(self, path: str, args: str) -> IAction:
        raise NotImplementedError()

    def inject_command(self, injector_name: str, injected_command: str, once: bool, passthrough: bool,
                       duration: Optional[float] = None, command_id: Optional[str] = None) -> IAction:
        raise NotImplementedError()

    def remove_injected_command(self, injector_name: str, command_id: str) -> IAction:
        raise NotImplementedError()

    def inject_prefix(self, injector_name: str, prefix: str) -> IAction:
        raise NotImplementedError()

    def inject_postfix(self, injector_name: str, postfix: str) -> IAction:
        raise NotImplementedError()

    def find_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None) -> IAction:
        raise NotImplementedError()

    def find_multiple_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                                    max_matches: Optional[int] = None) -> IAction:
        raise NotImplementedError()

    def get_capture(self, capture_area: CaptureArea) -> IAction:
        raise NotImplementedError()

    def save_capture(self, capture: Capture, tag: str) -> IAction:
        raise NotImplementedError()

    def click_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                            max_clicks: Optional[int] = None, click_delay: Optional[float] = None, click_offset: Optional[Offset] = None) -> IAction:
        raise NotImplementedError()

    def capture_cursor(self) -> IAction:
        raise NotImplementedError()

    def get_cursor_fingerprint(self) -> IAction:
        raise NotImplementedError()

    def custom_action(self, action_id: ActionID, **kwargs) -> IAction:
        raise NotImplementedError()


# noinspection PyAbstractClass
class IAction(ICommandBuilder):
    def _add_command(self, command: Dict[str: Any]) -> IAction:
        raise NotImplementedError()

    def set_default_post_sync(self, sync: bool):
        raise NotImplementedError()

    def get_average_delay(self, client_id: str) -> float:
        raise NotImplementedError()

    def post_auto(self, client_id: str) -> bool:
        raise NotImplementedError()

    def post_async(self, client_id: str, completion_cb: Optional[Callable[[None], None]] = None) -> bool:
        raise NotImplementedError()

    def post_sync(self, client_id: str, completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> bool:
        raise NotImplementedError()

    def call_action(self, client_id: str) -> Tuple[bool, Optional[List]]:
        raise NotImplementedError()

    def post_async_cancel(self, client_id: str):
        raise NotImplementedError()

    def is_cancellable(self) -> bool:
        raise NotImplementedError()

    def append(self, action: IAction):
        raise NotImplementedError()

    def prototype(self, **kwargs) -> IAction:
        raise NotImplementedError()

    def iter_commands(self) -> Iterable[Dict[str: Any]]:
        raise NotImplementedError()


class IClientConfig:
    def get_host_config(self) -> HostConfig:
        raise NotImplementedError()

    def get_client_config_data(self) -> ClientConfigData:
        raise NotImplementedError()

    def get_current_host_id(self) -> int:
        raise NotImplementedError()

    def get_inputs_config(self) -> InputConfig:
        raise NotImplementedError()

    def set_current_host_id(self, host_int: int):
        raise NotImplementedError()

    def set_inputs_config(self, inputs: InputConfig):
        raise NotImplementedError()


class IHasClient:
    def get_client_id(self) -> str:
        raise NotImplementedError()


class Hotbar:
    def __init__(self):
        self.hotkey1: Optional[IAction] = None
        self.hotkey2: Optional[IAction] = None
        self.hotkey3: Optional[IAction] = None
        self.hotkey4: Optional[IAction] = None
        self.hotkey5: Optional[IAction] = None
        self.hotkey6: Optional[IAction] = None
        self.hotkey7: Optional[IAction] = None
        self.hotkey8: Optional[IAction] = None
        self.hotkey9: Optional[IAction] = None
        self.hotkey10: Optional[IAction] = None
        self.hotkey11: Optional[IAction] = None
        self.hotkey12: Optional[IAction] = None


class Keyboard:
    def __init__(self):
        self.crouch: Optional[IAction] = None
        self.jump: Optional[IAction] = None
        self.key_turn_left: Optional[str] = None
        self.key_turn_right: Optional[str] = None
        self.key_move_forward: Optional[str] = None
        self.key_move_backwards: Optional[str] = None

    def update_keys(self, from_keys: Keyboard):
        self.key_turn_left = from_keys.key_turn_left
        self.key_turn_right = from_keys.key_turn_right
        self.key_move_forward = from_keys.key_move_forward
        self.key_move_backwards = from_keys.key_move_backwards


class ScreenCoords:
    def __init__(self):
        # client area
        self.X: Optional[int] = None
        self.Y: Optional[int] = None
        self.W: Optional[int] = None
        self.H: Optional[int] = None
        # in-game viewport
        self.VP_W_center: Optional[int] = None
        self.VP_H_center: Optional[int] = None
        self.bags_item_1: Optional[List[Tuple[int, int]]] = None
        self.bags_width: Optional[List[int]] = None
        self.bag_slot_size: Optional[int] = None
        # specific windows location? TODO read it from UI XML files
        self.detrim_list_window: Optional[Rect] = None
        self.detrim_count_window: Optional[Rect] = None
        self.target_buff_window: Optional[Rect] = None
        self.target_casting_bar: Optional[Rect] = None

    def get_screen_box(self) -> Optional[Rect]:
        if self.X is None or self.Y is None or self.W is None or self.H is None:
            return None
        screen_box = Rect(x1=self.X, y1=self.Y, w=self.W, h=self.H)
        return screen_box


class SpecialActions:
    def __init__(self):
        self.consume_command_injection: Optional[IAction] = None
        self.consume_ability_injection: Optional[IAction] = None
        self.select_nearest_npc: Optional[IAction] = None
        self.open_journal: Optional[IAction] = None
        self.open_character: Optional[IAction] = None
        self.open_bags: Optional[IAction] = None


class InputConfig:
    def __init__(self):
        self.hotbar1: Optional[Hotbar] = None
        self.hotbar2: Optional[Hotbar] = None
        self.hotbar3: Optional[Hotbar] = None
        self.hotbar4: Optional[Hotbar] = None
        self.hotbar5: Optional[Hotbar] = None
        self.hotbarUp11: Optional[Hotbar] = None
        self.hotbarUp12: Optional[Hotbar] = None
        self.crafting_hotbar: Optional[Hotbar] = None
        self.keyboard: Optional[Keyboard] = None
        self.special: Optional[SpecialActions] = None
        self.screen = ScreenCoords()
