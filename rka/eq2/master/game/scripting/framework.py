from __future__ import annotations

import random
import time
from threading import RLock
from typing import Optional, Tuple, Callable, Dict, List, Union

from rka.components.cleanup import CloseGuard
from rka.components.concurrency.workthread import RKAWorkerThreadPool, RKAFuture
from rka.components.resources import Resource
from rka.components.ui.capture import Offset, Rect, CaptureArea, MatchPattern, CaptureMode, CaptureWindowFlags
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.rka_constants import CLICK_DELAY
from rka.eq2.master import IRuntime, HasRuntime
from rka.eq2.master.game.ability import AbilityPriority
from rka.eq2.master.game.ability.ability_locator import AbilityLocator
from rka.eq2.master.game.ability.generated_abilities import CommonerAbilities
from rka.eq2.master.game.engine.filter_tasks import ConfirmAbilityCasting
from rka.eq2.master.game.engine.request import CastOneAndExpire, Request
from rka.eq2.master.game.engine.resolver import AbilityResolver
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer, TOptionalPlayer, IAbility
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import ScriptException, logger, RepeatMode, MovePrecision, RotatePrecision, RaidSlotInfo
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.patterns.detrims.bundle import detrim_patterns
from rka.eq2.master.game.scripting.procedures.common import GetCommandResult, ClickWhenCursorType
from rka.eq2.master.game.scripting.procedures.items import BagActionsProcedure
from rka.eq2.master.game.scripting.procedures.login import LoginProcedure
from rka.eq2.master.game.scripting.procedures.movement import LocationCheckerProcedure, MovementProcedureFactory
from rka.eq2.master.game.scripting.procedures.tradeskill import BuyFromMerchantProcedure, CraftProcedure
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.game.scripting.toolkit import ScriptingToolkit, PlayerScriptingToolkit
from rka.eq2.master.game.scripting.util.ts_script_utils import compare_normal_item_names
from rka.eq2.shared.flags import MutableFlags


class ScriptingFramework:
    # static thread pool
    __workers = RKAWorkerThreadPool('Player Scripting Task', pool_size=12)

    def __init__(self, runtime_ref: HasRuntime, scripting: ScriptingToolkit):
        self.__runtime_ref = runtime_ref
        self.__scripting = scripting
        self.__player_scripting_frameworks: Dict[IPlayer, PlayerScriptingFramework] = dict()
        self.__workers = ScriptingFramework.__workers
        self.__parallel_tasks: List[RKAFuture] = list()
        self.__parallel_tasks_lock = RLock()
        self.__parallel_tasks_wait_guard: Optional[CloseGuard] = None

    def resolve_player(self, player: TOptionalPlayer) -> IPlayer:
        runtime = self.__runtime_ref.get_runtime()
        if isinstance(player, str):
            player = runtime.player_mgr.get_player_by_name(player_name=player)
            if not player:
                raise ScriptException(f'could not resolve player {player}')
        elif player is None:
            overlay_id = runtime.overlay.get_selection_id()
            player = runtime.player_mgr.get_online_player_by_overlay_id(overlay_id)
            assert player, self
        if player.get_status() < PlayerStatus.Online:
            logger.warn(f'player {player} not online')
            return player
        return player

    def get_player_scripting_framework(self, player: TOptionalPlayer, allow_offline=False) -> PlayerScriptingFramework:
        player = self.resolve_player(player)
        if not player.is_online() and not allow_offline:
            raise ValueError(player)
        if player not in self.__player_scripting_frameworks:
            self.__player_scripting_frameworks[player] = PlayerScriptingFramework(self.__runtime_ref, self.__scripting, player)
            # TODO probably unnecessary
            if MutableFlags.REFOCUS_MAIN_WINDOW_FOR_SCRIPTS and player.is_local():
                # send control to local window immediately
                self.__runtime_ref.get_runtime().master_bridge.send_switch_to_client_window(player=player, sync=True)
            # if MutableFlags.REFOCUS_MAIN_WINDOW_FOR_SCRIPTS and player.is_online():
            #     self.__player_scripting_frameworks[player].activate_window()
        return self.__player_scripting_frameworks[player]

    # noinspection PyMethodMayBeStatic
    def __get_task_wrapper(self, task: Callable, args, kwargs) -> Callable:
        def task_wrapper():
            try:
                return task(*args, **kwargs)
            except ScriptException as e:
                logger.warn(f'Task-Script failed: {task}, {args}, {kwargs}, {e}')
                raise e
            except Exception as e:
                logger.error(f'Task failed: {task}, {args}, {kwargs}, {e}')
                raise e

        return task_wrapper

    def run_concurrent_task(self, task: Callable, *args, **kwargs) -> RKAFuture:
        task_wrapper = self.__get_task_wrapper(task, args, kwargs)
        future = self.__workers.push_task(task_wrapper)
        if not future:
            raise ScriptException('worker closed/full')
        future.set_description(str(task))
        with self.__parallel_tasks_lock:
            self.__parallel_tasks.append(future)
        return future

    def wait_for_parallel_tasks(self, timeout=0.0):
        if timeout <= 0.0:
            timeout = 300.0
        while True:
            with self.__parallel_tasks_lock:
                if not self.__parallel_tasks:
                    break
                task = self.__parallel_tasks.pop()
                if task.is_completed():
                    continue
                guard = self.__parallel_tasks_wait_guard = CloseGuard(task.get_description(), close_callback=lambda _task=task: _task.cancel_future())
            task.get_result(timeout=timeout, guard=guard)

    def stop_waiting_for_parallel_tasks(self):
        with self.__parallel_tasks_lock:
            self.__parallel_tasks.clear()
            if self.__parallel_tasks_wait_guard:
                self.__parallel_tasks_wait_guard.close()
                self.__parallel_tasks_wait_guard = None


class PlayerScriptingFramework(PlayerScriptingToolkit):
    def __init__(self, runtime_ref: HasRuntime, scripting: ScriptingToolkit, player: IPlayer):
        PlayerScriptingToolkit.__init__(self, runtime_ref, scripting, player)

    def __str__(self) -> str:
        return f'PlayerScriptingFramework({self.get_player()})'

    def run_script(self, script: ScriptTask):
        self.get_runtime().processor.run_task(script)

    def get_command_result(self, command: str, result_re: str) -> Optional[str]:
        cmd_procedure = GetCommandResult(self, command, result_re)
        return cmd_procedure.run_command()

    def get_ready_ability_request(self, ability_locator: AbilityLocator, target: Optional[str] = None, duration=10.0) -> Optional[Request]:
        ability = ability_locator.resolve_for_player(self.get_player())
        if not ability:
            logger.info(f'Unable to resolve {ability_locator} for {self.get_player()}')
            return None
        if target:
            ability = ability.prototype(target=target)
        request = CastOneAndExpire(ability, resolver=AbilityResolver(), duration=duration)
        abilities = request.get_available_ability_bag()
        if abilities.is_empty():
            logger.info(f'No available abilities of {ability_locator} for {self.get_player()}')
            self.get_runtime().processor.print_debug()
            return None
        abilities = self.get_runtime().processor.apply_current_filters(abilities)
        abilities = abilities.get_bag_by_reusable()
        if abilities.is_empty():
            logger.info(f'{ability_locator} for {self.get_player()} not available')
            return None
        return request

    def cast_ability_async(self, ability_locator: AbilityLocator, target: Optional[str] = None, duration=10.0) -> bool:
        request = self.get_ready_ability_request(ability_locator, target, duration)
        if not request:
            return False
        self.get_runtime().processor.run_request(request)
        return True

    def cast_ability_sync(self, ability_locator: AbilityLocator, target: Optional[str] = None, waiting=10.0) -> bool:
        ability = ability_locator.resolve_for_player(self.get_player())
        if not ability:
            return False
        confirmation = ConfirmAbilityCasting(ability, duration=waiting)
        self.get_runtime().processor.run_filter(confirmation)
        if not self.cast_ability_async(ability_locator, target, duration=waiting):
            confirmation.expire()
            return False
        if not confirmation.wait_for_ability(timeout=waiting):
            return False
        self.sleep(ability.get_casting_secs())
        return True

    def cast_custom_ability_async(self, ability: IAbility):
        request = self.get_runtime().request_factory.custom_ability_request(ability)
        self.get_runtime().processor.run_request(request)

    def cast_custom_ability_sync(self, ability: IAbility) -> bool:
        request = self.get_runtime().request_factory.custom_ability_request(ability)
        waiting = request.get_duration()
        confirmation = ConfirmAbilityCasting(ability, waiting)
        self.get_runtime().processor.run_filter(confirmation)
        self.get_runtime().processor.run_request(request)
        if not confirmation.wait_for_ability(timeout=waiting):
            return False
        self.sleep(ability.get_casting_secs())
        return True

    def leave_group(self) -> bool:
        ac_leave_group = self.build_command('leavegroup')
        return self.player_bool_action(ac_leave_group)

    # result: login_was_required, login_succeeded
    def login_async(self, target_player: Optional[IPlayer] = None) -> Tuple[bool, bool]:
        target_player = target_player if target_player else self.get_player()
        login_procedure = LoginProcedure(self, target_player=target_player)
        if target_player != self.get_player():
            if not login_procedure.is_in_login_screen() and not login_procedure.is_in_character_screen():
                self.logout()
        login_was_required, login_succeeded = login_procedure.login_player()
        logger.info(f'Player {target_player} login result {login_was_required}, {login_succeeded}')
        if login_was_required and not login_succeeded:
            logger.warn(f'Player {target_player} login failed {True}, {False}')
            return True, False
        if not login_was_required:
            logger.info(f'Player {target_player} async login succeeded {False}, {True}')
            return False, True
        logger.info(f'Player {target_player} async login succeeded {True}, {True}')
        return True, True

    def player_processing_start_random_wait(self):
        local_random = random.Random()
        local_random.seed(time.time())
        self.sleep(local_random.uniform(0.0, 5.0) + local_random.choice([0.0, 10.0, 20.0]))

    @staticmethod
    def __complete_login_of_changed_player(target_psf: Optional[PlayerScriptingFramework]) -> bool:
        if not target_psf:
            return False
        target_player = target_psf.get_player()
        # wait a bit until the player comes online - this is due to delay of switching players
        if not CloseGuard(name=f'Complete login of {target_player}').meet_condition(lambda: target_player.is_online(), timeout=10.0):
            logger.warn(f'Changed player {target_player} still offline')
            return False
        login_procedure = LoginProcedure(target_psf)
        login_completed, _ = login_procedure.wait_for_login_complete()
        if not login_completed:
            logger.warn(f'Changed player {target_player} wait for login complete failed')
            return False
        player_change = login_procedure.login_cooldown()
        if player_change:
            logger.warn(f'Changed player {target_player} wait for login cooldown failed')
            return False
        if target_player.get_status() < PlayerStatus.Logged:
            logger.warn(f'Changed player {target_player} wrong status after cooldown: {target_player.get_status().name}')
            return False
        return True

    # result: player_changed, login_was_required, login_succeeded
    def login_sync(self, target_psf: Optional[PlayerScriptingFramework] = None) -> Tuple[bool, bool, bool]:
        target_player = target_psf.get_player() if target_psf else self.get_player()
        login_was_required, login_succeeded = self.login_async(target_player=target_player)
        if not login_was_required or not login_succeeded:
            # either no login needed, or it failed
            return False, login_was_required, login_succeeded
        # wait for login to start
        login_procedure = LoginProcedure(self, target_player=target_player)
        _, player_changed = login_procedure.wait_for_login_start()
        if player_changed:
            logger.warn(f'During login start of {target_player}, {self.get_player()} logged out')
            login_succeeded = PlayerScriptingFramework.__complete_login_of_changed_player(target_psf)
            return True, True, login_succeeded
        # wait for login to complete
        login_completed, player_changed = login_procedure.wait_for_login_complete()
        if player_changed:
            logger.warn(f'During login complete of {target_player}, {self.get_player()} logged out')
            login_succeeded = PlayerScriptingFramework.__complete_login_of_changed_player(target_psf)
            return True, True, login_succeeded
        # wait for login to take effect (cooldown)
        player_changed = login_procedure.login_cooldown()
        if player_changed:
            logger.warn(f'During login cooldown of {target_player}, {self.get_player()} logged out')
            login_succeeded = PlayerScriptingFramework.__complete_login_of_changed_player(target_psf)
            return True, True, login_succeeded
        if target_player.get_status() < PlayerStatus.Logged:
            logger.warn(f'Player {self.get_player()} login failed after cooldown')
            return False, True, False
        return False, True, True

    def logout(self) -> bool:
        self.leave_group()
        ac_leave_group = self.build_command('camp login')
        if not self.player_bool_action(ac_leave_group):
            return False
        self.sleep(40.0)
        return self.get_player().get_status() < PlayerStatus.Logged

    def wait_for_zoning_complete(self) -> bool:
        login_helper = LoginProcedure(self)
        login_started, _ = login_helper.wait_for_login_start()
        if login_started:
            login_completed, _ = login_helper.wait_for_login_complete()
            if login_completed:
                login_helper.zoning_cooldown()
            return login_completed
        return True

    def go_to_home_city(self) -> bool:
        if not self.cast_ability_sync(CommonerAbilities.call_to_home):
            logger.warn(f'Could not send {self.get_player()} to home city')
            return False
        return self.wait_for_zoning_complete()

    def go_to_guild_hall(self) -> bool:
        if not self.cast_ability_sync(CommonerAbilities.call_to_guild_hall):
            logger.warn(f'Could not send {self.get_player()} to guild hall')
            return False
        return self.wait_for_zoning_complete()

    def stop_combat(self):
        self.get_runtime().request_ctrl.request_stop_combat(self.get_player())

    def stop_all_noncontrol(self, duration: float):
        self.get_runtime().request_ctrl.request_stop_all_non_control(self.get_player(), duration)

    def stop_all(self, duration: float):
        self.get_runtime().request_ctrl.request_stop_all(self.get_player(), duration)

    def send_tell(self, target: str, tells: Union[str, List[str]]) -> bool:
        action = self.build_multicommand(tells, f'tell {target}')
        return self.player_bool_action(action)

    def group_say(self, tells: Union[str, List[str]]) -> bool:
        action = self.build_multicommand(tells, 'gsay')
        return self.player_bool_action(action)

    def raid_say(self, tells: Union[str, List[str]]) -> bool:
        action = self.build_multicommand(tells, 'raidsay')
        return self.player_bool_action(action)

    def invite_to_group(self, target_player: str) -> bool:
        action = self.build_command(f'invite {target_player}')
        return self.player_bool_action(action)

    def follow(self, target_player: str) -> bool:
        action = self.build_command(f'follow {target_player}')
        return self.player_bool_action(action)

    def stop_follow(self) -> bool:
        action = self.build_command(f'stopfollow')
        return self.player_bool_action(action)

    def free_move(self):
        action = self.build_command(f'ics_combatautoface 0\nics_playercombatautoface 0\nstand')
        return self.post_player_action(action)

    def cancel_maintained_spell(self, effect_id: int) -> bool:
        action = self.build_command(f'cancel_maintained {effect_id}')
        return self.player_bool_action(action)

    def recenter_camera(self) -> bool:
        action = self.build_command(f'camera_recenter')
        result = self.player_bool_action(action)
        self.get_scripting().sleep(0.3)
        return result

    def reset_zones(self) -> bool:
        action = self.build_command(f'reset_all_zone_timers yes')
        result = self.player_bool_action(action, delay=0.3)
        return result

    def try_close_all_windows(self, close_externals=False, max_clicks=10, click_delay=CLICK_DELAY) -> bool:
        if super().try_close_all_windows(close_externals, max_clicks, click_delay):
            self.move_mouse_to_middle()
            return True
        return False

    def select_destination_zone(self, position: int) -> bool:
        offset = Offset(0, 30 + (position - 1) * 16, anchor=Offset.REL_FIND_MID)
        return self.click_match(pattern=ui_patterns.PATTERN_GFX_SELECT_DESTINATION, repeat=RepeatMode.DONT_REPEAT, click_offset=offset)

    def get_location(self) -> Optional[Location]:
        locate = LocationCheckerProcedure(self)
        location = locate.get_location()
        if not location:
            self.get_runtime().overlay.log_event(f'Failed to get location', Severity.Normal)
        return location

    def move_to_location(self, location: Location, high_precision=True, allow_moving_backwards=False) -> bool:
        if not location:
            return False
        if not self.get_player().is_local():
            self.try_close_all_windows()
        movement = MovementProcedureFactory.create_movement_procedure(self)
        if allow_moving_backwards:
            movement.set_angle_for_moving_backwards(100.0)
        if high_precision:
            return movement.move_to_location(location, movement_precision=MovePrecision.HIGH, rotation_precision=RotatePrecision.HIGH)
        else:
            return movement.move_to_location(location, movement_precision=MovePrecision.NORMAL, rotation_precision=RotatePrecision.NORMAL)

    def navigate_to_location(self, location: Location, high_precision=True) -> bool:
        if not location:
            return False
        if not self.get_player().is_local():
            self.try_close_all_windows()
        movement = MovementProcedureFactory.create_navigation_procedure(self, final_loc_high_precision=high_precision, final_loc_rotation=True)
        return movement.navigate_to_location(location)

    def show_waypoint_to_location(self, location: Location):
        waypoint_cmd = 'waypoint ' + location.get_position().encode_location(game_format=True)
        self.command_async(waypoint_cmd)

    def buy_from_merchant(self, merchant_name: str, item_name: str, count=1) -> Optional[int]:
        buyer = BuyFromMerchantProcedure(self, merchant_name)
        bought_items = buyer.open_buy_close(item_name, count)
        if bought_items is None:
            return None
        if not bought_items:
            return 0
        matching_items_count = sum((1 if compare_normal_item_names(item_name, bought_item) else 0 for bought_item in bought_items))
        return matching_items_count

    def use_repair_bot(self) -> bool:
        self.try_close_all_windows()
        merchant_clicker = ClickWhenCursorType(self)
        vp_mid_x = self.get_player().get_inputs().screen.VP_W_center
        vp_mid_y = self.get_player().get_inputs().screen.VP_H_center
        merchant_clicker.click_when_cursor_type_is(ClickWhenCursorType.CURSOR_FP_MERCHANT, around_x=vp_mid_x, around_y=vp_mid_y)
        return self.click_match(pattern=ui_patterns.PATTERN_BUTTON_REPAIR_ALL, repeat=RepeatMode.REPEAT_ON_FAIL)

    def use_item_by_id(self, item_id: int, casting=3.0, min_state=PlayerStatus.Zoned) -> bool:
        ability = self.get_runtime().request_factory.custom_ability(self.get_player(), casting=casting, reuse=6.0, recovery=2.0, item_id=item_id,
                                                                    min_state=min_state, priority=AbilityPriority.SCRIPT)
        return self.cast_custom_ability_sync(ability)

    def use_ability_by_id(self, spell_id: int, casting=3.0, min_state=PlayerStatus.Zoned) -> bool:
        ability = self.get_runtime().request_factory.custom_ability(self.get_player(), casting=casting, reuse=5.0, recovery=2.0, ability_crc=spell_id,
                                                                    min_state=min_state, priority=AbilityPriority.SCRIPT)
        return self.cast_custom_ability_sync(ability)

    def use_item_in_bags(self, item_name: str, open_bags: bool, count=1, exact_name=True) -> int:
        bag_actions = BagActionsProcedure(self)
        return bag_actions.use_item_in_bags(item_name=item_name, open_bags=open_bags, count=count, exact_name=exact_name)

    def destroy_item_in_bags(self, item_name: str, open_bags: bool, count=1, exact_name=True) -> int:
        bag_actions = BagActionsProcedure(self)
        return bag_actions.destroy_item_in_bags(item_name=item_name, open_bags=open_bags, count=count, exact_name=exact_name)

    def craft_items(self, item_name: str, quanity: int) -> bool:
        remaining_quantity = quanity
        try:
            while remaining_quantity > 0:
                crafter = CraftProcedure(self)
                crafter.open_craft_station()
                crafter.select_crafting_item(recipe_filter=item_name)
                round_quantity = 1
                if remaining_quantity >= 10:
                    self.click_match(pattern=ui_patterns.PATTERN_GFX_CRAFT_QUANTITY_1, repeat=RepeatMode.DONT_REPEAT)
                    if self.click_match(pattern=ui_patterns.PATTERN_GFX_CRAFT_QUANTITY_DROPDOWN_10, repeat=RepeatMode.DONT_REPEAT):
                        round_quantity = 10
                crafter.craft_from_resources_view()
                remaining_quantity -= round_quantity
        except ScriptException:
            return False
        return True

    def has_detriment_type(self, detriment_type_tag: Resource) -> bool:
        self.try_close_all_access()
        player = self.get_player()
        area = self.get_capture_area(rect=player.get_inputs().screen.detrim_count_window)
        detrim_rect = self.find_match_by_tag(detriment_type_tag, area=area, repeat=RepeatMode.DONT_REPEAT)
        return detrim_rect is not None

    def detriment_find_location(self, detriment_tag: Resource) -> Optional[Rect]:
        self.try_close_all_access()
        player = self.get_player()
        area = self.get_capture_area(player.get_inputs().screen.detrim_list_window)
        detrim_rect = self.find_match_by_tag(detriment_tag, area=area, repeat=RepeatMode.DONT_REPEAT)
        return detrim_rect

    def detriment_tooltip_inspect(self, detriment_tag: Resource) -> bool:
        player = self.get_player()
        player_name = player.get_player_name()
        detrim_rect = self.detriment_find_location(detriment_tag)
        if not detrim_rect:
            logger.warn(f'No detriment {detriment_tag.resource_name} found on {player_name}')
            return False
        middle = detrim_rect.middle()
        return self.move_mouse_to(middle)

    def detriment_read_number(self, detriment_tag: Resource) -> Optional[int]:
        detrim_rect = self.detriment_find_location(detriment_tag)
        player = self.get_player()
        player_name = player.get_player_name()
        if not detrim_rect:
            logger.warn(f'No detriment {detriment_tag.resource_name} found on {player_name}')
            return None
        # hardcoded offsets for the location of detriment increments - depend on icon sizes
        number_rect = Rect(x1=detrim_rect.x1 + 13, y1=detrim_rect.y1 + 12, w=12, h=9)
        logger.debug(f'detriment_read_number: number_rect={number_rect}')
        number_capture = self.capture_box(number_rect, mode=CaptureMode.COLOR)
        logger.debug(f'detriment_read_number: number_capture={number_capture}')
        self.save_capture(number_capture, f'detrim_number-{self.get_player()}')
        digit_1_rect = Rect(x1=0, y1=0, w=6, h=number_rect.height())
        digit_2_rect = Rect(x1=6, y1=0, w=6, h=number_rect.height())
        logger.debug(f'detriment_read_number: digit_1_rect={digit_1_rect}, digit_2_rect={digit_2_rect}')
        digit_1 = self.ocr_single_digit(number_capture, description=f'{player_name}_1', rect=digit_1_rect, font_color=255)
        digit_2 = self.ocr_single_digit(number_capture, description=f'{player_name}_2', rect=digit_2_rect, font_color=255)
        if digit_1 is None:
            digit_1 = 0
        if digit_2 is None:
            logger.warn(f'detriment_read_number: No digit 2 found on {player_name}, detrim {detriment_tag}')
            return None
        return digit_1 * 10 + digit_2

    def find_raid_window_box(self) -> Optional[CaptureArea]:
        cached_raid_window_box = self.get_runtime().zonestate.get_cached_raidsetup_variable('raid_window_box')
        if cached_raid_window_box:
            logger.debug('Returning cached raid_window_box')
            return cached_raid_window_box
        player = self.get_player()
        screen_box = player.get_inputs().screen.get_screen_box()
        screen_area = self.get_capture_area(rect=screen_box, mode=CaptureMode.COLOR, relative=False)
        raid_window_stripe_box = self.find_match_by_tag(detrim_patterns.RAID_WINDOW_STRIPE, repeat=RepeatMode.DONT_REPEAT, area=screen_area)
        if not raid_window_stripe_box:
            logger.warn('Could not locate raid window')
            return None
        # using raid_window_stripe_box.x1 as left boundary, because capture will find the most top-left match
        raid_window_box = Rect(x1=raid_window_stripe_box.x1, y1=raid_window_stripe_box.y1, x2=screen_box.x2, y2=raid_window_stripe_box.y2)
        self.get_runtime().zonestate.cache_raidsetup_variable('raid_window_box', raid_window_box)
        return raid_window_box

    def get_raid_window_area(self, mode=CaptureMode.COLOR, winflags=CaptureWindowFlags.ACTIVATE_WINDOW) -> Optional[CaptureArea]:
        raid_window_box = self.find_raid_window_box()
        if not raid_window_box:
            return None
        player = self.get_player()
        screen_box = player.get_inputs().screen.get_screen_box()
        screen_area = self.get_capture_area(rect=screen_box, mode=mode, relative=False, winflags=winflags)
        raid_window_area = screen_area.capture_rect(raid_window_box, relative=True)
        return raid_window_area

    def get_raid_members_info(self) -> Dict[int, RaidSlotInfo]:
        """
        Return raid slot descriptions.
        Returns:
            mapping of slot-number to the respective RaidSlotInfo objects. Empty dict if any issue occured.
        """
        raid_member_map = self.get_runtime().zonestate.get_cached_raidsetup_variable('raid_member_map')
        if raid_member_map:
            logger.debug('Returning cached raid_member_map')
            return raid_member_map
        raid_window_area = self.get_raid_window_area()
        logger.debug(f'get_raid_members_info: raid_window_area={raid_window_area}')
        if not raid_window_area:
            return {}
        raid_member_map = dict.fromkeys(range(24), None)
        class_icons = {ui_patterns.RAID_WND_ARCHETYPE_ICON_PRIEST: GameClasses.Priest,
                       ui_patterns.RAID_WND_ARCHETYPE_ICON_FIGHTER: GameClasses.Fighter,
                       ui_patterns.RAID_WND_ARCHETYPE_ICON_SCOUT: GameClasses.Scout,
                       ui_patterns.RAID_WND_ARCHETYPE_ICON_MAGE: GameClasses.Mage}
        for class_icon, gameclass in class_icons.items():
            class_matches = self.find_multiple_match_by_pattern(pattern=MatchPattern.by_tag(class_icon), repeat=RepeatMode.DONT_REPEAT,
                                                                area=raid_window_area, max_matches=24)
            if not class_matches:
                continue
            for (tag, rect) in class_matches:
                slot_number = RaidSlotInfo.get_slot_number(raid_window_area.get_bounding_box(), rect)
                logger.debug(f'get_raid_members_info: tag={ui_patterns[tag].resource_name}, rect={rect}, slot={slot_number}')
                if slot_number not in raid_member_map:
                    logger.warn(f'Wrong slot number {slot_number}, raid_window_area={raid_window_area}, match_rect={rect} of tag {tag}')
                    continue
                raid_member_map[slot_number] = RaidSlotInfo(gameclass, 0, slot_number)
        ord_num = 0
        for slot_number in range(24):
            if not raid_member_map[slot_number]:
                logger.debug(f'Missing raid member at slot {slot_number}')
                continue
            raid_member_map[slot_number].ord_num = ord_num
            ord_num += 1
        self.get_runtime().zonestate.cache_raidsetup_variable('raid_member_map', raid_member_map)
        return raid_member_map

    def get_selected_raid_window_members_infos(self, raid_wnd_locations: List[Rect]) -> List[RaidSlotInfo]:
        if not raid_wnd_locations:
            return []
        raid_window_area = self.get_raid_window_area()
        if not raid_window_area:
            return []
        raid_members = self.get_raid_members_info()
        if not raid_members:
            return []
        raid_members_infos = list()
        for rect in raid_wnd_locations:
            slot_num = RaidSlotInfo.get_slot_number(raid_window_area.get_bounding_box(), rect)
            if slot_num not in raid_members or not raid_members[slot_num]:
                logger.warn(f'Raid slot info not found for slot {slot_num} with location {rect}')
                continue
            raid_slot = raid_members[slot_num]
            raid_members_infos.append(raid_slot)
        return raid_members_infos

    def get_raid_window_detriments(self, detriment_tag: Resource) -> List[RaidSlotInfo]:
        """
        Return raid slots which have the detriment present.
        Arguments:
            detriment_tag: resource tag for the detriment icon
        Returns:
            list of RaidSlotInfo objects describing those slots. Empty if could not detect raid positions.
        """
        raid_window_area = self.get_raid_window_area()
        if not raid_window_area:
            return []
        matches = self.find_multiple_match_by_pattern(pattern=MatchPattern.by_tag(detriment_tag), repeat=RepeatMode.DONT_REPEAT,
                                                      area=raid_window_area, max_matches=24)
        if not matches:
            return []
        locations = [location for (tag, location) in matches]
        return self.get_selected_raid_window_members_infos(locations)

    def take_screenshot(self) -> bool:
        return self.command_async('cl_screenshot')


class PlayerScriptTask(ScriptTask, ScriptingFramework):
    def __init__(self, description: Optional[str], duration: float):
        ScriptTask.__init__(self, description=description, duration=duration)
        ScriptingFramework.__init__(self, self, self)
        self.__running_players: List[IPlayer] = list()

    def get_running_players(self) -> List[IPlayer]:
        return list(self.__running_players)

    def __get_player_task_wrapper(self, player: IPlayer, task: Callable[[PlayerScriptingFramework], None]) -> Callable[[PlayerScriptingFramework], None]:
        def player_task_wrapper(psf: PlayerScriptingFramework):
            self.__running_players.append(player)
            try:
                task(psf)
            finally:
                self.__running_players.remove(player)

        return player_task_wrapper

    def run_concurrent_players(self, players: List[IPlayer], task: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        if task is None:
            task = self._run_player
        for player in players:
            psf = self.get_player_scripting_framework(player)
            player_task_wrapper = self.__get_player_task_wrapper(player, task)
            self.run_concurrent_task(player_task_wrapper, psf)

    def _on_run_completed(self):
        self.wait_for_parallel_tasks(timeout=self.get_duration())

    def _on_expire(self):
        ScriptingFramework.stop_waiting_for_parallel_tasks(self)

    def _run(self, runtime: IRuntime):
        raise NotImplementedError()

    def _run_player(self, psf: PlayerScriptingFramework):
        pass
