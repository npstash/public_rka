from __future__ import annotations

from typing import Optional, List, Tuple, Dict, Callable

from rka.components.resources import Resource
from rka.components.ui.capture import MatchPattern, CaptureArea, Rect, Offset, CaptureMode
from rka.components.ui.overlay import Severity
from rka.eq2.configs.master.overseer_missions import OverseerSeasons, OverseerMissionTier
from rka.eq2.configs.master.overseer_rewards import LOOT_BOX_ITEMNAME_PATTERNS, VALUABLE_RECIPE_ITEMNAME_PATTERNS, HARVESTABLES_ITEMNAME_PATTERNS, \
    CONSUMABLES_ITEMNAME_PATTERNS, DISPOSABLES_ITEMNAME_PATTERNS
from rka.eq2.configs.shared.game_constants import CURRENT_MAX_LEVEL, MAX_OVERSEER_CHARGED_MISSIONS, MAX_OVERSEER_MISSION_CHARGES, MAX_OVERSEER_DAILY_MISSIONS
from rka.eq2.configs.shared.rka_constants import CLICK_DELAY, SERVER_REACT_DELAY
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability.generated_abilities import CommonerAbilities, ArtisanAbilities
from rka.eq2.master.game.engine.task import Task
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.interfaces import TOptionalPlayer, IPlayerSelector
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus, HomeCityNames
from rka.eq2.master.game.scripting import RepeatMode, BagLocation
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptingFramework, PlayerScriptTask
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.patterns.overseer.bundle import overseer_patterns
from rka.eq2.master.game.scripting.patterns.overseer.traits.bundle import overseer_trait_patterns
from rka.eq2.master.game.scripting.procedures.items import ActionOnItemInBagProcedure, ItemLootingCheckerProcedure
from rka.eq2.master.game.scripting.procedures.tradeskill import ProcessOneItem, BuyFromMerchantProcedure
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.scripts.player_processing import ProcessingScriptFactory, ProcessPlayers
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit, Procedure
from rka.eq2.master.game.scripting.util.ts_script_utils import compare_normal_item_names
from rka.eq2.shared import Groups
from rka.eq2.shared.flags import MutableFlags

_trait_patterns = overseer_trait_patterns.list_resources()


class _Register:
    mission_filter_combomenus = list()
    mission_agent_combomenus = list()
    mission_tiers = list()


class _MissionFilter:
    def __init__(self, already_selected: Resource, dropdown: Resource):
        self.already_selected = already_selected
        self.dropdown = dropdown
        _Register.mission_filter_combomenus.append(already_selected)


class _MissionFilters:
    NoFilter = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_1, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_NOFILTER)
    Celestial = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_2, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_CELESTIAL)
    Fabled = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_3, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_FABLED)
    Legendary = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_4, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_LEGENDARY)
    Treasured = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_5, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_TREASURED)
    Completed = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_6, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_COMPLETED)
    Charged = _MissionFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_7, overseer_patterns.PATTERN_OVERSEER_FILTER_MISSIONS_CHARGED)


class _AgentFilter:
    def __init__(self, already_selected: Resource, dropdown: Resource):
        self.already_selected = already_selected
        self.dropdown = dropdown
        _Register.mission_agent_combomenus.append(already_selected)


class _AgentFilters:
    NoFilter = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_1, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_NOFILTER)
    Available = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_2, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_AVAILABLE)
    AvailableByRarity = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_3, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_AVAILABLEBYRARITY)
    OnAdventure = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_4, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_ONADVENTURE)
    OnCooldown = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_5, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_ONCOOLDOWN)
    Mishap = _AgentFilter(overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_6, overseer_patterns.PATTERN_OVERSEER_FILTER_AGENTS_MISHAP)


class _MissionTier:
    def __init__(self, tier_name: str, mission_filter: _MissionFilter):
        self.tier_name = tier_name
        self.mission_filter = mission_filter
        _Register.mission_tiers.append(self)

    def __str__(self) -> str:
        return f'Mission tier: {self.tier_name}'


class _MissionTiers:
    Celestial = _MissionTier('Celestial', _MissionFilters.Celestial)
    Fabled = _MissionTier('Fabled', _MissionFilters.Fabled)
    Legendary = _MissionTier('Legendary', _MissionFilters.Legendary)
    Treasured = _MissionTier('Treasured', _MissionFilters.Treasured)


_mission_time_patterns_by_tier = {
    _MissionTiers.Treasured: [
        overseer_patterns.PATTERN_OVERSEER_MISSION_30MIN,
        overseer_patterns.PATTERN_OVERSEER_MISSION_1H,
        overseer_patterns.PATTERN_OVERSEER_MISSION_1H30MIN,
        overseer_patterns.PATTERN_OVERSEER_MISSION_2H,
    ],
    _MissionTiers.Legendary: [
        overseer_patterns.PATTERN_OVERSEER_MISSION_2H30MIN,
        overseer_patterns.PATTERN_OVERSEER_MISSION_3H30MIN,
        overseer_patterns.PATTERN_OVERSEER_MISSION_5H,
        overseer_patterns.PATTERN_OVERSEER_MISSION_1D,
    ],
    _MissionTiers.Fabled: [
        overseer_patterns.PATTERN_OVERSEER_MISSION_10H,
    ],
    _MissionTiers.Celestial: [
        overseer_patterns.PATTERN_OVERSEER_MISSION_15H,
        overseer_patterns.PATTERN_OVERSEER_MISSION_1D6H,
    ],
}


class _OverseerWindowControl(Procedure):
    @staticmethod
    def __get_overseer_window_title_rect(scripting: PlayerScriptingToolkit) -> Optional[Rect]:
        window_area = CaptureArea()
        for _ in range(5):
            result = scripting.find_match_by_tag(pattern_tag=overseer_patterns.PATTERN_OVERSEER_WINDOW_TITLE,
                                                 area=window_area, repeat=RepeatMode.DONT_REPEAT)
            if result:
                return result
            scripting.sleep(1.0)
        return None

    @staticmethod
    def open_overseers(psf: PlayerScriptingFramework) -> Optional[_OverseerWindowControl]:
        psf.try_close_all_windows()
        action = psf.build_command('toggleoverseer')
        psf.call_player_action(action, delay=SERVER_REACT_DELAY)
        overseer_title_rect = _OverseerWindowControl.__get_overseer_window_title_rect(psf)
        if not overseer_title_rect:
            return None
        overseer_window_rect = Rect(x1=overseer_title_rect.x1, y1=overseer_title_rect.y1,
                                    x2=overseer_title_rect.x1 + (941 - 119), y2=overseer_title_rect.y1 + (735 - 146))
        return _OverseerWindowControl(overseer_window_rect, psf)

    def __init__(self, overseer_window_rect: Rect, psf: PlayerScriptingFramework):
        Procedure.__init__(self, psf)
        self.overseer_window_rect = overseer_window_rect
        window_area = CaptureArea(mode=CaptureMode.COLOR)
        self.overseer_window_area = window_area.capture_rect(overseer_window_rect, relative=True)
        self.psf = psf

    def __filter_list(self, required: Resource, dropdown: Resource, all_combomenu_tags: List[Resource], dropdown_offset_x: int) -> bool:
        if self._get_player_toolkit().find_match_by_tag(pattern_tag=required, area=self.overseer_window_area, repeat=RepeatMode.DONT_REPEAT):
            # already selected
            return True
        match_any_combobox = MatchPattern.by_tags(all_combomenu_tags)
        attempts = 5
        # use low threshold due to partial transparency of drop down menu items
        min_threshold = 0.5
        max_threshold = 0.9
        current_threshold = max_threshold
        for attempt in range(attempts):
            self.psf.move_mouse_to_middle()
            self._get_player_toolkit().assert_click_match(pattern=match_any_combobox, area=self.overseer_window_area,
                                                          threshold=0.9, repeat=RepeatMode.REPEAT_ON_FAIL)
            # offset is required to move the cursor away from agent traits
            offset = Offset(x=dropdown_offset_x, y=3, anchor=Offset.REL_FIND_MID)
            if not self._get_player_toolkit().click_match(pattern=dropdown, repeat=RepeatMode.DONT_REPEAT, threshold=current_threshold,
                                                          area=self.overseer_window_area, click_offset=offset):
                current_threshold -= (max_threshold - min_threshold) / attempts
                continue
            if self._get_player_toolkit().find_match_by_tag(pattern_tag=required, area=self.overseer_window_area, repeat=RepeatMode.DONT_REPEAT):
                break
            if attempt == attempts:
                logger.warn(f'Failed to filter list for {required}, attempt limit reached')
                return False
        # let results update on the screen - mission timers take some time to update
        self._get_player_toolkit().sleep(2.0)
        return True

    def __scroll_to_top(self, scrollup_area: Resource, scrollup_max: Resource) -> bool:
        self._get_player_toolkit().move_mouse_to_middle()
        scrollup_rect = self._get_player_toolkit().find_match_by_tag(pattern_tag=scrollup_area, repeat=RepeatMode.DONT_REPEAT,
                                                                     area=self.overseer_window_area)
        if not scrollup_rect:
            logger.warn(f'Could not find scroll area {scrollup_area}')
            return False
        scrollup_area = self.overseer_window_area.capture_rect(scrollup_rect, relative=True)
        max_attempts = 20
        for _ in range(max_attempts):
            if self._get_player_toolkit().find_match_by_tag(pattern_tag=scrollup_max, repeat=RepeatMode.DONT_REPEAT,
                                                            area=self.overseer_window_area, threshold=0.95):
                return True
            self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_GFX_SCROLLUP, repeat=RepeatMode.DONT_REPEAT,
                                                   area=scrollup_area, max_clicks=5, delay=0.0)
        return False

    def __scroll_down(self, scrolldown_area: Resource, scrolldown_max: Resource) -> bool:
        max_scrolled = self._get_player_toolkit().find_match_by_tag(pattern_tag=scrolldown_max, repeat=RepeatMode.DONT_REPEAT,
                                                                    area=self.overseer_window_area, threshold=0.95)
        if max_scrolled:
            return False
        scrolldown_rect = self._get_player_toolkit().assert_find_match_by_tag(pattern_tag=scrolldown_area, repeat=RepeatMode.DONT_REPEAT,
                                                                              area=self.overseer_window_area)
        scrolldown_area = self.overseer_window_area.capture_rect(scrolldown_rect, relative=True)
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_GFX_SCROLLDOWN, repeat=RepeatMode.DONT_REPEAT,
                                               area=scrolldown_area, max_clicks=3, delay=0.0)
        return True

    def __scroll_agents_to_top(self):
        self.__scroll_to_top(overseer_patterns.PATTERN_OVERSEER_AGENTS_SCROLLUP_AREA, overseer_patterns.PATTERN_OVERSEER_AGENTS_SCROLLUP_MAX)

    def __scroll_missions_to_top(self):
        self.__scroll_to_top(overseer_patterns.PATTERN_OVERSEER_MISSIONS_SCROLLUP_AREA, overseer_patterns.PATTERN_OVERSEER_MISSIONS_SCROLLUP_MAX)

    def scroll_agents_down(self) -> bool:
        return self.__scroll_down(overseer_patterns.PATTERN_OVERSEER_AGENTS_SCROLLDOWN_AREA, overseer_patterns.PATTERN_OVERSEER_AGENTS_SCROLLDOWN_MAX)

    def scroll_missions_down(self) -> bool:
        return self.__scroll_down(overseer_patterns.PATTERN_OVERSEER_MISSIONS_SCROLLDOWN_AREA, overseer_patterns.PATTERN_OVERSEER_MISSIONS_SCROLLDOWN_MAX)

    def filter_missions(self, mission_filter: _MissionFilter) -> bool:
        if not self.__filter_list(mission_filter.already_selected, mission_filter.dropdown, _Register.mission_filter_combomenus, 0):
            return False
        self.__scroll_missions_to_top()
        return True

    def filter_agents(self, agent_filter: _AgentFilter) -> bool:
        if not self.__filter_list(agent_filter.already_selected, agent_filter.dropdown, _Register.mission_agent_combomenus, 70):
            return False
        self.__scroll_agents_to_top()
        return True


class _RewardHandler(Procedure):
    @staticmethod
    def match_item_from_list(loot: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if pattern in loot:
                return True
        return False

    def __init__(self, psf: PlayerScriptingFramework):
        Procedure.__init__(self, psf)
        self.psf = psf
        self.item_clicker = ActionOnItemInBagProcedure(self._get_player_toolkit())

    def __handle_package(self, loot: str, _bag_loc: BagLocation) -> Tuple[bool, bool]:
        if _RewardHandler.match_item_from_list(loot, LOOT_BOX_ITEMNAME_PATTERNS):
            self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_ITEM_MENU_UNPACK, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY)
            self.psf.try_click_accepts(click_delay=SERVER_REACT_DELAY)
        else:
            msg = f'Unknown loot box found: {loot} on {self.psf.get_player()}'
            self._get_runtime().notification_service.post_notification(msg)
        return False, False

    def __handle_book(self, _loot: str, _bag_loc: BagLocation) -> Tuple[bool, bool]:
        # try to scribe
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_ITEM_MENU_SCRIBE, repeat=RepeatMode.DONT_REPEAT)
        # will be destroyed if not scribed
        return True, False

    def __handle_agent(self, _loot: str, bag_loc: BagLocation) -> Tuple[bool, bool]:
        try_add_agent = MutableFlags.OVERSEER_ADD_AGENTS.__bool__()
        try_convert_agent = MutableFlags.OVERSEER_CONVERT_AGENTS.__bool__()
        if try_add_agent:
            if self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_ITEM_MENU_ADDTOCOLLECTION, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY):
                if self.psf.try_click_accepts(click_delay=SERVER_REACT_DELAY):
                    # agent is added
                    return False, False
        if try_convert_agent:
            if self.item_clicker.click_menu(bag_loc, pattern_tag=ui_patterns.PATTERN_ITEM_MENU_CONVERTAGENT, attempts=2):
                if self.psf.try_click_accepts(click_delay=SERVER_REACT_DELAY):
                    return False, False
        if self.psf.get_player().get_player_info().keep_overseers_for_alt:
            return False, False
        return True, False

    # noinspection PyMethodMayBeStatic
    def __handle_equipment(self, _loot: str, _bag_loc: BagLocation) -> Tuple[bool, bool]:
        return False, True

    def __handle_item_by_context_menu(self, loot: str, bag_loc: BagLocation) -> Tuple[bool, bool]:
        item_handlers: Dict[str, Callable[[str, BagLocation], Tuple[bool, bool]]] = {
            ui_patterns.PATTERN_ITEM_MENU_UNPACK.resource_id: self.__handle_package,
            ui_patterns.PATTERN_ITEM_MENU_SCRIBE.resource_id: self.__handle_book,
            ui_patterns.PATTERN_ITEM_MENU_CONVERTAGENT.resource_id: self.__handle_agent,
            ui_patterns.PATTERN_ITEM_MENU_EQUIP.resource_id: self.__handle_equipment,
        }
        all_patterns = MatchPattern.by_tags(list(item_handlers.keys()))
        tag_id_found = self.item_clicker.find_menu(bag_loc, pattern=all_patterns, attempts=3)
        if not tag_id_found:
            return False, False
        handler_fn = item_handlers[tag_id_found]
        return handler_fn(loot, bag_loc)

    @staticmethod
    def __is_overseer_mission_token(item_name: str) -> bool:
        item_name = item_name.lower()
        for season in OverseerSeasons.__members__.values():
            for mission in season.value.all_missions:
                if compare_normal_item_names(item_name, mission):
                    return True
        return False

    def handle_loot(self, loot_list: List[str]):
        if not loot_list:
            return
        bags_opened = False
        overall_level = lvl if (lvl := self._get_player().get_level(GameClasses.Commoner)) else 1
        crafter_level = lvl if (lvl := self._get_player().get_level(GameClasses.Artisan)) else 1
        if MutableFlags.OVERSEER_LOOT_ALLOW_TRANSMUTE and overall_level >= CURRENT_MAX_LEVEL:
            conversion_ability = CommonerAbilities.transmute
        elif MutableFlags.OVERSEER_LOOT_ALLOW_SALVAGE and crafter_level >= 100:
            conversion_ability = ArtisanAbilities.salvage
        else:
            conversion_ability = None
        item_disposer = ProcessOneItem(self._get_player_toolkit(), conversion_ability) if conversion_ability else None
        looting_checker = ItemLootingCheckerProcedure(self._get_player_toolkit())
        looting_checker.start_looting_tracking()
        try:
            while loot_list:
                loot = loot_list.pop()
                # ignore consumables and harvestables - should be stacked in dedicated bags
                if _RewardHandler.match_item_from_list(loot, CONSUMABLES_ITEMNAME_PATTERNS):
                    continue
                if _RewardHandler.match_item_from_list(loot, HARVESTABLES_ITEMNAME_PATTERNS):
                    continue
                if _RewardHandler.match_item_from_list(loot, VALUABLE_RECIPE_ITEMNAME_PATTERNS):
                    msg = f'Valuable recipe found: {loot} on {self.psf.get_player()}'
                    self._get_runtime().notification_service.post_notification(msg)
                    continue
                bag_loc = self.item_clicker.find_item_in_bags(loot)
                if not bag_loc:
                    logger.warn(f'Item {loot} not found in {self._get_player()} bags')
                    continue
                # only 1st bag is supported for safety (to not destroy something in other bags)
                if bag_loc.bag_n != 1:
                    logger.debug(f'Item {loot} not in first bag of {self._get_player()}')
                    continue
                if not bags_opened:
                    self._get_player_toolkit().try_close_all_windows()
                    self.item_clicker.toggle_bags()
                    bags_opened = True
                convert_this_loot = False
                if _RewardHandler.__is_overseer_mission_token(loot):
                    self.psf.use_item_in_bags(loot, open_bags=False)
                    continue
                # check name patterns for items that are always to be destroyed
                if _RewardHandler.match_item_from_list(loot, DISPOSABLES_ITEMNAME_PATTERNS):
                    destroy_this_loot = True
                else:
                    # right click the item and detect its type by contents of its context menu
                    destroy_this_loot, convert_this_loot = self.__handle_item_by_context_menu(loot, bag_loc)
                    logger.debug(f'Handle item {loot} for {self._get_player()}: destory={destroy_this_loot}, scrap={convert_this_loot}')
                # for items means to be salvaged or transmuted
                if convert_this_loot and not destroy_this_loot:
                    if item_disposer:
                        if not item_disposer.process_one_item(bag_loc):
                            # cloud not convert, destroy anyway
                            destroy_this_loot = True
                    else:
                        # no conditions to convert, destroy it
                        destroy_this_loot = True
                if destroy_this_loot:
                    self.psf.destroy_item_in_bags(loot, open_bags=False)
                looted_items = looting_checker.get_last_results()
                looting_checker.clear_last_results()
                loot_list.extend(looted_items)
        finally:
            if bags_opened:
                self.item_clicker.toggle_bags()
            looting_checker.stop_looting_tracking()


class _OverseerMissionManager(Procedure):
    def __init__(self, overseer_window: _OverseerWindowControl):
        Procedure.__init__(self, overseer_window._get_player_toolkit())
        self.overseer_window = overseer_window
        self.overseer_window_area = overseer_window.overseer_window_area
        self.overseer_window_rect = overseer_window.overseer_window_rect
        self.all_rewards = []
        self.started_missions = []
        self.completed_missions = []
        self.psf = overseer_window.psf

    def __accept_rewards(self) -> bool:
        looting_checker = ItemLootingCheckerProcedure(self._get_player_toolkit())
        looting_checker.start_looting_tracking()
        # wait for rewards to show up
        self._get_player_toolkit().sleep(1.5)
        self._get_player_toolkit().move_mouse_to_middle()
        self._get_player_toolkit().try_click_accepts(max_clicks=10, click_delay=SERVER_REACT_DELAY)
        self._get_player_toolkit().sleep(0.5)
        looting_checker.stop_looting_tracking()
        looted_items = looting_checker.get_last_results()
        if not looted_items:
            return False
        self.all_rewards += looted_items
        return True

    def __get_mission_title(self, y: int, height: int) -> Optional[str]:
        # if mission was selected by clicking a "time to complete", the bottom of the text could get truncated
        height = max(height, 20)
        mission_title_rect = Rect(x1=self.overseer_window_rect.x1 + (340 - 123), y1=y,
                                  x2=self.overseer_window_rect.x1 + (675 - 123), h=height)
        mission_title = self._get_player_toolkit().ocr_normal_line_of_text(mission_title_rect)
        if not mission_title:
            mission_title = '<unknown>'
        return mission_title

    def __get_charges_left(self, y: int, height: int) -> Optional[int]:
        height = max(height, 20)
        charges_rect = Rect(x1=self.overseer_window_rect.x1 + (689 - 123), y1=y,
                            x2=self.overseer_window_rect.x1 + (733 - 123), h=height)
        charges = self._get_player_toolkit().ocr_normal_line_of_text(charges_rect)
        if not charges or not charges.isnumeric():
            return None
        return int(charges)

    def __select_mission_on_list(self, label_pattern: MatchPattern) -> Tuple[Optional[str], Optional[int]]:
        max_attepmts = 30
        matched_label_rect = None
        matched_label_tag = None
        for _ in range(max_attepmts):
            result = self._get_player_toolkit().find_match_by_pattern(pattern=label_pattern, area=self.overseer_window_area,
                                                                      repeat=RepeatMode.DONT_REPEAT, threshold=0.95)
            if result:
                matched_label_tag, matched_label_rect = result
                break
            scrolled = self.overseer_window.scroll_missions_down()
            if not scrolled:
                return None, None
        if not matched_label_rect:
            return None, None
        matched_label_area = self.overseer_window_area.capture_rect(matched_label_rect, relative=True)
        mission_title = self.__get_mission_title(matched_label_rect.y1, matched_label_rect.height())
        charges_left = self.__get_charges_left(matched_label_rect.y1, matched_label_rect.height())
        self._get_player_toolkit().click_match(pattern=MatchPattern.by_tag(matched_label_tag), repeat=RepeatMode.REPEAT_ON_FAIL,
                                               area=matched_label_area, threshold=0.0, delay=CLICK_DELAY)
        return mission_title, charges_left

    def __click_mission_start(self) -> bool:
        # add delay to let mission list update
        return self._get_player_toolkit().click_match(pattern=overseer_patterns.PATTERN_OVERSEER_START_MISSION, area=self.overseer_window_area,
                                                      repeat=RepeatMode.DONT_REPEAT, delay=2.0)

    def __click_mission_complete(self) -> bool:
        # add delay to let mission list update
        return self._get_player_toolkit().click_match(pattern=overseer_patterns.PATTERN_OVERSEER_COMPLETE_MISSION, area=self.overseer_window_area,
                                                      repeat=RepeatMode.DONT_REPEAT, delay=2.0)

    def complete_any_mission_on_list(self) -> Tuple[Optional[str], Optional[int]]:
        for attempt in range(10):
            pattern_completed = MatchPattern.by_tags([overseer_patterns.PATTERN_OVERSEER_MISSION_COMPLETED,
                                                      overseer_patterns.PATTERN_OVERSEER_MISSION_COMPLETED_SELECTED])
            mission_title, charges_left = self.__select_mission_on_list(pattern_completed)
            if not mission_title:
                return None, None
            if mission_title in self.completed_missions:
                # wait for mission timers to update and find another mission
                self.psf.sleep(1.0)
                continue
            # add delay to let mission list update
            if not self.__click_mission_complete():
                logger.warn(f'failed to complete a click complete mission: {mission_title}')
                self.psf.sleep(1.0)
                continue
            self.completed_missions.append(mission_title)
            if not self.__accept_rewards():
                logger.warn(f'completed mission {mission_title} did not return any rewards')
            return mission_title, charges_left
        logger.warn(f'failed to complete a new mission: {self.completed_missions}')
        return None, None

    # mission_title, charges_left, agents_failed
    def start_any_mission_on_list(self, charged: bool, agents: _OverseerAgentManager, tiers: List[_MissionTier]) -> Tuple[Optional[str], Optional[int], bool]:
        if not charged and self.is_zero_daily_missions_left():
            return None, None, False
        mission_time_patterns = []
        for tier in tiers:
            mission_time_patterns += _mission_time_patterns_by_tier[tier]
        pattern_mission_time = MatchPattern.by_tags(mission_time_patterns)
        for attempt in range(10):
            mission_title, charges_left = self.__select_mission_on_list(pattern_mission_time)
            if not mission_title:
                return None, None, False
            if mission_title in self.started_missions:
                # wait for mission list to update and try another one
                self.psf.sleep(1.0)
                continue
            if self.is_heritage_mission(mission_title):
                added = agents.add_any_agents_to_selected_mission(mission_title)
            else:
                added = agents.add_best_agents_to_selected_mission(mission_title)
            if added is None:
                # wait for mission list to update and try another one
                self.psf.sleep(1.0)
                continue
            if not added:
                # more more agents?
                return None, None, True
            if not self.__click_mission_start():
                logger.warn(f'Could not click to start mission {mission_title}')
                self.psf.sleep(1.0)
                continue
            self.started_missions.append(mission_title)
            return mission_title, charges_left, False
        logger.warn(f'Failed not start any mission; started so far: {self.started_missions}')
        return None, None, False

    def is_missions_list_empty(self) -> bool:
        result = self._get_player_toolkit().find_match_by_tag(pattern_tag=overseer_patterns.PATTERN_OVERSEER_NO_MISSIONS_AVAILABLE,
                                                              repeat=RepeatMode.DONT_REPEAT, threshold=0.95,
                                                              area=self.overseer_window_area)
        return result is not None

    def is_zero_daily_missions_left(self) -> bool:
        result = self._get_player_toolkit().find_match_by_tag(pattern_tag=overseer_patterns.PATTERN_OVERSEER_0_MISSIONS,
                                                              repeat=RepeatMode.DONT_REPEAT, threshold=0.95,
                                                              area=self.overseer_window_area)
        return result is not None

    # noinspection PyMethodMayBeStatic
    def is_heritage_mission(self, mission_title: str) -> bool:
        if not mission_title:
            return False
        return 'heritage hunt' in mission_title.lower()


class _OverseerAgentManager(Procedure):
    def __init__(self, overseer_window: _OverseerWindowControl):
        Procedure.__init__(self, overseer_window._get_player_toolkit())
        self.overseer_window = overseer_window
        self.overseer_window_area = overseer_window.overseer_window_area
        self.overseer_window_rect = overseer_window.overseer_window_rect
        self.psf = overseer_window.psf
        self.agents_filtered = False

    def __click_agent_on_list(self, agent_num: int) -> bool:
        agent_x = self.overseer_window_rect.x1 + 80
        agent_y = self.overseer_window_rect.y1 + 92 + (agent_num * 50)
        action = action_factory.new_action().mouse(x=agent_x, y=agent_y, button=None).double_click()
        if not self._get_player_toolkit().player_bool_action(action, delay=CLICK_DELAY):
            logger.warn(f'failed double click agent {agent_num}')
            return False
        return True

    def __is_any_agent_on_the_list(self) -> bool:
        result = self._get_player_toolkit().find_match_by_tag(pattern_tag=overseer_patterns.PATTERN_OVERSEER_NO_AGENTS_AVAILABLE,
                                                              repeat=RepeatMode.DONT_REPEAT, area=self.overseer_window_area, threshold=0.95)
        return result is None

    def __get_required_agent_count(self) -> Optional[int]:
        patterns = [overseer_patterns.PATTERN_OVERSEER_MISSION_AGENTS_REQUIRED_1.resource_id,
                    overseer_patterns.PATTERN_OVERSEER_MISSION_AGENTS_REQUIRED_2.resource_id,
                    overseer_patterns.PATTERN_OVERSEER_MISSION_AGENTS_REQUIRED_3.resource_id,
                    overseer_patterns.PATTERN_OVERSEER_MISSION_AGENTS_REQUIRED_4.resource_id,
                    ]
        agent_count_match = self._get_player_toolkit().find_match_by_pattern(pattern=MatchPattern.by_tags(patterns), repeat=RepeatMode.DONT_REPEAT,
                                                                             area=self.overseer_window_area)
        if not agent_count_match:
            logger.warn(f'could not determine required agent count')
            return None
        tag, _ = agent_count_match
        return patterns.index(tag) + 1

    def __get_required_agent_tag_ids(self) -> Tuple[List[str], CaptureArea]:
        agent_trait_rect = Rect(x1=self.overseer_window_rect.x1 + (791 - 414), y1=self.overseer_window_rect.y1 + (618 - 284),
                                x2=self.overseer_window_rect.x1 + (1034 - 414), y2=self.overseer_window_rect.y1 + (647 - 284))
        agent_trait_area = self.overseer_window_area.capture_rect(agent_trait_rect, relative=True)
        tags_rects = self._get_player_toolkit().find_multiple_match_by_pattern(pattern=MatchPattern.by_tags(_trait_patterns), area=agent_trait_area,
                                                                               threshold=0.99, repeat=RepeatMode.DONT_REPEAT)
        matched_tag_ids = [tag_id for tag_id, rect in tags_rects]
        return matched_tag_ids, agent_trait_area

    def __clear_agent_search_area(self) -> bool:
        if not self._get_player_toolkit().click_match(pattern=overseer_patterns.PATTERN_OVERSEER_AGENT_SEARCH_CLEAR, repeat=RepeatMode.DONT_REPEAT,
                                                      area=self.overseer_window_area):
            logger.warn('failed to click agent search area')
            return False
        self.agents_filtered = False
        return True

    def __get_empty_agent_slot_count(self) -> int:
        pattern = MatchPattern.by_tag(overseer_patterns.PATTERN_OVERSEER_EMPTY_AGENT_SLOT)
        result = self._get_player_toolkit().find_multiple_match_by_pattern(pattern=pattern, repeat=RepeatMode.DONT_REPEAT,
                                                                           threshold=0.95, area=self.overseer_window_area)
        return len(result)

    def __validate_agents_to_add(self, mission_title: str) -> Optional[Tuple[int, int]]:
        required_agents = self.__get_required_agent_count()
        if not required_agents:
            logger.warn(f'no agents required? {mission_title}')
            return None
        empty_slots = self.__get_empty_agent_slot_count()
        if required_agents > empty_slots:
            logger.warn(f'not enough ({required_agents} > {empty_slots}) empty slots? {mission_title}')
            return None
        return required_agents, empty_slots

    def __fill_with_any_agents(self, mission_title: str, total_slots: int, required_agents: int) -> bool:
        empty_slots_remaining = self.__get_empty_agent_slot_count()
        added_agents = total_slots - empty_slots_remaining
        if added_agents < required_agents:
            if self.agents_filtered:
                self.__clear_agent_search_area()
            if not self.__is_any_agent_on_the_list():
                # no agents at all remain
                logger.warn(f'no agents remain for {mission_title}')
                return False
            min_agents_to_add = required_agents - added_agents
            # 9 is the max amount of agents in the list
            for agent_num_on_the_list in range(9):
                if agent_num_on_the_list >= min_agents_to_add:
                    # now check again, in case there was simply not enough any agents or it duplicated
                    empty_slots_remaining = self.__get_empty_agent_slot_count()
                    added_agents = total_slots - empty_slots_remaining
                    if added_agents >= required_agents:
                        break
                if not self.__click_agent_on_list(agent_num_on_the_list):
                    logger.warn(f'failed to click {agent_num_on_the_list}th agent for {mission_title} from list')
                    return False
            empty_slots_remaining = self.__get_empty_agent_slot_count()
            added_agents = total_slots - empty_slots_remaining
            if added_agents < required_agents:
                logger.warn(f'failed to add enough agents to {mission_title}, still need {required_agents - added_agents}')
                return False
        return True

    def add_any_agents_to_selected_mission(self, mission_title: str) -> Optional[bool]:
        validation_result = self.__validate_agents_to_add(mission_title)
        if not validation_result:
            # ignore this mission
            logger.warn('add_any_agents_to_selected_mission: could not determine required agents')
            return None
        required_agents, empty_slots = validation_result
        return self.__fill_with_any_agents(mission_title, empty_slots, required_agents)

    def add_best_agents_to_selected_mission(self, mission_title: str) -> Optional[bool]:
        validation_result = self.__validate_agents_to_add(mission_title)
        if not validation_result:
            # ignore this mission
            logger.warn('add_best_agents_to_selected_mission: could not determine required agents')
            return None
        required_agents, empty_slots = validation_result
        added_agents = 0
        agent_trait_tag_ids, agent_trait_area = self.__get_required_agent_tag_ids()
        for agent_trait_tag_id in agent_trait_tag_ids:
            agent_trait_tag = MatchPattern.by_tag(agent_trait_tag_id)
            self._get_player_toolkit().click_match(pattern=agent_trait_tag, area=agent_trait_area, repeat=RepeatMode.DONT_REPEAT, threshold=0.0)
            self.agents_filtered = True
            if not self.__is_any_agent_on_the_list():
                # try another
                continue
            if not self.__click_agent_on_list(0):
                logger.warn(f'failed to click first agent for {mission_title}')
                return False
            added_agents += 1
            if added_agents >= empty_slots:
                break
        # must check how many agents have been really added - some agents could have been clicked twice (2 traits)
        return self.__fill_with_any_agents(mission_title, empty_slots, required_agents)


class _OverseerManager(Procedure):
    def __init__(self, overseer_window: _OverseerWindowControl):
        Procedure.__init__(self, overseer_window._get_player_toolkit())
        self.overseer_window = overseer_window
        self.charged_missions_with_no_charges_left = 0
        self.overseer_missions = _OverseerMissionManager(overseer_window)
        self.overseer_agents = _OverseerAgentManager(overseer_window)
        self.psf = overseer_window.psf

    def __need_recharge(self, mission_title: str, charges_left: Optional[int]) -> bool:
        if charges_left is None:
            return False
        if charges_left == 0 and not self.overseer_missions.is_heritage_mission(mission_title):
            return True
        return False

    def complete_all_missions(self) -> bool:
        self._get_player_toolkit().try_close_all_access()
        if not self.overseer_window.filter_missions(_MissionFilters.Completed):
            return False
        for _ in range(MAX_OVERSEER_CHARGED_MISSIONS + MAX_OVERSEER_DAILY_MISSIONS):
            mission_title, charges_left = self.overseer_missions.complete_any_mission_on_list()
            if mission_title is None:
                break
            if self.__need_recharge(mission_title, charges_left):
                self.charged_missions_with_no_charges_left += 1
            self._get_runtime().overlay.log_event(f'{self._get_player()} completed overseer {mission_title.strip()}', Severity.Low)
        return True

    # returns (1) True if there is still daily allowance for missions, (2) number of started missions
    def start_normal_missions_at_tier(self, tier: _MissionTier) -> Tuple[bool, int]:
        self._get_player_toolkit().try_close_all_access()
        if self.overseer_missions.is_zero_daily_missions_left():
            return False, 0
        if not self.overseer_window.filter_missions(tier.mission_filter):
            return False, 0
        if not self.overseer_window.filter_agents(_AgentFilters.Available):
            return False, 0
        started_missions = 0
        for _ in range(MAX_OVERSEER_DAILY_MISSIONS):
            mission_title, _, agents_fail = self.overseer_missions.start_any_mission_on_list(charged=False, agents=self.overseer_agents, tiers=[tier])
            if agents_fail:
                return False, started_missions
            if mission_title is None:
                break
            self._get_runtime().overlay.log_event(f'{self._get_player()} started overseer {mission_title}', Severity.Low)
            started_missions += 1
        return not self.overseer_missions.is_zero_daily_missions_left(), started_missions

    def start_all_normal_missions(self):
        total_started_missions = 0
        for tier in [_MissionTiers.Celestial, _MissionTiers.Fabled, _MissionTiers.Legendary]:
            remaining_allowance, started_missions = self.start_normal_missions_at_tier(tier)
            total_started_missions += started_missions
            if not remaining_allowance:
                return
        if total_started_missions < 5:
            # dont do Treasured missions if at least 5 other missions had been already completed
            # to prevent accumulating treasured rewards on characters that dont really need to run Treasured missions
            self.start_normal_missions_at_tier(_MissionTiers.Treasured)

    def start_all_charged_missions(self) -> bool:
        self._get_player_toolkit().try_close_all_access()
        if not self.overseer_window.filter_missions(_MissionFilters.Charged):
            return False
        if self.overseer_missions.is_missions_list_empty():
            self.charged_missions_with_no_charges_left = max(1, self.charged_missions_with_no_charges_left)
            return True
        try:
            if not self.overseer_window.filter_agents(_AgentFilters.Available):
                return False
        except AssertionError as e:
            raise e
        tiers = [_MissionTiers.Celestial, _MissionTiers.Fabled, _MissionTiers.Legendary, _MissionTiers.Treasured]
        for _ in range(MAX_OVERSEER_CHARGED_MISSIONS):
            title, charges, agents_fail = self.overseer_missions.start_any_mission_on_list(charged=True, agents=self.overseer_agents, tiers=tiers)
            if agents_fail:
                return False
            if title is None:
                break
            if self.__need_recharge(title, charges):
                self.charged_missions_with_no_charges_left += 1
            self._get_runtime().overlay.log_event(f'{self._get_player()} started overseer {title}', Severity.Low)
        return True

    def handle_rewards(self):
        reward_handler = _RewardHandler(self.psf)
        reward_handler.handle_loot(self.overseer_missions.all_rewards)


class AFKOverseers(PlayerScriptTask):
    def __init__(self, overseer_player: TOptionalPlayer = None):
        PlayerScriptTask.__init__(self, f'AFK overseers for {overseer_player}', -1.0)
        self.overseer_player = overseer_player

    def _run_player(self, psf: PlayerScriptingFramework):
        overseer_window = _OverseerWindowControl.open_overseers(psf)
        if overseer_window:
            overseers = _OverseerManager(overseer_window)
            overseers.complete_all_missions()
            overseers.start_all_charged_missions()
            overseers.start_all_normal_missions()
            psf.try_close_all_windows()
            overseers.handle_rewards()
            if overseers.charged_missions_with_no_charges_left > 3:
                msg = f'Player {psf.get_player()} needs to restock charged quests'
                psf.get_runtime().overlay.log_event(msg, Severity.High)
                psf.get_runtime().tts.say(msg)
        else:
            logger.warn(f'Player {self.overseer_player} could not open overseer window')

    @staticmethod
    def expire_ooz_scripts(runtime: IRuntime):
        def add_scripts_to_list(task: Task):
            from rka.eq2.master.game.scripting.scripts.ooz_control_scripts import OOZAutoCombat, EnableOOZCombat
            if isinstance(task, OOZAutoCombat) or isinstance(task, EnableOOZCombat):
                task.expire()

        runtime.processor.visit_tasks(add_scripts_to_list)

    def _run(self, runtime: IRuntime):
        AFKOverseers.expire_ooz_scripts(runtime)
        self.overseer_player = self.resolve_player(self.overseer_player)
        self._run_player(self.get_player_scripting_framework(self.overseer_player))


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Do overseer missions (selected player)')
class AFKOverseersSelectedPlayer(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self, player: TOptionalPlayer = None):
        ProcessPlayers.__init__(self, f'Overseers: {player}', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__(), max_running_players=1)
        self.player = player

    def resolve_players(self) -> List[IPlayer]:
        if not self.player:
            self.player = self._resolve_best_player_by_overlay_id(lambda player_: player_.get_player_info().run_overseer_missions)
        return [self.player] if self.player else []

    def create_script(self, player: IPlayer) -> ScriptTask:
        return AFKOverseers(player)


@GameScriptManager.register_game_script([ScriptCategory.OVERSEERS, ScriptCategory.QUICKSTART], 'Do overseer missions (remote players)')
class AFKOverseersRemotePlayers(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self):
        ProcessPlayers.__init__(self, f'Remote players do overseer', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__())

    def resolve_players(self) -> List[IPlayer]:
        overseer_players = [player for player in self.get_runtime().player_mgr.find_players() if
                            player.get_player_info().run_overseer_missions and player.is_remote()]
        return overseer_players

    def create_script(self, player: IPlayer):
        return AFKOverseers(player)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Do overseer missions (logged remote players)')
class AFKOverseersRemotePlayers(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self):
        ProcessPlayers.__init__(self, f'Logged remote players do overseer', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__())

    def resolve_players(self) -> List[IPlayer]:
        overseer_players = [player for player in self.get_runtime().player_mgr.find_players() if
                            player.get_player_info().run_overseer_missions and player.is_remote()
                            and player.get_status() >= PlayerStatus.Logged]
        return overseer_players

    def create_script(self, player: IPlayer):
        return AFKOverseers(player)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Do overseer missions (group 1 remote players)')
class AFKOverseersRemotePlayers(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self):
        ProcessPlayers.__init__(self, f'Group 1 remote players do overseer', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__())

    def resolve_players(self) -> List[IPlayer]:
        overseer_players = [player for player in self.get_runtime().player_mgr.find_players() if
                            player.get_player_info().run_overseer_missions and player.is_remote()
                            and player.get_client_config_data().group_id & Groups.RAID_1]
        return overseer_players

    def create_script(self, player: IPlayer):
        return AFKOverseers(player)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Do overseer missions (group 2 remote players)')
class AFKOverseersRemotePlayers(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self):
        ProcessPlayers.__init__(self, f'Group 2 remote players do overseer', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__())

    def resolve_players(self) -> List[IPlayer]:
        overseer_players = [player for player in self.get_runtime().player_mgr.find_players() if
                            player.get_player_info().run_overseer_missions and player.is_remote()
                            and player.get_client_config_data().group_id & Groups.RAID_2]
        return overseer_players

    def create_script(self, player: IPlayer):
        return AFKOverseers(player)


class BuyOverseerMissions(PlayerScriptTask):
    def __init__(self, player: Optional[IPlayer] = None):
        PlayerScriptTask.__init__(self, f'Player {player} buy overseer quests', duration=-1.0)
        self.player = player

    def go_to_overseer_admin(self):
        self.player = self.resolve_player(self.player)
        psf = self.get_player_scripting_framework(self.player)
        psf.leave_group()
        city = self.player.get_player_info().home_city
        city_name = city.value
        # call to home
        current_zone = psf.get_command_result('who', '/who search results for (.*):')
        if city_name not in current_zone:
            psf.go_to_home_city()
        # move to merchant
        merchant_locs = {HomeCityNames.qeynos: Location(x=971.0, z=93.0, axz=325.5),
                         HomeCityNames.freeport: Location(x=-246.5, z=60.8, axz=3.5)}
        loc = merchant_locs[city]
        psf.navigate_to_location(loc)

    def __buy_charged_missions(self, mission_names: List[str], mission_count: int, charges_count: int) -> bool:
        self.player = self.resolve_player(self.player)
        psf = self.get_player_scripting_framework(self.player)
        psf.try_close_all_windows()
        missions_types_scribed = 0
        merchant_name = 'Stanley Parnem'
        buyer = BuyFromMerchantProcedure(psf, merchant_name)
        for quest in mission_names:
            if not buyer.get_merchant_window_archor():
                if not buyer.open_merchant_window():
                    logger.warn(f'{self.player} could failed to open merchant: {merchant_name}')
                    break
            missions_received = buyer.buy_item(quest, count=charges_count)
            if missions_received is None:
                logger.warn(f'{self.player} failed to buy "{quest}" from merchant "{merchant_name}"')
                buyer.close_merchant_window()
                break
            if not missions_received:
                logger.info(f'{self.player} could not find quest on merchant: {quest}')
                buyer.clear_search_field()
                continue
            # closes merchant window here
            buyer.close_merchant_window()
            charges_count = len(missions_received)
            # exact_name is False, because of a possible [Charged] postfix
            if psf.use_item_in_bags(item_name=quest, open_bags=True, count=charges_count, exact_name=False):
                missions_types_scribed += 1
            else:
                logger.warn(f'{self.player} could failed to scribe any overseer missions: {quest}')
                break
            # destroy more to clean up previously accumulated mess, sometimes ;)
            psf.destroy_item_in_bags(item_name=quest, open_bags=True, count=charges_count + 1, exact_name=False)
            if missions_types_scribed >= mission_count:
                break
        # closes merchant window here
        psf.try_close_all_windows()
        return missions_types_scribed > 0

    def buy_charged_missions_by_season_variety(self, mission_count: int, charges_count: int) -> bool:
        missions_to_buy = []
        seasons = list(OverseerSeasons.__members__.values())[:-1]
        count_per_round = 2
        for i in range(3):
            for tier in [OverseerMissionTier.Celestial, OverseerMissionTier.Fabled, OverseerMissionTier.Legendary]:
                for season in seasons:
                    missions_to_buy += season.value.missions_by_tier[tier][i * count_per_round: (i + 1) * count_per_round]
        return self.__buy_charged_missions(missions_to_buy, mission_count, charges_count)

    def buy_charged_missions_by_season_priority(self, mission_count: int, charges_count: int) -> bool:
        seasons = list(OverseerSeasons.__members__.values())[:-1]
        sorted_seasons = sorted(filter(lambda s: s.value.buy_charged_priority is not None, seasons), key=lambda s: s.value.buy_charged_priority)
        missions_to_buy = []
        for tier in OverseerMissionTier.__members__.values():
            for season in sorted_seasons:
                missions_to_buy += season.value.missions_by_tier[tier]
        return self.__buy_charged_missions(missions_to_buy, mission_count, charges_count)

    def go_back_home(self):
        self.player = self.resolve_player(self.player)
        if self.player.is_remote():
            psf = self.get_player_scripting_framework(self.player)
            psf.go_to_guild_hall()

    def _run(self, runtime: IRuntime):
        self.player = self.resolve_player(self.player)
        self.go_to_overseer_admin()
        self.buy_charged_missions_by_season_variety(MAX_OVERSEER_CHARGED_MISSIONS, MAX_OVERSEER_MISSION_CHARGES)
        self.go_back_home()


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Buy overseer missions (selected player)')
class BuyOverseerMissionsSelectedPlayer(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self, player: TOptionalPlayer = None):
        ProcessPlayers.__init__(self, f'Buy missions: {player}', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__(),
                                max_running_players=1, allow_mixed_hidden_players=False)
        self.player = player

    def resolve_players(self) -> List[IPlayer]:
        if not self.player:
            self.player = self._resolve_best_player_by_overlay_id(lambda player_: player_.get_player_info().buy_overseer_missions)
        return [self.player] if self.player else []

    def create_script(self, player: IPlayer):
        return BuyOverseerMissions(player)


class BuyOverseerMissionsRemotePlayers(ProcessPlayers, ProcessingScriptFactory, IPlayerSelector):
    def __init__(self, min_status: PlayerStatus, max_running_players: int):
        ProcessPlayers.__init__(self, f'buy missions', player_selector=self, script_factory=self,
                                auto_logout=MutableFlags.OVERSEER_AUTOMATIC_LOGOUT.__bool__(),
                                max_running_players=max_running_players, allow_mixed_hidden_players=False)
        self.__min_status = min_status

    def resolve_players(self) -> List[IPlayer]:
        overseer_players = [player for player in self.get_runtime().player_mgr.find_players() if
                            player.get_player_info().buy_overseer_missions and player.is_remote()
                            and player.get_status() >= self.__min_status]
        # only one per account
        overseer_players = {player.get_client_config_data().cred_key: player for player in overseer_players}.values()
        return list(overseer_players)

    def create_script(self, player: IPlayer) -> ScriptTask:
        return BuyOverseerMissions(player)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Buy overseer missions - caferul (remote players)')
class BuyOverseerMissionsRemotePlayers1(BuyOverseerMissionsRemotePlayers):
    def __init__(self):
        BuyOverseerMissionsRemotePlayers.__init__(self, min_status=PlayerStatus.Offline, max_running_players=1)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Buy overseer missions - aggressive (remote players)')
class BuyOverseerMissionsRemotePlayers1(BuyOverseerMissionsRemotePlayers):
    def __init__(self):
        BuyOverseerMissionsRemotePlayers.__init__(self, min_status=PlayerStatus.Offline, max_running_players=2)


@GameScriptManager.register_game_script(ScriptCategory.OVERSEERS, 'Buy overseer missions (logged remote players)')
class AFKOverseersLoggedRemotePlayers(BuyOverseerMissionsRemotePlayers):
    def __init__(self):
        BuyOverseerMissionsRemotePlayers.__init__(self, min_status=PlayerStatus.Logged, max_running_players=2)
