import subprocess
from time import sleep
from typing import Dict, Any, List, Tuple, Optional

from rka.components.impl.factories import AutomationFactory, CaptureFactory, CursorCaptureFactory
from rka.components.io.injector import IInjector
from rka.components.io.log_service import LogLevel
from rka.components.rpc_brokers.command_util import command_debug_str
from rka.components.rpc_services import IInterpreter
from rka.components.rpc_services.remote import InterpretException
from rka.components.ui.automation import IAutomation, MouseCoordMode
from rka.components.ui.capture import CaptureArea, MatchPattern, Capture, Offset, ICaptureService
from rka.components.ui.cursor_capture import ICursorCapture
from rka.eq2.shared.control import logger
from rka.eq2.shared.control.action_id import ACTION_ID_KEY, ActionID
from rka.eq2.shared.host import HostConfig
from rka.util.util import to_bool


class AbstractInterpreter(IInterpreter):
    def _interpret_action(self, action_id: ActionID, command: Dict[str, Any]) -> Any:
        raise NotImplementedError()

    def interpret(self, command: Dict[str, Any]) -> Optional[bool]:
        if logger.get_level() <= LogLevel.DETAIL:
            logger.detail(f'interpreting: {command_debug_str(LogLevel.DETAIL, command)}')
        elif logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'interpreting: {command_debug_str(LogLevel.DEBUG, command)}')
        if ACTION_ID_KEY not in command.keys():
            # TODO make it action ID key?? maybe not need to handle ping specifically, just a NOP
            if 'ping' in command.keys():
                logger.detail(f'handling ping command')
                return True
            logger.error(f'missing action code, ignoring: {command}')
            return None
        action_id = ActionID(command[ACTION_ID_KEY])
        result = self._interpret_action(action_id, command)
        logger.debug(f'interpret result: {result}')
        return result


class ActionInterpreter(AbstractInterpreter):
    def __init__(self, host_config: HostConfig, injectors: List[IInjector]):
        self.__injectors: Dict[str, IInjector] = {injector.get_name(): injector for injector in injectors}
        self.__host_config = host_config
        self.__config_window_name = None
        self.__automation: IAutomation = AutomationFactory.create_automation()
        self.__captureservice = CaptureFactory.create_capture_service()
        self.__cursorcapture = CursorCaptureFactory.create_cursor_capture()

    def _get_automation(self) -> IAutomation:
        return self.__automation

    def _get_capture_service(self) -> ICaptureService:
        return self.__captureservice

    def _get_cursor_capture(self) -> ICursorCapture:
        return self.__cursorcapture

    def key(self, command: Dict[str, Any]) -> bool:
        count = int(command['count'])
        key_type_delay = None
        if 'key_type_delay' in command.keys():
            key_type_delay = float(command['key_type_delay'])
        for i in range(count):
            keyspec = str(command['key'])
            self.__automation.send_key_spec(keyspec, key_type_delay)
        return True

    def text(self, command: Dict[str, Any]) -> bool:
        text = str(command['text'])
        key_type_delay = None
        if 'key_type_delay' in command.keys():
            key_type_delay = float(command['key_type_delay'])
        self.__automation.send_text(text, key_type_delay)
        return True

    def mouse(self, command: Dict[str, Any]) -> bool:
        if self.__config_window_name is not None:
            self.__automation.activate_window(self.__config_window_name)
        click_only = False
        if 'x' not in command.keys() or command['x'] is None:
            click_only = True
        if 'y' not in command.keys() or command['y'] is None:
            click_only = True
        if not click_only:
            x = int(command['x'])
            y = int(command['y'])
            if 'speed' in command.keys():
                speed = int(command['speed'])
            else:
                speed = None
            if 'coord_mode' in command.keys():
                coord_mode = MouseCoordMode(int(command['coord_mode']))
            else:
                coord_mode = MouseCoordMode.RELATIVE_WINDOW
            self.__automation.mouse_move(x, y, speed=speed, coord_mode=coord_mode)
        if 'button' in command.keys() and command['button'] is not None:
            button = str(command['button'])
            modifiers = None
            if 'modifiers' in command.keys():
                modifiers = command['modifiers']
            self.__automation.mouse_click(button, modifiers=modifiers)
        elif click_only:
            raise InterpretException(f'missing button informatio for {command}')
        return True

    def double_click(self, _command: Dict[str, Any]) -> bool:
        self.__automation.mouse_double_click()
        return True

    def mouse_scroll(self, command: Dict[str, Any]) -> bool:
        scroll_up = int(command['scroll_up'])
        clicks = 1
        if 'clicks' in command.keys():
            clicks = int(command['clicks'])
        self.__automation.mouse_scroll(scroll_up, clicks)
        return True

    def window_activate(self, command: Dict[str, Any]) -> bool:
        window_name = str(command['window'])
        if 'set_default' in command.keys():
            set_default = bool(command['set_default'])
            if set_default:
                logger.info(f'Setting default window name to {window_name}')
                self.__config_window_name = window_name
        if not window_name:
            logger.warn(f'Window name is None')
            raise InterpretException(f'Window name is None in {command}')
        wait_time = None
        if 'wait_time' in command.keys():
            wait_time = command['wait_time']
        maximize = self.__host_config.maximized_window
        self.__automation.activate_window(window_name, win_wait=wait_time, maximize=maximize)
        return True

    def window_check(self, command: Dict[str, Any]) -> bool:
        window_name = str(command['window'])
        return self.__automation.is_window_active(window_name)

    # noinspection PyMethodMayBeStatic
    def delay(self, command: Dict[str, Any]) -> bool:
        delay = float(command['delay'])
        sleep(delay)
        return True

    # noinspection PyMethodMayBeStatic
    def process(self, command: Dict[str, Any]) -> bool:
        path = str(command['path'])
        args = str(command['args']).split()
        subprocess.run([path, *args])
        return True

    def inject_command(self, command: Dict[str, Any]) -> bool:
        injected_command = str(command['injected_command'])
        injector_name = str(command['injector_name'])
        once = to_bool(command['once'])
        passthrough = to_bool(command['passthrough'])
        command_id = str(command['command_id'])
        duration = None
        if 'duration' in command.keys():
            duration = command['duration']
        return self.__injectors[injector_name].inject_command(command=injected_command, command_id=command_id,
                                                              once=once, pass_through=passthrough, duration=duration)

    def remove_injectd_command(self, command: Dict[str, Any]) -> bool:
        injector_name = str(command['injector_name'])
        command_id = str(command['command_id'])
        self.__injectors[injector_name].remove_command(command_id)
        # don't inform about failed injection cancels, it just means the injection wasnt added or already expired
        return True

    def inject_prefix(self, command: Dict[str, Any]) -> bool:
        prefix = str(command['prefix'])
        injector_name = str(command['injector_name'])
        self.__injectors[injector_name].set_injection_prefix(prefix)
        return True

    def inject_postfix(self, command: Dict[str, Any]) -> bool:
        postfix = str(command['postfix'])
        injector_name = str(command['injector_name'])
        self.__injectors[injector_name].set_injection_postfix(postfix)
        return True

    def find_capture_match(self, command: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        patterns = MatchPattern.decode_pattern(command['patterns'])
        if 'capture_area' in command.keys():
            capture_area = CaptureArea.decode_area(command['capture_area'])
            capture_area.set_default_wintitle(self.__config_window_name)
        else:
            capture_area = CaptureArea(mode=patterns.get_mode(), wintitle=self.__config_window_name)
        threshold = None
        if 'threshold' in command.keys():
            threshold = float(command['threshold'])
        result = self.__captureservice.find_capture_match(patterns, capture_area, threshold)
        if result is None:
            return None
        tag_str, rect = result
        return tag_str, rect.encode_rect()

    def find_multiple_capture_match(self, command: Dict[str, Any]) -> List[Tuple[str, str]]:
        patterns = MatchPattern.decode_pattern(command['patterns'])
        if 'capture_area' in command.keys():
            capture_area = CaptureArea.decode_area(command['capture_area'])
            capture_area.set_default_wintitle(self.__config_window_name)
        else:
            capture_area = CaptureArea(mode=patterns.get_mode(), wintitle=self.__config_window_name)
        threshold = None
        if 'threshold' in command.keys():
            threshold = float(command['threshold'])
        max_matches = None
        if 'max_matches' in command.keys():
            max_matches = int(command['max_matches'])
        result = self.__captureservice.find_multiple_capture_match(patterns, capture_area, threshold, max_matches)
        return [(tag_str, rect.encode_rect()) for (tag_str, rect) in result]

    def get_capture(self, command: Dict[str, Any]) -> Optional[str]:
        capture_area = CaptureArea.decode_area(command['capture_area'])
        capture = self.__captureservice.get_capture(capture_area)
        if not capture:
            return None
        return capture.encode_capture()

    def save_capture(self, command: Dict[str, Any]) -> bool:
        capture = Capture.decode_capture(command['capture'])
        tag = command['tag']
        return self.__captureservice.save_capture_as_tag(capture, tag)

    def click_capture_match(self, command: Dict[str, Any]) -> bool:
        patterns = MatchPattern.decode_pattern(command['patterns'])
        if 'capture_area' in command.keys():
            capture_area = CaptureArea.decode_area(command['capture_area'])
            capture_area.set_default_wintitle(self.__config_window_name)
        else:
            capture_area = CaptureArea(mode=patterns.get_mode(), wintitle=self.__config_window_name)
        threshold = None
        if 'threshold' in command.keys():
            threshold = float(command['threshold'])
        max_clicks = None
        if 'max_clicks' in command.keys():
            max_clicks = int(command['max_clicks'])
        click_delay = None
        if 'click_delay' in command.keys():
            click_delay = float(command['click_delay'])
        click_offset = None
        if 'click_offset' in command.keys():
            click_offset = Offset.decode_offset(command['click_offset'])
        return self.__captureservice.click_capture_match(self._get_automation(), patterns, capture_area, threshold, max_clicks, click_delay, click_offset)

    def capture_cursor(self, _command: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        mask, color = self.__cursorcapture.get_cursor_base64_bitmaps()
        mask_d, color_d = None, None
        if mask:
            mask_d = mask.save_to_dict()
        if color:
            color_d = color.save_to_dict()
        return mask_d, color_d

    def get_cursor_fingerprint(self, _command: Dict[str, Any]) -> Optional[bytes]:
        return self.__cursorcapture.get_cursor_fingerprint()

    action_interpreter_mapping: Dict[ActionID, callable] = {
        ActionID.KEY: key,
        ActionID.TEXT: text,
        ActionID.MOUSE: mouse,
        ActionID.DOUBLE_CLICK: double_click,
        ActionID.MOUSE_SCROLL: mouse_scroll,
        ActionID.WINDOW_ACTIVATE: window_activate,
        ActionID.WINDOW_CHECK: window_check,
        ActionID.PROCESS: process,
        ActionID.DELAY: delay,
        ActionID.INJECT_COMMAND: inject_command,
        ActionID.REMOVE_INJECTED_COMMAND: remove_injectd_command,
        ActionID.INJECT_PREFIX: inject_prefix,
        ActionID.INJECT_POSTFIX: inject_postfix,
        ActionID.GET_CAPTURE_MATCH: get_capture,
        ActionID.FIND_CAPTURE_MATCH: find_capture_match,
        ActionID.FIND_MULTIPLE_CAPTURE_MATCH: find_multiple_capture_match,
        ActionID.CLICK_CAPTURE_MATCH: click_capture_match,
        ActionID.SAVE_CAPTURE: save_capture,
        ActionID.CAPTURE_CURSOR: capture_cursor,
        ActionID.CURSOR_FINGERPRINT: get_cursor_fingerprint,
    }

    action_cancel_mapping: Dict[ActionID, callable] = {
        ActionID.INJECT_COMMAND: remove_injectd_command,
    }

    def _interpret_action(self, action_id: ActionID, command: Dict[str, Any]) -> Any:
        if action_id not in ActionInterpreter.action_interpreter_mapping.keys():
            logger.info(f'action code not in mapping: {command}')
            raise ValueError(action_id)
        cancel = False
        if 'cancel' in command.keys():
            cancel = to_bool(command['cancel'])
        if cancel:
            if action_id not in ActionInterpreter.action_cancel_mapping.keys():
                logger.error(f'action not cancellable: {command}')
                return False
            action_handler = ActionInterpreter.action_cancel_mapping[action_id]
        else:
            action_handler = ActionInterpreter.action_interpreter_mapping[action_id]
        return action_handler(self, command)
