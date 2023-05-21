import sys
from typing import Any, Dict, List, Optional

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events import Event
from rka.components.events.event_system import IEventBusPoster, EventSystem
from rka.components.io.injector import IInjector
from rka.eq2.parsing import ILogInjector, ILogParser
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.control import logger
from rka.eq2.shared.control.action_id import ActionID
from rka.eq2.shared.control.interpreter import ActionInterpreter
from rka.eq2.shared.control.slave_bridge import SlaveBridge
from rka.eq2.shared.host import HostConfig
from rka.eq2.shared.shared_workers import shared_scheduler


class SlaveInterpreter(ActionInterpreter):
    def __init__(self, host_config: HostConfig, bridge: SlaveBridge, injectors: List[IInjector], event_system: EventSystem):
        ActionInterpreter.__init__(self, host_config, injectors)
        self.__bridge = bridge
        self.__log_parser: Optional[ILogParser] = None
        self.__log_injector: Optional[ILogInjector] = None
        self.__event_system = event_system
        self.__click_future: Optional[RKAFuture] = None

    def set_active_log(self, log_parser: Optional[ILogParser], log_injector: Optional[ILogInjector]):
        self.__log_parser = log_parser
        self.__log_injector = log_injector

    def _get_bus(self) -> Optional[IEventBusPoster]:
        if not self.__log_parser:
            logger.warn(f'No active client for the bus')
            return None
        return self.__event_system.get_bus(self.__log_parser.get_parser_id())

    def _interpret_action(self, action_id: ActionID, command: Dict[str, Any]) -> Any:
        try:
            return super()._interpret_action(action_id, command)
        except ValueError:
            logger.info(f'action code not handled by base interpreter: {command}')
            pass
        if action_id == ActionID.PARSER_SUBSCRIBE:
            if self.__log_parser is None:
                logger.warn(f'No parser configured for subscribe')
                return False
            parse_filter = command['parse_filter']
            preparsed_logs = command['preparsed_logs']
            self.__log_parser.unsubscribe_all(parse_filter, preparsed_logs)
            subscribe_result = self.__log_parser.subscribe(parse_filter, preparsed_logs)
            return subscribe_result
        elif action_id == ActionID.PARSER_UNSUBSCRIBE:
            if self.__log_parser is None:
                logger.warn(f'No parser configured for unsubscribe')
                return False
            parse_filter = command['parse_filter']
            preparsed_logs = command['preparsed_logs']
            unsubscribe_result = self.__log_parser.unsubscribe_all(parse_filter, preparsed_logs)
            return unsubscribe_result
        elif action_id == ActionID.EVENT_SUBSCRIBE:
            event_bus = self._get_bus()
            if event_bus is None:
                logger.warn(f'No event bus configured for subscribe')
                return False
            event_name = command['event_name']
            event_type = Event.get_event_type_from_name(event_name)
            event_bus.unsubscribe_all(event_type, self.__send_bus_event)
            event_bus.subscribe(event_type(), self.__send_bus_event)
            return True
        elif action_id == ActionID.EVENT_UNSUBSCRIBE:
            event_bus = self._get_bus()
            if event_bus is None:
                logger.warn(f'No event bus available to unsubscribe for {self.__log_parser.get_parser_id()}')
                return False
            event_name = command['event_name']
            event_type = Event.get_event_type_from_name(event_name)
            unsubscribe_result = event_bus.unsubscribe_all(event_type, self.__send_bus_event)
            return unsubscribe_result
        elif action_id == ActionID.TESTLOG_INJECT:
            if self.__log_injector is None:
                logger.warn(f'No log injector configured')
                return False
            testloglines = command['testloglines']
            self.__log_injector.write_log(testloglines)
            return True
        elif action_id == ActionID.GET_HOSTNAME:
            host_send_result = self.__bridge.send_hostname()
            return host_send_result
        logger.error(f'slave: cannot interpret unknown action: {command}')
        return None

    def __send_bus_event(self, event: ClientEvent):
        result = self.__bridge.send_bus_event(event)
        event_bus = self._get_bus()
        if not result and event_bus:
            event_bus.unsubscribe_all(type(event), self.__send_bus_event)

    def print_mouse_pos(self):
        pos = self._get_automation().get_mouse_pos()
        print(f'mouse position is {pos}', file=sys.stderr)
        cursor = self._get_cursor_capture().get_cursor_fingerprint()
        print(f'mouse cursor is {cursor}', file=sys.stderr)

    def __click(self):
        self._get_automation().mouse_click('left')
        if self.__click_future:
            self.__click_future = shared_scheduler.schedule(self.__click, 0.6)

    def toggle_keep_clicking(self):
        if self.__click_future:
            self.__click_future.cancel_future()
            self.__click_future = None
            return
        self.__click_future = shared_scheduler.schedule(self.__click, 0.6)
