from typing import Union, Tuple, Optional, List, Callable

from rka.components.resources import Resource
from rka.components.ui.capture import MatchPattern, CaptureArea
from rka.eq2.configs.shared.rka_constants import PROCESSOR_TICK, GAME_LAG
from rka.eq2.master.game.engine.filter_tasks import StopCastingFilter
from rka.eq2.master.game.engine.task import Task
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.scripting import BagLocation, RepeatMode
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.procedures.common import TriggerReaderProcedure
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit, Procedure
from rka.eq2.shared.client_events import ClientEvents


class BagItemCheckerProcedure(TriggerReaderProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit, item_name: str, exact_name=True):
        TriggerReaderProcedure.__init__(self, scripting, game_command=f'finditem {item_name}')
        self.__item_name = item_name
        self.__exact_name = exact_name
        self.__item_name_lower = item_name.lower()
        self._get_trigger().add_bus_event(PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY(player=scripting.get_player()), filter_cb=self.__filter_items)
        self._get_trigger().add_parser_events(rf'No items were found matching "{item_name}".')

    def __filter_items(self, event: PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY) -> bool:
        return self.__item_name_lower in event.item_name.lower()

    def _get_object(self, event: Union[ClientEvents.PARSER_MATCH, PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY]) -> Tuple[bool, Optional[BagLocation]]:
        if isinstance(event, ClientEvents.PARSER_MATCH):
            logger.warn(f'Item {self.__item_name} not found for {self._get_player()}: {event}')
            return False, None
        assert isinstance(event, PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY)
        if self.__exact_name and event.item_name != self.__item_name:
            logger.warn(f'Found other item {event.item_name} for {self._get_player()}: {event}')
            return False, None
        logger.info(f'Found item {self.__item_name} for {self._get_player()} in bag {event.bag}, slot {event.slot}')
        return True, BagLocation(self._get_player(), event.bag, event.slot)

    def get_bag_location(self) -> Optional[BagLocation]:
        self._get_trigger().start_trigger()
        try:
            result = self._get_new_result()
            if not result:
                return None
            received, bag_location = result
            if not received:
                return None
        finally:
            self._get_trigger().cancel_trigger()
        return bag_location

    def get_all_bag_locations(self, approximate_count: int) -> List[BagLocation]:
        self._get_trigger().start_trigger()
        items: List[BagLocation] = []
        try:
            result = self._get_new_result()
            if not result:
                return []
            # wait a bit for more results to collect, because the program may be too busy to collect all events on time
            check_period = 0.25
            time_left = max(approximate_count, 1) * check_period + GAME_LAG
            logger.debug(f'get_all_bag_locations waits up to {time_left} to collect approx. {approximate_count} locations')
            while len(items) < approximate_count and time_left > 0.0:
                self._get_toolkit().sleep(check_period)
                time_left -= check_period
                for result in self.get_and_clear_last_results():
                    received, bag_location = result
                    if received:
                        items.append(bag_location)
        finally:
            self._get_trigger().cancel_trigger()
            return items


class ItemLootingCheckerProcedure(TriggerReaderProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        TriggerReaderProcedure.__init__(self, scripting, game_command=None)
        self._get_trigger().add_bus_event(PlayerInfoEvents.ITEM_RECEIVED(player=self._get_player()))

    def _get_object(self, event: PlayerInfoEvents.ITEM_RECEIVED) -> str:
        return event.item_name

    def get_item(self) -> Optional[str]:
        return self.get_last_result()

    def start_looting_tracking(self):
        logger.debug(f'start_looting_tracking')
        self._get_trigger().start_trigger()

    def stop_looting_tracking(self):
        logger.debug(f'stop_looting_tracking')
        self._get_trigger().cancel_trigger()


class ActionOnItemInBagProcedure(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)

    def find_item_in_bags(self, item_name: str, exact_name=True) -> Optional[BagLocation]:
        assert item_name
        bag_checker = BagItemCheckerProcedure(scripting=self._get_player_toolkit(), item_name=item_name, exact_name=exact_name)
        return bag_checker.get_bag_location()

    def find_menu(self, bag_loc: BagLocation, pattern: MatchPattern, attempts=5) -> Optional[str]:
        x, y = bag_loc.get_item_screen_coords()
        window_area = CaptureArea()
        menu_pattern_tag_id = None
        for _ in range(attempts):
            self._get_player_toolkit().try_close_all_access()
            # context menu does not pop reliably, this seems to be best combination
            self._get_player_toolkit().click_at(x, y, button='left')
            self._get_player_toolkit().click_at(x, y, button='right', delay=GAME_LAG * 2)
            result = self._get_player_toolkit().find_match_by_pattern(pattern, area=window_area, repeat=RepeatMode.DONT_REPEAT)
            if result is not None:
                menu_pattern_tag_id, _ = result
                break
        return menu_pattern_tag_id

    def toggle_bags(self):
        # dont use toolkit, script may be expired
        self._get_player().get_inputs().special.open_bags.call_action(self._get_player().get_client_id())

    def click_menu(self, bag_loc: BagLocation, pattern_tag: Resource, attempts=5) -> bool:
        if not self.find_menu(bag_loc, MatchPattern.by_tag(pattern_tag), attempts):
            logger.warn(f'Could not find menu pattern {pattern_tag}')
            return False
        if not self._get_player_toolkit().click_match(pattern_tag, repeat=RepeatMode.REPEAT_ON_SUCCESS):
            return False
        self._get_player_toolkit().move_mouse_to_middle()
        return True

    def find_item_and_click_menu(self, item_name: str, pattern_tag: Resource, attempts=5, exact_name=True) -> Optional[BagLocation]:
        bag_loc = self.find_item_in_bags(item_name=item_name, exact_name=exact_name)
        if not bag_loc:
            return None
        if not self.click_menu(bag_loc, pattern_tag, attempts):
            return None
        return bag_loc

    def open_bags_and_find_item_and_click_menu(self, item_name: str, pattern_tag: Resource, attempts=5, exact_name=True) -> bool:
        bag_loc = self.find_item_in_bags(item_name=item_name, exact_name=exact_name)
        if not bag_loc:
            return False
        try:
            self.toggle_bags()
            if not self.click_menu(bag_loc, pattern_tag, attempts):
                return False
        finally:
            self.toggle_bags()
        return True


class BagActionsProcedure(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)

    def __protect_from_actions(self, duration: float) -> Task:
        stop_casting = StopCastingFilter(self._get_player(), duration=duration)
        self._get_runtime().processor.run_filter(stop_casting)
        self._get_toolkit().sleep(PROCESSOR_TICK * 2)
        return stop_casting

    # noinspection PyMethodMayBeStatic
    def __use_one_item(self, _item_location: BagLocation) -> bool:
        return True

    def __destroy_one_item(self, _item_location: BagLocation) -> bool:
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_DESTROY, repeat=RepeatMode.REPEAT_ON_FAIL)
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_DESTROY, repeat=RepeatMode.REPEAT_ON_SUCCESS)
        return True

    def __handle_items_all_at_once(self, item_name: str, count: int, menu_tag: Resource,
                                   handler: Callable[[BagLocation], bool], exact_name: bool) -> int:
        handled_count = 0
        failed_count = 0
        # find all items
        bag_checker = BagItemCheckerProcedure(scripting=self._get_player_toolkit(), item_name=item_name, exact_name=exact_name)
        item_locations = bag_checker.get_all_bag_locations(approximate_count=count)
        logger.debug(f'Total locations for {item_name}: {len(item_locations)}, limit is {count}')
        # limit to a max of count
        item_locations = item_locations[:count]
        item_clicker = ActionOnItemInBagProcedure(self._get_player_toolkit())
        for item_loc in item_locations:
            logger.detail(f'{item_name}: check location {item_loc}')
            if item_clicker.click_menu(item_loc, menu_tag):
                handled = handler(item_loc)
                logger.debug(f'{item_name}, used {menu_tag.resource_name}, handle result {handled} in {item_loc} (all at once)')
                if handled:
                    handled_count += 1
            else:
                logger.warn(f'{item_name}, cloud not use {menu_tag.resource_name}, in {item_loc} (all at once)')
                failed_count += 1
                if failed_count > 2:
                    break
        return handled_count

    def __handle_items_one_by_one(self, item_name: str, count: int, menu_tag: Resource,
                                  handler: Callable[[BagLocation], bool], exact_name: bool) -> int:
        handled_count = 0
        failed_count = 0
        item_clicker = ActionOnItemInBagProcedure(scripting=self._get_player_toolkit())
        while True:
            item_loc = item_clicker.find_item_and_click_menu(item_name=item_name, pattern_tag=menu_tag, exact_name=exact_name)
            if item_loc:
                handled = handler(item_loc)
                logger.debug(f'{item_name}, used {menu_tag.resource_name}, handle result {handled} in {item_loc} (one by one)')
                if handled:
                    handled_count += 1
                if handled_count >= count:
                    break
            else:
                logger.warn(f'{item_name}, cloud not use {menu_tag.resource_name}, in {item_loc} (one by one)')
                failed_count += 1
                if failed_count > 2:
                    break
        return handled_count

    def __handle_items_in_bags(self, item_name: str, open_bags: bool, count: int, verb: str,
                               menu_tag: Resource, handler: Callable[[BagLocation], bool], exact_name: bool) -> int:
        logger.info(f'{verb} ({menu_tag.resource_name}) items: {item_name}, count: {count}, for {self._get_player()}')
        item_clicker = ActionOnItemInBagProcedure(self._get_player_toolkit())
        stop_casting = self.__protect_from_actions(5.0 + count * 5.0)
        if open_bags:
            item_clicker.toggle_bags()
        try:
            if count > 2:
                handled_count = self.__handle_items_all_at_once(item_name=item_name, count=count, menu_tag=menu_tag,
                                                                handler=handler, exact_name=exact_name)
            else:
                handled_count = self.__handle_items_one_by_one(item_name=item_name, count=count, menu_tag=menu_tag,
                                                               handler=handler, exact_name=exact_name)
            logger.debug(f'Total handled {item_name}: {handled_count}')
        finally:
            if open_bags:
                item_clicker.toggle_bags()
            stop_casting.expire()
        if not handled_count:
            logger.warn(f'Failed to {verb} {item_name} (x{count}) on {self._get_player()}')
        return handled_count

    def use_item_in_bags(self, item_name: str, open_bags: bool, count=1, exact_name=True) -> int:
        return self.__handle_items_in_bags(item_name=item_name, open_bags=open_bags, count=count, verb='use', exact_name=exact_name,
                                           menu_tag=ui_patterns.PATTERN_ITEM_MENU_USE, handler=self.__use_one_item)

    def destroy_item_in_bags(self, item_name: str, open_bags: bool, count=1, exact_name=True) -> int:
        return self.__handle_items_in_bags(item_name=item_name, open_bags=open_bags, count=count, verb='destroy', exact_name=exact_name,
                                           menu_tag=ui_patterns.PATTERN_ITEM_MENU_DESTROY, handler=self.__destroy_one_item)
