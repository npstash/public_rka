from __future__ import annotations

import math
import random
from threading import Condition
from typing import List, Any, Optional

from rka.components.events import Event
from rka.components.impl.factories import CaptureFactory, AutomationFactory
from rka.components.ui.capture import MatchPattern, Radius, CaptureArea
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.rka_constants import GAME_LAG, CLICK_DELAY
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.scripting import RepeatMode
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.toolkit import Procedure, PlayerScriptingToolkit
from rka.eq2.master.triggers import IPlayerTrigger
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.shared.client_events import ClientEvents


class ClickAtPointerProcedure(Procedure):
    def __init__(self, script: PlayerScriptingToolkit):
        Procedure.__init__(self, script)

    def click(self, size: int, threshold: float, scale_var: float):
        cs = CaptureFactory.create_capture_service()
        aut = AutomationFactory.create_automation()
        mpos = aut.get_mouse_pos()
        cloc = Radius(mpos[0], mpos[1], size)
        capture = cs.get_capture(CaptureArea().capture_radius(cloc, relative=True))
        match = MatchPattern.by_capture(capture).set_scale(1.0 - scale_var, 1.0 + scale_var)
        success = self._get_player_toolkit().click_match(pattern=match, repeat=RepeatMode.REPEAT_ON_FAIL, threshold=threshold)
        if not success:
            self._get_runtime().overlay.log_event(f'click failed for {self._get_player()}', Severity.Normal)
        cs.close_capture_service()


class TriggerReaderProcedure(Procedure):
    def __init__(self, script: PlayerScriptingToolkit, game_command: Optional[str]):
        Procedure.__init__(self, script)
        self.trigger_read_attempts = 3
        self.trigger_read_wait_time = 5.0 + GAME_LAG
        self.__game_command = game_command
        self.__checker_action = None
        if game_command is not None:
            self.__checker_action = script.build_command(game_command)
        self.__last_results = list()
        self.__trigger_condition = Condition()
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        self.__trigger = trigger_factory.new_trigger(name=self.__game_command)
        self.__trigger.add_action(self.__trigger_action)

    def _set_result(self, result: Any):
        logger.detail(f'result set: {result}')
        with self.__trigger_condition:
            self.__last_results.append(result)
            self.__trigger_condition.notify_all()

    def __trigger_action(self, event: Event):
        result = self._get_object(event)
        self._set_result(result)

    def wait_for_trigger(self, timeout: float) -> Optional[Any]:
        with self.__trigger_condition:
            if not self.__last_results:
                self._get_toolkit().wait(self.__trigger_condition, timeout)
            return self.__last_results[-1] if self.__last_results else None

    def _get_object(self, event: Event) -> Any:
        raise NotImplementedError()

    def _get_trigger(self) -> IPlayerTrigger:
        return self.__trigger

    def _get_new_result(self) -> Optional[Any]:
        assert self.__checker_action, f'No action available to wait for ({self})'
        self.clear_last_results()
        new_result = None
        attempts = self.trigger_read_attempts
        while attempts > 0:
            logger.detail(f'posting trigger checker action {self.__checker_action}')
            self._get_player_toolkit().post_player_action(self.__checker_action)
            new_result = self.wait_for_trigger(self.trigger_read_wait_time)
            if new_result is not None:
                break
            attempts -= 1
        if new_result is None:
            logger.warn(f'could get not result of {self.__game_command} from {self._get_player()}')
            return None
        logger.detail(f'new result of {self.__game_command} from {self._get_player()} is {new_result}')
        return new_result

    def get_last_result(self) -> Optional[Any]:
        return self.__last_results[-1] if self.__last_results else None

    def get_last_results(self) -> List[Any]:
        return list(self.__last_results)

    def get_and_clear_last_results(self) -> List[Any]:
        results = self.__last_results
        self.__last_results = list()
        return list(results)

    def clear_last_results(self):
        self.__last_results = list()


class GetCommandResult(TriggerReaderProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit, game_command: str, result_re: str, result_re_group=1):
        TriggerReaderProcedure.__init__(self, scripting, game_command=game_command)
        self.result_re_group = result_re_group
        self._get_trigger().add_parser_events(result_re)

    def _get_object(self, event: ClientEvents.PARSER_MATCH) -> Optional[str]:
        match = event.match()
        if not match.lastindex:
            return None
        return match.group(self.result_re_group)

    def run_command(self) -> Optional[str]:
        try:
            self._get_trigger().start_trigger()
            result = self._get_new_result()
        finally:
            self._get_trigger().cancel_trigger()
        return result


class ClickWhenCursorType(Procedure):
    CURSOR_FP_NORMAL = b'c$4\xcf\xc6\x9b\xd7\x16\xc4\x015w\x15\xb2*8'
    CURSOR_FP_WHITE = b'\xc7\xd1\xd2X\xdai%\xbe\xaa\xae,\xc9\xa8\x10m\xea'
    CURSOR_FP_DIALOG = b'*\xd5\x95\xbf\xeaP\x1f7%\xc4\xb2\x00\xdc\xd0\x82\x88'
    CURSOR_FP_BANK = b'\x99\x97\xbeW\xdb\xd2g\xad\xaf\x9cM$L\xfc\r\xba'
    CURSOR_FP_MERCHANT = b'\xf0\x83\x98\xf1\x08\nWY\xa3\x97*\xee\xdb\xfc@$'
    CURSOR_FP_TRANSMUTE = b'\x14,\xf2\xa4I\xc9\x87\x81t}4\x82\x99\xa407'
    CURSOR_FP_HOSTILE = b'e$\x8d\xbcw\xea\xf0>\xcd\x93\xeb\x87\xcf\x16\xcb:'
    CURSOR_FP_ACTIVEHAND = b'ne\x96@\x8by\xda"/\x1b\x07\x8ac\x9c\xc0M'

    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)

    def click_when_cursor_type_is(self, cursor_fingerprint: bytes, around_x: int, around_y: int, search_range=150) -> bool:
        cursor_fp_get_action = action_factory.new_action().get_cursor_fingerprint()
        current_fingerprint = None
        current_range = 0
        turn = 0
        accumulated_s = 0.0
        accumulated_w = 0.0
        matched_count = 0
        while current_fingerprint != cursor_fingerprint and current_range <= search_range and matched_count < 5:
            w = math.pi / (2.0 * math.log(5.0 * turn + 2, math.e))
            s = 10.0 / (turn + 1.0) + 1.0
            x = accumulated_s * math.cos(accumulated_w) + around_x
            y = accumulated_s * math.sin(accumulated_w) + around_y
            move_mouse_action = action_factory.new_action().mouse(x=int(x), y=int(y), button=None)
            if not self._get_player_toolkit().call_player_action(move_mouse_action):
                break
            result = self._get_player_toolkit().call_player_action(cursor_fp_get_action)
            if result:
                current_fingerprint = result[0].data
            else:
                return False
            if current_fingerprint == cursor_fingerprint:
                # repeat, make sure the cursor isnt "blinking"
                matched_count += 1
                # wait up to 0.1 sec to avoid rapid checks with same result
                self._get_toolkit().sleep(random.random() * 0.1)
                continue
            else:
                matched_count = 0
            dx = x - around_x
            dy = y - around_y
            current_range = math.sqrt(dx * dx + dy * dy)
            accumulated_w += w
            accumulated_s += s
            turn += 1
        if current_fingerprint == cursor_fingerprint:
            click_action = action_factory.new_action().mouse(x=None, y=None, button='left')
            if self._get_player_toolkit().call_player_action(click_action, delay=CLICK_DELAY):
                return True
        return False
