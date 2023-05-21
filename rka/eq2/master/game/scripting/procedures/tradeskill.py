import time
from random import random
from threading import RLock
from typing import Tuple, Dict, List, Optional

import regex as re

from rka.components.impl.factories import OCRServiceFactory
from rka.components.ui.capture import MatchPattern, Radius, CaptureArea, Rect, Capture, MatchMethod, Point, Offset, CaptureMode
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import EQ2_US_LOCALE_FILE_TEMPLATE
from rka.eq2.configs.shared.rka_constants import CLICK_DELAY, SERVER_REACT_DELAY, UI_REACT_DELAY
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability import AbilityPriority, AbilityType
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import AlchemistAbilities, SageAbilities, JewelerAbilities, ProvisionerAbilities, \
    CarpenterAbilities, ArmorerAbilities, TailorAbilities, WoodworkerAbilities, WeaponsmithAbilities
from rka.eq2.master.game.engine.task import FilterTask
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.gameclass import GameClassName, GameClass, GameClasses
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus, TellType
from rka.eq2.master.game.requests.special_request import CastTradeskillReaction
from rka.eq2.master.game.scripting import BagLocation, RepeatMode
from rka.eq2.master.game.scripting.patterns.craft.bundle import craft_patterns
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.procedures.common import ClickWhenCursorType, GetCommandResult
from rka.eq2.master.game.scripting.procedures.items import ItemLootingCheckerProcedure, ActionOnItemInBagProcedure, BagActionsProcedure
from rka.eq2.master.game.scripting.procedures.movement import MovementProcedureFactory, LocationGuard
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.toolkit import Procedure, PlayerScriptingToolkit
from rka.eq2.master.game.scripting.util import ts_spellchecker
from rka.eq2.master.game.scripting.util.ts_filter_cache import get_cached_recipe_filter, save_recipe_filter
from rka.eq2.master.game.scripting.util.ts_script_utils import guess_items_per_craft, find_differentiation_word, strip_to_minimal_crafing_representation, \
    compare_crafting_item_names, get_itemname_modifications_for_class, get_compressed_keywords, get_itemname_corrected_for_input, compare_normal_item_names
from rka.eq2.master.triggers import ITrigger
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.shared.client_events import ClientEvents

RECIPE_BOOK_INPUT_CHARS = 19


class CraftProcedure(Procedure):
    __ts_reaction_abilities = {
        GameClassName.Alchemist: [AlchemistAbilities.endothermic,
                                  AlchemistAbilities.reactions,
                                  AlchemistAbilities.experiment,
                                  AlchemistAbilities.exothermic,
                                  AlchemistAbilities.synthesis,
                                  AlchemistAbilities.analyze],
        GameClassName.Sage: [SageAbilities.spellbinding,
                             SageAbilities.notation,
                             SageAbilities.lettering,
                             SageAbilities.incantation,
                             SageAbilities.scripting,
                             SageAbilities.calligraphy],
        GameClassName.Jeweler: [JewelerAbilities.mind_over_matter,
                                JewelerAbilities.focus_of_spirit,
                                JewelerAbilities.faceting,
                                JewelerAbilities.sixth_sense,
                                JewelerAbilities.center_of_spirit,
                                JewelerAbilities.round_cut],
        GameClassName.Provisioner: [ProvisionerAbilities.constant_heat,
                                    ProvisionerAbilities.seasoning,
                                    ProvisionerAbilities.awareness,
                                    ProvisionerAbilities.slow_simmer,
                                    ProvisionerAbilities.pinch_of_salt,
                                    ProvisionerAbilities.realization],
        GameClassName.Carpenter: [CarpenterAbilities.tee_joint,
                                  CarpenterAbilities.concentrate,
                                  CarpenterAbilities.metallurgy,
                                  CarpenterAbilities.wedge_joint,
                                  CarpenterAbilities.ponder,
                                  CarpenterAbilities.smelting],
        GameClassName.Woodworker: [WoodworkerAbilities.carving,
                                   WoodworkerAbilities.measure,
                                   WoodworkerAbilities.handwork,
                                   WoodworkerAbilities.chiselling,
                                   WoodworkerAbilities.calibrate,
                                   WoodworkerAbilities.whittling],
        GameClassName.Armorer: [ArmorerAbilities.strikes,
                                ArmorerAbilities.steady_heat,
                                ArmorerAbilities.angle_joint,
                                ArmorerAbilities.hammering,
                                ArmorerAbilities.stoke_coals,
                                ArmorerAbilities.bridle_joint],
        GameClassName.Weaponsmith: [WeaponsmithAbilities.hardening,
                                    WeaponsmithAbilities.tempering,
                                    WeaponsmithAbilities.anneal,
                                    WeaponsmithAbilities.set,
                                    WeaponsmithAbilities.strengthening,
                                    WeaponsmithAbilities.compress],
        GameClassName.Tailor: [TailorAbilities.stitching,
                               TailorAbilities.nimble,
                               TailorAbilities.knots,
                               TailorAbilities.hem,
                               TailorAbilities.dexterous,
                               TailorAbilities.binding],
    }

    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)
        self.need_durability = 0
        self.__crafting_result_lock = RLock()
        self.craft_completed = False
        self.crafted_item: Optional[str] = None

    def __get_reaction_ability_locator(self, reaction_num: int) -> IAbilityLocator:
        for gameclassname, ability_list in CraftProcedure.__ts_reaction_abilities.items():
            gameclass = GameClasses.get_class_by_name(gameclassname)
            if self._get_player().is_class(gameclass):
                return ability_list[reaction_num]
        assert False, f'unknown reaction/TS class'

    def _get_reaction_ability(self, reaction_num: int) -> IAbility:
        locator = self.__get_reaction_ability_locator(reaction_num)
        return locator.resolve_for_player(self._get_player())

    def __create_fail_reaction_trigger(self) -> ITrigger:
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        trigger = trigger_factory.new_trigger('reaction failed')
        trigger.add_parser_events(r'You failed to counter .*')

        def loc_trigger_action(event: ClientEvents.PARSER_MATCH):
            self.need_durability = 4
            logger.info(f'craft reaction fail {self._get_player()}: {event.match().group(0)}')

        trigger.add_action(loc_trigger_action)
        return trigger

    def __create_craft_completed_trigger(self) -> ITrigger:
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        trigger = trigger_factory.new_trigger('craft completed')
        trigger.add_parser_events(r'You created (.*)\.')

        def loc_trigger_action(event: ClientEvents.PARSER_MATCH):
            with self.__crafting_result_lock:
                self.craft_completed = True
                self.crafted_item = event.match().group(1)
                logger.info(f'craft done {self._get_player()}: ({self.crafted_item})')

        trigger.add_action(loc_trigger_action)
        return trigger

    def open_craft_station(self):
        self._get_player_toolkit().try_close_all_windows()
        x = self._get_player().get_inputs().screen.VP_W_center
        y = self._get_player().get_inputs().screen.VP_H_center + 45
        ac_mouse_to_station = action_factory.new_action().mouse(x, y)
        self._get_player_toolkit().call_player_action(self._get_player().get_inputs().special.select_nearest_npc, delay=SERVER_REACT_DELAY)
        self._get_player_toolkit().call_player_action(ac_mouse_to_station, delay=3.0)

    def __sort_recipes(self):
        window_area = CaptureArea()
        # count all trivial(1) tags
        trivial_rects = self._get_player_toolkit().find_multiple_match_by_pattern(MatchPattern.by_tag(craft_patterns.PATTERN_GFX_TRIVIAL_1),
                                                                                  repeat=RepeatMode.DONT_REPEAT, area=window_area)
        if not trivial_rects:
            return
        # now change sorting
        self._get_player_toolkit().assert_click_match(pattern=craft_patterns.PATTERN_GFX_DIFFICULTY, repeat=RepeatMode.DONT_REPEAT)
        # and count trivla(1) again
        trivial_rects_2 = self._get_player_toolkit().find_multiple_match_by_pattern(MatchPattern.by_tag(craft_patterns.PATTERN_GFX_TRIVIAL_1),
                                                                                    repeat=RepeatMode.DONT_REPEAT, area=window_area)
        if not trivial_rects_2:
            return
        if len(trivial_rects) < len(trivial_rects_2):
            # change sorting back, if there was less trivials before the sort change
            self._get_player_toolkit().assert_click_match(pattern=craft_patterns.PATTERN_GFX_DIFFICULTY, repeat=RepeatMode.DONT_REPEAT)

    def __clear_search_field(self):
        window_area = CaptureArea()
        searh_field_offset = Offset(-40, 10, Offset.REL_FIND_BOX)
        self._get_player_toolkit().click_match(pattern=craft_patterns.PATTERN_BUTTON_FIND_RECIPE, repeat=RepeatMode.DONT_REPEAT, delay=0.0,
                                               area=window_area, click_offset=searh_field_offset)
        self._get_player_toolkit().call_player_action(action_factory.new_action().key('backspace', count=20))

    # noinspection PyMethodMayBeStatic
    def get_filter_for_recipe(self, requested_item: str) -> str:
        corrected_requested_item = get_itemname_corrected_for_input(requested_item)
        logger.debug(f'get_filter_for_recipe: corrected_requested_item = {corrected_requested_item} (from {requested_item})')
        words = get_compressed_keywords(corrected_requested_item, RECIPE_BOOK_INPUT_CHARS)
        recipe_filter = ''.join(words)
        return recipe_filter

    def __filter_recipes(self, recipe_filter: str):
        self._get_player_toolkit().call_player_action(action_factory.new_action().text(recipe_filter))
        self._get_player_toolkit().call_player_action(action_factory.new_action().key('enter'), delay=UI_REACT_DELAY)

    def __click_recipe_on_list(self, list_position: int):
        window_area = CaptureArea()
        item_offset = Offset(0, 40 + list_position * 42, Offset.REL_FIND_MID)
        for attempt in range(10):
            # clicking below the 'difficulty' column header - using offset
            self._get_player_toolkit().click_match(pattern=craft_patterns.PATTERN_GFX_DIFFICULTY, repeat=RepeatMode.DONT_REPEAT,
                                                   area=window_area, click_offset=item_offset)
            # confirm that the create button is enabled
            if self._get_player_toolkit().find_match_by_tag(pattern_tag=craft_patterns.PATTERN_BUTTON_CREATE,
                                                            repeat=RepeatMode.DONT_REPEAT, threshold=0.98, area=window_area):
                break

    def select_crafting_item(self, recipe_filter: str, list_position=0, orig_requested_item: Optional[str] = None):
        logger.debug(f'select_crafting_item: {recipe_filter}, position: {list_position}, orig_requested_item: {orig_requested_item}')
        # verify we are at recipe selection view
        self._get_player_toolkit().assert_find_match_by_tag(craft_patterns.PATTERN_BUTTON_CREATE, repeat=RepeatMode.REPEAT_ON_FAIL, threshold=0.85)
        self.__sort_recipes()
        self.__clear_search_field()
        self.__filter_recipes(recipe_filter)
        self.__click_recipe_on_list(list_position)
        # click button to start crafting. high threshold because if grayed out - no materials/no recipe selected
        if not self._get_player_toolkit().click_match(pattern=craft_patterns.PATTERN_BUTTON_CREATE, delay=2.0,
                                                      threshold=0.98, repeat=RepeatMode.REPEAT_ON_BOTH):
            orig_requested_item = orig_requested_item if orig_requested_item else recipe_filter
            self._get_toolkit().fail_script(f'Cannot start crafting "{orig_requested_item}" with "{recipe_filter}". No recipe?')

    def get_reaction_num(self, reaction_num: int, crafting_turn: int):
        if crafting_turn % 3 == 2 and self.need_durability == 0:
            self.need_durability += 2
        if self.need_durability > 0:
            reaction_num += 3
            self.need_durability -= 1
        return reaction_num

    def craft_from_resources_view(self, time_limit=120.0) -> Optional[str]:
        self.need_durability = 0
        with self.__crafting_result_lock:
            self.craft_completed = False
            self.crafted_item: Optional[str] = None
        crafting_timeout = False
        no_reaction_count = 0
        patterns_captured = False
        window_area = CaptureArea()
        color_window_area = CaptureArea(mode=CaptureMode.COLOR)

        # verify that crafting window is open, get offset - all coords are later relative to Craft label
        toolkit = self._get_player_toolkit()
        craft_label_loc = toolkit.assert_find_match_by_tag(ui_patterns.PATTERN_TAB_CRAFT, repeat=RepeatMode.REPEAT_ON_FAIL)
        offset = Point(craft_label_loc.x1 - 378, craft_label_loc.y1 - 90)

        # click button to being crafting
        time_before_start = time.time()
        match_begin_pattern = MatchPattern.by_tag(craft_patterns.PATTERN_BUTTON_BEGIN).set_match_method(MatchMethod.TM_SQDIFF_NORMED)
        toolkit.assert_click_match(pattern=match_begin_pattern, threshold=0.96, repeat=RepeatMode.REPEAT_ON_FAIL)
        time_after_start = time.time()
        start_crafting_time = time.time() - (time_after_start - time_before_start) / 2
        toolkit.click_match(pattern=ui_patterns.PATTERN_TAB_CRAFT, repeat=RepeatMode.DONT_REPEAT, threshold=0.96)

        # stop button is detected to confirm that the craft is still ongoing
        find_stop_button_area = window_area.capture_radius(Radius(offset.x + 708, offset.y + 661, r=40), relative=True)

        # ability for reactions - required and supplementary
        high_priority_abilities = [self._get_reaction_ability(i).prototype(priority=AbilityPriority.SCRIPT) for i in range(6)]
        low_priority_abilities = [self._get_reaction_ability(i).prototype(priority=AbilityPriority.EXTRA_TRADESKILL) for i in range(6)]
        high_priority_requests = [CastTradeskillReaction(high_priority_abilities[i]) for i in range(6)]
        low_priority_requests = [CastTradeskillReaction(low_priority_abilities[i]) for i in range(6)]
        reaction_tags = [f'reaction_{i}' for i in range(3)]
        reaction_check_area = window_area.capture_radius(Radius(offset.x + 404, offset.y + 594, r=20), relative=True)

        # triggers for failing a reaction (switch to using durability reactions) and craft completion
        trigger_fail_reaction = self.__create_fail_reaction_trigger()
        trigger_fail_reaction.start_trigger()
        trigger_craft_complete = self.__create_craft_completed_trigger()
        trigger_craft_complete.start_trigger()
        # create a separate processor
        request_ctrl = self._get_runtime().request_ctrl_factory.create_offzone_request_controller()
        request_ctrl.processor.run_filter(FilterTask(AbilityFilter().ability_type(AbilityType.tradeskills), 'only TS', -1.0))
        request_ctrl.player_switcher.borrow_player(self._get_player())
        try:
            while not self.craft_completed:
                ability_requested = False
                time_from_start = time.time() - start_crafting_time
                crafting_turn = int(time_from_start // 4.0)
                if time_limit and time_from_start > time_limit:
                    toolkit.click_match(pattern=craft_patterns.PATTERN_GFX_STOP_CRAFTING, repeat=RepeatMode.DONT_REPEAT)
                    crafting_timeout = True
                    break

                # look at ability bar and register patterns as tags for faster matching
                # ability need to be laid out like: 1st progress, 2nd progress, 3rd progress, 1st durability, 2nd durability, 3rd durability
                if not patterns_captured:
                    toolkit.sleep(1.0)
                    reaction_x_offset = [442, 486, 530]
                    for i, x in enumerate(reaction_x_offset):
                        reaction_area = window_area.capture_radius(Radius(offset.x + x, offset.y + 661, 8), True)
                        reaction_str = toolkit.call_player_action(action_factory.new_action().get_capture(reaction_area))[0]
                        reaction_capture = Capture.decode_capture(reaction_str)
                        action = action_factory.new_action().save_capture(reaction_capture, f'reaction_{i}')
                        results = toolkit.call_player_action(action)
                        toolkit.assert_action_results(results, bool, True, f'failed to save pattern {i}', action)
                    patterns_captured = True

                # try matching previously captured patterns
                reaction_pattern_to_match = MatchPattern.by_tags(reaction_tags).set_match_method(MatchMethod.TM_SQDIFF_NORMED)
                find_result = toolkit.find_match_by_pattern(reaction_pattern_to_match, repeat=RepeatMode.DONT_REPEAT,
                                                            area=reaction_check_area, threshold=0.96)
                reaction_found = find_result is not None
                if reaction_found:
                    # reaction is found, expire all potentially ongoing requests
                    for i in range(6):
                        low_priority_requests[i].expire()
                        high_priority_requests[i].expire()
                    found_tag, found_rect = find_result
                    reaction_num = reaction_tags.index(found_tag)
                    logger.detail(f'reaction {reaction_num}')
                    reaction_num_05 = self.get_reaction_num(reaction_num, crafting_turn)
                    request_ctrl.processor.run_request(high_priority_requests[reaction_num_05])
                    ability_requested = True
                    # reset counter of iterations without any reaction, required for checking stop condition
                    no_reaction_count = 0
                interval_part = time_from_start % 4.0

                # only cast additional reactions at the beginning of the interval
                if 0.3 < interval_part < 1.5:
                    for reaction_num in range(3):
                        reaction_num_05 = self.get_reaction_num(reaction_num, crafting_turn)
                        logger.detail(f'extra reaction {reaction_num_05}')
                        extra_request = low_priority_requests[reaction_num_05]
                        request_ctrl.processor.run_request(extra_request)
                        ability_requested = True

                # slow down screen capturing, especially if ability was just requested
                if ability_requested:
                    toolkit.sleep(min(1.0, 4.0 - interval_part))
                else:
                    toolkit.sleep(0.3)
                if reaction_found:
                    continue
                toolkit.try_close_all_access()
                toolkit.click_match(pattern=ui_patterns.PATTERN_TAB_CRAFT, repeat=RepeatMode.DONT_REPEAT, threshold=0.96)

                # if there is no stop button, craft is not going
                no_reaction_count += 1
                if no_reaction_count % 20 == 0:
                    result = toolkit.find_match_by_tag(pattern_tag=craft_patterns.PATTERN_GFX_STOP_CRAFTING, repeat=RepeatMode.DONT_REPEAT,
                                                       area=find_stop_button_area)
                    if not result and not self.craft_completed:
                        logger.warn('stop button not found')
                        break
        finally:
            with self.__crafting_result_lock:
                logger.debug(f'completed crafting loop, craft_completed={self.craft_completed}, crafted_item={self.crafted_item}')
            request_ctrl.close()
            trigger_craft_complete.cancel_trigger()
            trigger_fail_reaction.cancel_trigger()
            # prevent extra keystrokes form being generated - cancel all requests
            for i in range(6):
                low_priority_requests[i].expire()
                high_priority_requests[i].expire()
        with self.__crafting_result_lock:
            if not crafting_timeout and (not self.craft_completed or self.crafted_item is None):
                self._get_toolkit().fail_script(f'craft_completed={self.craft_completed}, crafted_item={self.crafted_item}, craft_cancelled={crafting_timeout}')
        # check if pristine item was created - if not, assume it wasnt crafted at all
        if not toolkit.click_match(pattern=craft_patterns.PATTERN_GFX_PRISTINE_ITEM, repeat=RepeatMode.DONT_REPEAT, area=color_window_area, threshold=0.8):
            logger.warn(f'Pristine item not created, instead got {self.crafted_item}')
            self.craft_completed = False
        # accept any rewards
        toolkit.try_click_accepts(click_delay=SERVER_REACT_DELAY)
        toolkit.click_match(pattern=ui_patterns.PATTERN_TAB_CRAFT, repeat=RepeatMode.DONT_REPEAT, threshold=0.96)
        return self.crafted_item

    def return_to_crafting_book(self):
        if not self._get_player_toolkit().click_match(pattern=craft_patterns.PATTERN_GFX_CRAFTING_BOOK, repeat=RepeatMode.REPEAT_ON_BOTH):
            logger.warn('Could not click crafting book icon to return to recipe list')

    def repeat_crafting(self):
        self._get_player_toolkit().assert_click_match(pattern=craft_patterns.PATTERN_GFX_START_CRAFTING, repeat=RepeatMode.REPEAT_ON_BOTH)


class TakeTradeskillWritProcedure(Procedure):
    __requisition_dictionary_ready = False

    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)
        separator1 = '(?: |:|: )?'
        term = r'\.?$'
        craft_verbs = 'create|make|brew|steep|grill|bake|blend|mix|cook|prepare|fill|pour|whip'
        requeststr_common = fr'.*I (?:need to|must) ?(?:{craft_verbs}){separator1}'
        units = '(?:drink)'
        measures = '(?:cup|stein|shot|plate|serving|bottle|glass|bowl|loaf|mug)'
        quantifiers = f'(?:some|a|an)?(?: ?{measures} ?(?:with|of|an|a))?'
        self.__requestitem_rx = re.compile(fr'{requeststr_common}(.*){term}')
        # spaces are optional because OCR might remove them and this item part is not subject to spellchecking
        self.__itemname_rxs = [re.compile(fr'(?:{quantifiers} )?(.*? \([a-zA-Z ]+\)).*$'),
                               re.compile(fr'(?:{quantifiers} )?(.*?) \(.*\).*$'),
                               re.compile(fr'(?:{quantifiers} )?(.*?) {units}\.?$'),
                               re.compile(fr'(?:{quantifiers} )?(.*?)\.?$'),
                               ]
        self.__requestitemstack_rx = re.compile(fr'{requeststr_common}(.*) \((\d+)/(\d+)\){term}')
        eq2_path = self._get_runtime().host_config.get_eq2_path(self._get_player().get_server())
        self.__read_requisition_dictionary(eq2_path)

    def __read_requisition_dictionary(self, eq2_path: str):
        if TakeTradeskillWritProcedure.__requisition_dictionary_ready:
            return
        requisition_dictionary = set()
        dict_file = EQ2_US_LOCALE_FILE_TEMPLATE.format(eq2_path)
        crafting_regex = re.compile(r'\d+\s+uddt\s+(.*)')

        # read requisition texts from game files. it doesnt cover level 90+ requisitions or so
        with open(dict_file, 'r', encoding='Latin-1') as file:
            for line in file:
                match = crafting_regex.match(line)
                if match is None:
                    continue
                text = match.group(1)
                match = self.__requestitem_rx.match(text)
                if match is None:
                    continue
                requestitem = match.group(1)
                matches = [rx.match(requestitem) for rx in self.__itemname_rxs]
                itemname = None
                for match in matches:
                    if match is None:
                        continue
                    itemname = match.group(1)
                    break
                if itemname is None:
                    assert False, f'no pattern for {requestitem}'
                requisition_dictionary.add(itemname)
        ts_spellchecker.init_dictionary(requisition_dictionary)
        TakeTradeskillWritProcedure.__requisition_dictionary_ready = True

    def _prepare_itemname_for_spellchecking(self, ocr_textline: str) -> Optional[str]:
        match = self.__requestitem_rx.match(ocr_textline)
        if match is None:
            return None
        requestitem = match.group(1)
        matches = [rx.match(requestitem) for rx in self.__itemname_rxs]
        for match in matches:
            if match is None:
                continue
            itemname = match.group(1)
            return itemname
        return None

    # noinspection PyMethodMayBeStatic
    def _correct_common_ocr_mistakes(self, req_ocr_item_text: str) -> str:
        replacements = {
            '’': '\'',
            '‘': '\'',
            '`': '\'',
            '|': 'I',
            '1': 'I',
            ']': 'I',
            '[': 'I',
            '!': 'I',
            'I\'V': 'IV',
            '\'I': 'I',
        }
        wrong_endings = [',']
        for find_str, replace_str in replacements.items():
            req_ocr_item_text = req_ocr_item_text.replace(find_str, replace_str)
        if req_ocr_item_text and req_ocr_item_text[-1] in wrong_endings:
            req_ocr_item_text = req_ocr_item_text[:-1]
        while True:
            replaced = req_ocr_item_text.replace('\'\'', '\'')
            if replaced != req_ocr_item_text:
                req_ocr_item_text = replaced
            else:
                break
        return req_ocr_item_text

    # noinspection PyMethodMayBeStatic
    def _correct_common_ocr_mistakes_for_stack(self, stack_ocr_text: str) -> str:
        replacements = {
            'o': '0',
            'O': '0',
        }
        for find_str, replace_str in replacements.items():
            stack_ocr_text = stack_ocr_text.replace(find_str, replace_str)
        if len(stack_ocr_text) > 1 and stack_ocr_text[1] == '1':
            stack_ocr_text_list = list(stack_ocr_text)
            stack_ocr_text_list[1] = '/'
            stack_ocr_text = ''.join(stack_ocr_text_list)
        return stack_ocr_text

    def extract_crafted_item_name(self, crafted_item_name: str) -> Optional[Tuple[int, str]]:
        logger.debug(f'extract_crafted_item_name: {crafted_item_name}')
        if crafted_item_name is None:
            return None
        match = re.match(r'(\d+ )?\\aITEM -?\d+ -?\d+:(.*)\\/a', crafted_item_name)
        if match is None:
            return None
        crafted_item_count = 1
        if match.group(1):
            crafted_item_count = int(match.group(1).strip())
        crafted_item_name = match.group(2)
        matches = [rx.match(crafted_item_name) for rx in self.__itemname_rxs]
        for match in matches:
            if match is None:
                continue
            itemname = match.group(1)
            logger.debug(f'extracted crafted item name: {crafted_item_name}')
            return crafted_item_count, itemname
        return None

    def _extract_crafted_item_stacks(self, crafted_item_name) -> Optional[int]:
        logger.debug(f'extract_crafted_item_stacks: {crafted_item_name}')
        if crafted_item_name is None:
            return None
        match = self.__requestitemstack_rx.match(crafted_item_name)
        if match is None:
            return None
        total = int(match.group(3))
        return total

    def summon_writ_agent(self) -> bool:
        bag_actions = BagActionsProcedure(self._get_player_toolkit())
        self._get_player_toolkit().try_close_all_windows()
        if not bag_actions.use_item_in_bags(item_name='Grandmaster Service Summoning Scroll', open_bags=True, count=1):
            return False
        self._get_toolkit().sleep(3.0)
        return True

    def take_ts_quest(self, agent_name: str) -> bool:
        # target the writ agent
        self._get_player_toolkit().try_close_all_windows()
        target_agent_action = self._get_player_toolkit().build_command(command=f'target {agent_name}')
        for _ in range(2):
            self._get_player_toolkit().call_player_action(target_agent_action, delay=SERVER_REACT_DELAY)
        # hail the writ agent
        response_reader = GetCommandResult(self._get_player_toolkit(), 'hail', '.*Hail(?:, )?(.*)')
        response = response_reader.run_command()
        if not response or agent_name not in response:
            logger.warn(f'Agent not hailed, response {response}')
            return False
        # zoom out to better see dialog options
        self._get_player_toolkit().set_camera_distance(15)
        # select first dialog option from top - highest level writ, and accept it
        if not self._get_player_toolkit().click_first_from_top(craft_patterns.PATTERN_DIALOG_I_WOULD_LIKE_A_WRIT,
                                                               repeat=RepeatMode.REPEAT_ON_SUCCESS,
                                                               object_heigth=35, delay=SERVER_REACT_DELAY):
            # already have the quest
            return True
        self._get_player_toolkit().assert_click_match(pattern=ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT, repeat=RepeatMode.REPEAT_ON_BOTH, delay=SERVER_REACT_DELAY)
        self._get_player_toolkit().assert_click_match(pattern=craft_patterns.PATTERN_DIALOG_THANK_YOU_I_WILL_GET, repeat=RepeatMode.REPEAT_ON_BOTH, delay=SERVER_REACT_DELAY)
        return True

    def take_ts_job(self):
        # get camera view right
        # noinspection PyUnresolvedReferences TODO
        self._get_player_toolkit().recenter_camera()
        if self._get_player().get_player_info().guildhall_config.housing:
            camera_distance = 5
        else:
            camera_distance = 10
        self._get_player_toolkit().set_camera_distance(camera_distance)
        # find taskboard and click it
        taskboard_capture_patterns = [craft_patterns.PATTERN_GFX_TASKBOARD_1, craft_patterns.PATTERN_GFX_TASKBOARD_2, craft_patterns.PATTERN_GFX_TASKBOARD_3,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_4, craft_patterns.PATTERN_GFX_TASKBOARD_5, craft_patterns.PATTERN_GFX_TASKBOARD_6,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_7, craft_patterns.PATTERN_GFX_TASKBOARD_8, craft_patterns.PATTERN_GFX_TASKBOARD_9,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_10, craft_patterns.PATTERN_GFX_TASKBOARD_11, craft_patterns.PATTERN_GFX_TASKBOARD_12,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_13, craft_patterns.PATTERN_GFX_TASKBOARD_14, craft_patterns.PATTERN_GFX_TASKBOARD_15,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_16, craft_patterns.PATTERN_GFX_TASKBOARD_17, craft_patterns.PATTERN_GFX_TASKBOARD_18,
                                      craft_patterns.PATTERN_GFX_TASKBOARD_19, craft_patterns.PATTERN_GFX_TASKBOARD_20,
                                      ]
        taskboard_found = False
        threshold = 0.0
        low_scale = 0.0
        high_scale = 0.0
        for threshold_i in range(3):
            threshold = 0.85 - threshold_i * 0.05
            for spread_i in range(3):
                low_scale = 1.0 - 0.1 * (spread_i + 1)
                high_scale = 1.0 + 0.1 * (spread_i + 1)
                taskboard_match_patterns = MatchPattern.by_tags(taskboard_capture_patterns).set_scale(low_scale, high_scale)
                taskboard_found = self._get_player_toolkit().click_match(pattern=taskboard_match_patterns, repeat=RepeatMode.DONT_REPEAT, threshold=threshold, delay=0.0)
                if taskboard_found:
                    break
            if taskboard_found:
                logger.info(f'Workorder Clipboard found: threshold={threshold}, scale={low_scale} - {high_scale}')
                self._get_toolkit().sleep(2.0)
                break
        if not taskboard_found:
            self._get_toolkit().fail_script(f'Workorder Clipboard not found! threshold={threshold}, scale={low_scale} - {high_scale}')
        # select invoice from dialog and close the dialog
        self._get_player_toolkit().assert_click_match(pattern=craft_patterns.PATTERN_DIALOG_TAKE_INVOICE, repeat=RepeatMode.REPEAT_ON_BOTH)
        self._get_player_toolkit().assert_click_match(pattern=ui_patterns.PATTERN_BUTTON_X, repeat=RepeatMode.REPEAT_ON_FAIL)

    def read_quest_contents(self, crafter_class: GameClass) -> Dict[str, Tuple[int, int]]:
        ocr = OCRServiceFactory.create_ocr_service()
        window_area = CaptureArea(mode=CaptureMode.COLOR)
        font_heigth_1 = 12
        font_heigth_2 = 11

        # open the quest journal and switch to quests tab, if its not switched
        self._get_player_toolkit().call_player_action(self._get_player().get_inputs().special.open_journal, delay=UI_REACT_DELAY)
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_TAB_QUESTS, repeat=RepeatMode.DONT_REPEAT, delay=UI_REACT_DELAY)
        # try to click the new quest to select it
        self._get_player_toolkit().click_match(pattern=craft_patterns.PATTERN_GFX_RUSH, repeat=RepeatMode.DONT_REPEAT, delay=CLICK_DELAY, threshold=0.85)
        # location of the anchor text and its offset from window start. all further coordinates are relating to window start too
        # for the script to work, the journal window must be maximized, and its left pane as narrow as possible, to allow 1-lined requisition bullets
        quests_label_loc = self._get_player_toolkit().assert_find_match_by_tag(pattern_tag=craft_patterns.PATTERN_DIALOG_I_HAVE_MY_ASSIGNED_TASK,
                                                                               repeat=RepeatMode.REPEAT_ON_FAIL)
        offset = Point(quests_label_loc.x1 - 379, quests_label_loc.y1 - 262)
        items_found: Dict[str, Tuple[int, int]] = dict()
        req_item_text = None
        dy = 0
        dy_change_with_icon = 45
        dy_change_no_icon = 20
        remaing_requests_count = 6
        while remaing_requests_count > 0:
            # capture and recognize item name. it needs to fit in one line
            req_text_rect = Rect(x1=offset.x + 398 + 1,  # 1 pixel before text start
                                 y1=offset.y + 307 - 1 + dy,  # 1 pixel above text topline
                                 x2=offset.x + 950,
                                 y2=offset.y + 307 - 1 + 1 + font_heigth_1 + dy  # area lower bound is inclusive, so -1. but +1 to end 1 line below text
                                 )
            req_text_area = window_area.capture_rect(req_text_rect, relative=True)
            req_text_capture_action = action_factory.new_action().get_capture(req_text_area)
            req_text_capture_str = self._get_player_toolkit().call_player_action(req_text_capture_action)[0]
            req_text_capture = Capture.decode_capture(req_text_capture_str)
            req_ocr_text = ocr.ocr_normal_line_of_text_no_bg(req_text_capture, info=f'prev-item-{req_item_text}')
            if not req_ocr_text.strip():
                # normal situation, there isnt a next entry in journal
                logger.debug(f'Could not read craft item name, previous was: "{req_item_text}"')
                break
            logger.debug(f'OCR result: "{req_ocr_text}"')
            corrected_ocr_text = self._correct_common_ocr_mistakes(req_ocr_text)
            logger.debug(f'Corrected OCR result: "{corrected_ocr_text}"')
            req_ocr_item_text = self._prepare_itemname_for_spellchecking(corrected_ocr_text)
            if req_ocr_item_text is None:
                logger.warn(f'Could not extract craft item name from: "{corrected_ocr_text}"')
                break
            req_item_text = req_ocr_item_text.strip().lower()

            # use spellchecker if its available
            use_spellchecker = self._get_player().get_level(crafter_class) < 100
            logger.detail(f'Spellchecking ({use_spellchecker}): "{req_ocr_item_text}"')
            if use_spellchecker:
                spellchecked_req_item_text = ts_spellchecker.correction(req_ocr_item_text)
                if spellchecked_req_item_text is not None:
                    if spellchecked_req_item_text != req_ocr_item_text:
                        logger.info(f'OCR vs Spellcheck difference: "{req_ocr_item_text}" -> "{spellchecked_req_item_text}"')
                    # replace value of requested item with spellcheck result
                    req_item_text = spellchecked_req_item_text
                else:
                    logger.warn(f'Spellcheck failed for: "{req_ocr_item_text}"')

            # check distance to next requisition item. if its 20, no icons will be present
            req_box_radius = Radius(offset.x + 390,  # middle of checkbox, almost (width is 14 - even)
                                    offset.y + 314 + dy + dy_change_no_icon,  # topline of current checkbox + half its size + skip to next line
                                    12)
            req_box_area = window_area.capture_radius(req_box_radius, relative=True)
            req_box_check_result = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_O,
                                                                                repeat=RepeatMode.DONT_REPEAT, area=req_box_area)
            if req_box_check_result:
                logger.debug(f'Found next checkbox, no icons present')
                icons_present = False
            else:
                logger.debug(f'Checkbox not found, checking for icons')
                icons_present = True

            check_stack_at_icon = False
            item_count = 0
            if icons_present:
                # look for the 1st icon under the requisition text - capture it
                icon_radius = Radius(offset.x + 416, offset.y + 329 + dy, 10)  # small radius - search pattern
                icon_area = window_area.capture_radius(icon_radius, relative=True)
                icon_capture_action = action_factory.new_action().get_capture(icon_area)
                icon_capture_str = self._get_player_toolkit().call_player_action(icon_capture_action)[0]
                icon_capture = Capture.decode_capture(icon_capture_str)
                # detect amount of icons to see how many times to craft
                for column in range(6):
                    dx = column * 32
                    icon_radius = Radius(offset.x + 416 + dx, offset.y + 329 + dy, 16)  # full radius - search area
                    icon_area = window_area.capture_radius(icon_radius, relative=True)
                    if not self._get_player_toolkit().find_match_by_pattern(pattern=MatchPattern.by_capture(icon_capture),
                                                                            repeat=RepeatMode.DONT_REPEAT, area=icon_area):
                        break
                    item_count += 1
                assert item_count >= 1
                if item_count == 1:
                    check_stack_at_icon = True
            else:
                item_count = 1

            # check stackable items with amounts in the requisition text
            craft_count_within_req_text = self._extract_crafted_item_stacks(corrected_ocr_text)
            if craft_count_within_req_text is not None:
                logger.debug(f'stackable amount resolved to 0/{craft_count_within_req_text}')
                item_count = craft_count_within_req_text
                check_stack_at_icon = False

            # check stackable items for case when a single icon is present, will OCR to "amount / max"
            if check_stack_at_icon:
                stack_text_rect = Rect(x1=offset.x + 431, y1=offset.y + 320 + dy, x2=offset.x + 463, y2=offset.y + 320 + font_heigth_2 + dy)
                stack_text_area = window_area.capture_rect(stack_text_rect, relative=True)
                stack_text_capture_action = action_factory.new_action().get_capture(stack_text_area)
                stack_text_capture_str = self._get_player_toolkit().call_player_action(stack_text_capture_action)[0]
                stack_text_capture = Capture.decode_capture(stack_text_capture_str)
                stack_ocr_text = ocr.ocr_tiny_text_no_bg(stack_text_capture, info=f'amount_of_{req_item_text[:6]}', chars='/0123456789')
                if stack_ocr_text:
                    stack_ocr_text = self._correct_common_ocr_mistakes_for_stack(stack_ocr_text)
                    stack_ocr_text_match = re.match(r'0/?(\d+)', stack_ocr_text.strip().replace(' ', ''))
                    if stack_ocr_text_match is not None:
                        item_count = int(stack_ocr_text_match.group(1))
                        logger.debug(f'stackable amount (2) resolved to 0/{item_count}')

            items_per_craft = guess_items_per_craft(crafter_class, item_count)
            craft_count = item_count // items_per_craft

            # save item name, total count, count per craft
            items_found[req_item_text] = item_count, items_per_craft
            remaing_requests_count -= craft_count
            position_count = len(items_found.keys())
            logger.debug(f'{position_count}. Item count: {item_count} x {req_item_text}, remaining requests: {remaing_requests_count}')
            if icons_present:
                dy += dy_change_with_icon
            else:
                dy += dy_change_no_icon

        # close journal
        self._get_player_toolkit().call_player_action(self._get_player().get_inputs().special.open_journal, delay=UI_REACT_DELAY)
        return items_found

    # noinspection PyMethodMayBeStatic
    def fill_vov_quest_contents(self, items_to_craft: Dict[str, Tuple[int, int]]) -> Dict[str, Tuple[int, int]]:
        vov_items = {
            'forlorn intangible ring': ('forlorn intangible scout ability', 3, 1),
        }
        for vov_item, vov_2nd_item in vov_items.items():
            if vov_item.lower() in items_to_craft:
                logger.debug(f'VoV special quests: adding {vov_2nd_item} because of {vov_item}')
                items_to_craft[vov_2nd_item[0]] = (vov_2nd_item[1], vov_2nd_item[2])
        return items_to_craft


class TradeskillTriggersProcedure(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit, use_panic_mode: bool):
        Procedure.__init__(self, scripting)
        self.__levelup_trigger = self.__create_levelup_trigger()
        self.__tells_trigger = self.__create_tells_trigger(use_panic_mode)
        self.__guildmate_logged = self.__create_guildmate_trigger(use_panic_mode)
        self.__levels_gained: List[int] = []

    def start_tradeskill_triggers(self):
        self.__levelup_trigger.start_trigger()
        self.__tells_trigger.start_trigger()
        self.__guildmate_logged.start_trigger()

    def cancel_tradeskill_triggers(self):
        self.__levelup_trigger.cancel_trigger()
        self.__tells_trigger.cancel_trigger()
        self.__guildmate_logged.cancel_trigger()

    def retrieve_acquired_levels(self) -> List[int]:
        new_levels = self.__levels_gained.copy()
        self.__levels_gained.clear()
        return new_levels

    def __create_guildmate_trigger(self, panic_mode: bool) -> ITrigger:
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        trigger = trigger_factory.new_trigger('guildmate login')
        trigger.add_parser_events(r'Guildmate: (.*) has logged in\.')

        def guildmate_action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            player_name = match.group(1)
            if player_name in self._get_runtime().player_mgr.get_player_names(min_status=PlayerStatus.Offline):
                return
            message = match.group(0)
            logger.warn(message)
            if panic_mode:
                self._get_runtime().notification_service.post_notification(message)
                self._get_player_toolkit().get_scripting().fail_script(f'guildmate {player_name} has logged in')

        trigger.add_action(guildmate_action)
        return trigger

    def __create_tells_trigger(self, panic_mode: bool) -> ITrigger:
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        trigger = trigger_factory.new_trigger('someone tells you')
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell_type=TellType.tell, to_player=self._get_player()))

        def tells_received_action(event: ChatEvents.PLAYER_TELL):
            if event.from_player_name in self._get_runtime().player_mgr.get_player_names(min_status=PlayerStatus.Offline):
                return
            logger.warn(f'{self._get_player().get_player_name()} got tell: {event.tell}')
            self._get_runtime().notification_service.post_notification(f'Tell from {event.from_player_name} to {event.to_player_name}:{event.tell}')
            if panic_mode:
                self._get_player_toolkit().get_scripting().fail_script(f'{event.from_player_name} sent you a tell: {event.tell}')

        trigger.add_action(tells_received_action)
        return trigger

    def __create_levelup_trigger(self) -> ITrigger:
        trigger_factory = PlayerTriggerFactory(self._get_runtime(), self._get_player())
        trigger = trigger_factory.new_trigger('level up')
        trigger.add_parser_events(r'Your tradeskill level is now (\d+)\.')

        def levelup_received_action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            message = match.group(0)
            self._get_runtime().overlay.log_event(message, Severity.Normal)
            level = int(match.group(1))
            if level % 10 == 0:
                self._get_runtime().notification_service.post_notification(f'{self._get_player().get_player_name()}: {message}')
            self.__levels_gained.append(level)

        trigger.add_action(levelup_received_action)
        return trigger


class TradeskillWritProcedure(Procedure):
    MAX_NEGATIVE_WORDS = 3
    MAX_CRAFT_ATTEMPTS = 10

    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)
        guild_hall_config = self._get_player().get_player_info().guildhall_config
        self.zone_name = guild_hall_config.guildhall_name
        self.crafter_class = self._get_player().get_crafter_class()
        self.crafter_level = self._get_player().get_level(self.crafter_class)
        self.agent_location = guild_hall_config.writ_agent_location
        self.agent_location.info = 'Agent'
        self.taskboard_location = guild_hall_config.taskboard_location
        self.taskboard_location.info = 'Taskboard'
        self.station_location = guild_hall_config.workstation_locations[self.crafter_class]
        self.station_location.info = f'{self.crafter_class} station'
        self.agent_name = guild_hall_config.writ_agent_name
        pst = self._get_player_toolkit()
        self.crafter = CraftProcedure(pst)
        self.quest_taker = TakeTradeskillWritProcedure(pst)
        self.__navigator = MovementProcedureFactory.create_navigation_procedure(pst, final_loc_high_precision=True, final_loc_rotation=True)
        self.__current_locked_location: Optional[Location] = None

    def craft_items(self, items_to_craft: Dict[str, Tuple[int, int]]):
        for orig_requested_item, (item_count, items_per_craft) in items_to_craft.items():
            orig_requested_item = orig_requested_item.lower()
            reselect_item_name = True
            cached_recipe_filter = get_cached_recipe_filter(orig_requested_item)
            recipe_filter: Optional[str] = None
            remaining_items = item_count
            total_crafted_item_count = 0
            while remaining_items > 0:
                crafting_success = False
                list_position = 0
                wrong_crafts = []
                negative_words = []
                for filter_attempt in range(TradeskillWritProcedure.MAX_CRAFT_ATTEMPTS):
                    curr_requested_item = orig_requested_item
                    for diff_word in negative_words:
                        curr_requested_item = f'{curr_requested_item} -{diff_word}'
                    logger.debug(f'crafting: {items_per_craft}/{remaining_items} of "{curr_requested_item}"')
                    # select item in the crafting window
                    if reselect_item_name:
                        if not cached_recipe_filter:
                            modified_item_name = get_itemname_modifications_for_class(self.crafter_class, self.crafter_level, curr_requested_item)
                            recipe_filter = self.crafter.get_filter_for_recipe(modified_item_name)
                        else:
                            recipe_filter = cached_recipe_filter
                        self.crafter.select_crafting_item(recipe_filter=recipe_filter, list_position=list_position, orig_requested_item=orig_requested_item)
                        reselect_item_name = False
                    else:
                        self.crafter.repeat_crafting()
                    # craft the item
                    actual_crafted = self.crafter.craft_from_resources_view()
                    if not actual_crafted:
                        if self.crafter.craft_completed:
                            logger.error(f'no product crafted, but craft is completed (!?)')
                        else:
                            logger.info(f'no product crafted, craft not completed')
                        continue
                    craft_results = self.quest_taker.extract_crafted_item_name(actual_crafted)
                    if craft_results is None:
                        continue
                    crafted_item_count, raw_crafted_itemname = craft_results
                    # compare crafted and requested items
                    if compare_crafting_item_names(raw_crafted_itemname, orig_requested_item):
                        logger.debug(f'exact match: {raw_crafted_itemname} (req:{orig_requested_item})')
                        crafting_success = True
                    elif cached_recipe_filter:
                        logger.error(f'accepting non-match: {raw_crafted_itemname} (req:{orig_requested_item}), due to cached filter')
                        crafting_success = True
                    if crafting_success:
                        remaining_items -= crafted_item_count
                        total_crafted_item_count += crafted_item_count
                        logger.debug(f'total crafted: {total_crafted_item_count}/{item_count} of "{raw_crafted_itemname}", requested "{curr_requested_item}"')
                        break
                    else:
                        if not self.crafter.craft_completed:
                            logger.info(f'craft was not properly completed, and received item did not match requested item')
                            continue
                        # proceed to changing the recipe search filter
                        logger.warn(f'wrong craft: "{raw_crafted_itemname}", requested "{curr_requested_item}". filter={recipe_filter}, list_pos={list_position}')
                    # crafted item differs from requested item, find a differentiation sequence
                    corrected_crafted = strip_to_minimal_crafing_representation(raw_crafted_itemname)
                    wrong_crafts.append(corrected_crafted)
                    diff_word = find_differentiation_word(positive_sentence=orig_requested_item, negative_sentences=wrong_crafts, min_length=2)
                    if diff_word:
                        if len(negative_words) <= TradeskillWritProcedure.MAX_NEGATIVE_WORDS:
                            logger.debug(f'adding diff word: {diff_word} to current negative words: {negative_words}, current list position: {list_position}')
                            negative_words.append(diff_word)
                            list_position = 0
                        else:
                            logger.debug(f'advancing list position to: {list_position + 1}. current negative words: {negative_words}')
                            list_position += 1
                        logger.info(f'sub-match: {corrected_crafted} / {orig_requested_item}, diff {diff_word}')
                        self.crafter.return_to_crafting_book()
                        reselect_item_name = True
                    else:
                        # using differentiation sequences did not result in correct item - craft next item on the list
                        logger.debug(f'advancing list position to: {list_position + 1}')
                        list_position += 1
                # if crafting succeeded, differentiation words were used and the filter points to the correct item now - cache it for future
                if crafting_success and wrong_crafts and recipe_filter:
                    if list_position == 0:
                        logger.debug(f'save modified recipe_filter: {recipe_filter} for {orig_requested_item}')
                        save_recipe_filter(orig_requested_item, recipe_filter)
                    else:
                        logger.error(f'Fixed recipe filter required for: {orig_requested_item} ({self.crafter_class})')
                if not crafting_success:
                    self._get_player_toolkit().get_scripting().fail_script(f'requested crafting "{orig_requested_item}"')
            self._get_player_toolkit().sleep(1.0)
            self._get_player_toolkit().try_click_accepts()
            self.crafter.return_to_crafting_book()
            # wait for "Quest Item completed" message to stop obscuring the display
            self._get_player_toolkit().sleep(2.0)

    def __unlock_current_location(self):
        logger.detail(f'{time.time()}: {self.crafter_class} UNLOCKING {self.__current_locked_location}')
        if self.__current_locked_location:
            LocationGuard.unlock_exclusive_shared_location(zone=self.zone_name, location=self.__current_locked_location)

    def __navigate_to_exclusive_shared_location(self, location: Location, lock_duration: float) -> bool:
        logger.detail(f'{time.time()}: {self.crafter_class} LOCKING {location}')
        self.__unlock_current_location()
        LocationGuard.lock_exclusive_shared_location(zone=self.zone_name, location=location, radius=4.0, duration=lock_duration)
        self.__current_locked_location = location
        logger.detail(f'{time.time()}: {self.crafter_class} MOVING TO {location}')
        reached = self.__navigator.navigate_to_location(location)
        logger.detail(f'{time.time()}: {self.crafter_class} REACHED {location} {reached}')
        return reached

    def take_ts_quest(self) -> bool:
        if self.quest_taker.take_ts_quest(self.agent_name):
            return True
        if not self._get_player().get_player_info().guildhall_config.housing:
            logger.warn(f'Agent not found in a guild hall of {self._get_player()}')
            # agent should be in guild hall, dont summon agent, report problem
            return False
        logger.debug(f'Summoning writ agent for {self._get_player()}')
        if not self.quest_taker.summon_writ_agent():
            logger.warn(f'Failed to summon writ agent for {self._get_player()}')
            return False
        # try again after summon agent
        return self.quest_taker.take_ts_quest(self.agent_name)

    def ts_writ_round(self):
        try:
            # move to agent
            if not self.__navigate_to_exclusive_shared_location(self.agent_location, 30.0):
                self._get_toolkit().fail_script('Failed to reach writ agent location')
            # get quest from the agent
            if not self.take_ts_quest():
                self._get_toolkit().fail_script('Failed to take writ from agent')
            # move to taskboard
            if not self.__navigate_to_exclusive_shared_location(self.taskboard_location, 30.0):
                self._get_toolkit().fail_script('Failed to reach taskboard location')
            # get job from the taskboard
            self.quest_taker.take_ts_job()
            # move to crafting station
            if not self.__navigate_to_exclusive_shared_location(self.station_location, 180.0):
                self._get_toolkit().fail_script('Failed to reach crafting station location')
            # read quest contents
            items_to_craft = self.quest_taker.read_quest_contents(self.crafter_class)
            items_to_craft = self.quest_taker.fill_vov_quest_contents(items_to_craft)
            # open the crafting station
            self.crafter.open_craft_station()
            # craft items one by one
            self.craft_items(items_to_craft)
            # complete, close any pending windows
            self.crafter._get_player_toolkit().try_close_all_windows(click_delay=UI_REACT_DELAY)
        finally:
            self.__unlock_current_location()

    def craft_test(self):
        # read quest contents
        quest_taker = TakeTradeskillWritProcedure(self._get_player_toolkit())
        _items_to_craft = quest_taker.read_quest_contents(self.crafter_class)


class BuyFromMerchantProcedure(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit, merchant_name: str):
        Procedure.__init__(self, scripting)
        self.__merchant_name = merchant_name
        self.__search_field_loc: Optional[Rect] = None
        self.__last_search_text: Optional[str] = None

    def open_merchant_window(self) -> bool:
        logger.debug(f'open_merchant_window: {self.__merchant_name}')
        if self.get_merchant_window_archor():
            return True
        target_agent_action = self._get_player_toolkit().build_command(command=f'target {self.__merchant_name}')
        self._get_player_toolkit().call_player_action(target_agent_action, delay=SERVER_REACT_DELAY)
        merchant_clicker = ClickWhenCursorType(self._get_player_toolkit())
        around_x = self._get_player().get_inputs().screen.VP_W_center
        around_y = self._get_player().get_inputs().screen.VP_H_center + 40
        if not merchant_clicker.click_when_cursor_type_is(ClickWhenCursorType.CURSOR_FP_MERCHANT, around_x=around_x, around_y=around_y):
            logger.warn(f'Merchant {self.__merchant_name} not found by {self._get_player()}')
            return False
        return True

    def close_merchant_window(self) -> bool:
        self._get_player_toolkit().try_close_all_windows()

    def __get_search_field_loc(self) -> Optional[Rect]:
        if not self.__search_field_loc:
            self.__search_field_loc = self._get_player_toolkit().find_match_by_tag(ui_patterns.PATTERN_SEARCH_BUY, repeat=RepeatMode.DONT_REPEAT)
        return self.__search_field_loc

    def clear_search_field(self, search_text_len: Optional[int] = None):
        search_field_loc = self.__get_search_field_loc()
        if not search_field_loc:
            logger.warn(f'{self._get_player()} could not clear merchant search filter, no Search field')
            return
        if search_text_len is None:
            if self.__last_search_text is not None:
                search_text_len = len(self.__last_search_text)
            else:
                search_text_len = 40
        mid = search_field_loc.middle()
        self._get_player_toolkit().call_player_action(action_factory.new_action().mouse(mid.x, mid.y), delay=CLICK_DELAY)
        self._get_player_toolkit().call_player_action(action_factory.new_action().key('backspace', count=search_text_len + 1))
        self._get_player_toolkit().call_player_action(action_factory.new_action().key('delete', count=search_text_len + 1))

    def get_merchant_window_archor(self, wait_for_open=False) -> Optional[Rect]:
        repeat_mode = RepeatMode.REPEAT_ON_FAIL if wait_for_open else RepeatMode.DONT_REPEAT
        buy_tab_loc = self._get_player_toolkit().find_match_by_tag(ui_patterns.PATTERN_TAB_BUY, repeat=repeat_mode | RepeatMode.TRY_ALL_ACCESS)
        return buy_tab_loc

    def buy_item(self, item_name: str, count=1) -> Optional[List[str]]:
        logger.info(f'buy_item: {item_name} (x{count}) for {self._get_player()}')
        bought_items: List[str] = list()
        # enter item name and confirm
        buy_tab_loc = self.get_merchant_window_archor(wait_for_open=True)
        if not buy_tab_loc:
            logger.warn(f'{self._get_player()} could not buy from {self.__merchant_name}, no Buy tab')
            return None
        offset = Point(buy_tab_loc.x1 - 32, buy_tab_loc.y1 - 129)
        search_field_loc = self.__get_search_field_loc()
        if not search_field_loc:
            logger.warn(f'{self._get_player()} could not buy from {self.__merchant_name}, no Search field')
            return None
        self._get_player_toolkit().assert_click_match(pattern=ui_patterns.PATTERN_SEARCH_BUY, repeat=RepeatMode.DONT_REPEAT)
        self._get_player_toolkit().call_player_action(action_factory.new_action().text(item_name.lower()))
        self._get_player_toolkit().call_player_action(action_factory.new_action().key('enter'), delay=UI_REACT_DELAY)
        self.__last_search_text = item_name.lower()
        # click first item on list and hit button to buy
        looting_checker = ItemLootingCheckerProcedure(self._get_player_toolkit())
        looting_checker.start_looting_tracking()
        self._get_player_toolkit().call_player_action(action_factory.new_action().mouse(offset.x + 131, offset.y + 211), delay=CLICK_DELAY)
        buy_one_pattern = MatchPattern.by_tags([ui_patterns.PATTERN_BUTTON_BUY_ONE, ui_patterns.PATTERN_BUTTON_BUY_MERCHANT])
        for i in range(count):
            looting_checker.clear_last_results()
            if not self._get_player_toolkit().click_match(pattern=buy_one_pattern, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY):
                logger.info(f'Cannot click Buy to purchase {item_name}, player {self._get_player()} - not on sale?')
                break
            looting_checker.wait_for_trigger(4.0)
            bought_item_name = looting_checker.get_item()
            if not bought_item_name:
                logger.warn(f'Item not found or not purchased: {item_name}, player {self._get_player()}')
                break
            if not compare_normal_item_names(bought_item_name, item_name):
                logger.warn(f'Purchased item not matching requested: {item_name}, instead purchased: {bought_item_name}, player {self._get_player()}')
            elif bought_item_name.lower() != item_name.lower():
                logger.info(f'Purchased item not exactly matching requested: {item_name}, instead purchased: {bought_item_name}, player {self._get_player()}')
            bought_items.append(bought_item_name)
        looting_checker.stop_looting_tracking()
        logger.debug(f'bought_items ({len(bought_items)}): {bought_items}')
        return bought_items

    def open_buy_close(self, item_name: str, count=1) -> Optional[List[str]]:
        if not self.open_merchant_window():
            return None
        result = self.buy_item(item_name, count)
        self.close_merchant_window()
        return result


class BuyRecipesProcedure(BuyFromMerchantProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit, merchant_name: str, craft_classname: str):
        BuyFromMerchantProcedure.__init__(self, scripting, merchant_name)
        self.craft_classname = craft_classname
        self.item_clicker = ActionOnItemInBagProcedure(self._get_player_toolkit())

    def get_recipe_book_name(self, level: int) -> Optional[str]:
        if level <= 110:
            recipe_book_name = f'{self.craft_classname} Essentials Volume {level}'
        elif level <= 120:
            changed_level = level - 100
            recipe_book_name = f'{self.craft_classname}\'s Primer Volume {changed_level}'
        elif level <= 125:
            changed_level = level - 120
            roman_level = ['I', 'II', 'III', 'IV', 'V'][changed_level - 1]
            recipe_book_name = f'Vetrovian {self.craft_classname}\'s Primer Volume {roman_level}'
        else:
            logger.error(f'No coded recipe book name patter for level {level} of {self.craft_classname}')
            return None
        return recipe_book_name

    def scripe_recipe_book(self, book_name: str) -> bool:
        return self.item_clicker.open_bags_and_find_item_and_click_menu(book_name, ui_patterns.PATTERN_ITEM_MENU_SCRIBE)

    def buy_recipe_book(self, level: int) -> Optional[str]:
        recipe_book_name = self.get_recipe_book_name(level)
        if not recipe_book_name:
            return None
        bought_recipe_books = self.open_buy_close(recipe_book_name, count=1)
        return bought_recipe_books[0] if bought_recipe_books else None

    def go_to_merchant_and_get_recipe_books(self, merchant_location: Location, levels: List[int]) -> bool:
        logger.info(f'go_to_merchant_and_get_recipe_books: {levels}, for {self._get_player()}')
        if not levels:
            return False
        mover = MovementProcedureFactory.create_navigation_procedure(self._get_player_toolkit(), final_loc_high_precision=True, final_loc_rotation=True)
        if not mover.navigate_to_location(merchant_location):
            return False
        result = True
        for level in levels:
            book_name = self.buy_recipe_book(level)
            if book_name:
                result = result and self.scripe_recipe_book(book_name)
            else:
                logger.warn(f'Recipe book not purchased for level {level}, for {self._get_player()}')
                result = False
        return result

    def scribe_recipe_books_from_inventory(self, levels: List[int]) -> bool:
        result = True
        logger.info(f'scribe_recipe_books_from_inventory: {levels}, for {self._get_player()}')
        for level in levels:
            book_name = self.get_recipe_book_name(level)
            if book_name:
                result = result and self.scripe_recipe_book(book_name)
        return result

    def acquire_recipes(self, levels: List[int]) -> bool:
        guild_hall_config = self._get_player().get_player_info().guildhall_config
        recipe_merchant_location = guild_hall_config.recipe_merchant_location
        if guild_hall_config.recipe_merchant_location and guild_hall_config.recipe_merchant_name:
            recipes_scribed = self.go_to_merchant_and_get_recipe_books(recipe_merchant_location, levels)
        else:
            recipes_scribed = self.scribe_recipe_books_from_inventory(levels)
        return recipes_scribed


class BuyItems(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)
        self.__toggle_bags = action_factory.new_action().append(self._get_player().get_inputs().special.open_bags)

    def buy_bag_of_items_from_open_broker(self, request_number_of_items_to_buy: Optional[int] = None):
        w = self._get_player().get_inputs().screen.bags_width[0]
        h = 8
        to_buy = w * h if request_number_of_items_to_buy is None else request_number_of_items_to_buy
        while to_buy > 0:
            self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_FIND_BROKER, repeat=RepeatMode.DONT_REPEAT,
                                                   threshold=0.77, delay=SERVER_REACT_DELAY)
            for i in range(5):
                rect = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_FIND_BROKER,
                                                                    repeat=RepeatMode.DONT_REPEAT, threshold=0.77)
                click = action_factory.new_action().mouse((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2 + 90 + i * 44)
                self._get_player_toolkit().call_player_action(click, delay=CLICK_DELAY)
                click = action_factory.new_action().mouse((rect.x1 + rect.x2) // 2 + 5, (rect.y1 + rect.y2) // 2 + 90 + i * 44 - 5)
                self._get_player_toolkit().call_player_action(click, delay=CLICK_DELAY)
                self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_BUY_BROKER, repeat=RepeatMode.DONT_REPEAT,
                                                       threshold=0.77, delay=SERVER_REACT_DELAY + random() * 3.0)
                to_buy -= 1
                if to_buy == 0:
                    break

    def toggle_bags(self):
        self._get_player_toolkit().call_player_action(self.__toggle_bags, delay=UI_REACT_DELAY)

    def trade_items_to_first_in_group(self, request_number_of_items_to_trade: int, receiving_player: IPlayer):
        click_person_l = action_factory.new_action().mouse(64, 296, button='left')
        click_person_r = action_factory.new_action().mouse(64, 296, button='right')
        receiver = PlayerScriptingToolkit(self._get_runtime(), self._get_toolkit(), receiving_player)
        sx, sy = self._get_player().get_inputs().screen.bags_item_1[0]
        dx = self._get_player().get_inputs().screen.bag_slot_size
        dy = self._get_player().get_inputs().screen.bag_slot_size
        w = self._get_player().get_inputs().screen.bags_width[0]
        items_traded = 0
        while items_traded < request_number_of_items_to_trade:
            items_in_this_trade = 12
            trade_open_attempts = 5
            while trade_open_attempts > 0:
                self._get_player_toolkit().call_player_action(click_person_l, delay=CLICK_DELAY)
                self._get_player_toolkit().call_player_action(click_person_r, delay=SERVER_REACT_DELAY)
                if self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_PLAYER_MENU_TRADE, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY):
                    break
                trade_open_attempts -= 1
            assert trade_open_attempts > 0
            self.toggle_bags()
            while items_in_this_trade > 0 and items_traded < request_number_of_items_to_trade:
                x = sx + (items_traded % w) * dx
                y = sy + (items_traded // w) * dy
                mouse_move_click = action_factory.new_action().mouse(x=x, y=y, modifiers='alt')
                self._get_player_toolkit().call_player_action(mouse_move_click)
                items_in_this_trade -= 1
                items_traded += 1
            self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_TAB_TRADE, repeat=RepeatMode.DONT_REPEAT, delay=0.0)
            self._get_player_toolkit().assert_click_match(pattern=ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT, repeat=RepeatMode.REPEAT_ON_FAIL, delay=2.0)
            self.toggle_bags()
            receiver.try_close_all_access()
            receiver.assert_click_match(pattern=ui_patterns.PATTERN_TAB_TRADE, repeat=RepeatMode.DONT_REPEAT)
            receiver.assert_click_match(pattern=ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT, repeat=RepeatMode.REPEAT_ON_FAIL, delay=UI_REACT_DELAY)


class ProcessItems(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit, ability: IAbilityLocator):
        Procedure.__init__(self, scripting)
        self.__toggle_bags = action_factory.new_action().append(self._get_player().get_inputs().special.open_bags)
        self.__process_ability = ability.resolve_for_player(self._get_player())

    def toggle_bags(self):
        self._get_player_toolkit().call_player_action(self.__toggle_bags, delay=UI_REACT_DELAY)

    def _get_ability(self) -> Optional[IAbility]:
        return self.__process_ability

    def _call_ability(self) -> bool:
        if not self._get_ability():
            return False
        self._get_player_toolkit().call_player_action(self.__process_ability.get_action(), delay=1.5)
        return True

    def _click_ok_all(self) -> bool:
        pattern = MatchPattern.by_tags([ui_patterns.PATTERN_BUTTON_TEXT_OK,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE,
                                        ])
        result = self._get_player_toolkit().click_match(pattern=pattern, repeat=RepeatMode.REPEAT_ON_SUCCESS,
                                                        max_clicks=5, threshold=0.85, delay=UI_REACT_DELAY)
        return result

    def _click_ok_accept_all(self) -> bool:
        pattern = MatchPattern.by_tags([ui_patterns.PATTERN_BUTTON_TEXT_OK,
                                        ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE,
                                        ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT,
                                        ])
        result = self._get_player_toolkit().click_match(pattern=pattern, repeat=RepeatMode.REPEAT_ON_SUCCESS,
                                                        max_clicks=5, threshold=0.85, delay=SERVER_REACT_DELAY)
        return result


class ProcessBagsOfItems(ProcessItems):
    def __init__(self, scripting: PlayerScriptingToolkit, ability: IAbilityLocator, max_items: Optional[int] = None):
        ProcessItems.__init__(self, scripting, ability)
        self.__max_items = max_items

    def process_bag_of_items(self, request_number_of_items_to_process: Optional[int] = None) -> bool:
        if not self._get_ability():
            return False
        if self.__max_items is not None:
            request_number_of_items_to_process = self.__max_items
        sx, sy = self._get_player().get_inputs().screen.bags_item_1[0]
        x = sx
        y = sy
        dx = self._get_player().get_inputs().screen.bag_slot_size
        dy = self._get_player().get_inputs().screen.bag_slot_size
        w = self._get_player().get_inputs().screen.bags_width[0]
        h = 13 if self._get_player().is_main_player() else 8
        max_failures = 3
        items_to_process = w * h if request_number_of_items_to_process is None else request_number_of_items_to_process
        process_fails = 0
        success = True
        for i in range(h):
            self._get_player_toolkit().try_close_all_access()
            for j in range(w):
                if not self._call_ability():
                    success = False
                    break
                self._get_player_toolkit().click_at(x, y, delay=1.0)
                self._get_player_toolkit().move_mouse_to_middle()
                success = self._click_ok_all()
                if success:
                    self._click_ok_accept_all()
                    items_to_process -= 1
                    process_fails = 0
                else:
                    process_fails += 1
                x += dx
                if process_fails > max_failures or items_to_process == 0:
                    break
                self._get_player_toolkit().sleep(0.5)
            y += dy
            x = sx
            if process_fails > max_failures or items_to_process == 0:
                break
        self._click_ok_accept_all()
        return success


class ProcessOneItem(ProcessItems):
    def __init__(self, scripting: PlayerScriptingToolkit, ability: IAbilityLocator):
        ProcessItems.__init__(self, scripting, ability)

    def process_one_item(self, bag_loc: BagLocation) -> bool:
        if not self._get_ability():
            return False
        if not self._call_ability():
            return False
        x, y = bag_loc.get_item_screen_coords()
        self._get_player_toolkit().click_at(x, y, delay=1.5)
        self._get_player_toolkit().move_mouse_to_middle()
        confirmed = self._click_ok_all()
        if confirmed:
            self._get_player_toolkit().move_mouse_to_middle()
            self._click_ok_accept_all()
        return confirmed
