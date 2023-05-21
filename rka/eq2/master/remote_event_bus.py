from __future__ import annotations

from typing import Callable, Type

from rka.components.events import EventType
from rka.components.events.event_bus import EventBus, SpecificEventBus
from rka.components.events.event_system import BusThread, IEventBusPoster, IEventBusPosterFactory
from rka.components.io.log_service import LogService
from rka.eq2.master import IRuntime
from rka.log_configs import LOG_EVENTS

logger = LogService(LOG_EVENTS)


class RemoteSpecificEventBusProxy(SpecificEventBus[EventType]):
    def __init__(self, runtime: IRuntime, worker: BusThread, client_id: str, event_type: Type[EventType]):
        SpecificEventBus.__init__(self, client_id, worker, event_type)
        self.__runtime = runtime
        self.__client_id = client_id
        self.__event_type = event_type

    def describe(self) -> str:
        return f'RemoteSpecificEventBusProxy [{self.__client_id}-{self.__event_type.value}]'

    def __remote_subscribe(self) -> bool:
        connected, result = self.__runtime.master_bridge.send_event_subscribe(client_id=self.__client_id, event_name=self.__event_type.name)
        return connected and result

    def __remote_unsubscribe(self):
        self.__runtime.master_bridge.send_event_unsubscribe(client_id=self.__client_id, event_name=self.__event_type.name)

    # from IEventBus
    def subscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]):
        if self.is_empty() and not self.__remote_subscribe():
            logger.info(f'could not subscribe {subscriber} to {self.__client_id}')
            return
        super().subscribe(subscribe_template, subscriber)

    # from IEventBus
    def unsubscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]) -> bool:
        found = super().unsubscribe(subscribe_template, subscriber)
        if found and self.is_empty():
            self.__remote_unsubscribe()
        return found

    # from IEventBus
    def unsubscribe_all(self, event_type: Type[EventType], subscriber: Callable[[EventType], None]) -> bool:
        found = super().unsubscribe_all(event_type, subscriber)
        if found and self.is_empty():
            self.__remote_unsubscribe()
        return found

    # from IEventBus
    def close_bus(self):
        super().close_bus()
        self.__remote_unsubscribe()


class RemoteEventBus(EventBus):
    def __init__(self, runtime: IRuntime, client_id: str):
        EventBus.__init__(self, bus_id=client_id)
        self.__runtime = runtime
        self.__client_id = client_id
        logger.info(f'created remote event bus system for {client_id}')

    def _create_specific_event_bus(self, event_type: Type[EventType]) -> IEventBusPoster[EventType]:
        return RemoteSpecificEventBusProxy(self.__runtime, self._get_worker(), self.__client_id, event_type)


class RemoteEventBusFactory(IEventBusPosterFactory):
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime

    def create_event_bus(self, bus_id: str) -> IEventBusPoster:
        return RemoteEventBus(self.__runtime, bus_id)
