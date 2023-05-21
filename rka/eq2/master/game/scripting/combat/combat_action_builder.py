from __future__ import annotations

import inspect
import re
import time
import typing
from typing import Callable, Optional, List, Match, Union

import regex

from rka.components.events import Event
from rka.components.resources import Resource
from rka.components.ui.capture import Rect, CaptureArea, CaptureMode, CaptureWindowFlags
from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.engine.task import Task, FilterTask
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.interfaces import IPlayerSelector, IPlayer, IEffectBuilder, IAbilityLocator
from rka.eq2.master.game.scripting import RaidSlotInfo
from rka.eq2.master.game.scripting.combat import logger, ICombatPhase, CombatPhaseActions, CombatPhaseAction
from rka.eq2.master.game.scripting.combat.combat_actions import MainProcessorTaskAction, DynamicMainProcessorTaskAction, PlayerEffectAction, CombatantEffectAction, SchedulerTaskAction, \
    SetTargetAction, FormationAction, MovementAction, TriggerAction, ParseTriggerAction, OffZoneCombatAction, ScriptStopperAction, AutoattackModeAction, DelayedStartStopAction, \
    MasterEventStartStopAction, ClientEventStartStopAction, StopWhenNoMoreClientEventsAction, FlagSettingAction, BoundScriptAction, NotificationAction, GameSettingAction, ParseTriggerStartStopAction
from rka.eq2.master.game.scripting.script_task import ScriptTask, ScriptMultiExclusionGuard, ScriptMultiQueue, IScriptTaskFactory
from rka.eq2.master.screening.screen_reader_events import ScreenReaderEvents
from rka.eq2.master.triggers import ITrigger
from rka.eq2.master.triggers.trigger import Trigger
from rka.eq2.master.triggers.trigger_subscribers import EventSubscriberToolkit
from rka.eq2.shared.client_combat import ClientCombatParserEvents
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.flags import MutableFlags
from rka.util.util import RateGuard


class CombatPhaseActionBuilder:
    def __init__(self, phase: ICombatPhase, actions: CombatPhaseActions):
        assert isinstance(phase, ICombatPhase)
        assert isinstance(actions, CombatPhaseActions)
        self.__phase = phase
        self.__actions = actions
        self.__script_guards = ScriptMultiExclusionGuard(phase)
        self.__script_queues = ScriptMultiQueue(phase)

    def __add_phase_action(self, action: CombatPhaseAction):
        self.__actions.add(action)

    # ========================== scripts, tasks and processing
    def add_preemptive_script(self, key: str, script: Union[IScriptTaskFactory, ScriptTask], restart_delay: float):
        action = BoundScriptAction(self.__phase, key, self.__script_guards.get_guard(key, restart_delay), script)
        self.__add_phase_action(action)

    def add_queued_script(self, key: str, script: Union[IScriptTaskFactory, ScriptTask]):
        action = BoundScriptAction(self.__phase, key, self.__script_queues.get_queue(key), script)
        self.__add_phase_action(action)

    def add_main_processor_task(self, task: Task):
        action = MainProcessorTaskAction(self.__phase, task)
        self.__add_phase_action(action)

    def add_dynamic_processor_task(self, task_factory_method: Callable[[ICombatPhase], Task]):
        action = DynamicMainProcessorTaskAction(self.__phase, task_factory_method)
        self.__add_phase_action(action)

    def add_repeated_task(self, task: Callable, repeat_rate: float, baseline=SchedulerTaskAction.SchedulingBaseline.FROM_STARTED):
        action = SchedulerTaskAction(self.__phase, task, repeat_rate, repeat_rate, baseline)
        self.__add_phase_action(action)

    def add_single_task(self, task: Callable, delay: float, baseline=SchedulerTaskAction.SchedulingBaseline.FROM_STARTED):
        action = SchedulerTaskAction(self.__phase, task, delay, None, baseline)
        self.__add_phase_action(action)

    def add_custom_action(self, action: CombatPhaseAction):
        self.__add_phase_action(action)

    # ========================== player and combatant state and manipulation
    def add_player_effect(self, effect: IEffectBuilder, player_sel: IPlayerSelector):
        action = PlayerEffectAction(self.__phase, effect, player_sel)
        self.__add_phase_action(action)

    def add_combatant_effect(self, combatant_name: str, effect: IEffectBuilder):
        action = CombatantEffectAction(self.__phase, combatant_name, effect)
        self.__add_phase_action(action)

    def add_target(self, target_name: str, targetting_players: Optional[IPlayerSelector] = None, repeat_rate: Optional[float] = None,
                   delay: Optional[float] = None):
        # by default, local players wont be included (if targetting_players is None)
        action = SetTargetAction(self.__phase, target_name=target_name, targetting_players=targetting_players, repeat_rate=repeat_rate, delay=delay)
        self.__add_phase_action(action)

    def add_target_boss(self, targetting_players: Optional[IPlayerSelector] = None, repeat_rate: Optional[float] = None, delay: Optional[float] = None):
        self.add_target(self.__phase.get_combat_script().get_combatant_name(), targetting_players, repeat_rate, delay)

    def add_opt_target(self, opt_target_name: str, targetting_players: Optional[IPlayerSelector] = None, repeat_rate: Optional[float] = None,
                       delay: Optional[float] = None):
        # by default, local players wont be included (if targetting_players is None)
        action = SetTargetAction(self.__phase, opt_target_name=opt_target_name, targetting_players=targetting_players, repeat_rate=repeat_rate, delay=delay)
        self.__add_phase_action(action)

    def add_target_through(self, target_name: str, through_player_sel: IPlayerSelector, targetting_players: Optional[IPlayerSelector] = None,
                           repeat_rate: Optional[float] = None, delay: Optional[float] = None):
        action = SetTargetAction(self.__phase, target_name=target_name, targetting_players=targetting_players, through_player_sel=through_player_sel,
                                 repeat_rate=repeat_rate, delay=delay)
        self.__add_phase_action(action)

    # ========================== detriments and curses
    @DeprecationWarning
    def add_detect_raid_detrims_old(self, task: Callable[[List[RaidSlotInfo]], None], detrim_tag: Resource, check_period=3.0, check_pause=5.0):
        last_successful_check = 0.0

        def detection_task():
            now = time.time()
            nonlocal last_successful_check
            if now - last_successful_check < check_pause:
                return
            psf = self.__phase.get_combat_script().get_local_player_scripting_framework()
            raid_slots = psf.get_raid_window_detriments(detrim_tag)
            if raid_slots:
                last_successful_check = now
                task(raid_slots)

        action = SchedulerTaskAction(self.__phase, detection_task, check_period, check_period, SchedulerTaskAction.SchedulingBaseline.FROM_STARTED)
        self.__add_phase_action(action)

    def add_detect_raid_detrims(self, task: Callable[[List[RaidSlotInfo]], None], detrim_tag: Resource, check_period=3.0, check_pause=5.0):
        def _get_raid_check_area(player_: IPlayer):
            psf_ = self.__phase.get_combat_script().get_player_scripting_framework(player_)
            area = psf_.get_raid_window_area(winflags=CaptureWindowFlags.IGNORE_NOT_MATCHING)
            return area

        def _event_receied(event_: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
            player_ = self.__phase.get_runtime().player_mgr.get_player_by_client_id(event_.client_id)
            psf_ = self.__phase.get_combat_script().get_player_scripting_framework(player_)
            raid_slot_infos = psf_.get_selected_raid_window_members_infos(event_.location_rects)
            task(raid_slot_infos)

        with self.add_new_trigger(f'raid detrim check for {detrim_tag}') as trigger:
            local_player = self.__phase.get_local_player()
            EventSubscriberToolkit.add_screen_event_to_trigger(trigger=trigger, client_ids=[local_player], tag=detrim_tag, area_source=_get_raid_check_area,
                                                               check_period=check_period, event_period=check_pause, max_matches=24)
            trigger.add_action(_event_receied)

    def add_detect_personal_detrim(self, players: IPlayerSelector, task: Callable[[IPlayer, Rect], None], detrim_tag: Resource, check_period=3.0, check_pause=5.0):
        def _event_receied(event_: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
            player_ = self.__phase.get_runtime().player_mgr.get_player_by_client_id(event_.client_id)
            task(player_, event_.location_rects[0])

        def _area_source(player_: IPlayer) -> CaptureArea:
            window_area = CaptureArea(mode=CaptureMode.GRAY, wintitle=EQ2_WINDOW_NAME, winflags=CaptureWindowFlags.IGNORE_NOT_MATCHING)
            return window_area.capture_rect(player_.get_inputs().screen.detrim_list_window, relative=True)

        with self.add_new_trigger(f'personal detrim check for {detrim_tag}') as trigger:
            EventSubscriberToolkit.add_screen_event_to_trigger(trigger=trigger, client_ids=players, tag=detrim_tag, area_source=_area_source,
                                                               check_period=check_period, event_period=check_pause, max_matches=1)
            trigger.add_action(_event_receied)
        self.add_close_all_access()

    def add_detect_target_buff(self, players: IPlayerSelector, task: Callable[[IPlayer, Rect], None], detrim_tag: Resource, check_period=3.0, check_pause=5.0):
        def _event_receied(event_: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
            player_ = self.__phase.get_runtime().player_mgr.get_player_by_client_id(event_.client_id)
            task(player_, event_.location_rects[0])

        def _area_source(player_: IPlayer) -> CaptureArea:
            window_area = CaptureArea(mode=CaptureMode.COLOR, wintitle=EQ2_WINDOW_NAME, winflags=CaptureWindowFlags.IGNORE_NOT_MATCHING)
            return window_area.capture_rect(player_.get_inputs().screen.target_buff_window, relative=True)

        with self.add_new_trigger(f'target buff check for {detrim_tag}') as trigger:
            EventSubscriberToolkit.add_screen_event_to_trigger(trigger=trigger, client_ids=players, tag=detrim_tag, area_source=_area_source,
                                                               check_period=check_period, event_period=check_pause, max_matches=1)
            trigger.add_action(_event_receied)

    def add_detect_target_casting(self, players: IPlayerSelector, task: Callable[[IPlayer, Rect], None], detrim_tag: Resource, check_period=1.0, check_pause=15.0):
        def _event_receied(event_: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
            player_ = self.__phase.get_runtime().player_mgr.get_player_by_client_id(event_.client_id)
            task(player_, event_.location_rects[0])

        def _area_source(player_: IPlayer) -> CaptureArea:
            window_area = CaptureArea(mode=CaptureMode.BW, wintitle=EQ2_WINDOW_NAME, winflags=CaptureWindowFlags.IGNORE_NOT_MATCHING)
            return window_area.capture_rect(player_.get_inputs().screen.target_casting_bar, relative=True)

        with self.add_new_trigger(f'target casting check for {detrim_tag}') as trigger:
            EventSubscriberToolkit.add_screen_event_to_trigger(trigger=trigger, client_ids=players, tag=detrim_tag, area_source=_area_source,
                                                               check_period=check_period, event_period=check_pause, max_matches=1)
            trigger.add_action(_event_receied)

    def add_disable_autocuring(self):
        self.add_flag_setting(MutableFlags.ENABLE_AUTOCURE, False)

    def add_disable_group_cures(self):
        no_group_cures = FilterTask(AbilityFilter().no_group_cures(), description='no group cures', duration=-1.0)
        self.add_main_processor_task(no_group_cures)

    # ========================== location and movement
    def add_formation(self, formation_id: str, anchor: bool):
        action = FormationAction(self.__phase, formation_id, anchor)
        self.__add_phase_action(action)

    def add_location_check(self, location_name: str, player_sel: Optional[IPlayerSelector] = None):
        action = MovementAction(self.__phase, move_type=MovementAction.MovementType.CHECK, location_name=location_name, players_sel=player_sel)
        self.__add_phase_action(action)

    def add_move_to_location(self, location_name: str, player_sel: Optional[IPlayerSelector] = None):
        action = MovementAction(self.__phase, move_type=MovementAction.MovementType.MOVE, location_name=location_name, players_sel=player_sel)
        self.__add_phase_action(action)

    def add_anchor_to_location(self, location_name: str, player_sel: Optional[IPlayerSelector] = None):
        action = MovementAction(self.__phase, move_type=MovementAction.MovementType.ANCHOR, location_name=location_name, players_sel=player_sel)
        self.__add_phase_action(action)

    # ========================== trigger factories
    def add_trigger(self, trigger: ITrigger):
        action = TriggerAction(self.__phase, trigger)
        self.__add_phase_action(action)

    def add_player_parse_triggers(self, pattern: str, preparsed_log: bool, action: Callable[[ClientEvents.PARSER_MATCH], None],
                                  player_filter: Optional[Callable[[IPlayer], bool]] = None, repeat_period=0.0, delay=0.0):
        action = ParseTriggerAction(self.__phase, pattern=pattern, preparsed_log=preparsed_log, player_filter=player_filter,
                                    action=action, repeat_period=repeat_period, delay=delay)
        self.__add_phase_action(action)

    def add_new_trigger(self, name: str):
        trigger = Trigger(name)
        actions = self.__actions
        phase = self.__phase

        class TriggerBuilder:
            def __enter__(self) -> ITrigger:
                return trigger

            def __exit__(self, exc_type, exc_val, exc_tb):
                actions.add(TriggerAction(phase, trigger))

        return TriggerBuilder()

    def add_new_emote_trigger(self, emote_rgx: str,
                              action: Union[Callable[[], None], Callable[[ChatEvents.EMOTE], None], Callable[[ChatEvents.EMOTE, Optional[Match]], None]],
                              action_delay=0.0, only_local=True, guard_inverval: Optional[float] = None) -> ITrigger:
        if guard_inverval:
            guard = RateGuard(guard_inverval)
        arg_count = len(inspect.signature(action).parameters)
        assert 0 <= arg_count <= 2

        def event_handler(event: ChatEvents.EMOTE):
            match = regex.search(emote_rgx, event.emote, flags=regex.IGNORECASE)
            if not match and emote_rgx.lower() not in event.emote.lower():
                return
            if guard_inverval and not guard.next():
                logger.info(f'Rejected by guard: {self.__phase.get_description()}')
                return
            called = False
            signature = inspect.signature(action)
            if arg_count == 0:
                action()
                called = True
            elif arg_count == 1:
                for param in signature.parameters.values():
                    if param.annotation is ChatEvents.EMOTE:
                        action(event)
                        called = True
                        break
                    if param.annotation is regex.Match or param.annotation is re.Match or param.annotation is typing.Match:
                        action(match)
                        called = True
                        break
            else:
                action(event, match)
                called = True
            if not called:
                logger.warn(f'Did not find appropriate parameters to call action {signature.parameters}, for {emote_rgx}')

        trigger = Trigger(emote_rgx)
        if only_local:
            trigger.add_bus_event(ChatEvents.EMOTE(to_local=True))
        else:
            trigger.add_bus_event(ChatEvents.EMOTE())
        trigger.add_action(event_handler, delay=action_delay)
        self.__add_phase_action(TriggerAction(self.__phase, trigger))
        return trigger

    # ========================== combat and ability control
    def add_offzone_combat(self):
        action = OffZoneCombatAction(self.__phase)
        self.__add_phase_action(action)

    def add_autoattack_mode(self, mode: int):
        action = AutoattackModeAction(self.__phase, mode)
        self.__add_phase_action(action)

    def add_disable_melee(self):
        self.add_dynamic_processor_task(lambda phase: FilterTask(AbilityFilter().non_hostile_ca(
            except_player=phase.get_local_player()),
            description='no CAs', duration=15.0))

    def add_disable_aoe(self):
        self.add_dynamic_processor_task(lambda phase: FilterTask(AbilityFilter().non_hostile_aoe(
            except_player=phase.get_local_player()),
            description='no AOEs', duration=15.0))

    def add_disable_ascensions(self):
        self.add_main_processor_task(FilterTask(AbilityFilter().no_ascensions_except([]), 'no ascensions', -1.0))

    def add_disable_specific_abilities(self, abilities: List[IAbilityLocator]):
        self.add_main_processor_task(FilterTask(AbilityFilter().dont_cast_abilities(abilities), 'no specified abilities', -1.0))

    # ========================== other actions
    def add_close_all_access(self):
        def _close_all_access():
            for player in self.__phase.get_phase_participants(include_local=False):
                if player.get_player_info().membership:
                    continue
                psf = self.__phase.get_combat_script().get_player_scripting_framework(player)
                psf.try_close_all_access()

        self.add_single_task(_close_all_access, delay=0.0)

    def add_flag_setting(self, flag: MutableFlags, value: bool):
        action = FlagSettingAction(self.__phase, flag, value)
        self.__add_phase_action(action)

    def add_game_command_setting(self, on_command: str, off_command: str, local_player: bool, remote_players: bool):
        action = GameSettingAction(self.__phase, on_command, off_command, local_player, remote_players)
        self.__add_phase_action(action)

    def add_notification(self, message: Optional[Union[str, Callable[[], str]]] = None):
        if not message:
            message = f'{self.__phase.get_combat_script().get_combatant_name()} in {self.__phase.get_combat_script().get_zone_name()}'
        action = NotificationAction(self.__phase, message)
        self.__add_phase_action(action)

    def add_script_extension(self, helper: CombatScriptBuilderCustomAction):
        self.__add_phase_action(helper)
        helper.build_phase(self)

    # ========================== combat script control
    def add_script_stopper(self):
        action = ScriptStopperAction(self.__phase)
        self.__add_phase_action(action)

    def start_by_master_event(self, event: Event):
        action = MasterEventStartStopAction(self.__phase, event, True, False)
        self.__add_phase_action(action)

    def start_by_client_event(self, event: ClientEvent):
        action = ClientEventStartStopAction(self.__phase, event, True, False)
        self.__add_phase_action(action)

    def start_by_parsefilter(self, parse_filter: str, preparsed_log: bool):
        action = ParseTriggerStartStopAction(phase=self.__phase, pattern=parse_filter, preparsed_log=preparsed_log, player_filter=None,
                                             starting_trigger=True, ending_trigger=False)
        self.__add_phase_action(action)

    def start_by_combatant(self, combatant_name: str):
        event = ClientCombatParserEvents.COMBATANT_JOINED(combatant_name=combatant_name)
        self.start_by_client_event(event)

    def start_by_delay(self, delay: float):
        action = DelayedStartStopAction(self.__phase, delay, True, False)
        self.__add_phase_action(action)

    def end_by_master_event(self, event: Event):
        action = MasterEventStartStopAction(self.__phase, event, False, True)
        self.__add_phase_action(action)

    def end_by_client_event(self, event: ClientEvent):
        action = ClientEventStartStopAction(self.__phase, event, False, True)
        self.__add_phase_action(action)

    def end_by_client_combat_expire(self):
        action = StopWhenNoMoreClientEventsAction(self.__phase, event=ClientCombatParserEvents.COMBAT_PARSE_TICK(), delay=10.0)
        self.__add_phase_action(action)

    def end_by_parsefilter(self, parse_filter: str, preparsed_log: bool):
        action = ParseTriggerStartStopAction(phase=self.__phase, pattern=parse_filter, preparsed_log=preparsed_log, player_filter=None,
                                             starting_trigger=False, ending_trigger=True)
        self.__add_phase_action(action)

    def end_by_duration(self, duration: float):
        action = DelayedStartStopAction(self.__phase, duration, False, True)
        self.__add_phase_action(action)


class CombatScriptBuilderCustomAction(CombatPhaseAction):
    def __init__(self, name: str, phase: ICombatPhase):
        CombatPhaseAction.__init__(self, phase)
        self.__name = name

    def build_phase(self, builder: CombatPhaseActionBuilder):
        raise NotImplementedError()

    def _get_description(self) -> str:
        return self.__name

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        pass

    def _phase_stopped(self):
        pass
