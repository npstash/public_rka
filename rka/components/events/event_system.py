from __future__ import annotations

import threading
import time
from typing import Callable, Generic, List, Type, Optional, Dict, Hashable, Union, Tuple

from rka.components.cleanup import Closeable
from rka.components.concurrency.workthread import RKAWorkerThread
from rka.components.events import logger, default_worker_queue_limit, EventType


class BusThread(RKAWorkerThread):
    def __init__(self, name: str, bus_thread_num: int):
        RKAWorkerThread.__init__(self, f'{name}-{bus_thread_num}', default_worker_queue_limit)
        self.bus_thread_num = bus_thread_num

    def push_with_description(self, event_name: str, callback: Callable[[], None]) -> bool:
        future = RKAWorkerThread.push_task(self, callback)
        if not future:
            # queue limit reached - delivery thread is locked up
            return False
        future.set_description(event_name)
        return True

    @staticmethod
    def is_running_on_bus_thread() -> bool:
        thread = threading.current_thread()
        return isinstance(thread, BusThread)


class ISubscriberContainer(Generic[EventType]):
    def get_last_update(self) -> float:
        raise NotImplementedError()

    def is_empty(self) -> bool:
        raise NotImplementedError()

    def filter_subscribers(self, event: EventType) -> List[EventSubscription[EventType]]:
        raise NotImplementedError()

    def filter_into_subcontainer(self, event_template: EventType, subcontainer: ISubscriberDB):
        raise NotImplementedError()


# noinspection PyAbstractClass
class ISubscriberDB(Generic[EventType], ISubscriberContainer[EventType]):
    def add_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType):
        raise NotImplementedError()

    def remove_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType) -> bool:
        raise NotImplementedError()

    def remove_subscriber_all(self, subscriber: Callable[[EventType], None]) -> int:
        raise NotImplementedError()

    def clear_subscribers(self):
        raise NotImplementedError()


class IEventPoster(Generic[EventType]):
    def post(self, event: EventType):
        raise NotImplementedError()

    def call(self, event: EventType):
        raise NotImplementedError()

    def mute_logs(self):
        raise NotImplementedError()


class IEventPosterFactory:
    def get_poster(self, posting_template: EventType) -> IEventPoster[EventType]:
        raise NotImplementedError()


class IEventBus(Generic[EventType]):
    def subscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]):
        raise NotImplementedError()

    def unsubscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]) -> bool:
        raise NotImplementedError()

    def unsubscribe_all(self, event_type: Type[EventType], subscriber: Callable[[EventType], None]) -> bool:
        raise NotImplementedError()

    def close_bus(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class IEventBusPoster(Generic[EventType], IEventPoster[EventType], IEventBus[EventType]):
    pass


class IEventBusPosterFactory:
    def create_event_bus(self, bus_id: str) -> IEventBusPoster:
        raise NotImplementedError()


class EventSubscription(Generic[EventType]):
    def __init__(self, subscriber: Callable[[EventType], None], subscribe_template: EventType):
        self.__subscriber = subscriber
        self.__subscribe_template = subscribe_template
        self.__description = f'Sub: {self.__subscribe_template} -> {self.__subscriber}'

    def __str__(self) -> str:
        return self.__description

    def get_subscriber(self) -> Callable[[EventType], None]:
        return self.__subscriber

    def get_subscribe_template(self) -> EventType:
        return self.__subscribe_template

    def pass_event(self, event: EventType, description: Optional[str] = None):
        if not description:
            description = f'{event} for {self.__subscriber}'
        logger.info(f'Passing event {description}')
        self.__subscriber(event)

    def post_event(self, worker: BusThread, event: EventType) -> bool:
        description = f'{event} for {self.__subscriber}'
        return worker.push_with_description(description, lambda: self.pass_event(event, description))

    def match_subscriber(self, subscriber: Callable[[EventType], None]) -> bool:
        # do not change this to 'is'. bound methods cant be compared with 'is'
        return subscriber == self.__subscriber

    def match_subscription(self, subscription: EventSubscription) -> bool:
        return self.__description == subscription.__description

    def match_event_field(self, event: EventType, field_name: str) -> bool:
        if not self.__subscribe_template.is_param_set(field_name):
            return True
        if not event.is_param_set(field_name):
            return False
        return self.__subscribe_template.get_param(field_name) == event.get_param(field_name)

    def match_event(self, event: EventType, strict_comparison: bool) -> bool:
        if event.event_id != self.__subscribe_template.event_id:
            return False
        for sub_param_name in self.__subscribe_template.get_params_set():
            if not event.is_param_set(sub_param_name):
                if strict_comparison:
                    # template mandates this param but it is not set in the event
                    return False
                continue
            # value present in template and event
            sub_param_value = self.__subscribe_template.get_param(sub_param_name)
            event_param_value = event.get_param(sub_param_name)
            if sub_param_value is event_param_value:
                continue
            if sub_param_value != event_param_value:
                return False
        return True


class UpdateFlag:
    def __init__(self):
        self.__last_subscriber_list_update = time.time()

    def get_last_update(self) -> float:
        return self.__last_subscriber_list_update

    def set_last_update(self):
        self.__last_subscriber_list_update = time.time()


class EventSystem(Closeable):
    MAIN_EVENT_SYSTEM_ID = 'Main Event System'
    MAIN_EVENT_BUS_ID = 'Main Event Bus'

    __instances: Dict[Hashable, EventSystem] = dict()

    @staticmethod
    def get_system(system_id: Union[int, str], bus_factory: Optional[IEventBusPosterFactory] = None) -> EventSystem:
        if system_id not in EventSystem.__instances.keys():
            assert bus_factory
            EventSystem.__instances[system_id] = EventSystem(system_id, bus_factory=bus_factory)
        return EventSystem.__instances[system_id]

    @staticmethod
    def get_main_system(bus_factory: Optional[IEventBusPosterFactory] = None) -> EventSystem:
        if EventSystem.MAIN_EVENT_SYSTEM_ID not in EventSystem.__instances:
            if bus_factory is None:
                logger.warn('Implicit initialization of default event bus factory')
                from rka.components.events.event_bus import EventBusFactory
                bus_factory = EventBusFactory()
            system = EventSystem(EventSystem.MAIN_EVENT_SYSTEM_ID, bus_factory=bus_factory)
            system.install_bus(EventSystem.MAIN_EVENT_BUS_ID)
            EventSystem.__instances[EventSystem.MAIN_EVENT_SYSTEM_ID] = system
        return EventSystem.__instances[EventSystem.MAIN_EVENT_SYSTEM_ID]

    @staticmethod
    def get_main_bus() -> IEventBusPoster:
        system = EventSystem.get_main_system()
        return system.get_bus(EventSystem.MAIN_EVENT_BUS_ID)

    def __init__(self, system_id: Union[int, str], bus_factory: IEventBusPosterFactory):
        Closeable.__init__(self, explicit_close=False)
        self.__system_id = system_id
        self.__bus_factory = bus_factory
        self.__buses: Dict[Hashable, IEventBusPoster] = dict()

    def install_bus(self, bus_id: Union[int, str]):
        if bus_id in self.__buses:
            logger.error(f'Bus {bus_id} already installed')
            self.__buses[bus_id].close_bus()
        self.__buses[bus_id] = self.__bus_factory.create_event_bus(bus_id)

    def uninstall_bus(self, bus_id: Union[int, str]):
        if bus_id not in self.__buses:
            logger.warn(f'Bus {bus_id} not installed')
            return
        event_bus = self.__buses[bus_id]
        del self.__buses[bus_id]
        event_bus.close_bus()

    def get_bus(self, bus_id: Union[int, str]) -> Optional[IEventBusPoster]:
        if bus_id not in self.__buses.keys():
            logger.info(f'Bus {bus_id} not installed')
            return None
        return self.__buses[bus_id]

    def close(self):
        buses = list(self.__buses.values())
        self.__buses.clear()
        for bus in buses:
            bus.close_bus()
        Closeable.close(self)


class CloseableSubscriber(Closeable):
    def __init__(self, bus: IEventBus):
        Closeable.__init__(self, explicit_close=False)
        self.__bus = bus
        self.__subscribers: List[Tuple[Type[EventType], Callable]] = list()

    def subscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]):
        self.__subscribers.append((type(subscribe_template), subscriber))
        self.__bus.subscribe(subscribe_template, subscriber)

    def close(self):
        for event_type, subscriber in self.__subscribers:
            self.__bus.unsubscribe_all(event_type, subscriber)
        self.__subscribers.clear()
        Closeable.close(self)
