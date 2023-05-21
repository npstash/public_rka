from rka.components.cleanup import Closeable
from rka.components.events.event_system import EventSystem
from rka.components.ui.capture import CaptureArea, Rect, Offset, MatchPattern, CaptureMode
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.configs.shared.rka_constants import CLICK_DELAY
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.screening import IScreenReader
from rka.eq2.master.screening.screen_reader_events import ScreenReaderEvents
from rka.services.broker import ServiceBroker


class ScreenAutomation(Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=True)
        self.__runtime = runtime
        self.__all_access_subscriber_id = 'screen automation: all access'
        all_access_check_players = runtime.playerselectors.remote_online_non_member()
        self.__screen_reader: IScreenReader = ServiceBroker.get_broker().get_service(IScreenReader)
        mark_rect = Rect(84, 228, 160, 284)
        area = CaptureArea(mode=CaptureMode.BW, wintitle=EQ2_WINDOW_NAME).capture_rect(mark_rect, relative=True)
        self.__screen_reader.subscribe(client_ids=all_access_check_players, subscriber_id=self.__all_access_subscriber_id,
                                       tag=ui_patterns.PATTERN_GFX_ALL_ACCESS_SMALL, area=area,
                                       check_period=60.0)
        EventSystem.get_main_bus().subscribe(ScreenReaderEvents.SCREEN_OBJECT_FOUND(subscriber_id=self.__all_access_subscriber_id), self.__all_access_banner)

    def __all_access_banner(self, event: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
        self.__runtime.overlay.log_event(f'Close All Access for {event.client_id}', Severity.Low)
        all_access_pattern = MatchPattern.by_tag(ui_patterns.PATTERN_GFX_ALL_ACCESS_SMALL)
        action = action_factory.new_action().click_capture_match(patterns=all_access_pattern, capture_area=event.area,
                                                                 click_delay=CLICK_DELAY, click_offset=Offset(386, 192, Offset.REL_WIND_BOX))
        action.post_async(event.client_id)

    def close(self):
        self.__screen_reader.unsubscribe(subscriber_id=self.__all_access_subscriber_id)
        main_bus = EventSystem.get_main_bus()
        if main_bus:
            main_bus.unsubscribe_all(event_type=ScreenReaderEvents.SCREEN_OBJECT_FOUND, subscriber=self.__all_access_banner)
        Closeable.close(self)
