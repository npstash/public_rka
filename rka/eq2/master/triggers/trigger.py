from __future__ import annotations

import time
import traceback
from itertools import chain
from threading import RLock
from typing import List, Callable, Iterable, Optional, Any, Dict, Union

from rka.components.events import Event, EventType
from rka.components.events.event_system import IEventBus, EventSystem
from rka.eq2.master import IRuntime
from rka.eq2.master.triggers import ITrigger, logger, IPlayerTrigger, IEventSubscriber, ITriggerEvent
from rka.eq2.master.triggers.trigger_subscribers import EventSubscriberToolkit
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.shared_workers import shared_scheduler


class SubscribedEvent:
    def __init__(self, event_bus: IEventBus, event: Event, custom_subscriber: Optional[IEventSubscriber], on_event: Callable[[Event], None]):
        self.__event_bus = event_bus
        self.__event = event
        self.__custom_subscriber = custom_subscriber
        self.__on_event = on_event

    def __str__(self) -> str:
        return f'{self.__class__.__name__} [{self.__event}]'

    def unsubscribe(self):
        if self.__custom_subscriber:
            self.__custom_subscriber.unsubscribe()
        self.__event_bus.unsubscribe(self.__event, self.__on_event)


class RegisteredEvent(ITriggerEvent):
    def __init__(self, event_bus: IEventBus, event: Event, filter_cb: Optional[Callable[[Event], bool]],
                 custom_subscriber: Optional[IEventSubscriber] = None):
        self.__event_bus = event_bus
        self.__event = event
        self.__filter_cb = filter_cb
        self.__custom_subscriber = custom_subscriber
        self.__test_event: Optional[Event] = None
        self.__test_event_updated = False

    def __str__(self) -> str:
        return f'{self.__class__.__name__} [{self.__event}]'

    def get_event(self) -> Event:
        return self.__event

    def has_filter_cb(self) -> bool:
        return self.__filter_cb is not None

    def subscribe(self, callback: Callable[[EventType], None]) -> Optional[SubscribedEvent]:
        def on_event(event: Event):
            if self.__filter_cb is not None and not self.__filter_cb(event):
                return
            self.set_test_event(event)
            callback(event)

        self.__event_bus.subscribe(self.__event, on_event)
        if self.__custom_subscriber:
            if not self.__custom_subscriber.subscribe():
                logger.warn(f'Failed custom subscribe for {self.__event}')
                self.__event_bus.unsubscribe(self.__event, on_event)
                return None

        subscriber = SubscribedEvent(event_bus=self.__event_bus, event=self.__event, custom_subscriber=self.__custom_subscriber, on_event=on_event)
        return subscriber

    def get_test_event(self) -> Optional[Event]:
        return self.__test_event

    def set_test_event(self, event: Event):
        if self.__test_event is None:
            self.__test_event_updated = True
        self.__test_event = event

    def is_test_event_updated(self) -> bool:
        return self.__test_event_updated

    def clear_test_event_update_flag(self):
        self.__test_event_updated = False


class Trigger(ITrigger):
    DEFAULT_REPEAT_KEY_VALUE = 'default'

    class _Action:
        def __init__(self, trigger: Trigger, cb: Callable[[EventType], None], delay: float):
            self.__trigger = trigger
            self.__cb = cb
            self.__delay = delay

        def __call_action(self, event: Event):
            try:
                self.__cb(event)
            except Exception as e:
                logger.error(f'Callback {self.__cb} raised error {e} with event {event} in trigger {self.__trigger.describe()}')
                traceback.print_exc()
                return

        def get_cb(self) -> Callable[[EventType], None]:
            return self.__cb

        def invoke_action(self, event: Event):
            if self.__delay and self.__delay > 0.0:
                shared_scheduler.schedule(lambda: self.__call_action(event), delay=self.__delay)
            else:
                self.__call_action(event)

        def test_action(self, event: Event):
            self.__call_action(event)

    def __init__(self, name: Optional[str] = None):
        ITrigger.__init__(self)
        self.__registered_events: List[RegisteredEvent] = list()
        self.__subscribed_events: List[SubscribedEvent] = list()
        self.__actions: List[Trigger._Action] = list()
        self.__actions_once: List[Trigger._Action] = list()
        self.__saved_original_spec: Optional[Any] = None
        self.__lock = RLock()
        self.__name = name
        self.__description = None
        self.__last_trigger_times: Dict[str, float] = dict()

    def __str__(self) -> str:
        if self.__name:
            return self.__name
        return self.describe()

    def describe(self) -> str:
        if self.__description:
            return self.__description
        self.__description = ', '.join((str(event.get_event()) for event in self.__registered_events))
        return f'Trigger[{self.__description}]'

    def __test_actions(self, event: Event):
        with self.__lock:
            all_actions: Iterable[Trigger._Action] = chain(self.__actions.copy(), self.__actions_once.copy())
        for action in all_actions:
            action.test_action(event)

    def __get_repeat_key_value(self, event: Event):
        if not self.repeat_key:
            return Trigger.DEFAULT_REPEAT_KEY_VALUE
        if self.repeat_key not in event.param_names:
            logger.warn(f'Repeat Key {self.repeat_key} not found in {event}')
            return Trigger.DEFAULT_REPEAT_KEY_VALUE
        return event.get_param(self.repeat_key)

    def __unsubscribe_all(self):
        with self.__lock:
            for subscribed_event in self.__subscribed_events:
                subscribed_event.unsubscribe()
            self.__subscribed_events.clear()

    def __fire_actions(self, event: Event):
        if self.repeat_period:
            now = time.time()
            repeat_key_value = self.__get_repeat_key_value(event)
            if now - self.__last_trigger_times.setdefault(repeat_key_value, 0.0) < self.repeat_period:
                return
            self.__last_trigger_times[repeat_key_value] = now
        with self.__lock:
            actions_once = self.__actions_once
            self.__actions_once = list()
            all_actions: Iterable[Trigger._Action] = chain(self.__actions.copy(), actions_once)
            # if all and only one-time actions are fired, stop the trigger
            unsubscribe_after = not self.__actions
        for action in all_actions:
            action.invoke_action(event)
        if unsubscribe_after:
            self.__unsubscribe_all()

    def add_action(self, action: Callable[[EventType], None], once=False, delay=0.0):
        action_wrapper = Trigger._Action(self, cb=action, delay=delay)
        with self.__lock:
            if once:
                self.__actions_once.append(action_wrapper)
            else:
                self.__actions.append(action_wrapper)

    def _add_trigger_event(self, new_event: RegisteredEvent):
        with self.__lock:
            self.__registered_events.append(new_event)
            self.__description = None

    def add_bus_event(self, event: Event, event_bus: Optional[IEventBus] = None, filter_cb: Optional[Callable[[Event], bool]] = None):
        if not event_bus:
            event_bus = EventSystem.get_main_bus()
        new_event = RegisteredEvent(event_bus=event_bus, event=event, filter_cb=filter_cb)
        self._add_trigger_event(new_event)

    def add_subscribed_bus_event(self, subscriber: IEventSubscriber, event_bus: Optional[IEventBus] = None, filter_cb: Optional[Callable[[Event], bool]] = None):
        if not event_bus:
            event_bus = EventSystem.get_main_bus()
        new_event = RegisteredEvent(event_bus=event_bus, event=subscriber.get_event(), filter_cb=filter_cb, custom_subscriber=subscriber)
        self._add_trigger_event(new_event)

    def iter_trigger_events(self) -> Iterable[ITriggerEvent]:
        with self.__lock:
            for registered_event in self.__registered_events:
                yield registered_event

    def iter_trigger_actions(self) -> Iterable[Callable[[EventType], None]]:
        with self.__lock:
            for trigger_action in self.__actions:
                yield trigger_action.get_cb()

    def start_trigger(self):
        logger.info(f'start_trigger: {self}')
        with self.__lock:
            if self.__subscribed_events:
                logger.warn(f'start_trigger: not cancelled properly: {self}')
                self.__unsubscribe_all()
            for registered_event in self.__registered_events:
                subscribed_event = registered_event.subscribe(self.__fire_actions)
                if not subscribed_event:
                    logger.warn(f'start_trigger: failed to subscribe event: {registered_event}')
                    continue
                self.__subscribed_events.append(subscribed_event)

    def is_subscribed(self) -> bool:
        with self.__lock:
            return bool(self.__subscribed_events)

    def cancel_trigger(self):
        logger.info(f'cancel_trigger: {self}')
        with self.__lock:
            if not self.__subscribed_events:
                logger.warn(f'cancel: {self} has no subscribers')
                return
            self.__unsubscribe_all()

    def test_trigger(self) -> bool:
        test_event = self.get_test_event()
        if not test_event:
            return False
        self.__test_actions(test_event)
        return True

    def save_original_spec(self, spec):
        self.__saved_original_spec = spec

    def get_original_spec(self) -> Any:
        return self.__saved_original_spec

    def set_test_event(self, event: Event):
        with self.__lock:
            for registered_event in self.__registered_events:
                event_template = registered_event.get_event()
                if type(event) == type(event_template):
                    registered_event.set_test_event(event)
                    return True
        return False

    def get_test_event(self) -> Optional[Event]:
        with self.__lock:
            for registered_event in self.__registered_events:
                test_event = registered_event.get_test_event()
                if test_event:
                    return test_event
        return None

    def is_test_event_updated(self) -> bool:
        with self.__lock:
            for registered_event in self.__registered_events:
                if registered_event.is_test_event_updated():
                    return True
        return False

    def clear_test_event_update_flag(self):
        with self.__lock:
            for registered_event in self.__registered_events:
                registered_event.clear_test_event_update_flag()


class PlayerTrigger(Trigger, IPlayerTrigger):
    def __init__(self, runtime: IRuntime, client_id: str, name: Optional[str] = None):
        Trigger.__init__(self, name)
        IPlayerTrigger.__init__(self, runtime, client_id)

    def add_client_bus_event(self, event: ClientEvent, filter_cb: Optional[Callable[[ClientEvent], bool]] = None):
        event_bus = self.get_runtime().remote_client_event_system.get_bus(self.get_client_id())
        if not event_bus:
            logger.error(f'add_client_bus_event: no event bus for: {self.get_client_id()}, trigger: {self.describe()}')
            return
        self.add_bus_event(event, event_bus=event_bus, filter_cb=filter_cb)

    def add_subscribed_client_bus_event(self, subscriber: IEventSubscriber, filter_cb: Optional[Callable[[Event], bool]] = None):
        client_event = subscriber.get_event()
        assert isinstance(client_event, ClientEvent), client_event
        event_bus = self.get_runtime().remote_client_event_system.get_bus(self.get_client_id())
        if not event_bus:
            logger.error(f'add_subscribed_client_bus_event: no event bus for: {self.get_client_id()}, trigger: {self.describe()}')
            return
        self.add_subscribed_bus_event(subscriber=subscriber, event_bus=event_bus, filter_cb=filter_cb)

    # convenience function, generating subscriber is done in Toolkit
    def add_parser_events(self, parse_filters: Union[str, List[str]], parse_preparsed_logs=False,
                          filter_cb: Optional[Callable[[ClientEvents.PARSER_MATCH], bool]] = None):
        EventSubscriberToolkit.add_parser_events_to_trigger(trigger=self,
                                                            parse_filters=parse_filters,
                                                            parse_preparsed_logs=parse_preparsed_logs,
                                                            filter_cb=filter_cb)
