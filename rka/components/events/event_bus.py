from __future__ import annotations

from threading import Lock
from typing import Callable, List, Dict, Hashable, Type, Union, Optional, Any, Set, Generic, get_origin

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.events import Event, logger, EventType
from rka.components.events.event_system import BusThread, ISubscriberContainer, ISubscriberDB, IEventPoster, IEventPosterFactory, IEventBusPoster, \
    EventSubscription, UpdateFlag, IEventBusPosterFactory


class SubscriberList(Generic[EventType], ISubscriberDB[EventType], UpdateFlag):
    def __init__(self, event_type: Type[EventType]):
        UpdateFlag.__init__(self)
        self.__event_type = event_type
        self.__lock = Lock()
        self.__subscribers: List[EventSubscription[EventType]] = list()

    # from ISubscriberDB
    def add_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType):
        assert isinstance(subscribe_template, self.__event_type)
        with self.__lock:
            subscription = EventSubscription(subscriber, subscribe_template)
            self.__subscribers.append(subscription)
            self.set_last_update()

    # from ISubscriberDB
    def remove_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType) -> bool:
        assert isinstance(subscribe_template, self.__event_type)
        found = False
        with self.__lock:
            for sub in self.__subscribers:
                if sub.match_subscriber(subscriber) and sub.match_event(subscribe_template, strict_comparison=True):
                    self.__subscribers.remove(sub)
                    found = True
                    break
            self.set_last_update()
        return found

    # from ISubscriberDB
    def remove_subscriber_all(self, subscriber: Callable[[EventType], None]) -> int:
        removed_count = 0
        with self.__lock:
            subscribers_after_removing = list()
            for sub in self.__subscribers:
                if not sub.match_subscriber(subscriber):
                    subscribers_after_removing.append(sub)
                else:
                    removed_count += 1
            if removed_count:
                self.__subscribers = subscribers_after_removing
            if removed_count:
                self.set_last_update()
        return removed_count

    # from ISubscriberDB
    def clear_subscribers(self):
        with self.__lock:
            self.__subscribers.clear()
            self.set_last_update()

    # from ISubscriberContainer
    def filter_subscribers(self, event: EventType) -> List[EventSubscription[EventType]]:
        assert isinstance(event, self.__event_type)
        with self.__lock:
            return [sub for sub in self.__subscribers if sub.match_event(event, strict_comparison=True)]

    def filter_into_subcontainer(self, event_template: EventType, subcontainer: ISubscriberDB):
        assert isinstance(event_template, self.__event_type)
        with self.__lock:
            for subscription in self.__subscribers:
                if subscription.match_event(event_template, strict_comparison=False):
                    subcontainer.add_subscriber(subscription.get_subscriber(), subscription.get_subscribe_template())

    # from ISubscriberContainer
    def get_last_update(self) -> float:
        return UpdateFlag.get_last_update(self)

    # from ISubscriberContainer
    def is_empty(self) -> bool:
        return not bool(self.__subscribers)


class SubscriberIndexer(Generic[EventType], ISubscriberDB[EventType], UpdateFlag):
    def __init__(self, event_type: Type[EventType]):
        UpdateFlag.__init__(self)
        self.__event_type = event_type
        self.__lock = Lock()
        # set field name -> field value -> subscribers
        self.__by_set_indexed_fields: Dict[str, Dict[Any, Set[EventSubscription[EventType]]]] = dict()
        # set field name -> subscribers
        self.__by_set_unindexed_fields: Dict[str, Set[EventSubscription[EventType]]] = dict()
        # None field name -> subscribers
        self.__by_none_fields: Dict[str, Set[EventSubscription[EventType]]] = dict()
        # unset field name -> subscribers
        self.__by_unset_fields: Dict[str, Set[EventSubscription[EventType]]] = dict()
        # subscription -> list of sets where to find it; dont index by subscriber, they may repeat and not every callable will be hashable
        self.__by_subscription: Dict[EventSubscription[EventType], List[Set[EventSubscription[EventType]]]] = dict()

    @staticmethod
    def __get_from_dict(d: Dict, key: Hashable, default_fn: Callable) -> Any:
        if key not in d:
            d[key] = default_fn()
        return d[key]

    def __get_indexed_subscribers(self, field_name: str, field_value: Hashable, create_set_for_values: bool) -> Set[EventSubscription[EventType]]:
        field_value_dict = SubscriberIndexer.__get_from_dict(self.__by_set_indexed_fields, field_name, dict)
        if not create_set_for_values:
            if field_value not in field_value_dict:
                return set()
        return SubscriberIndexer.__get_from_dict(field_value_dict, field_value, set)

    def __get_all_indexed_subscribers(self, field_name: str) -> Set[EventSubscription[EventType]]:
        field_value_dict = SubscriberIndexer.__get_from_dict(self.__by_set_indexed_fields, field_name, dict)
        all_subs = set()
        for subs in field_value_dict.values():
            all_subs = all_subs.union(subs)
        return all_subs

    def __get_unindexed_subscribers(self, field_name: str) -> Set[EventSubscription[EventType]]:
        return SubscriberIndexer.__get_from_dict(self.__by_set_unindexed_fields, field_name, set)

    def __get_none_subscribers(self, field_name: str) -> Set[EventSubscription[EventType]]:
        return SubscriberIndexer.__get_from_dict(self.__by_none_fields, field_name, set)

    def __get_unset_subscribers(self, field_name: str) -> Set[EventSubscription[EventType]]:
        return SubscriberIndexer.__get_from_dict(self.__by_unset_fields, field_name, set)

    def __get_subscriber_setlist(self, subscription: EventSubscription[EventType]) -> List[Set[EventSubscription[EventType]]]:
        return SubscriberIndexer.__get_from_dict(self.__by_subscription, subscription, list)

    def __get_subscriber_set_for_field(self, field_name: str, subscribe_template: EventType, create: bool) -> Set[EventSubscription[EventType]]:
        if not subscribe_template.is_param_set(field_name):
            subs = self.__get_unset_subscribers(field_name)
        else:
            field_value = subscribe_template.get_param(field_name)
            if field_value is None:
                subs = self.__get_none_subscribers(field_name)
            elif isinstance(field_value, Hashable):
                subs = self.__get_indexed_subscribers(field_name, field_value, create_set_for_values=create)
            else:
                subs = self.__get_unindexed_subscribers(field_name)
        return subs

    # from ISubscriberDB
    def add_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType):
        assert isinstance(subscribe_template, self.__event_type)
        with self.__lock:
            new_subscription = EventSubscription(subscriber, subscribe_template)
            for subscription in self.__by_subscription.keys():
                if subscription.match_subscription(new_subscription):
                    logger.warn(f'Subscription already exists! {subscribe_template} -> {subscriber}')
                    break
            for field_name in subscribe_template.param_names:
                subs = self.__get_subscriber_set_for_field(field_name, subscribe_template, True)
                subs.add(new_subscription)
                subs_list = self.__get_subscriber_setlist(new_subscription)
                subs_list.append(subs)
            self.set_last_update()

    def __remove_subscription_sets(self, subscription: EventSubscription[EventType]):
        subs_list = self.__by_subscription[subscription]
        for subs in subs_list:
            subs.remove(subscription)

    # from ISubscriberDB
    def remove_subscriber(self, subscriber: Callable[[EventType], None], subscribe_template: EventType) -> bool:
        assert isinstance(subscribe_template, self.__event_type)
        with self.__lock:
            for field_name in subscribe_template.param_names:
                subs = self.__get_subscriber_set_for_field(field_name, subscribe_template, False)
                for subscription in subs:
                    if subscription.match_subscriber(subscriber) and subscription.match_event(subscribe_template, strict_comparison=True):
                        self.__remove_subscription_sets(subscription)
                        del self.__by_subscription[subscription]
                        self.set_last_update()
                        return True
        return False

    # from ISubscriberDB
    def remove_subscriber_all(self, subscriber: Callable[[EventType], None]) -> int:
        subscriptions_to_del = list()
        with self.__lock:
            for subscription in self.__by_subscription.keys():
                if subscription.match_subscriber(subscriber):
                    self.__remove_subscription_sets(subscription)
                    subscriptions_to_del.append(subscription)
            for subscription in subscriptions_to_del:
                del self.__by_subscription[subscription]
            if subscriptions_to_del:
                self.set_last_update()
            return len(subscriptions_to_del)

    # from ISubscriberDB
    def clear_subscribers(self):
        with self.__lock:
            self.__by_set_indexed_fields.clear()
            self.__by_set_unindexed_fields.clear()
            self.__by_none_fields.clear()
            self.__by_unset_fields.clear()
            self.__by_subscription.clear()
            self.set_last_update()

    # from ISubscriberContainer
    def filter_subscribers(self, event: EventType) -> List[EventSubscription[EventType]]:
        assert isinstance(event, self.__event_type)
        # event param set -> sub param set and equal, or unset
        # event param unset -> sub param unset
        with self.__lock:
            candidates = None
            for field_name in event.param_names:
                unset_subs = self.__get_unset_subscribers(field_name)
                if event.is_param_set(field_name):
                    field_value = event.get_param(field_name)
                    # compare value
                    if field_value is None:
                        candidates_by_field = self.__get_none_subscribers(field_name)
                    elif isinstance(field_value, Hashable):
                        candidates_by_field = self.__get_indexed_subscribers(field_name, field_value, create_set_for_values=False)
                    else:
                        unfiltered_subs = self.__get_unindexed_subscribers(field_name)
                        candidates_by_field = set()
                        for subscription in unfiltered_subs:
                            if subscription.match_event_field(event, field_name):
                                candidates_by_field.add(subscription)
                    # add subs with value unset
                    candidates_by_field = candidates_by_field.union(unset_subs)
                else:
                    candidates_by_field = unset_subs
                if candidates is None:
                    candidates = candidates_by_field
                else:
                    candidates = candidates.intersection(candidates_by_field)
            return list(candidates) if candidates else list()

    def filter_into_subcontainer(self, event_template: EventType, subcontainer: ISubscriberDB):
        assert isinstance(event_template, self.__event_type)
        for subscription in self.__by_subscription.keys():
            if subscription.match_event(event_template, strict_comparison=False):
                subcontainer.add_subscriber(subscription.get_subscriber(), subscription.get_subscribe_template())

    # from ISubscriberContainer
    def get_last_update(self) -> float:
        return UpdateFlag.get_last_update(self)

    # from ISubscriberContainer
    def is_empty(self) -> bool:
        with self.__lock:
            return not bool(self.__by_subscription)


class SubscriberDBFactory:
    @staticmethod
    def create_subscriber_db(event_type: Type[EventType]) -> ISubscriberDB[EventType]:
        # indexing container only if there are hashable fields
        for param_name in event_type.param_names:
            param_type = event_type.get_param_type(param_name)
            origin_param_type = get_origin(param_type)
            if origin_param_type:
                param_type = origin_param_type
            if issubclass(param_type, Hashable):
                return SubscriberIndexer(event_type)
        return SubscriberList(event_type)


# Attention for posters made using events with unset fields: when created and an event with unset fields is given, and
# filtered subscribers exclude subscribers, which have those fields SET
class PrefilteredEventPoster(Generic[EventType], IEventPoster[EventType], IEventPosterFactory):
    def __init__(self, poster: EventDispatcher[EventType], container: ISubscriberContainer[EventType], posting_template: EventType):
        self.__poster = poster
        self.__parent_container = container
        self.__filtered_container = SubscriberList(event_type=type(posting_template))
        self.__parent_container.filter_into_subcontainer(posting_template, self.__filtered_container)
        self.__status_timestamp = self.__parent_container.get_last_update()
        self.__posting_template = posting_template
        self.__quiet = False

    def __update_filtered_container(self):
        container_last_update = self.__parent_container.get_last_update()
        if container_last_update > self.__status_timestamp:
            self.__filtered_container.clear_subscribers()
            self.__parent_container.filter_into_subcontainer(self.__posting_template, self.__filtered_container)
            self.__status_timestamp = self.__parent_container.get_last_update()

    def __prepare_event(self, event: Optional[EventType]) -> EventType:
        if event:
            merged_event = event.merge_with(self.__posting_template)
        else:
            merged_event = self.__posting_template
        return merged_event

    # from IEventPoster
    def post(self, event: EventType):
        self.__update_filtered_container()
        if self.__filtered_container.is_empty():
            return
        merged_event = self.__prepare_event(event)
        deliver_subs = self.__filtered_container.filter_subscribers(merged_event)
        if deliver_subs:
            self.__poster.post_event_to(event=merged_event, deliver_subs=deliver_subs)

    # from IEventPoster
    def call(self, event: EventType):
        self.__update_filtered_container()
        if self.__filtered_container.is_empty():
            return
        merged_event = self.__prepare_event(event)
        deliver_subs = self.__filtered_container.filter_subscribers(merged_event)
        if deliver_subs:
            self.__poster.pass_event_to(event=merged_event, deliver_subs=deliver_subs)

    # from IEventPoster
    def mute_logs(self):
        self.__quiet = True

    # from IEventPosterFactory
    def get_poster(self, posting_template: EventType) -> IEventPoster[EventType]:
        return PrefilteredEventPoster(self.__poster, self.__parent_container, posting_template.merge_with(self.__posting_template))


class EventDispatcher(Generic[EventType]):
    def __init__(self, worker: BusThread):
        self.__worker = worker
        self.__quiet = False

    def mute_logs(self):
        self.__quiet = True

    def post_event_to(self, event: EventType, deliver_subs: List[EventSubscription[EventType]]):
        if not self.__quiet:
            logger.info(f'posting {event} to {len(deliver_subs)} subscribers')
        for sub in deliver_subs:
            if not sub.post_event(self.__worker, event):
                if self.__worker.is_closed():
                    logger.warn(f'Bus Thread closed, ignore ({event})')
                    return
                new_thread_num = self.__worker.bus_thread_num + 1
                logger.error(f'Bus Thread queue filled (sending {event}) in new thread #{new_thread_num}')
                self.__worker.print_queue()
                RKAThread.dump_threads()
                self.__worker = BusThread(f'Replacement Bus thread #{new_thread_num}', new_thread_num)
                if not sub.post_event(self.__worker, event):
                    logger.fatal(f'Unable to send event {event}')

    def pass_event_to(self, event: EventType, deliver_subs: List[EventSubscription[EventType]]):
        if not self.__quiet:
            logger.info(f'passing {event} to {len(deliver_subs)} subscribers')
        for sub in deliver_subs:
            sub.pass_event(event)

    def complete_pending_events(self):
        future = self.__worker.push_task(lambda: None)
        if future:
            future.get_result()


class SpecificEventBus(Generic[EventType], IEventBusPoster[EventType], ISubscriberContainer[EventType], IEventPosterFactory, EventDispatcher[EventType]):
    def __init__(self, bus_id: str, worker: BusThread, event_type: Type[EventType]):
        EventDispatcher.__init__(self, worker)
        self.__bus_id = bus_id
        self.__event_type = event_type
        self.__subscribers = SubscriberDBFactory.create_subscriber_db(event_type)

    def __str__(self) -> str:
        return self.describe()

    def describe(self) -> str:
        return f'SpecificEventBus [{self.__bus_id}-{self.__event_type.value}]'

    # from IEventPoster
    def post(self, event: EventType):
        if self.__subscribers.is_empty():
            return
        deliver_subs = self.__subscribers.filter_subscribers(event)
        if deliver_subs:
            self.post_event_to(event, deliver_subs)

    # from IEventPoster
    def call(self, event: EventType):
        if self.__subscribers.is_empty():
            return
        deliver_subs = self.__subscribers.filter_subscribers(event)
        if deliver_subs:
            self.pass_event_to(event, deliver_subs)

    # from IEventPoster
    def mute_logs(self):
        EventDispatcher.mute_logs(self)

    # from IEventPosterFactory
    def get_poster(self, posting_template: EventType) -> IEventPoster[EventType]:
        return PrefilteredEventPoster(self, self, posting_template)

    # from IEventBus
    def subscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]):
        logger.info(f'subscribing in {self.describe()} for event {subscribe_template}, sub {subscriber}')
        self.__subscribers.add_subscriber(subscriber=subscriber, subscribe_template=subscribe_template)

    # from IEventBus
    def unsubscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]) -> bool:
        logger.info(f'unsubscribing in {self.describe()} for event {subscribe_template}, sub {subscriber}')
        removed = self.__subscribers.remove_subscriber(subscriber=subscriber, subscribe_template=subscribe_template)
        if not removed:
            logger.warn(f'failed to unsubscribe, template={subscribe_template} with subscriber={subscriber}')
        return removed

    # from IEventBus
    def unsubscribe_all(self, event_type: Type[EventType], subscriber: Callable[[EventType], None]) -> bool:
        removed_count = self.__subscribers.remove_subscriber_all(subscriber)
        logger.info(f'unsubscribing in {self.describe()} all for event_id {self.__event_type}, sub {subscriber} [{removed_count} occurrences]')
        if not removed_count:
            logger.info(f'cannot unsubscribe, sub not present')
        return removed_count > 0

    # from IEventBus
    def close_bus(self):
        logger.info(f'close_bus {self.describe()}')
        self.complete_pending_events()
        self.__subscribers.clear_subscribers()

    # from ISubscriberContainer
    def filter_subscribers(self, event: EventType) -> List[EventSubscription[EventType]]:
        return self.__subscribers.filter_subscribers(event)

    # from ISubscriberContainer
    def filter_into_subcontainer(self, event_template: EventType, subcontainer: ISubscriberDB):
        self.__subscribers.filter_into_subcontainer(event_template, subcontainer)

    # from ISubscriberContainer
    def get_last_update(self) -> float:
        return self.__subscribers.get_last_update()

    # from ISubscriberContainer
    def is_empty(self) -> bool:
        return self.__subscribers.is_empty()


class EventBus(IEventBusPoster[Event], IEventPosterFactory, Closeable):
    def __init__(self, bus_id: Union[int, str]):
        Closeable.__init__(self, explicit_close=True)
        self.__bus_id = bus_id
        self.__lock = Lock()
        self.__worker = BusThread(f'Bus Thread [{bus_id}]', 1)
        self.__specific_event_buses: List[Optional[SpecificEventBus]] = []
        logger.info(f'started event bus id {self.__worker.describe_resource()}')

    def _get_worker(self) -> BusThread:
        return self.__worker

    def _create_specific_event_bus(self, event_type: Type[EventType]) -> SpecificEventBus[EventType]:
        return SpecificEventBus(self.__bus_id, self.__worker, event_type)

    def _get_specific_event_bus(self, event_type: Type[EventType]) -> SpecificEventBus[EventType]:
        with self.__lock:
            event_id = event_type.event_id
            if event_id >= len(self.__specific_event_buses):
                self.__specific_event_buses += [None] * (event_id - len(self.__specific_event_buses) + 1)
            if self.__specific_event_buses[event_id] is None:
                self.__specific_event_buses[event_id] = self._create_specific_event_bus(event_type)
            return self.__specific_event_buses[event_id]

    # from IEventPoster
    def post(self, event: Event):
        return self._get_specific_event_bus(event_type=type(event)).post(event)

    # from IEventPoster
    def call(self, event: Event):
        return self._get_specific_event_bus(event_type=type(event)).call(event)

    # from IEventPoster
    def mute_logs(self):
        with self.__lock:
            for event_bus in self.__specific_event_buses:
                if not event_bus:
                    continue
                event_bus.mute_logs()

    # from IEventPosterFactory
    def get_poster(self, posting_template: EventType) -> IEventPoster[EventType]:
        return self._get_specific_event_bus(event_type=type(posting_template)).get_poster(posting_template)

    # from IEventBus
    def subscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]):
        return self._get_specific_event_bus(event_type=type(subscribe_template)).subscribe(subscribe_template, subscriber)

    # from IEventBus
    def unsubscribe(self, subscribe_template: EventType, subscriber: Callable[[EventType], None]) -> bool:
        return self._get_specific_event_bus(event_type=type(subscribe_template)).unsubscribe(subscribe_template, subscriber)

    # from IEventBus
    def unsubscribe_all(self, event_type: Type[EventType], subscriber: Callable[[EventType], None]) -> bool:
        return self._get_specific_event_bus(event_type=event_type).unsubscribe_all(event_type, subscriber)

    # from IEventBus
    def close_bus(self):
        self.close()

    # from Closeable
    def close(self):
        with self.__lock:
            for event_bus in self.__specific_event_buses:
                if event_bus:
                    event_bus.close_bus()
        self.__worker.close()
        Closeable.close(self)


class EventBusFactory(IEventBusPosterFactory):
    def create_event_bus(self, bus_id: str) -> IEventBusPoster:
        return EventBus(bus_id)
