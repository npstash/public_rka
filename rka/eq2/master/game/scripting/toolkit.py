import traceback
from itertools import chain
from threading import Condition
from time import sleep
from typing import Optional, List, Any, Union, Tuple

from rka.components.events.event_system import BusThread
from rka.components.impl.factories import OCRServiceFactory
from rka.components.resources import Resource
from rka.components.ui.capture import Rect, CaptureArea, MatchPattern, Offset, Capture, Point, CaptureMode, CaptureWindowFlags
from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.configs.shared.rka_constants import GAME_LAG, CLICK_DELAY
from rka.eq2.master import HasRuntime, IRuntime
from rka.eq2.master.control import IAction
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.scripting import ScriptGuard, logger, ScriptException, RepeatMode
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.patterns.external_ui.bundle import external_patterns
from rka.eq2.shared.flags import MutableFlags


class ScriptingToolkit:
    def __init__(self, guard: ScriptGuard):
        self.__guard = guard

    # noinspection PyMethodMayBeStatic
    def verify_action_results(self, results: List[Any], expected_type: Any, expected_value: Any, action: IAction) -> bool:
        if results is None:
            logger.info(f'verify_action_results: results: {results}, expected_type: {expected_type}, expected_value: {expected_value}, action: {action}')
            return False
        elif not isinstance(results[0], expected_type):
            logger.info(f'verify_action_results: results[0]: {results[0]}, expected_type: {expected_type}, expected_value: {expected_value}, action: {action}')
            return False
        elif results[0] != expected_value:
            logger.info(f'verify_action_results: results[0]: {results[0]}, expected_type: {expected_type}, expected_value: {expected_value}, action: {action}')
            return False
        return True

    def _check_script_guard(self):
        if not self.__guard.is_script_action_allowed():
            raise ScriptException('expired')

    def _check_script_blocking(self):
        if BusThread.is_running_on_bus_thread():
            logger.error(f'Blocking Event Bus thread with script {self}')
            traceback.print_stack()

    def sleep(self, duration: float):
        self._check_script_blocking()
        for _ in range(int(duration // 2.0)):
            self._check_script_guard()
            sleep(2.0)
        if duration % 2.0 > 0.0:
            self._check_script_guard()
            sleep(duration % 2.0)

    def wait(self, condition: Condition, duration: float):
        self._check_script_blocking()
        self._check_script_guard()
        condition.wait(duration)

    def fail_script(self, reason):
        assert False, reason

    def compensate_lag(self, delay: Optional[float] = None):
        if delay is not None:
            delay += GAME_LAG
            self.sleep(delay)

    def call_client_action(self, action: IAction, client_id, delay: Optional[float] = None) -> Optional[List]:
        self._check_script_blocking()
        self._check_script_guard()
        logger.detail(f'the script {self} calls action {action}')
        success, results = action.call_action(client_id)
        if not success:
            logger.warn(f'action {action} failed for client {client_id}, delay {delay}, results = {success} / {results}')
            raise ScriptException(f'action failed for {client_id}')
        self.compensate_lag(delay)
        return results

    def post_client_action(self, action: IAction, client_id, delay: Optional[float] = None):
        self._check_script_guard()
        logger.detail(f'the script {self} posts action {action}')
        if not action.post_async(client_id):
            raise ScriptException(f'action failed for {client_id}')
        self.compensate_lag(delay)

    def post_client_action_sync(self, action: IAction, client_id, delay: Optional[float] = None):
        self._check_script_blocking()
        self._check_script_guard()
        logger.detail(f'the script {self} posts sync action {action}')
        if not action.post_sync(client_id):
            raise ScriptException(f'action failed for {client_id}')
        self.compensate_lag(delay)

    def client_bool_action(self, action: IAction, client_id, delay: Optional[float] = None) -> bool:
        result = self.call_client_action(action, client_id, delay=delay)
        return result and result[0]


class PlayerScriptingToolkit(HasRuntime):
    MAX_REPEATS = 10

    class _Decorators:
        @classmethod
        def ignore_for_local_player(cls, default_result):
            def decorator(decorated):
                def wrapper(self, *args, **kwargs):
                    assert isinstance(self, PlayerScriptingToolkit)
                    if self.get_player().is_local():
                        return default_result
                    return decorated(self, *args, **kwargs)

                return wrapper

            return decorator

        @classmethod
        def hide_overlay_for_local_player(cls, decorated):
            def wrapper(self, *args, **kwargs):
                assert isinstance(self, PlayerScriptingToolkit)
                if not self.get_player().is_local():
                    return decorated(self, *args, **kwargs)
                hide_required = True
                hide_done = False
                capture_box = None
                try:
                    screen_box = self.get_player().get_inputs().screen.get_screen_box()
                    if not screen_box:
                        logger.warn(f'No screen configured for {self.get_player()}')
                        return None
                    for arg in chain(args, kwargs.values()):
                        if isinstance(arg, CaptureArea):
                            # if arg is relative coords rect, it will convert to absolute here - absolute is used by Overlay
                            capture_box = arg.get_capture_bbox(screen_box)
                            if self.get_runtime().overlay.is_capture_safe(capture_box):
                                hide_required = False
                            break
                    if hide_required:
                        logger.detail(f'Hide overlay due to: screen={screen_box}, c_box={capture_box}')
                        hide_done = True
                        self._hide_overlay()
                    return decorated(self, *args, **kwargs)
                finally:
                    if hide_done:
                        self._restore_overlay()

            return wrapper

    def __init__(self, runtime_ref: HasRuntime, scripting: ScriptingToolkit, player: IPlayer):
        assert isinstance(scripting, ScriptingToolkit)
        assert isinstance(player, IPlayer)
        self.__runtime = runtime_ref.get_runtime()
        self.__scripting = scripting
        self.__player = player
        self.__cid = player.get_client_id()
        self.__hidden_overlay = False
        self.__ocr = OCRServiceFactory.create_ocr_service()

    def _hide_overlay(self):
        if self.__player.is_local():
            self.get_runtime().overlay.hide()
            self.__hidden_overlay = True
            self.__scripting.sleep(0.2)

    def _restore_overlay(self):
        if self.__player.is_local():
            self.get_runtime().overlay.show()
            self.__hidden_overlay = False

    # noinspection PyMethodMayBeStatic
    def __repeat_cb(self, cb, repeat: RepeatMode) -> Optional[Any]:
        final_result = None
        for _ in range(PlayerScriptingToolkit.MAX_REPEATS):
            result = cb()
            if result or not final_result:
                final_result = result
            if result and (repeat & RepeatMode.REPEAT_ON_SUCCESS != 0):
                continue
            if not result and (repeat & RepeatMode.TRY_ALL_ACCESS != 0) and self.try_close_all_access():
                continue
            if not result and (repeat & RepeatMode.REPEAT_ON_FAIL != 0):
                if final_result:
                    break
                continue
            break
        return final_result

    def __click_first_from_top(self, tag: Resource, object_heigth: int, click_delay: Optional[float] = None) -> bool:
        window_area = CaptureArea()
        screen_width = self.__player.get_inputs().screen.W
        screen_height = self.__player.get_inputs().screen.H
        results = None
        action = None
        for i in range((screen_height - 2 * object_heigth) // object_heigth):
            capture_area = window_area.capture_rect(Rect(x1=0, y1=i * object_heigth, w=screen_width, h=2 * object_heigth), relative=True)
            action = action_factory.new_action().click_capture_match(patterns=MatchPattern.by_tag(tag), capture_area=capture_area)
            # dont induce delay if clicking failed
            results = self.__scripting.call_client_action(action, self.__cid)
            if results[0]:
                break
        if self.__scripting.verify_action_results(results, bool, True, action):
            self.__scripting.compensate_lag(click_delay)
            return True
        return False

    def __click_match(self, pattern: Union[MatchPattern, Resource], click_delay: float, threshold: Optional[float] = None, area: Optional[CaptureArea] = None,
                      click_offset: Optional[Offset] = None, max_clicks: Optional[int] = None) -> bool:
        if isinstance(pattern, Resource):
            pattern = MatchPattern.by_tag(pattern)
        assert isinstance(pattern, MatchPattern)
        action = action_factory.new_action().click_capture_match(patterns=pattern, threshold=threshold, capture_area=area,
                                                                 click_offset=click_offset, max_clicks=max_clicks, click_delay=click_delay)
        # dont induce delay if clicking failed
        results = self.__scripting.call_client_action(action, client_id=self.__cid)
        if self.__scripting.verify_action_results(results, bool, True, action):
            self.__scripting.compensate_lag(click_delay)
            return True
        return False

    def __find_match_by_tag(self, pattern_tag: Resource, area: Optional[CaptureArea] = None, threshold: Optional[float] = None) -> Optional[Rect]:
        pattern = MatchPattern.by_tag(pattern_tag)
        action = action_factory.new_action().find_capture_match(patterns=pattern, capture_area=area, threshold=threshold)
        results = self.__scripting.call_client_action(action, client_id=self.__cid)
        if results is None:
            self.__scripting.fail_script(pattern_tag)
        result = results[0]
        if result is None:
            return None
        tag_id, loc_rect = result
        if tag_id != pattern_tag.resource_id:
            return None
        return Rect.decode_rect(loc_rect)

    def __find_match_by_pattern(self, pattern: MatchPattern, area: CaptureArea, threshold: Optional[float] = None) -> Optional[Tuple[str, Rect]]:
        action = action_factory.new_action().find_capture_match(patterns=pattern, capture_area=area, threshold=threshold)
        results = self.__scripting.call_client_action(action, client_id=self.__player.get_client_id())
        if results is None:
            self.__scripting.fail_script(pattern)
        result = results[0]
        if result is None:
            return None
        tag, loc_rect = result
        return tag, Rect.decode_rect(loc_rect)

    def __find_multiple_match_by_pattern(self, pattern: MatchPattern, area: CaptureArea, threshold: Optional[float] = None,
                                         max_matches: Optional[int] = None) -> List[Tuple[str, Rect]]:
        action = action_factory.new_action().find_multiple_capture_match(patterns=pattern, capture_area=area, threshold=threshold, max_matches=max_matches)
        all_results = self.__scripting.call_client_action(action, client_id=self.__player.get_client_id())
        if all_results is None:
            self.__scripting.fail_script(pattern)
        action_result = all_results[0]
        return [(tag, Rect.decode_rect(loc_rect)) for (tag, loc_rect) in action_result]

    def has_runtime(self) -> bool:
        return True

    def get_runtime(self) -> IRuntime:
        return self.__runtime

    def get_scripting(self) -> ScriptingToolkit:
        return self.__scripting

    def get_player(self) -> IPlayer:
        return self.__player

    def build_command(self, command: str, once=True, passthrough=False) -> IAction:
        command_action = action_factory.new_action()
        command_action.inject_command(injector_name=self.__player.get_command_injector_name(), injected_command=command, once=once, passthrough=passthrough)
        command_action.append(self.__player.get_inputs().special.consume_command_injection)
        return command_action

    def build_multicommand(self, commands: Union[str, List[str]], prefix: Optional[str] = None) -> IAction:
        if isinstance(commands, str):
            commands = list(commands.split('\n'))
        command_action = action_factory.new_action()
        injector_name = self.__player.get_command_injector_name()
        for i, single_line in enumerate(commands):
            if prefix:
                cmd = f'{prefix} {single_line}'
            else:
                cmd = single_line
            passthrough = i < len(commands) - 1
            command_action = command_action.inject_command(injector_name=injector_name, injected_command=cmd, once=True, passthrough=passthrough)
        return command_action.append(self.__player.get_inputs().special.consume_command_injection)

    def command_async(self, command: str):
        action = self.build_command(command, True, False)
        self.post_player_action(action)

    def command_sync(self, command: str) -> bool:
        action = self.build_command(command, True, False)
        return self.player_bool_action(action)

    def sleep(self, duration: float):
        self.__scripting.sleep(duration)

    def call_player_action(self, action: IAction, delay: Optional[float] = None) -> Optional[List]:
        return self.__scripting.call_client_action(action=action, client_id=self.__cid, delay=delay)

    def post_player_action(self, action: IAction, delay: Optional[float] = None):
        self.__scripting.post_client_action(action=action, client_id=self.__cid, delay=delay)

    def post_player_action_sync(self, action: IAction, delay: Optional[float] = None):
        self.__scripting.post_client_action_sync(action=action, client_id=self.__cid, delay=delay)

    def player_bool_action(self, action: IAction, delay: Optional[float] = None) -> bool:
        return self.__scripting.client_bool_action(action=action, client_id=self.__cid, delay=delay)

    def assert_action_results(self, results: List[Any], expected_type: Any, expected_value: Any, fail_reason: str, action: IAction):
        if not self.__scripting.verify_action_results(results, expected_type, expected_value, action):
            self.__scripting.fail_script(fail_reason)

    def __show_capture(self, area: CaptureArea):
        ac = action_factory.new_action().get_capture(capture_area=area)
        capture_str = self.call_player_action(ac)[0]
        capture = Capture.decode_capture(capture_str)
        self.__ocr.show_image(capture)

    @_Decorators.hide_overlay_for_local_player
    def show_capture(self, area: CaptureArea):
        self.__show_capture(area)

    @_Decorators.hide_overlay_for_local_player
    def click_first_from_top(self, tag: Resource, object_heigth: int, repeat: RepeatMode, delay=CLICK_DELAY) -> bool:
        return self.__repeat_cb(lambda: self.__click_first_from_top(tag=tag, object_heigth=object_heigth, click_delay=delay), repeat)

    @_Decorators.hide_overlay_for_local_player
    def click_match(self, pattern: Union[MatchPattern, Resource], repeat: RepeatMode, delay=CLICK_DELAY,
                    area: Optional[CaptureArea] = None, threshold: Optional[float] = None, click_offset: Optional[Offset] = None,
                    max_clicks: Optional[int] = None) -> bool:
        return self.__repeat_cb(lambda: self.__click_match(pattern=pattern, click_delay=delay, area=area, threshold=threshold,
                                                           click_offset=click_offset, max_clicks=max_clicks), repeat)

    @_Decorators.hide_overlay_for_local_player
    def assert_click_match(self, pattern: Union[MatchPattern, Resource], repeat: RepeatMode, delay=CLICK_DELAY,
                           area: Optional[CaptureArea] = None, threshold: Optional[float] = None, click_offset: Optional[Offset] = None,
                           max_clicks: Optional[int] = None):
        result = self.__repeat_cb(lambda: self.__click_match(pattern=pattern, click_delay=delay, area=area, threshold=threshold,
                                                             click_offset=click_offset, max_clicks=max_clicks), repeat)
        if not result:
            if MutableFlags.SHOW_FAILED_CAPTURE_ASSERTS:
                self.__show_capture(area)
            self.__scripting.fail_script(f'could not click {pattern}')

    @_Decorators.hide_overlay_for_local_player
    def find_match_by_tag(self, pattern_tag: Resource, repeat: RepeatMode, area: Optional[CaptureArea] = None,
                          threshold: Optional[float] = None) -> Optional[Rect]:
        return self.__repeat_cb(lambda: self.__find_match_by_tag(pattern_tag=pattern_tag, area=area, threshold=threshold), repeat)

    @_Decorators.hide_overlay_for_local_player
    def assert_find_match_by_tag(self, pattern_tag: Resource, repeat: RepeatMode, area: Optional[CaptureArea] = None,
                                 threshold: Optional[float] = None) -> Optional[Rect]:
        result = self.__repeat_cb(lambda: self.__find_match_by_tag(pattern_tag=pattern_tag, area=area, threshold=threshold), repeat)
        if not result:
            if MutableFlags.SHOW_FAILED_CAPTURE_ASSERTS:
                self.__show_capture(area)
            self.__scripting.fail_script(f'Tag not found: {pattern_tag}')
        return result

    @_Decorators.hide_overlay_for_local_player
    def find_match_by_pattern(self, pattern: MatchPattern, repeat: RepeatMode, area: Optional[CaptureArea] = None,
                              threshold: Optional[float] = None) -> Optional[Tuple[str, Rect]]:
        return self.__repeat_cb(lambda: self.__find_match_by_pattern(pattern=pattern, area=area, threshold=threshold), repeat)

    @_Decorators.hide_overlay_for_local_player
    def find_multiple_match_by_pattern(self, pattern: MatchPattern, repeat: RepeatMode, area: Optional[CaptureArea] = None,
                                       threshold: Optional[float] = None, max_matches: Optional[int] = None) -> List[Tuple[str, Rect]]:
        return self.__repeat_cb(lambda: self.__find_multiple_match_by_pattern(pattern=pattern, area=area, threshold=threshold,
                                                                              max_matches=max_matches), repeat)

    @_Decorators.hide_overlay_for_local_player
    def try_click_ok(self, click_delay=CLICK_DELAY) -> bool:
        pattern = MatchPattern.by_tags([ui_patterns.PATTERN_BUTTON_TEXT_OK,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE,
                                        ])
        action = action_factory.new_action().click_capture_match(pattern, max_clicks=1, click_delay=click_delay)
        return self.player_bool_action(action=action, delay=click_delay)

    @_Decorators.hide_overlay_for_local_player
    def try_click_accepts(self, max_clicks=5, click_delay=CLICK_DELAY) -> bool:
        pattern = MatchPattern.by_tags([ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT,
                                        ui_patterns.PATTERN_BUTTON_TEXT_YES,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE_SMALL,
                                        ])
        action = action_factory.new_action().click_capture_match(pattern, max_clicks=max_clicks, click_delay=click_delay)
        return self.player_bool_action(action=action, delay=click_delay)

    @_Decorators.hide_overlay_for_local_player
    def try_close_all_windows(self, close_externals=False, max_clicks=10, click_delay=CLICK_DELAY) -> bool:
        tags = [ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT,
                ui_patterns.PATTERN_BUTTON_TEXT_YES,
                ui_patterns.PATTERN_BUTTON_TEXT_OK,
                ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE,
                ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE_SMALL,
                ui_patterns.PATTERN_BUTTON_X,
                ]
        if close_externals:
            tags.extend([external_patterns.PATTERN_TV_BUTTON_OK])
        pattern = MatchPattern.by_tags(tags)
        action = action_factory.new_action().click_capture_match(pattern, max_clicks=max_clicks, click_delay=click_delay)
        return self.player_bool_action(action=action, delay=click_delay)

    @_Decorators.ignore_for_local_player(True)
    def try_close_all_access(self) -> bool:
        window_area = CaptureArea()
        all_access_pattern = MatchPattern.by_tag(ui_patterns.PATTERN_GFX_ALL_ACCESS_SMALL)
        action_1 = action_factory.new_action().click_capture_match(patterns=all_access_pattern, capture_area=window_area, click_delay=CLICK_DELAY)
        result = self.call_player_action(action_1)
        if result is None or not result[0]:
            return False
        action_2 = action_factory.new_action().click_capture_match(patterns=all_access_pattern, capture_area=window_area, click_delay=CLICK_DELAY,
                                                                   click_offset=Offset(386, 192, Offset.REL_WIND_BOX))
        result = self.call_player_action(action_2)
        return result and result[0]

    def activate_window(self, window_title: Optional[str] = None) -> bool:
        if not window_title:
            window_title = EQ2_WINDOW_NAME
        action = action_factory.new_action().window_activate(window_title)
        return self.player_bool_action(action)

    def __capture_area(self, capture_area: CaptureArea) -> Optional[Capture]:
        capture_action = action_factory.new_action().get_capture(capture_area)
        capture_result = self.call_player_action(capture_action)
        if not capture_result:
            return None
        decoded_capture = Capture.decode_capture(capture_result[0])
        return decoded_capture

    def __capture_box(self, box: Rect, mode: CaptureMode) -> Optional[Capture]:
        window_area = CaptureArea(mode=mode)
        capture_area = window_area.capture_rect(box, relative=True)
        return self.__capture_area(capture_area)

    @_Decorators.hide_overlay_for_local_player
    def capture_box(self, box: Rect, mode: CaptureMode) -> Optional[Capture]:
        return self.__capture_box(box, mode=mode)

    @_Decorators.hide_overlay_for_local_player
    def capture_area(self, capture_area: CaptureArea) -> Optional[Capture]:
        return self.__capture_area(capture_area)

    @_Decorators.hide_overlay_for_local_player
    def ocr_normal_line_of_text(self, capture_or_box: Union[Rect, Capture], description: Optional[str] = None, rect: Optional[Rect] = None) -> Optional[str]:
        if isinstance(capture_or_box, Rect):
            capture = self.__capture_box(box=capture_or_box, mode=CaptureMode.COLOR)
            if not capture:
                return None
        else:
            capture = capture_or_box
        if rect:
            capture = capture.crop(rect)
        ocr_text = self.__ocr.ocr_normal_line_of_text_no_bg(capture, info=description)
        return ocr_text

    @_Decorators.hide_overlay_for_local_player
    def ocr_single_digit(self, capture_or_box: Union[Rect, Capture], description: Optional[str] = None,
                         rect: Optional[Rect] = None, font_color: Optional[int] = None) -> Optional[int]:
        if isinstance(capture_or_box, Rect):
            capture = self.__capture_box(box=capture_or_box, mode=CaptureMode.COLOR)
            if not capture:
                return None
        else:
            capture = capture_or_box
        if rect:
            capture = capture.crop(rect)
        digit = self.__ocr.ocr_single_digit_with_bg_noise(capture, info=description, font_color=font_color)
        if digit is None:
            return None
        return digit

    def save_capture(self, capture: Capture, info):
        if MutableFlags.SAVE_SCRIPT_CAPTURES:
            self.__ocr.save_image(capture.get_array(), info)

    # noinspection PyMethodMayBeStatic
    def get_capture_area(self, rect: Rect, mode=CaptureMode.DEFAULT, relative=True, winflags=CaptureWindowFlags.DEFAULTS) -> CaptureArea:
        if MutableFlags.ALWAYS_CAPTURE_MAIN_WINDOW:
            window_area = CaptureArea(mode=mode, wintitle=EQ2_WINDOW_NAME, winflags=winflags)
        else:
            window_area = CaptureArea(mode=mode, winflags=winflags)
        rect_area = window_area.capture_rect(rect, relative=relative)
        return rect_area

    def click_screen_middle(self) -> bool:
        self.try_close_all_windows()
        screen_mid_x = self.__player.get_inputs().screen.W // 2
        screen_mid_y = self.__player.get_inputs().screen.H // 2
        click_screen_middle = action_factory.new_action().mouse(x=screen_mid_x, y=screen_mid_y, button='left')
        result = self.player_bool_action(click_screen_middle, delay=CLICK_DELAY)
        return result

    def click_viewport_middle(self) -> bool:
        self.try_close_all_windows()
        vp_mid_x = self.__player.get_inputs().screen.VP_W_center
        vp_mid_y = self.__player.get_inputs().screen.VP_H_center
        mouse_move_to_middle_vp = action_factory.new_action().mouse(x=vp_mid_x, y=vp_mid_y, button='left')
        result = self.player_bool_action(mouse_move_to_middle_vp, delay=CLICK_DELAY)
        return result

    def set_camera_distance(self, distance: int) -> bool:
        scrolls = 30
        scroll_view = action_factory.new_action().mouse_scroll(scroll_up=True, clicks=scrolls)
        if not self.player_bool_action(scroll_view, delay=2.0):
            return False
        if not self.set_max_camera_distance(distance):
            return False
        scroll_view = action_factory.new_action().mouse_scroll(scroll_up=False, clicks=scrolls)
        result = self.player_bool_action(scroll_view, delay=2.0)
        if result:
            self.set_max_camera_distance(35)
        return result

    def set_max_camera_distance(self, distance=35) -> bool:
        if distance < 5 or distance > 35:
            old_distance = distance
            distance = min(max(distance, 5), 35)
            logger.warn(f'wrong camera distance: {old_distance}, changed to {distance}')
        return self.command_sync(f'ics_maxcameradistance {distance}')

    def move_mouse_to(self, point: Point, speed=2) -> bool:
        mouse_move_to_middle = action_factory.new_action().mouse(x=point.x, y=point.y, speed=speed, button=None)
        return self.player_bool_action(mouse_move_to_middle, delay=0.0)

    def move_mouse_to_middle(self) -> bool:
        screen_mid_x = self.__player.get_inputs().screen.W // 2
        screen_mid_y = self.__player.get_inputs().screen.H // 2
        return self.move_mouse_to(Point(x=screen_mid_x, y=screen_mid_y))

    def click_at(self, x: int, y: int, button='left', delay=0.1) -> bool:
        click_action = action_factory.new_action().mouse(x=x, y=y, button=button)
        return self.player_bool_action(click_action, delay=delay)

    def switch_to_client_window(self) -> bool:
        return self.get_runtime().master_bridge.send_switch_to_client_window(player=self.__player, sync=True)


class Procedure:
    def __init__(self, scripting: PlayerScriptingToolkit):
        self.__player_scripting = scripting

    def _get_runtime(self) -> IRuntime:
        return self.__player_scripting.get_runtime()

    def _get_toolkit(self) -> ScriptingToolkit:
        return self.__player_scripting.get_scripting()

    def _get_player(self) -> IPlayer:
        return self.__player_scripting.get_player()

    def _get_player_toolkit(self) -> PlayerScriptingToolkit:
        return self.__player_scripting
