from __future__ import annotations

from typing import Union, Callable, Iterable, Optional, List

from rka.components.events import Event
from rka.components.resources import Resource
from rka.components.ui.capture import CaptureArea
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IHasClient
from rka.eq2.master.screening import IScreenReader
from rka.eq2.master.screening.screen_reader_events import ScreenReaderEvents
from rka.eq2.master.triggers import logger, IEventSubscriber, ITrigger, IPlayerTrigger
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.client_events import ClientEvents
from rka.services.broker import ServiceBroker


class EventSubscriberFactory:
    @staticmethod
    def create_parser_subscriber_from_event(runtime: IRuntime, event: ClientEvents.PARSER_MATCH) -> IEventSubscriber:
        # in case of request for pre-parsed logs, it needs to affect both preparsed and non-preparsed
        if event.preparsed_log or event.preparsed_log is None:
            event.preparsed_log = None
            preparsed_logs = True
        else:
            preparsed_logs = False

        class Subscriber(IEventSubscriber):
            def get_event(self) -> Event:
                return event

            def subscribe(self) -> bool:
                parser = runtime.parser_mgr.get_parser(event.client_id)
                return parser.subscribe(parse_filter=event.parse_filter, preparsed_logs=preparsed_logs)

            def unsubscribe(self):
                parser = runtime.parser_mgr.get_parser(event.client_id)
                parser.unsubscribe(parse_filter=event.parse_filter, preparsed_logs=preparsed_logs)

        return Subscriber()

    @staticmethod
    def create_parser_subscriber(runtime: IRuntime, client_id: str, parse_filter: str, preparsed_logs: bool) -> IEventSubscriber:
        event = ClientEvents.PARSER_MATCH(client_id=client_id, parse_filter=parse_filter, preparsed_log=preparsed_logs)
        return EventSubscriberFactory.create_parser_subscriber_from_event(runtime, event)

    @staticmethod
    def create_screen_reader_subscriber_from_event(event: ScreenReaderEvents.SCREEN_OBJECT_FOUND) -> IEventSubscriber:
        owner = object()
        subscriber_id = repr(id(owner))
        event = ScreenReaderEvents.SCREEN_OBJECT_FOUND(tag=event.tag, subscriber_id=subscriber_id)
        screen_reader: IScreenReader = ServiceBroker.get_broker().get_service(IScreenReader)

        class Subscriber(IEventSubscriber):
            def __init__(self):
                # keep ref, prevent duplicate subscriber_id until this object is GC'ed
                self.__owner = owner

            def get_event(self) -> Event:
                return event

            def subscribe(self) -> bool:
                screen_reader.subscribe(client_ids=[event.client_id], subscriber_id=subscriber_id, tag=event.tag, area=event.area)
                return True

            def unsubscribe(self):
                screen_reader.unsubscribe(subscriber_id=subscriber_id, tag=event.tag, area=event.area)

        return Subscriber()

    @staticmethod
    def create_screen_reader_subscriber(tag: Resource,
                                        area_source: Union[CaptureArea, Callable[[Union[str, IHasClient]], CaptureArea]],
                                        client_ids: Iterable[Union[str, IHasClient]],
                                        check_period: Optional[float] = None,
                                        event_period: Optional[float] = None,
                                        max_matches: Optional[int] = None) -> IEventSubscriber:
        owner = object()
        subscriber_id = repr(id(owner))
        event = ScreenReaderEvents.SCREEN_OBJECT_FOUND(tag=tag, subscriber_id=subscriber_id)
        screen_reader: IScreenReader = ServiceBroker.get_broker().get_service(IScreenReader)
        client_ids = list(client_ids)

        class Subscriber(IEventSubscriber):
            def __init__(self):
                # keep ref, prevent duplicate subscriber_id until this object is GC'ed
                self.__owner = owner

            def get_event(self) -> Event:
                return event

            def subscribe(self) -> bool:
                if isinstance(area_source, CaptureArea):
                    areas_for_clients = {area_source: client_ids}
                else:
                    assert isinstance(area_source, Callable), f'{area_source}, {tag}'
                    areas_for_clients = dict()
                    for client_id in client_ids:
                        area = area_source(client_id)
                        if not area:
                            logger.warn(f'No capture area for tag={tag}, client={client_id}, subid={subscriber_id}')
                            continue
                        areas_for_clients.setdefault(area, []).append(client_id)
                for area, area_client_ids in areas_for_clients.items():
                    screen_reader.subscribe(client_ids=area_client_ids, subscriber_id=subscriber_id, tag=tag, area=area,
                                            check_period=check_period, event_period=event_period, max_matches=max_matches)
                return True

            def unsubscribe(self):
                screen_reader.unsubscribe(subscriber_id=subscriber_id, tag=event.tag)

        return Subscriber()


class EventSubscriberToolkit:
    @staticmethod
    def add_event_to_trigger(runtime: IRuntime, trigger: ITrigger, event: Event, filter_cb: Optional[Callable[[Event], bool]] = None):
        if isinstance(event, ClientEvents.PARSER_MATCH):
            assert isinstance(trigger, IPlayerTrigger), trigger.describe()
            # client_id might be missing (especially from saved JSON triggers)
            event.client_id = trigger.get_client_id()
            subscriber = EventSubscriberFactory.create_parser_subscriber_from_event(runtime, event)
            trigger.add_subscribed_client_bus_event(subscriber=subscriber, filter_cb=filter_cb)
        elif isinstance(event, ClientEvent):
            assert isinstance(trigger, IPlayerTrigger), trigger.describe()
            # client_id might be missing (especially from saved JSON triggers)
            event.client_id = trigger.get_client_id()
            trigger.add_client_bus_event(event)
        elif isinstance(event, ScreenReaderEvents.SCREEN_OBJECT_FOUND):
            subscriber = EventSubscriberFactory.create_screen_reader_subscriber_from_event(event)
            trigger.add_subscribed_bus_event(subscriber=subscriber, filter_cb=filter_cb)
        else:
            trigger.add_bus_event(event)

    @staticmethod
    def add_screen_event_to_trigger(trigger: ITrigger,
                                    client_ids: Iterable[Union[str, IHasClient]],
                                    tag: Resource,
                                    area_source: Union[CaptureArea, Callable[[Union[str, IHasClient]], CaptureArea]],
                                    check_period: Optional[float] = None,
                                    event_period: Optional[float] = None,
                                    max_matches: Optional[int] = None,
                                    filter_cb: Optional[Callable[[ScreenReaderEvents.SCREEN_OBJECT_FOUND], bool]] = None):
        subscriber = EventSubscriberFactory.create_screen_reader_subscriber(tag=tag,
                                                                            area_source=area_source,
                                                                            client_ids=client_ids,
                                                                            check_period=check_period,
                                                                            event_period=event_period,
                                                                            max_matches=max_matches)
        trigger.add_subscribed_bus_event(subscriber, filter_cb=filter_cb)

    @staticmethod
    def add_parser_events_to_trigger(trigger: ITrigger,
                                     parse_filters: Union[str, List[str]], parse_preparsed_logs=False,
                                     filter_cb: Optional[Callable[[ClientEvents.PARSER_MATCH], bool]] = None,
                                     runtime: Optional[IRuntime] = None, client_id: Optional[str] = None):
        if isinstance(trigger, IPlayerTrigger):
            runtime = trigger.get_runtime()
            client_id = trigger.get_client_id()
        else:
            assert runtime and client_id, trigger.describe()
        if not isinstance(parse_filters, list):
            parse_filters = [parse_filters]
        for parse_filter in parse_filters:
            custom_subscriber = EventSubscriberFactory.create_parser_subscriber(runtime=runtime,
                                                                                client_id=client_id,
                                                                                parse_filter=parse_filter,
                                                                                preparsed_logs=parse_preparsed_logs)
            trigger.add_subscribed_client_bus_event(subscriber=custom_subscriber, filter_cb=filter_cb)
