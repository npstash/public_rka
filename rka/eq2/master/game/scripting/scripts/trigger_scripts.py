from __future__ import annotations

import time
from threading import RLock
from typing import Optional, Callable, Union

import pyperclip

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events import Event
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityPriority
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.ability_locator import AbilityLocator
from rka.eq2.master.game.ability.generated_abilities import ItemsAbilities
from rka.eq2.master.game.engine.filter_tasks import ControlOnlyFilter
from rka.eq2.master.game.engine.request import CastAnyWhenReady
from rka.eq2.master.game.engine.resolver import AbilityResolver
from rka.eq2.master.game.engine.task import FilterTask, ExpireHook
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import ScriptGuard
from rka.eq2.master.game.scripting.framework import ScriptingFramework
from rka.eq2.master.game.scripting.scripts.inventory_scripts import DestroyItemInBags
from rka.eq2.master.game.scripting.scripts.ui_interaction_scripts import CureAnyVisibleCurses
from rka.eq2.master.game.scripting.toolkit import ScriptingToolkit
from rka.eq2.master.triggers import ITriggerWarningCodeFunctions
from rka.eq2.parsing.parsing_util import ParsingHelpers
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.shared_workers import shared_scheduler, shared_worker
from rka.log_configs import LOG_SCRIPTS
from rka.services.api.ps_connector import IPSConnector
from rka.services.broker import ServiceBroker

logger = LogService(LOG_SCRIPTS)


class _Decorators:
    @classmethod
    def sync(cls, trigger_script_fn: Callable):
        def wrapper(self, *args, **kwargs):
            shared_worker.push_task(lambda: trigger_script_fn(self, *args, **kwargs))

        return wrapper

    @classmethod
    def ignore_repeats(cls, period: float):
        def decorator(trigger_script_fn: Callable):
            last_call = [time.time()]

            def wrapper(self, *args, **kwargs):
                now = time.time()
                if now - last_call[0] <= period:
                    return
                last_call[0] = now
                shared_worker.push_task(lambda: trigger_script_fn(self, *args, **kwargs))

            return wrapper

        return decorator

    @classmethod
    def static_vars(cls, **static_kwargs):
        def decorator(trigger_script_fn: Callable):
            for k in static_kwargs:
                setattr(trigger_script_fn, k, static_kwargs[k])
            return trigger_script_fn

        return decorator


class Context:
    def __init__(self, player: IPlayer, event: Event, timestamp: float):
        self.player = player
        self.event = event
        self.timestamp = timestamp


class TriggerScripts(ScriptGuard, ITriggerWarningCodeFunctions):
    # single instance to preserve context variables; might be separated in future when multiple scripts run concurrently
    __instance = None
    __instance_lock = RLock()

    @staticmethod
    def get_trigger_scripts_instance(runtime: IRuntime) -> TriggerScripts:
        with TriggerScripts.__instance_lock:
            if TriggerScripts.__instance is None:
                TriggerScripts.__instance = TriggerScripts(runtime)
                TriggerScripts.__instance.register_events()
            return TriggerScripts.__instance

    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        # toolkit and framework can be used in calling thread, but its not recommended, because they may block or sleep
        self.scripting_toolkit = ScriptingToolkit(self)
        self.scripting_framework = ScriptingFramework(self.__runtime, self.scripting_toolkit)
        # futures
        self._cure_curse_future: Optional[RKAFuture] = None
        self._cure_detrim_future: Optional[RKAFuture] = None
        self._mage_cure_detrim_future: Optional[RKAFuture] = None
        self._deathsave_future: Optional[RKAFuture] = None
        self._next_cure_target: Optional[str] = None
        # other variables
        self._counter = 0
        self._time_measure_start = 0.0

    def is_script_action_allowed(self) -> bool:
        return True

    def register_events(self):
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.notify_new_zone)

    def notify_new_zone(self, _event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        self.__init__(self.__runtime)

    # noinspection PyMethodMayBeStatic
    def error(self, _player: IPlayer, event: Event, argument: Optional = None):
        logger.error(f'function not found for {event}, arg {argument}')

    def __get_player(self, ctx: Context, player_name: Optional[str]) -> IPlayer:
        if player_name:
            player_name = ParsingHelpers.get_canonical_player_name(ctx.player.get_player_name(), player_name)
        if player_name:
            player = self.__runtime.player_mgr.get_player_by_name(player_name)
        else:
            player = ctx.player
        if not player:
            logger.warn(f'Unrecognized player {player} / {player_name} in {ctx.event}')
            raise ValueError(player)
        return player

    # noinspection PyMethodMayBeStatic
    def __get_player_name(self, ctx: Context, player_name: Optional[str]) -> str:
        if player_name:
            return player_name
        return ctx.player.get_player_name()

    ## =============================== General usage ==================================================================
    def event_timer(self, ctx: Context, inctime_mins_str: Union[float, int, str] = 0.0):
        inctime_mins = float(inctime_mins_str)
        timer_name = ctx.player.get_zone()[:4] + '..' + ctx.player.get_zone()[-3:]
        self.__runtime.overlay.start_timer(timer_name, casting=inctime_mins * 60.0, duration=10 * 60.0, reuse=120 * 60.0, expire=30 * 60.0)

    def player_confirm(self, ctx: Context, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{ctx.player} confirmed', Severity.Normal)
        self.__runtime.request_ctrl.cancel_tasks_maintained_for_player(player)

    # noinspection PyMethodMayBeStatic
    def later(self, _ctx: Context, delay: float, cb: Callable):
        shared_scheduler.schedule(cb, delay=delay)

    def counter(self, _ctx: Context, counter_name: str, duration: float):
        old_timer_name = f'{counter_name}-{self._counter}'
        self.__runtime.overlay.del_timer(old_timer_name)
        self._counter += 1
        new_timer_name = f'{counter_name}-{self._counter}'
        self.__runtime.overlay.start_timer(new_timer_name, casting=0.0, duration=duration, reuse=0.0, expire=30.0)

    def time_watch_start(self, _ctx: Context):
        self._time_measure_start = time.time()

    def time_watch_end(self, _ctx: Context, label: Optional[str] = None):
        diff = time.time() - self._time_measure_start
        if label:
            message = f'DIFF ({label[:10]}): {diff:.1f}s'
        else:
            message = f'DIFF: {diff:.1f}s'
        self.__runtime.overlay.log_event(message, Severity.High)

    def clipboard(self, _ctx: Context, text: str):
        self.__runtime.overlay.log_event(f'copied {text}', Severity.Normal)
        pyperclip.copy(text)

    # noinspection PyMethodMayBeStatic
    def tts(self, _ctx: Context, text: str, urgent=False):
        self.__runtime.tts.say(text, interrupts=urgent)

    # noinspection PyMethodMayBeStatic
    def msg(self, _ctx: Context, text: str):
        self.__runtime.overlay.log_event(text, Severity.Normal)

    # noinspection PyMethodMayBeStatic
    def warning(self, _ctx: Context, text: str):
        self.__runtime.overlay.display_warning(text, duration=1.0)

    # noinspection PyMethodMayBeStatic
    def ps_tts(self, _ctx: Context, text: str):
        connector: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
        if not connector.send_tts(text):
            self.__runtime.tts.say(text)
            self.__runtime.overlay.log_event('Failed to use PS TTS', Severity.Normal)

    # noinspection PyMethodMayBeStatic
    def ps_msg(self, _ctx: Context, text: str):
        connector: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
        if not connector.send_message(text):
            self.__runtime.overlay.log_event(text, Severity.Normal)
            self.__runtime.overlay.log_event('Failed to use PS Msg', Severity.Normal)

    ## =============================== Blockers =======================================================================
    def player_stop_dps(self, ctx: Context, player_name: Optional[str] = None, duration=10.0):
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{player} stop dps', Severity.High)
        self.__runtime.request_ctrl.request_stop_combat(player, duration)

    def stop_dps(self, _ctx: Context, duration=10.0):
        self.__runtime.overlay.log_event(f'all stop dps', Severity.High)
        self.__runtime.request_ctrl.request_group_stop_combat(duration, False)

    def player_stop_everything(self, ctx: Context, player_name: Optional[str] = None, duration=10.0):
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{player} stop everything', Severity.High)
        self.__runtime.request_ctrl.request_stop_all(player, duration)

    def healers_stop_beneficials(self, _ctx: Context, duration=10.0):
        self.__runtime.overlay.log_event(f'healers stop beneficials', Severity.High)
        no_priest_beneficials = FilterTask(filter_cb=AbilityFilter().no_priest_beneficials(), description='no priest beneficials', duration=duration)
        self.__runtime.processor.run_auto(no_priest_beneficials)

    def player_stop_moving(self, ctx: Context, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{player} stop moving', Severity.High)
        self.__runtime.request_ctrl.request_player_dont_move(player, 10.0)

    def stop_curing(self, _ctx: Context, duration=15.0):
        self.__runtime.overlay.log_event(f'stop curing', Severity.High)
        no_cures = FilterTask(AbilityFilter().no_group_cures(), description='no cures', duration=duration)
        self.__runtime.processor.run_auto(no_cures)
        no_automatic_cures = FilterTask(AbilityFilter().no_automatic_cures(), description='no automatic cures', duration=duration)
        self.__runtime.processor.run_auto(no_automatic_cures)

    def dont_cure_player(self, ctx: Context, player_name: str, duration=10.0):
        player_name = ParsingHelpers.get_canonical_player_name(ctx.player.get_player_name(), player_name)
        self.__runtime.overlay.log_event(f'dont cure {player_name}', Severity.High)
        dont_cure_player = FilterTask(filter_cb=AbilityFilter().dont_cure_player(player_name),
                                      description=f'dont cure {player_name}', duration=duration)
        self.__runtime.processor.run_auto(dont_cure_player)

    def stop_powerfeed_player(self, ctx: Context, player_name: str, duration=10.0):
        player_name = ParsingHelpers.get_canonical_player_name(ctx.player.get_player_name(), player_name)
        self.__runtime.overlay.log_event(f'dont power feed {player_name}', Severity.High)
        dont_feed_player = FilterTask(filter_cb=AbilityFilter().dont_powerfeed_player(player_name),
                                      description=f'dont powerfeed {player_name}', duration=duration)
        self.__runtime.processor.run_auto(dont_feed_player)

    def stop_powerfeed(self, _ctx: Context, duration=10.0):
        self.__runtime.overlay.log_event(f'dont power feed', Severity.High)
        dont_feed = FilterTask(filter_cb=AbilityFilter().dont_powerfeed(), description=f'dont powerfeed', duration=duration)
        self.__runtime.processor.run_auto(dont_feed)

    def cancel_spellcasting(self, ctx: Context):
        self.__runtime.request_ctrl.request_cancel_spellcasting(ctx.player)

    ## =============================== Item manipulation ==============================================================
    def destroy_item(self, ctx: Context, item_name: str):
        self.__runtime.overlay.log_event(f'{ctx.player} destroy item {item_name}', Severity.High)
        if ctx.player.is_local():
            self.__runtime.alerts.minor_trigger()
            return
        self.__runtime.processor.run_auto(DestroyItemInBags(ctx.player, item_name))

    def use_item_on_self_until_confirmed(self, ctx: Context, item_id: Union[int, str], player_name: Optional[str] = None):
        item_id = int(item_id)
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{player} use item {item_id} on self', Severity.High)
        if player.is_local():
            self.__runtime.alerts.minor_trigger()
            return
        self.__runtime.combatstate.set_players_target(players=player, target_name=player.get_player_name())
        self.__runtime.request_ctrl.request_cancel_spellcasting(player)
        duration = 6.0
        control_filter = ControlOnlyFilter(player, duration=duration)
        ability = self.__runtime.request_factory.custom_ability(player, casting=4.0, reuse=4.0, recovery=2.0, item_id=item_id, priority=AbilityPriority.SCRIPT)
        request = CastAnyWhenReady(ability, resolver=AbilityResolver(), duration=duration)
        restore_target = ExpireHook(lambda: self.__runtime.combatstate.set_players_target(players=player, target_name=None),
                                    description=f'restore target of {player}', duration=duration)
        self.__runtime.request_ctrl.maintain_task_for_player(player, task=control_filter)
        self.__runtime.request_ctrl.maintain_task_for_player(player, task=request)
        self.__runtime.request_ctrl.maintain_task_for_player(player, task=restore_target)

    def use_item(self, ctx: Context, item_id: Union[int, str], player_name: Optional[str] = None):
        item_id = int(item_id)
        player = self.__get_player(ctx, player_name)
        if not player:
            # probably other player
            return
        self.__runtime.overlay.log_event(f'{player} use item {item_id}', Severity.Normal)
        if player.is_local():
            self.__runtime.alerts.minor_trigger()
            return
        self.__runtime.request_ctrl.request_custom_ability(player=player, item_id=item_id, casting=5.0, reuse=3.0, recovery=3.0)

    def __apply_damage_type(self, ability: AbilityLocator):
        self.__runtime.overlay.log_event(f'{ability.get_canonical_name()} requested', Severity.Normal)
        reqest = self.__runtime.request_factory.zoned_cast_one(ability_locator=ability, player=None, duration=10.0)
        self.__runtime.processor.run_request(reqest)

    def magic_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.voidlink)

    def mind_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.mindworms)

    def divine_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.divine_embrace)

    def fire_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.flames_of_yore)

    def cold_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.embrace_of_frost)

    def poison_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.poison_fingers)

    def disease_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.noxious_effusion)

    def crushing_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.essence_of_smash)

    def slashing_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.prepaded_cutdown)

    def piercing_damage(self, _ctx: Context):
        self.__apply_damage_type(ItemsAbilities.piercing_gaze)

    ## =============================== Curing =========================================================================
    def group_cure(self, _ctx: Context, delay=0.0):
        severity = Severity.High if delay > 10.0 else Severity.Normal
        self.__runtime.overlay.log_event(f'Group cure in {delay}s', severity)
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_cure_now(False), delay=delay)

    def cure_curse(self, ctx: Context, delay=0.5, player_name: Optional[str] = None):
        if self._cure_curse_future:
            self._cure_curse_future.cancel_future()
        player_name = self.__get_player_name(ctx, player_name)
        severity = Severity.High if delay > 10.0 else Severity.Normal
        self.__runtime.overlay.log_event(f'Cure Curse {ctx.player}', severity)
        self._cure_curse_future = shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_cure_curse_target(player_name), delay=delay)

    def cure_all_curses(self, ctx: Context, delay=0.0):
        if not ctx.player.is_local():
            logger.warn(f'NOT curing all curses - only trigger from local player allowed')
            return
        player_sel = self.__runtime.playerselectors.all_zoned()
        script = CureAnyVisibleCurses(player_sel).delay_next_start(delay)
        self.__runtime.processor.run_auto(script)

    def cure_curse_from_class(self, ctx: Context, delay=0.5, class_name: Optional[str] = None):
        archetype_name = class_name.lower().capitalize()
        game_class = GameClasses.get_class_by_name(archetype_name)
        player = self.__runtime.player_mgr.find_first_player(lambda p: p.get_status() >= PlayerStatus.Zoned and p.is_alive() and p.is_class(game_class))
        if player:
            self.cure_curse(ctx, delay, player.get_player_name())
        else:
            self.__runtime.overlay.log_event(f'No player for class {class_name}', Severity.High)

    def cure(self, ctx: Context, delay=0.5, player_name: Optional[str] = None):
        if self._cure_detrim_future:
            self._cure_detrim_future.cancel_future()
        player_name = self.__get_player_name(ctx, player_name)
        severity = Severity.High if delay > 10.0 else Severity.Normal
        self.__runtime.overlay.log_event(f'Cure {player_name}', severity)
        self._cure_detrim_future = shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_cure_target(player_name), delay=delay)

    def mage_cure(self, ctx: Context, delay=0.5, player_name: Optional[str] = None):
        if self._mage_cure_detrim_future:
            self._mage_cure_detrim_future.cancel_future()
        player_name = self.__get_player_name(ctx, player_name)
        severity = Severity.High if delay > 10.0 else Severity.Normal
        self.__runtime.overlay.log_event(f'Mage Cure {player_name}', severity)
        self._cure_detrim_future = shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_mage_cure_target(player_name), delay=delay)

    def set_cure_target(self, ctx: Context, player_name: str):
        player_name = ParsingHelpers.get_canonical_player_name(ctx.player.get_player_name(), player_name)
        self.__runtime.overlay.log_event(f'Cure target set {player_name}', Severity.Normal)
        self._next_cure_target = player_name

    def cure_preset_target(self, ctx: Context, delay=0.0):
        self.cure(ctx, delay, self._next_cure_target)
        self._next_cure_target = None

    ## =============================== Stunning, interrupting ==========================================================
    def dispel(self, _ctx: Context, delay=0.5):
        self.__runtime.overlay.log_event(f'Dispel!', Severity.Normal)
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_dispel(check_repeat_rate=False), delay=delay)

    def interrupt(self, _ctx: Context, delay=0.5):
        self.__runtime.overlay.log_event(f'Interrupt!', Severity.Normal)
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_interrupt(check_repeat_rate=False), delay=delay)

    def stun(self, _ctx: Context, delay=0.5):
        self.__runtime.overlay.log_event(f'Stun!', Severity.Normal)
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_stun(check_repeat_rate=False), delay=delay)

    def intercept(self, ctx: Context, player_name: str, delay=0.5):
        player_name = ParsingHelpers.get_canonical_player_name(ctx.player.get_player_name(), player_name)
        self.__runtime.overlay.log_event(f'Intercept on {player_name}!', Severity.Normal)
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_intercept(player_name), delay=delay)

    ## =============================== Emergencies ======================================================================
    def save_group(self, _ctx: Context, delay=0.0):
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_emergency(), delay=delay)

    def power_feed(self, _ctx: Context, delay=0.0):
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_group_power_feed_now(False), delay=delay)

    def reactive_heal(self, _ctx: Context, delay=0.0):
        shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_reactive_heals(), delay=delay)

    def deathsave(self, ctx: Context, delay=0.5, player_name: Optional[str] = None):
        if self._deathsave_future:
            self._deathsave_future.cancel_future()
        player_name = self.__get_player_name(ctx, player_name)
        severity = Severity.High if delay > 10.0 else Severity.Normal
        self.__runtime.overlay.log_event(f'Deathsave {player_name}', severity)
        self._deathsave_future = shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_deathsave(player_name), delay=delay)

    def too_much_damage(self, ctx: Context, threshold: Union[int, str]):
        if not isinstance(ctx.event, CombatParserEvents.COMBAT_HIT):
            logger.warn(f'too_much_damage: unexpected event: {ctx.event}')
            return
        threshold = int(threshold)
        if ctx.event.damage > threshold:
            self.__runtime.alerts.minor_trigger()
            self.__runtime.overlay.log_event(f'{ctx.event.target_name} was hit for {ctx.event.damage}!', Severity.Normal)

    ## =============================== Player interaction =============================================================
    def player_raid_say(self, ctx: Context, say: str, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        psf = self.scripting_framework.get_player_scripting_framework(player)
        psf.raid_say(say)

    def player_group_say(self, ctx: Context, say: str, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        psf = self.scripting_framework.get_player_scripting_framework(player)
        psf.group_say(say)

    def player_command(self, ctx: Context, command: str, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        self.__runtime.overlay.log_event(f'{player} command: {command}', Severity.Normal)
        if player.is_local():
            self.__runtime.alerts.major_trigger()
            return
        psf = self.scripting_framework.get_player_scripting_framework(player)
        psf.command_async(command)

    ## =============================== Movement =======================================================================
    def move_to_location_except_player(self, ctx: Context, player_name: str, location_name: str):
        location = self.__runtime.zonemaps.get_location_by_name(location_name)
        if not location:
            location = Location.decode_location(location)
        if not location:
            logger.warn(f'Location not found {location_name}')
            return
        for player in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned):
            except_player = self.__get_player(ctx, player_name)
            if player == except_player:
                continue
            if player.is_local():
                continue
            self.__runtime.automation.autopilot.player_move_to_location(player, location, only_position=True)

    def move_to_location_player(self, ctx: Context, player_name: str, location_name: str):
        location = self.__runtime.zonemaps.get_location_by_name(location_name)
        if not location:
            location = Location.decode_location(location)
        if not location:
            logger.warn(f'Location not found {location_name}')
            return
        player = self.__get_player(ctx, player_name)
        if player.is_local():
            return
        self.__runtime.automation.autopilot.player_move_to_location(player, location, only_position=True)

    def move_to_location(self, _ctx: Context, location_name: str):
        location = self.__runtime.zonemaps.get_location_by_name(location_name)
        if not location:
            location = Location.decode_location(location)
        if not location:
            logger.warn(f'Location not found {location_name}')
            return
        for player in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned):
            if player.is_local():
                continue
            self.__runtime.automation.autopilot.player_move_to_location(player, location, only_position=True)

    def sprint(self, ctx: Context, duration=10.0, player_name: Optional[str] = None):
        player = self.__get_player(ctx, player_name)
        if player.is_local():
            return
        self.__runtime.request_ctrl.request_toggle_sprint(player)
        if duration and duration > 0.0:
            shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_toggle_sprint(), delay=duration)

    def all_sprint(self, _ctx: Context, duration=10.0):
        self.__runtime.request_ctrl.request_toggle_sprint()
        if duration and duration > 0.0:
            shared_scheduler.schedule(lambda: self.__runtime.request_ctrl.request_toggle_sprint(), delay=duration)

    def waypoint(self, _ctx: Context, loc_str: str):
        loc = Location.decode_location(loc_str)
        if not loc:
            logger.warn(f'Wrong location {loc}')
            return
        main_player = self.__runtime.playerstate.get_main_player()
        psf = self.scripting_framework.get_player_scripting_framework(main_player)
        psf.show_waypoint_to_location(loc)
