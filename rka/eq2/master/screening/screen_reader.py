from __future__ import annotations

import time
from threading import RLock
from typing import Iterable, List, Optional, Dict, Tuple, Union

from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.components.resources import Resource
from rka.components.ui.capture import CaptureArea, MatchPattern, Rect
from rka.eq2.master.control import IHasClient
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.screening import IScreenReader
from rka.eq2.master.screening.screen_reader_events import ScreenReaderEvents
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.log_configs import LOG_CAPTURING
from rka.services.api import IService

logger = LogService(LOG_CAPTURING)


class _Subscription:
    def __init__(self, client_ids: Iterable[Union[str, IHasClient]], subscriber_id: Optional[str], tag: Resource, area: CaptureArea,
                 check_period: Optional[int], event_period: float, max_matches: Optional[int]):
        self.__client_ids = client_ids
        self.__subscriber_id = subscriber_id
        self.__tag = tag
        self.__area = area
        self.__check_period = check_period
        self.__event_period = event_period
        self.__max_matches = max_matches if max_matches and max_matches > 0 else 1
        self.__last_check_time = None
        self.__last_event_time: Dict[str, float] = dict()

    def __post_event(self, client_id: str, location_rects: List[Rect]):
        now = time.time()
        since_previous = now - self.__last_event_time.get(client_id, 0.0)
        if self.__event_period and since_previous < self.__event_period:
            logger.detail(f'_Subscription.__post_event: skip event for cid={client_id}, tag={self.__tag.resource_name}, since_last={since_previous}')
            return
        logger.detail(f'_Subscription.post_event: send for cid={client_id}, tag={self.__tag.resource_name}, rects={location_rects}')
        event = ScreenReaderEvents.SCREEN_OBJECT_FOUND(tag=self.__tag,
                                                       client_id=client_id,
                                                       area=self.__area,
                                                       location_rects=location_rects[:self.__max_matches],
                                                       since_previous=since_previous,
                                                       subscriber_id=self.__subscriber_id)
        EventSystem.get_main_bus().post(event)
        self.__last_event_time[client_id] = now

    def __is_ready_for_next_check(self) -> bool:
        if self.__check_period:
            now = time.time()
            if self.__last_check_time:
                since_previous_check = now - self.__last_check_time
                if since_previous_check < self.__check_period:
                    return False
            self.__last_check_time = now
        return True

    def __is_ready_for_next_event(self, client_id: str) -> bool:
        if self.__event_period:
            now = time.time()
            last_event_time = self.__last_event_time.get(client_id, 0.0)
            since_previous_event = now - last_event_time
            if since_previous_event < self.__event_period:
                return False
        return True

    def __get_client_ids(self) -> List[str]:
        client_ids = [cid.get_client_id() if isinstance(cid, IHasClient) else cid for cid in self.__client_ids]
        return client_ids

    def __dispatch_results(self, client_id: str, match_list: List[Tuple[str, Rect]]):
        # group by tag_id, send as a batch in one event - should be one tag
        tagid_to_rects: Dict[str, List[Rect]] = dict()
        for (tag_id, match_rect) in match_list:
            rects = tagid_to_rects.setdefault(tag_id, [])
            rects.append(match_rect)
        if len(tagid_to_rects) != 1:
            logger.error(f'_Subscription.__dispatch_results: Too many tag_ids received: {tagid_to_rects.keys()}')
        for (tag_id, match_rects) in tagid_to_rects.items():
            logger.detail(f'_Subscription.__dispatch_results: client_id={client_id} tagid={tag_id}')
            self.__post_event(client_id=client_id, location_rects=match_rects)

    def __single_match_cb(self, client_id: str, results: Optional[List]):
        logger.detail(f'_Subscription.__single_match_cb: client_id={client_id}, results={results}')
        if not results or not results[0]:
            return
        (tag_id, loc_rect_str) = results[0]
        match_list = [(tag_id, Rect.decode_rect(loc_rect_str))]
        self.__dispatch_results(client_id=client_id, match_list=match_list)

    def __multiple_match_cb(self, client_id: str, results: Optional[List]):
        logger.detail(f'_Subscription.__multiple_match_cb: client_id={client_id}, results={results}')
        if not results or not results[0]:
            return
        match_list = [(tag_id, Rect.decode_rect(loc_rect_str)) for (tag_id, loc_rect_str) in results[0]]
        self.__dispatch_results(client_id=client_id, match_list=match_list)

    def __post_action(self, pattern: MatchPattern, client_id: str):
        logger.debug(f'_Subscription.__post_action: posting match action for cid={client_id}, tag={self.__tag.resource_name}, area={self.__area}, max_m={self.__max_matches}')
        action = action_factory.new_action()
        if self.__max_matches > 1:
            action = action.find_multiple_capture_match(patterns=pattern, capture_area=self.__area, max_matches=self.__max_matches)
            action.post_sync(client_id=client_id, completion_cb=lambda results_: self.__multiple_match_cb(client_id, results_))
        else:
            action = action.find_capture_match(patterns=pattern, capture_area=self.__area)
            action.post_sync(client_id=client_id, completion_cb=lambda results_: self.__single_match_cb(client_id, results_))

    def post_actions(self):
        if not self.__is_ready_for_next_check():
            return
        client_ids = self.__get_client_ids()
        logger.debug(f'_Subscription.post_actions: cids={client_ids}, tag={self.__tag.resource_name}')
        pattern = MatchPattern.by_tag(self.__tag)
        for client_id in client_ids:
            if not self.__is_ready_for_next_event(client_id):
                continue
            self.__post_action(pattern, client_id)


class _AreaMonitor:
    def __init__(self, area: CaptureArea):
        self.__lock = RLock()
        self.__area = area
        self.__tagid_to_subscriptions: Dict[str, Dict[Optional[str], _Subscription]] = dict()

    def __str__(self):
        return 'MonitorArea[%s]' % self.__area.encode_area()

    def detect_objects(self):
        logger.detail(f'_MonitorArea.detect_objects {self.__area}')
        with self.__lock:
            for subid_to_subscription in self.__tagid_to_subscriptions.values():
                for subscription in subid_to_subscription.values():
                    subscription.post_actions()

    def subscribe(self, client_ids: Iterable[Union[str, IHasClient]], subscriber_id: str, tag: Resource, area: CaptureArea,
                  check_period: Optional[int], event_period: Optional[float], max_matches: Optional[int]):
        with self.__lock:
            if tag.resource_id not in self.__tagid_to_subscriptions:
                logger.detail(f'_MonitorArea:subscribe: new sub collection for tag={tag.resource_name}, with subid={subscriber_id} ')
                subscriptions = dict()
                self.__tagid_to_subscriptions[tag.resource_id] = subscriptions
            else:
                logger.detail(f'_MonitorArea:subscribe: add subid={subscriber_id} to subs for tag={tag.resource_name}')
                subscriptions = self.__tagid_to_subscriptions[tag.resource_id]
            new_subscription = _Subscription(client_ids=client_ids, subscriber_id=subscriber_id, tag=tag, area=area,
                                             check_period=check_period, event_period=event_period, max_matches=max_matches)
            subscriptions[subscriber_id] = new_subscription

    def unsubscribe(self, subscriber_id: str, tag: Optional[Resource]) -> bool:
        with self.__lock:
            any_removed = False
            if not tag:
                tag_ids = list(self.__tagid_to_subscriptions.keys())
            else:
                tag_ids = [tag.resource_id]
            for tag_id in tag_ids:
                if tag_id not in self.__tagid_to_subscriptions:
                    continue
                subscriptions = self.__tagid_to_subscriptions[tag_id]
                if subscriber_id in subscriptions:
                    logger.detail(f'_MonitorArea:unsubscribe: removing sub subid={subscriber_id} for tag={tag_id}')
                    any_removed = True
                    del subscriptions[subscriber_id]
                if not subscriptions:
                    logger.detail(f'_MonitorArea:unsubscribe: no more subs for tag={tag_id}, removing')
                    del self.__tagid_to_subscriptions[tag_id]
        return any_removed

    def has_subscriptions(self) -> bool:
        with self.__lock:
            return bool(self.__tagid_to_subscriptions)


class ScreenReader(IScreenReader, IService):
    def __init__(self, detect_period: float):
        self.__lock = RLock()
        self.__detect_period = detect_period
        self.__monitors: Dict[str, _AreaMonitor] = dict()
        self.__default_area = CaptureArea()

    def __detect_objects(self):
        with self.__lock:
            monitors = list(self.__monitors.values())
        logger.detail(f'ScreenReader:__detect_objects ({len(monitors)})')
        if not monitors:
            logger.debug(f'ScreenReader:__detect_objects: no monitors, stop detecting')
            return
        for monitor in monitors:
            monitor.detect_objects()
        self.__schedule_next_detection()

    def __schedule_next_detection(self):
        logger.debug(f'ScreenReader.__schedule_next_detection: delay={self.__detect_period}')
        shared_scheduler.schedule(self.__detect_objects, delay=self.__detect_period)

    def is_finalized(self) -> bool:
        return False

    def subscribe(self, client_ids: Iterable[Union[str, IHasClient]], subscriber_id: str, tag: Resource, area: Optional[CaptureArea] = None,
                  check_period: Optional[int] = None, event_period: Optional[float] = None, max_matches: Optional[int] = None):
        logger.info(f'ScreenReader:subscribe subid={subscriber_id}, tag={tag.resource_name}, area={area}, period={event_period}')
        if not area:
            area = self.__default_area
        with self.__lock:
            if not self.__monitors:
                self.__schedule_next_detection()
            area_str = area.encode_area()
            if area_str in self.__monitors:
                logger.debug(f'ScreenReader:subscribe: extend monitor for {area_str}, tag={tag.resource_name}, subid={subscriber_id}')
                target_monitor = self.__monitors[area_str]
            else:
                logger.debug(f'ScreenReader:subscribe: new monitor for {area_str}, tag={tag.resource_name}, subid={subscriber_id}')
                target_monitor = _AreaMonitor(area)
                self.__monitors[area_str] = target_monitor
            target_monitor.subscribe(client_ids=client_ids, subscriber_id=subscriber_id, tag=tag, area=area,
                                     check_period=check_period, event_period=event_period, max_matches=max_matches)

    def __unsubscribe_for_area(self, subscriber_id: str, tag: Optional[Resource], area_str: str) -> bool:
        target_monitor = self.__monitors[area_str]
        if not target_monitor.unsubscribe(subscriber_id=subscriber_id, tag=tag):
            return False
        if not target_monitor.has_subscriptions():
            logger.debug(f'ScreenReader:unsubscribe: no more subs for {target_monitor}, tag={tag}, removing')
            del self.__monitors[area_str]
        return True

    def unsubscribe(self, subscriber_id: str, tag: Optional[Resource] = None, area: Optional[CaptureArea] = None):
        logger.info(f'ScreenReader:unsubscribe subid={subscriber_id}, tag={tag}, area={area}')
        with self.__lock:
            areas_strs = [area.encode_area()] if area else list(self.__monitors.keys())
            any_removed = False
            for area_str in areas_strs:
                any_removed = any_removed or self.__unsubscribe_for_area(subscriber_id=subscriber_id, tag=tag, area_str=area_str)
        if not any_removed:
            logger.warn(f'ScreenReader:unsubscribe no subscriber removed for subid={subscriber_id}, tag={tag}, area={area}')
