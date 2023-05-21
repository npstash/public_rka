from __future__ import annotations

import datetime
import threading
from typing import Callable, Optional, Iterable, Any, Union, List

from rka.components.events import Event, EventType
from rka.components.events.event_system import IEventBus
from rka.components.io.log_service import LogService
from rka.eq2.master import IRuntime, TakesRuntime
from rka.eq2.master.control import IHasClient
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.client_events import ClientEvents
from rka.log_configs import LOG_TRIGGERS

logger = LogService(LOG_TRIGGERS)


class IEventSubscriber:
    def get_event(self) -> Event:
        raise NotImplementedError()

    def subscribe(self) -> bool:
        raise NotImplementedError()

    def unsubscribe(self):
        raise NotImplementedError()


class ITriggerEventTest:
    def get_test_event(self) -> Optional[Event]:
        raise NotImplementedError()

    def set_test_event(self, event: Event):
        raise NotImplementedError()

    def is_test_event_updated(self) -> bool:
        raise NotImplementedError()

    def clear_test_event_update_flag(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class ITriggerEvent(ITriggerEventTest):
    def get_event(self) -> Event:
        raise NotImplementedError()

    def has_filter_cb(self) -> bool:
        raise NotImplementedError()


# noinspection PyAbstractClass
class ITrigger(ITriggerEventTest):
    def __init__(self):
        self.repeat_period = 0.0
        self.repeat_key: Optional[str] = None

    def describe(self) -> str:
        return self.__str__()

    def add_action(self, action: Callable[[EventType], None], once=False, delay=0.0):
        raise NotImplementedError()

    def add_bus_event(self, event: Event, event_bus: Optional[IEventBus] = None, filter_cb: Optional[Callable[[Event], bool]] = None):
        raise NotImplementedError()

    def add_subscribed_bus_event(self, subscriber: IEventSubscriber, event_bus: Optional[IEventBus] = None, filter_cb: Optional[Callable[[Event], bool]] = None):
        raise NotImplementedError()

    def iter_trigger_events(self) -> Iterable[ITriggerEvent]:
        raise NotImplementedError()

    def iter_trigger_actions(self) -> Iterable[Callable[[EventType], None]]:
        raise NotImplementedError()

    def start_trigger(self):
        raise NotImplementedError()

    def is_subscribed(self) -> bool:
        raise NotImplementedError()

    def cancel_trigger(self):
        raise NotImplementedError()

    def wait_for_trigger(self, timeout: float) -> Event:
        lock = threading.Condition()
        completed = False
        result_event: Optional[Event] = None

        def notification_callback(event: Event) -> bool:
            with lock:
                nonlocal completed
                nonlocal result_event
                result_event = event
                completed = True
                lock.notify()
            return False

        with lock:
            self.add_action(notification_callback, once=True)
            self.start_trigger()
            while not completed:
                wait_started = datetime.datetime.now()
                lock.wait(timeout)
                if completed:
                    break
                waited_time = datetime.datetime.now() - wait_started
                timeout -= waited_time.seconds
                if timeout <= 0:
                    break
        self.cancel_trigger()
        return result_event

    def test_trigger(self) -> bool:
        raise NotImplementedError()

    def save_original_spec(self, spec):
        raise NotImplementedError()

    def get_original_spec(self) -> Any:
        raise NotImplementedError()


# noinspection PyAbstractClass
class IPlayerTrigger(ITrigger, TakesRuntime, IHasClient):
    def __init__(self, runtime: IRuntime, client_id: str):
        ITrigger.__init__(self)
        TakesRuntime.__init__(self, runtime)
        self.__client_id = client_id

    def get_client_id(self) -> str:
        return self.__client_id

    def add_client_bus_event(self, event: ClientEvent, filter_cb: Optional[Callable[[ClientEvent], bool]] = None):
        raise NotImplementedError()

    def add_subscribed_client_bus_event(self, subscriber: IEventSubscriber, filter_cb: Optional[Callable[[Event], bool]] = None):
        raise NotImplementedError()

    def add_parser_events(self, parse_filters: Union[str, List[str]], parse_preparsed_logs=False,
                          filter_cb: Optional[Callable[[ClientEvents.PARSER_MATCH], bool]] = None):
        raise NotImplementedError()


class ITriggerAction:
    def __init__(self, runtime: IRuntime):
        self.__runtime: IRuntime = runtime

    def get_runtime(self) -> IRuntime:
        return self.__runtime

    def action(self, event: Event):
        raise NotImplementedError()

    def __call__(self, event: Event):
        return self.action(event)


class ITriggerWarningCodeFunctions:
    def tts(self, *args, **kwargs):
        raise NotImplementedError()

    def msg(self, *args, **kwargs):
        raise NotImplementedError()

    def warning(self, *args, **kwargs):
        raise NotImplementedError()

    def ps_tts(self, *args, **kwargs):
        raise NotImplementedError()

    def ps_msg(self, *args, **kwargs):
        raise NotImplementedError()

    def player_raid_say(self, *args, **kwargs):
        raise NotImplementedError()

    def player_group_say(self, *args, **kwargs):
        raise NotImplementedError()

    def player_command(self, *args, **kwargs):
        raise NotImplementedError()
