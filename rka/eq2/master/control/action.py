from __future__ import annotations

import time
from typing import List, Any, Dict, Tuple, Callable, Optional, Iterable

from rka.components.io.log_service import LogService, LogLevel
from rka.components.rpc_brokers.command_util import set_command_blocking, set_command_sync
from rka.components.rpc_services import IClientBrokerProxy
from rka.components.rpc_services.client_proxy import ClientBrokerProxyFactory
from rka.components.ui.automation import MouseCoordMode
from rka.components.ui.capture import MatchPattern, CaptureArea, Capture, Offset
from rka.eq2.configs.shared.rka_constants import ACTION_MEASURE_DELAY, ACTION_OVERHEAD_DEFAULT
from rka.eq2.master.control import ICommandBuilder, IAction
from rka.eq2.shared.control.action_id import ACTION_ID_KEY, ActionID
from rka.eq2.shared.control.interpreter import ActionInterpreter
from rka.log_configs import LOG_COMMANDS

logger = LogService(LOG_COMMANDS)


class CommandBuilder(ICommandBuilder):
    @staticmethod
    def _synchronization_command(block: Optional[bool] = None, sync: Optional[bool] = None) -> Dict[str, Any]:
        command = {ACTION_ID_KEY: ActionID.DELAY.value,
                   'delay': 0.0}
        if block is not None:
            set_command_blocking(command, block)
        if sync is not None:
            set_command_sync(command, sync)
        return command

    def _add_command(self, command: Dict[str: Any]) -> IAction:
        raise NotImplementedError()

    def key(self, key: str, count=1, key_type_delay: Optional[float] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.KEY.value,
                   'key': key,
                   'count': count}
        if key_type_delay is not None:
            command['key_type_delay'] = key_type_delay
        return self._add_command(command)

    def text(self, text: str, key_type_delay: Optional[float] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.TEXT.value,
                   'text': text,
                   'count': 1}
        if key_type_delay is not None:
            command['key_type_delay'] = key_type_delay
        return self._add_command(command)

    def mouse(self, x: int, y: int, button='left', speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW,
              modifiers: Optional[str] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.MOUSE.value,
                   'x': x,
                   'y': y,
                   'button': button,
                   'coord_mode': coord_mode.value}
        if speed is not None:
            command['speed'] = speed
        if modifiers is not None:
            command['modifiers'] = modifiers
        return self._add_command(command)

    def double_click(self) -> IAction:
        command = {ACTION_ID_KEY: ActionID.DOUBLE_CLICK.value}
        return self._add_command(command)

    def mouse_scroll(self, scroll_up: bool, clicks: Optional[int] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.MOUSE_SCROLL.value,
                   'scroll_up': scroll_up}
        if clicks is not None:
            command['clicks'] = clicks
        return self._add_command(command)

    def window_activate(self, window: str, set_default=False, wait_time: Optional[float] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.WINDOW_ACTIVATE.value,
                   'window': window,
                   'set_default': set_default}
        if wait_time is not None:
            command['wait_time'] = wait_time
        return self._add_command(command)

    def window_check(self, window: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.WINDOW_CHECK.value,
                   'window': window}
        return self._add_command(command)

    def delay(self, delay: float) -> IAction:
        command = {ACTION_ID_KEY: ActionID.DELAY.value,
                   'delay': delay}
        return self._add_command(command)

    def process(self, path: str, args: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.PROCESS.value,
                   'path': path,
                   'args': args}
        return self._add_command(command)

    def inject_command(self, injector_name: str, injected_command: str, once: bool, passthrough: bool,
                       duration: Optional[float] = None, command_id: Optional[str] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.INJECT_COMMAND.value,
                   'injected_command': injected_command,
                   'injector_name': injector_name,
                   'once': once,
                   'passthrough': passthrough}
        if duration is not None:
            command['duration'] = duration
        if command_id is None:
            command_id = injected_command
        command['command_id'] = command_id
        return self._add_command(command)

    def remove_injected_command(self, injector_name: str, command_id: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.REMOVE_INJECTED_COMMAND.value,
                   'injector_name': injector_name,
                   'command_id': command_id}
        return self._add_command(command)

    def inject_prefix(self, injector_name: str, prefix: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.INJECT_PREFIX.value,
                   'prefix': prefix,
                   'injector_name': injector_name}
        return self._add_command(command)

    def inject_postfix(self, injector_name: str, postfix: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.INJECT_POSTFIX.value,
                   'postfix': postfix,
                   'injector_name': injector_name}
        return self._add_command(command)

    def find_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.FIND_CAPTURE_MATCH.value,
                   'patterns': patterns.encode_pattern()}
        if capture_area is not None:
            command['capture_area'] = capture_area.encode_area()
        if threshold is not None:
            command['threshold'] = threshold
        return self._add_command(command)

    def find_multiple_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                                    max_matches: Optional[int] = None) -> IAction:
        command = {ACTION_ID_KEY: ActionID.FIND_MULTIPLE_CAPTURE_MATCH.value,
                   'patterns': patterns.encode_pattern()}
        if capture_area is not None:
            command['capture_area'] = capture_area.encode_area()
        if threshold is not None:
            command['threshold'] = threshold
        if max_matches is not None:
            command['max_matches'] = max_matches
        return self._add_command(command)

    def get_capture(self, capture_area: CaptureArea) -> IAction:
        command = {ACTION_ID_KEY: ActionID.GET_CAPTURE_MATCH.value,
                   'capture_area': capture_area.encode_area()}
        return self._add_command(command)

    def save_capture(self, capture: Capture, tag: str) -> IAction:
        command = {ACTION_ID_KEY: ActionID.SAVE_CAPTURE.value,
                   'capture': capture.encode_capture(),
                   'tag': tag}
        return self._add_command(command)

    def click_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                            max_clicks: Optional[int] = None, click_delay: Optional[float] = None, click_offset: Optional[Offset] = None) -> IAction:
        enc_patterns = patterns.encode_pattern()
        command = {ACTION_ID_KEY: ActionID.CLICK_CAPTURE_MATCH.value,
                   'patterns': enc_patterns}
        if capture_area is not None:
            command['capture_area'] = capture_area.encode_area()
        if threshold is not None:
            command['threshold'] = threshold
        if max_clicks is not None:
            command['max_clicks'] = max_clicks
        if click_delay is not None:
            command['click_delay'] = click_delay
        if click_offset is not None:
            command['click_offset'] = click_offset.encode_offset()
        return self._add_command(command)

    def capture_cursor(self) -> IAction:
        command = {ACTION_ID_KEY: ActionID.CAPTURE_CURSOR.value}
        return self._add_command(command)

    def get_cursor_fingerprint(self) -> IAction:
        command = {ACTION_ID_KEY: ActionID.CURSOR_FINGERPRINT.value}
        return self._add_command(command)

    def custom_action(self, action_id: ActionID, **kwargs) -> IAction:
        command = {ACTION_ID_KEY: action_id.value}
        command.update(kwargs)
        return self._add_command(command)


class ActionDelegate(IAction):
    __next_delegate_id = 0

    def __init__(self, registry: Dict[str, ActionDelegate], name: str, action: Optional[IAction] = None):
        self.__delegate_id = ActionDelegate.__next_delegate_id
        ActionDelegate.__next_delegate_id += 1
        self.__name = name
        self.__action = action
        registry[self.__name] = self

    def __str__(self):
        return f'{self.__name}_{self.__delegate_id}->{str(self.__action)}'

    def __assert_target(self):
        assert self.__action, f'target action not set: {self.__name}'

    def __check_send_target(self) -> bool:
        if not self.__action:
            logger.error(f'target action not set: {self.__name}')
            return False
        return True

    def unwrap(self) -> Optional[IAction]:
        action = self.__action
        while isinstance(action, ActionDelegate):
            action = action.__action
        return action

    def unwrap_delegate(self) -> Optional[IAction]:
        delegate = self
        action = self.__action
        while isinstance(action, ActionDelegate):
            delegate = action
            action = action.__action
        return delegate

    def set_action(self, action: IAction) -> IAction:
        if action is self:
            logger.error(f'recursive delegation of {action}')
            assert False, self
        ac_tmp = action
        while isinstance(ac_tmp, ActionDelegate):
            assert ac_tmp.__action is not self
            ac_tmp = ac_tmp.__action
        self.__action = action
        return self

    def _add_command(self, command: Dict[str: Any]) -> IAction:
        self.__assert_target()
        return self.__action._add_command(command)

    def iter_commands(self) -> Iterable[Dict[str: Any]]:
        self.__assert_target()
        return self.__action.iter_commands()

    def set_default_post_sync(self, sync: bool):
        self.__assert_target()
        self.__action.set_default_post_sync(sync)

    def get_average_delay(self, client_id) -> float:
        self.__assert_target()
        return self.__action.get_average_delay(client_id)

    def post_auto(self, client_id: str) -> bool:
        if not self.__check_send_target():
            return False
        return self.__action.post_auto(client_id)

    def post_async(self, client_id: str, completion_cb: Optional[Callable[[None], None]] = None) -> bool:
        if not self.__check_send_target():
            return False
        return self.__action.post_async(client_id, completion_cb)

    def post_sync(self, client_id: str, completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> bool:
        if not self.__check_send_target():
            return False
        return self.__action.post_sync(client_id, completion_cb)

    def call_action(self, client_id: str) -> Tuple[bool, Optional[List]]:
        if not self.__check_send_target():
            return False, None
        return self.__action.call_action(client_id)

    def post_async_cancel(self, client_id: str):
        if not self.__check_send_target():
            return
        return self.__action.post_async_cancel(client_id)

    def is_cancellable(self) -> bool:
        self.__assert_target()
        return self.__action.is_cancellable()

    def append(self, action: IAction):
        self.__assert_target()
        self.__action.append(action)

    # noinspection PyTypeChecker
    def prototype(self, **kwargs) -> IAction:
        # due to registration of delegates, effect of creating a delegate with new prototype is unpredictable
        assert False, str(self.__action)

    def key(self, key: str, count=1, key_type_delay: Optional[float] = None) -> IAction:
        self.__assert_target()
        self.__action.key(key, count, key_type_delay)
        return self

    def text(self, text: str, key_type_delay: Optional[float] = None):
        self.__action.text(text, key_type_delay)

    def mouse(self, x: int, y: int, button='left', speed: Optional[int] = None, coord_mode=MouseCoordMode.RELATIVE_WINDOW,
              modifiers: Optional[str] = None) -> IAction:
        self.__assert_target()
        self.__action.mouse(x, y, button, speed, coord_mode, modifiers)
        return self

    def double_click(self) -> IAction:
        self.__assert_target()
        self.__action.double_click()
        return self

    def mouse_scroll(self, scroll_up: bool, clicks: Optional[int] = None) -> IAction:
        self.__assert_target()
        self.__action.mouse_scroll(scroll_up, clicks)
        return self

    def window_activate(self, window: str, set_default=False, wait_time: Optional[float] = None) -> IAction:
        self.__assert_target()
        self.__action.window_activate(window, set_default, wait_time)
        return self

    def window_check(self, window: str) -> IAction:
        self.__assert_target()
        self.__action.window_check(window)
        return self

    def delay(self, delay: float) -> IAction:
        self.__assert_target()
        self.__action.delay(delay)
        return self

    def process(self, path: str, args: str) -> IAction:
        self.__assert_target()
        self.__action.process(path, args)
        return self

    def inject_command(self, injector_name: str, injected_command: str, once: bool, passthrough: bool,
                       duration: Optional[float] = None, command_id: Optional[str] = None) -> IAction:
        self.__assert_target()
        self.__action.inject_command(injector_name=injector_name, injected_command=injected_command,
                                     once=once, passthrough=passthrough, duration=duration, command_id=command_id)
        return self

    def remove_injected_command(self, injector_name: str, command_id: str) -> IAction:
        self.__assert_target()
        self.__action.remove_injected_command(injector_name=injector_name, command_id=command_id)
        return self

    def inject_prefix(self, injector_name: str, prefix: str) -> IAction:
        self.__assert_target()
        self.__action.inject_prefix(injector_name, prefix)
        return self

    def inject_postfix(self, injector_name: str, postfix: str) -> IAction:
        self.__assert_target()
        self.__action.inject_postfix(injector_name, postfix)
        return self

    def find_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None) -> IAction:
        self.__assert_target()
        self.__action.find_capture_match(patterns, capture_area, threshold)
        return self

    def find_multiple_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                                    max_matches: Optional[int] = None) -> IAction:
        self.__assert_target()
        self.__action.find_multiple_capture_match(patterns, capture_area, threshold, max_matches)
        return self

    def get_capture(self, capture_area: CaptureArea) -> IAction:
        self.__assert_target()
        self.__action.get_capture(capture_area)
        return self

    def save_capture(self, capture: Capture, tag: str) -> IAction:
        self.__assert_target()
        self.__action.save_capture(capture, tag)
        return self

    def click_capture_match(self, patterns: MatchPattern, capture_area: Optional[CaptureArea] = None, threshold: Optional[float] = None,
                            max_clicks: Optional[int] = None, click_delay: Optional[float] = None, click_offset: Optional[Offset] = None) -> IAction:
        self.__assert_target()
        self.__action.click_capture_match(patterns, capture_area, threshold, max_clicks, click_delay, click_offset)
        return self

    def capture_cursor(self) -> IAction:
        return self.__action.capture_cursor()

    def get_cursor_fingerprint(self) -> IAction:
        return self.__action.get_cursor_fingerprint()

    def custom_action(self, action_id: ActionID, **kwargs) -> IAction:
        self.__assert_target()
        self.__action.custom_action(action_id, **kwargs)
        return self


class Action(IAction, CommandBuilder):
    _dummy_sync = CommandBuilder._synchronization_command(block=False, sync=True)
    _dummy_returning = CommandBuilder._synchronization_command(block=True, sync=True)

    def __init__(self, client_proxy: IClientBrokerProxy):
        assert isinstance(client_proxy, IClientBrokerProxy)
        self.__commands: List[Dict[str, Any]] = list()
        self.__cached_commands: Optional[List[Dict[str, Any]]] = None
        self.__cached_cancellable: Optional[bool] = None
        self.__client_proxy = client_proxy
        self.__last_start: Dict[str, float] = dict()
        self.__avg_delay: Dict[str, float] = dict()
        self.__default_post_sync = True
        self.__appended_actions: List[IAction] = list()

    def __str__(self) -> str:
        s = ','.join([str(cmd) for cmd in self.__commands])
        s += ' + ' + ' + '.join([str(ac) for ac in self.__appended_actions])
        return 'Action[' + s + ']'

    def _add_command(self, command: Dict[str, Any]) -> IAction:
        assert ACTION_ID_KEY in command.keys()
        assert isinstance(command[ACTION_ID_KEY], str)
        self.__commands.append(command)
        self.__cached_commands = None
        self.__cached_cancellable = None
        return self

    def iter_commands(self) -> Iterable[Dict[str: Any]]:
        for command in self.__commands:
            yield command

    def __get_all_commands_copy(self) -> List[Dict[str, Any]]:
        if self.__cached_commands is None:
            self.__cached_commands = list(self.__commands)
            for action in self.__appended_actions:
                nested_action = action
                if isinstance(nested_action, ActionDelegate):
                    nested_action = nested_action.unwrap()
                assert isinstance(nested_action, Action), f'nested_action is {nested_action}, last delegate # is {action}, in {self}'
                self.__cached_commands.extend(nested_action.__get_all_commands_copy())
        return list(self.__cached_commands)

    def is_cancellable(self) -> bool:
        if self.__cached_cancellable is None:
            commands = self.__get_all_commands_copy()
            self.__cached_cancellable = False
            for command in commands:
                action_id = ActionID(command[ACTION_ID_KEY])
                if action_id in ActionInterpreter.action_cancel_mapping.keys():
                    self.__cached_cancellable = True
                    break
        return self.__cached_cancellable

    def __latency_measure_cb(self, client_id: str):
        if not ACTION_MEASURE_DELAY:
            return
        delay = time.time() - self.__last_start[client_id]
        self.__avg_delay[client_id] = 0.2 * delay + 0.8 * self.__avg_delay[client_id]

    def set_default_post_sync(self, sync: bool):
        self.__default_post_sync = sync
        return self

    def get_average_delay(self, client_id: str) -> float:
        if client_id not in self.__avg_delay.keys():
            return 0.0
        return self.__avg_delay[client_id]

    def __set_send_time(self, client_id: str):
        self.__last_start[client_id] = time.time()
        if client_id not in self.__avg_delay.keys():
            self.__avg_delay[client_id] = ACTION_OVERHEAD_DEFAULT

    def __send_to_client(self, client_id: str, commands: List[Dict[str, Any]],
                         completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> Tuple[bool, Optional[List]]:
        if self.__client_proxy is None:
            logger.error(f'cannot sent action {self} from {client_id}, server not set')
            return False, None
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'sending action {commands} to {client_id}')
        else:
            logger.info(f'sending action to {client_id}')
        connected, results = self.__client_proxy.send_to_client(client_id, commands, completion_cb=completion_cb)
        logger.debug(f'action results from {client_id}: {results}')
        return connected, results

    def post_auto(self, client_id: str) -> bool:
        if self.__default_post_sync:
            return self.post_sync(client_id)
        else:
            return self.post_async(client_id)

    def post_async(self, client_id: str, completion_cb: Optional[Callable[[None], None]] = None) -> bool:
        commands = self.__get_all_commands_copy()
        connected, _ = self.__send_to_client(client_id=client_id, commands=commands, completion_cb=completion_cb)
        return connected

    def post_sync(self, client_id: str, completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> bool:
        def _completion_cb(results: Optional[List]):
            self.__latency_measure_cb(client_id)
            if completion_cb:
                completion_cb(results)

        commands = self.__get_all_commands_copy()
        commands.append(Action._dummy_sync)
        self.__set_send_time(client_id)
        connected, _ = self.__send_to_client(client_id=client_id, commands=commands, completion_cb=_completion_cb)
        return connected

    def call_action(self, client_id: str) -> Tuple[bool, Optional[List]]:
        commands = self.__get_all_commands_copy()
        commands.append(Action._dummy_returning)
        self.__set_send_time(client_id)
        connected, results = self.__send_to_client(client_id=client_id, commands=commands, completion_cb=lambda results_: self.__latency_measure_cb(client_id))
        if not connected:
            return False, None
        if not results:
            return True, None
        # strip the dummy command
        return connected, results[:-1]

    def post_async_cancel(self, client_id: str) -> bool:
        cancel_commands: List[Dict[str, Any]] = list()
        commands = self.__get_all_commands_copy()
        for command in commands:
            action_id = ActionID(command[ACTION_ID_KEY])
            if action_id in ActionInterpreter.action_cancel_mapping.keys():
                cancel_command = command.copy()
                cancel_command['cancel'] = True
                cancel_commands.append(cancel_command)
        connected, _ = self.__send_to_client(client_id=client_id, commands=cancel_commands)
        return connected

    def append(self, action: IAction):
        assert action is not None
        self.__appended_actions.append(action)
        self.__cached_commands = None
        self.__cached_cancellable = None
        return self

    # noinspection PyTypeChecker
    def prototype(self, **kwargs) -> IAction:
        # not supported in this class
        assert False, self


class ActionFactory(object):
    def __init__(self):
        self.__broker_proxy = ClientBrokerProxyFactory.create_proxy()

    def new_action(self) -> IAction:
        return Action(self.__broker_proxy)

    def initialize_broker(self, broker: IClientBrokerProxy):
        assert isinstance(broker, IClientBrokerProxy)
        self.__broker_proxy.set_target(broker)


action_factory = ActionFactory()
