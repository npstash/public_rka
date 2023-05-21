from threading import RLock
from typing import List

from rka.components.events.event_system import IEventPoster
from rka.services.api.ps_connector import IPSConnectorObserver, PSTriggerEventData
from rka.services.api.ps_connector_events import PSEvents


class PSConnectorObserverContainer(IPSConnectorObserver):
    def __init__(self):
        self.__observers_lock = RLock()
        self.__observers: List[IPSConnectorObserver] = list()

    def trigger_event_received(self, trigger_event: PSTriggerEventData):
        with self.__observers_lock:
            observers = list(self.__observers)
        for observer in observers:
            observer.trigger_event_received(trigger_event)

    def message_received(self, message: str):
        with self.__observers_lock:
            observers = list(self.__observers)
        for observer in observers:
            observer.message_received(message)

    def command_received(self, command: str, params: List[str]):
        with self.__observers_lock:
            observers = list(self.__observers)
        for observer in observers:
            observer.command_received(command, params)

    def client_list_received(self, clients: List[str]):
        with self.__observers_lock:
            observers = list(self.__observers)
        for observer in observers:
            observer.client_list_received(clients)

    def connector_closed(self):
        with self.__observers_lock:
            observers = list(self.__observers)
        for observer in observers:
            observer.connector_closed()

    def add_observer(self, observer: IPSConnectorObserver):
        assert isinstance(observer, IPSConnectorObserver)
        with self.__observers_lock:
            self.__observers.append(observer)

    def remove_observer(self, observer: IPSConnectorObserver):
        with self.__observers_lock:
            if observer in self.__observers:
                self.__observers.remove(observer)

    def clear(self):
        with self.__observers_lock:
            self.__observers.clear()


class PSConnectorObserverEventDispatcher(IPSConnectorObserver):
    def __init__(self, bus: IEventPoster):
        self.__bus = bus

    def trigger_event_received(self, trigger_event: PSTriggerEventData):
        self.__bus.post(PSEvents.TRIGGER_RECEIVED(trigger_event_data=trigger_event))

    def message_received(self, message: str):
        self.__bus.post(PSEvents.MESSAGE_RECEIVED(message=message))

    def command_received(self, command: str, params: List[str]):
        self.__bus.post(PSEvents.COMMAND_RECEIVED(command=command, params=params))

    def client_list_received(self, clients: List[str]):
        self.__bus.post(PSEvents.CLIENTS_RECEIVED(clients=clients))

    def connector_closed(self):
        self.__bus.post(PSEvents.DISCONNECTED())


class TestObserver(IPSConnectorObserver):
    def trigger_event_received(self, trigger_event: PSTriggerEventData):
        print(trigger_event)

    def message_received(self, message: str):
        print(message)

    def command_received(self, command: str, params: List[str]):
        print(command)

    def client_list_received(self, clients: List[str]):
        print(clients)

    def connector_closed(self):
        print('CLOSED')
