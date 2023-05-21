import enum
from enum import auto, Enum
from typing import Callable, Optional, List, Dict, Set, Union

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events import Event
from rka.components.events.event_system import EventSystem
from rka.eq2.master.game.engine.task import Task
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.interfaces import IPlayerSelector, IPlayer, IEffectBuilder, EffectTarget, IEffect
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.location.location_streams import LocationStreamConnector
from rka.eq2.master.game.player import AutoattackMode
from rka.eq2.master.game.scripting.combat import logger, ICombatPhase, CombatPhaseAction
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.script_task import ScriptTask, IScriptQueue, IScriptTaskFactory
from rka.eq2.master.game.scripting.scripts.game_command_scripts import RunCommand
from rka.eq2.master.game.scripting.scripts.movement_scripts import FollowLocationsScript
from rka.eq2.master.game.scripting.scripts.ooz_control_scripts import OOZAutoCombat
from rka.eq2.master.triggers import ITrigger
from rka.eq2.master.triggers.trigger import PlayerTrigger
from rka.eq2.master.triggers.trigger_subscribers import EventSubscriberToolkit
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.client_events import ClientEvents


class GroupRaidPlayersCheckerAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, check_raid: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__check_raid = check_raid
        self.__has_other_players: Optional[bool] = None

    def has_other_players(self) -> Optional[bool]:
        if self.__has_other_players is None:
            if self.__check_raid:
                logger.info('Receiving raid setup')
                players = self.get_runtime().zonestate.get_players_in_raid()
            else:
                logger.info('Receiving group setup')
                players = self.get_runtime().zonestate.get_players_in_main_group()
            self.__has_other_players = False
            for player_name in players:
                if not self.get_runtime().player_mgr.get_player_by_name(player_name):
                    self.__has_other_players = True
                    break
        logger.debug(f'Receiving raid/group setup: has_others={self.__has_other_players}')
        return self.__has_other_players

    def _get_description(self) -> str:
        return f'[GroupRaidPlayersCheckerAction check_raid={self.__check_raid}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__has_other_players = None
        participants = self.get_phase().get_phase_participants(include_local=True).resolve_players()
        if len(participants) == 6 and not self.__check_raid:
            # all players are own
            self.__has_other_players = False
            return
        psf = self.get_combat_script().get_local_player_scripting_framework()
        if psf:
            if self.__check_raid:
                psf.command_async('whoraid')
            else:
                psf.command_async('whogroup')

    def _phase_stopped(self):
        pass


class BoundScriptAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, name: str, script_queue: IScriptQueue, script: Union[IScriptTaskFactory, ScriptTask]):
        CombatPhaseAction.__init__(self, phase)
        self.__name = name
        self.__script = script if isinstance(script, ScriptTask) else None
        self.__script_factory = script if isinstance(script, IScriptTaskFactory) else None
        self.__script_queue = script_queue

    def _get_description(self) -> str:
        return f'[BoundScriptAction name={self.__name}, script={self.__script}, script_factory={self.__script_factory}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        if self.__script_factory:
            self.__script = self.__script_factory.create_script(self.__name)
        if self.__script:
            self.__script_queue.start_next_script(self.__script)

    def _phase_stopped(self):
        if self.__script:
            self.__script.expire()


class MainProcessorTaskAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, task: Task):
        CombatPhaseAction.__init__(self, phase)
        self.__task = task

    def _get_description(self) -> str:
        return f'[MainProcessorTaskAction task={self.__task}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.get_runtime().request_ctrl.run_and_sustain(self.__task, restart_when_expired=False)

    def _phase_stopped(self):
        self.__task.expire()


class DynamicMainProcessorTaskAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, task_factory_method: Callable[[ICombatPhase], Task]):
        CombatPhaseAction.__init__(self, phase)
        self.__task_factory_method = task_factory_method
        self.__task: Optional[Task] = None

    def _get_description(self) -> str:
        return f'[DynamicMainProcessorTaskAction task={self.__task_factory_method}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        task = self.__task = self.__task_factory_method(self.get_phase())
        self.get_runtime().request_ctrl.run_and_sustain(task, restart_when_expired=True)

    def _phase_stopped(self):
        task = self.__task
        if task:
            self.__task.expire()
        self.__task = None


class PlayerEffectAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, effect_builder: IEffectBuilder, player_sel: IPlayerSelector):
        CombatPhaseAction.__init__(self, phase)
        self.__effect_builder = effect_builder
        self.__player_sel = player_sel
        self.__effects: List[IEffect] = list()

    def _get_description(self) -> str:
        return f'[PlayerEffectAction task={self.__effect_builder}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        participants = self.get_phase().get_phase_participants().resolve_players()
        for player in self.__player_sel.resolve_players():
            if player in participants:
                effect_target = player.as_effect_target()
                effect = self.__effect_builder.build_effect(effect_mgr=self.get_runtime().effects_mgr, sustain_target=effect_target, sustain_source=effect_target)
                effect.start_effect()
                self.__effects.append(effect)

    def _phase_stopped(self):
        for effect in self.__effects:
            effect.cancel_effect()
        self.__effects.clear()


class CombatantEffectAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, combatant_name: str, effect_builder: IEffectBuilder):
        CombatPhaseAction.__init__(self, phase)
        self.__combatant_name = combatant_name
        self.__effect_builder = effect_builder
        self.__effect: Optional[IEffect] = None
        self.__event = CombatEvents.ENEMY_KILL(enemy_name=combatant_name)

    def _get_description(self) -> str:
        return f'[CombatantEffectAction task={self.__effect}, self={self}]'

    def _phase_prepared(self):
        pass

    def __stop_effect(self, _event: Optional[CombatEvents.ENEMY_KILL] = None):
        if self.__effect:
            self.__effect.cancel_effect()
        self.__effect = None
        EventSystem.get_main_bus().unsubscribe_all(type(self.__event), self.__stop_effect)

    def _phase_started(self):
        self.__stop_effect()
        effect_source = EffectTarget(npc_name=self.__combatant_name)
        self.__effect = self.__effect_builder.build_effect(effect_mgr=self.get_runtime().effects_mgr, sustain_target=None, sustain_source=effect_source)
        self.__effect.start_effect()
        EventSystem.get_main_bus().subscribe(self.__event, self.__stop_effect)

    def _phase_stopped(self):
        self.__stop_effect()


class OffZoneCombatAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase):
        CombatPhaseAction.__init__(self, phase)
        self.__oozc_script: Optional[Task] = None

    def _get_description(self) -> str:
        return f'[OffZoneCombatAction script={self.__oozc_script}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        participants_sel = self.get_phase().get_phase_participants(include_local=False)
        self.__oozc_script = OOZAutoCombat(participants_sel)
        self.get_runtime().request_ctrl.processor.run_auto(self.__oozc_script)

    def _phase_stopped(self):
        if self.__oozc_script:
            self.__oozc_script.expire()
            self.__oozc_script = None


class ScriptStopperAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase):
        CombatPhaseAction.__init__(self, phase)

    # noinspection PyMethodMayBeStatic
    def __script_stopper(self, task: Task, participants: Set[IPlayer]):
        if isinstance(task, PlayerScriptTask):
            players = task.get_running_players()
            for player in players:
                if player in participants:
                    task.expire()
                    break

    def _get_description(self) -> str:
        return f'[ScriptStopperAction self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        participants = self.get_combat_script().get_script_participants(include_local=True).resolve_players()
        self.get_runtime().processor.visit_tasks(lambda task: self.__script_stopper(task, set(participants)))

    def _phase_stopped(self):
        pass


class SchedulerTaskAction(CombatPhaseAction):
    class SchedulingBaseline(enum.Enum):
        FROM_PREPARED = auto()
        FROM_STARTED = auto()
        FROM_ENDED = auto()

    def __init__(self, phase: ICombatPhase, task: Callable, delay: float, period: Optional[float], baseline: SchedulingBaseline):
        CombatPhaseAction.__init__(self, phase)
        self.__task = task
        self.__delay = delay
        self.__period = period
        self.__baseline = baseline
        self.__future: Optional[RKAFuture] = None

    def __cleanup(self):
        if self.__future:
            self.__future.cancel_future()
            self.__future = None

    def __run_scheduler_task(self):
        self.__task()
        if self.__period is not None:
            self.__future = self.get_combat_script().get_scheduler().schedule(self.__run_scheduler_task, self.__period)

    def __schedule_task(self):
        self.__future = self.get_combat_script().get_scheduler().schedule(self.__run_scheduler_task, self.__delay)

    def _get_description(self) -> str:
        return f'[SchedulerTaskAction task={self.__task}, delay={self.__delay}, period={self.__period}, self={self}]'

    def _phase_prepared(self):
        if self.__baseline == SchedulerTaskAction.SchedulingBaseline.FROM_PREPARED:
            self.__cleanup()
            self.__schedule_task()

    def _phase_started(self):
        if self.__baseline == SchedulerTaskAction.SchedulingBaseline.FROM_STARTED:
            self.__cleanup()
            self.__schedule_task()

    def _phase_stopped(self):
        self.__cleanup()
        if self.__baseline == SchedulerTaskAction.SchedulingBaseline.FROM_ENDED:
            self.__schedule_task()


class SetTargetAction(CombatPhaseAction):
    DEFAULT_DELAY = 1.0

    def __init__(self, phase: ICombatPhase,
                 target_name: Optional[str] = None,
                 opt_target_name: Optional[str] = None,
                 targetting_players: Optional[IPlayerSelector] = None,
                 through_player_sel: Optional[IPlayerSelector] = None,
                 repeat_rate: Optional[float] = None,
                 delay: Optional[float] = None):
        CombatPhaseAction.__init__(self, phase)
        assert through_player_sel is None or target_name, f'Targetting through requires primary target, {self}'
        assert target_name or opt_target_name, f'Either set primary or optional target, {self}'
        self.__target_name = target_name
        self.__opt_target_name = opt_target_name
        self.__targetting_players = targetting_players
        self.__through_player_sel = through_player_sel
        self.__repeat_rate = repeat_rate
        self.__delay = delay if delay is not None else SetTargetAction.DEFAULT_DELAY
        self.__future: Optional[RKAFuture] = None
        self.__players_with_changed_target: List[IPlayer] = list()

    def __cleanup(self):
        if self.__future:
            self.__future.cancel_future()
            self.__future = None

    def __apply_targets(self):
        if self.__targetting_players:
            participants = self.get_phase().get_phase_participants(include_local=True).resolve_players()
            targetting_players = set(self.__targetting_players.resolve_players())
            participants = list(targetting_players.intersection(set(participants)))
        else:
            participants = self.get_phase().get_phase_participants(include_local=False).resolve_players()
        logger.info('SetTargetAction: participants: ' + ', '.join((str(participant) for participant in participants)))
        if self.__through_player_sel:
            through_players = self.__through_player_sel.resolve_players()
            logger.info('SetTargetAction: through: ' + ', '.join((str(participant) for participant in through_players)))
            # here target_name wont be None due to assert
            self.get_runtime().combatstate.target_through(through_players=through_players, players=participants,
                                                          target_name=self.__target_name, repeat_rate=self.__repeat_rate)
        elif self.__target_name or not self.__opt_target_name:
            logger.info(f'SetTargetAction: target: {self.__target_name}')
            # allow default target (target_name is None) if there are no optional targets
            self.get_runtime().combatstate.set_players_target(players=participants, target_name=self.__target_name, repeat_rate=self.__repeat_rate)
        if self.__opt_target_name:
            logger.info(f'SetTargetAction: opt target: {self.__opt_target_name}')
            self.get_runtime().combatstate.add_optional_players_target(players=participants, opt_target_name=self.__opt_target_name,
                                                                       repeat_rate=self.__repeat_rate)
        self.__players_with_changed_target = list(participants)

    def _get_description(self) -> str:
        return f'[SetTargetAction target={self.__target_name}, through_player={self.__through_player_sel}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__cleanup()
        logger.info(f'SetTargetAction in: {self.__delay}')
        if self.__delay:
            self.__future = self.get_combat_script().get_scheduler().schedule(self.__apply_targets, delay=self.__delay)
        else:
            self.__apply_targets()

    def _phase_stopped(self):
        self.__cleanup()
        if self.__players_with_changed_target:
            self.get_runtime().combatstate.clear_player_targets(players=self.__players_with_changed_target)
            if self.__through_player_sel:
                self.get_runtime().combatstate.clear_player_targets(players=self.__through_player_sel.resolve_players())
            self.__players_with_changed_target = list()


class MovementAction(CombatPhaseAction):
    MAX_HORIZONTAL_DISTANCE = 40.0
    MAX_VERTICAL_DISTANCE = 10.0

    class MovementType(Enum):
        CHECK = auto()
        MOVE = auto()
        ANCHOR = auto()

    def __init__(self, phase: ICombatPhase, move_type: MovementType, location_name: str, players_sel: Optional[IPlayerSelector] = None):
        CombatPhaseAction.__init__(self, phase)
        self.__location_name = location_name
        self.__move_type = move_type
        self.__players_sel = players_sel
        self.__moving_players: List[IPlayer] = list()

    def __get_player_locs(self, players: List[IPlayer]) -> Dict[IPlayer, Optional[Location]]:
        from rka.eq2.master.game.scripting.scripts.location_scripts import ReadLocation
        player_locs = dict()
        for player in players:
            sink = LocationStreamConnector()
            sink.set_max_pop_wait(3.0)
            script = ReadLocation(player, sink)
            self.get_runtime().processor.run_auto(script)
            location = sink.pop_location()
            player_locs[player] = location
        return player_locs

    def _get_description(self) -> str:
        return f'[MovementAction location_name={self.__location_name}, move_type={self.__move_type}, players={self.__players_sel}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        location = self.get_combat_script().get_location(self.__location_name)
        if not location:
            logger.warn(f'No location "{self.__location_name}" found in {self.get_runtime().zonemaps.get_current_zone_name()}')
            return
        if self.__players_sel:
            participants_sel = self.__players_sel
        else:
            participants_sel = self.get_phase().get_phase_participants(include_local=False)
        players = participants_sel.resolve_players()
        player_locs = self.__get_player_locs(players)
        self.__moving_players = list()
        for player in players:
            loc = player_locs[player]
            if not loc \
                    or loc.get_horizontal_distance(location) > MovementAction.MAX_HORIZONTAL_DISTANCE \
                    or loc.get_vertical_distance(location) > MovementAction.MAX_VERTICAL_DISTANCE:
                self.get_phase().exclude_phase_participant(player)
                continue
            if self.__move_type == MovementAction.MovementType.MOVE:
                self.get_runtime().automation.autopilot.player_move_to_location(player=player, location=location, only_position=True)
            elif self.__move_type == MovementAction.MovementType.ANCHOR:
                self.get_runtime().automation.autopilot.player_anchor_at_location(player=player, location=location, only_position=False, allow_cancel=False)
            elif self.__move_type == MovementAction.MovementType.CHECK:
                continue
            self.__moving_players.append(player)

    def _phase_stopped(self):
        for player in self.__moving_players:
            self.get_runtime().automation.autopilot.stop_player_movements(player=player, reason=FollowLocationsScript.CancelReason.UNCONDITIONAL)
        self.__moving_players = list()


class FormationAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, formation_id: str, anchor: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__formation_id = formation_id
        self.__anchor = anchor

    def _get_description(self) -> str:
        return f'[FormationAction formation_id={self.__formation_id}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        participants = self.get_phase().get_phase_participants()
        self.get_runtime().automation.autopilot.apply_formation(formation_id=self.__formation_id, anchor=self.__anchor,
                                                                player_sel=participants, allow_cancel=not self.__anchor)

    def _phase_stopped(self):
        participants = self.get_combat_script().get_script_participants().resolve_players()
        for player in participants:
            self.get_runtime().automation.autopilot.stop_player_movements(player=player, reason=FollowLocationsScript.CancelReason.UNCONDITIONAL)


class TriggerAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, trigger: ITrigger):
        CombatPhaseAction.__init__(self, phase)
        self.__trigger = trigger

    def _get_description(self) -> str:
        return f'[TriggerAction trigger={self.__trigger}, self={self}]'

    def __cleanup(self):
        if self.__trigger.is_subscribed():
            self.__trigger.cancel_trigger()

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__cleanup()
        self.__trigger.start_trigger()

    def _phase_stopped(self):
        self.__cleanup()


class TriggerStartStopAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, trigger: ITrigger, starting_trigger: bool, ending_trigger: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__trigger = trigger
        self.__starting_trigger = starting_trigger
        self.__ending_trigger = ending_trigger

    def _get_description(self) -> str:
        return f'[TriggerStartStopAction trigger={self.__trigger}, starting_trigger={self.__starting_trigger}, ending_trigger={self.__ending_trigger}, self={self}]'

    def __cleanup(self):
        if self.__trigger.is_subscribed():
            self.__trigger.cancel_trigger()

    def __start_stop(self, event: Event):
        self.__cleanup()
        if self.__starting_trigger:
            logger.debug(f'Start phase {self.get_phase().get_description()} due to trigger {self.__trigger} with {event}')
            self.get_phase().start()
        elif self.__ending_trigger:
            logger.debug(f'Stop phase {self.get_phase().get_description()} due to trigger {self.__trigger} with {event}')
            self.get_phase().stop()

    def _phase_prepared(self):
        self.__cleanup()
        if self.__starting_trigger:
            self.__trigger.add_action(self.__start_stop, once=True)
            self.__trigger.start_trigger()

    def _phase_started(self):
        self.__cleanup()
        if self.__ending_trigger:
            self.__trigger.add_action(self.__start_stop, once=True)
            self.__trigger.start_trigger()

    def _phase_stopped(self):
        self.__cleanup()


class ParseTriggerAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, pattern: str, preparsed_log: bool, player_filter: Optional[Callable[[IPlayer], bool]],
                 action: Callable[[ClientEvents.PARSER_MATCH], None], repeat_period: float, delay: float):
        CombatPhaseAction.__init__(self, phase)
        self.__pattern = pattern
        self.__preparsed_log = preparsed_log
        self.__player_filter = player_filter
        self.__action = action
        self.__repeat_period = repeat_period
        self.__action_delay = delay
        self.__started_triggers = list()

    def _get_description(self) -> str:
        return f'[ParseTriggerAction pattern={self.__pattern}, preparsed_log={self.__preparsed_log}, repeat_period={self.__repeat_period}, self={self}]'

    def __cleanup(self):
        for trigger in self.__started_triggers:
            if trigger.is_subscribed():
                trigger.cancel_trigger()
        self.__started_triggers.clear()

    def __create_trigger(self, player: IPlayer) -> PlayerTrigger:
        trigger = PlayerTrigger(self.get_runtime(), player.get_client_id())
        EventSubscriberToolkit.add_parser_events_to_trigger(trigger=trigger, parse_filters=self.__pattern, parse_preparsed_logs=self.__preparsed_log)
        trigger.add_action(self.__action, delay=self.__action_delay)
        trigger.repeat_period = self.__repeat_period
        return trigger

    def __start_triggers(self):
        for player in self.get_combat_script().get_script_participants(include_local=True).resolve_players():
            if self.__player_filter and not self.__player_filter(player):
                continue
            trigger = self.__create_trigger(player)
            self.__started_triggers.append(trigger)
            trigger.start_trigger()

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__cleanup()
        self.__start_triggers()

    def _phase_stopped(self):
        self.__cleanup()


class ParseTriggerStartStopAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, pattern: str, preparsed_log: bool, player_filter: Optional[Callable[[IPlayer], bool]],
                 starting_trigger: bool, ending_trigger: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__pattern = pattern
        self.__preparsed_log = preparsed_log
        self.__player_filter = player_filter
        self.__started_triggers = list()
        self.__starting_trigger = starting_trigger
        self.__ending_trigger = ending_trigger

    def _get_description(self) -> str:
        return f'[ParseTriggerStartStopAction pattern={self.__pattern}, preparsed_log={self.__preparsed_log}, ' \
               f'starting_trigger={self.__starting_trigger}, ending_trigger={self.__ending_trigger}, self={self}]'

    def __cleanup(self):
        for trigger in self.__started_triggers:
            if trigger.is_subscribed():
                trigger.cancel_trigger()
        self.__started_triggers.clear()

    def __start_stop(self, event: Event):
        self.__cleanup()
        if self.__starting_trigger:
            logger.debug(f'Start phase {self.get_phase().get_description()} with {event}')
            self.get_phase().start()
        elif self.__ending_trigger:
            logger.debug(f'Stop phase {self.get_phase().get_description()} with {event}')
            self.get_phase().stop()

    def __create_trigger(self, player: IPlayer) -> PlayerTrigger:
        trigger = PlayerTrigger(self.get_runtime(), player.get_client_id())
        EventSubscriberToolkit.add_parser_events_to_trigger(trigger=trigger, parse_filters=self.__pattern, parse_preparsed_logs=self.__preparsed_log)
        trigger.add_action(self.__start_stop, once=True)
        return trigger

    def __start_triggers(self):
        for player in self.get_combat_script().get_script_participants(include_local=True).resolve_players():
            if self.__player_filter and not self.__player_filter(player):
                continue
            trigger = self.__create_trigger(player)
            self.__started_triggers.append(trigger)
            trigger.start_trigger()

    def _phase_prepared(self):
        self.__cleanup()
        if self.__starting_trigger:
            self.__start_triggers()

    def _phase_started(self):
        self.__cleanup()
        if self.__ending_trigger:
            self.__start_triggers()

    def _phase_stopped(self):
        self.__cleanup()


class AddMapLocationsAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, locations_ref: List[Location]):
        CombatPhaseAction.__init__(self, phase)
        self.__locations = locations_ref
        self.__locations_added = list()

    def _get_description(self) -> str:
        return f'[AddMapLocationsAction locations_ref={self.__locations}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__locations_added = list(self.__locations)
        for location in self.__locations_added:
            self.get_runtime().zonemaps.add_temporary_location(location)

    def _phase_stopped(self):
        for location in self.__locations_added:
            self.get_runtime().zonemaps.remove_temporary_location(location)
        self.__locations_added = list()


class NotificationAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, message: Union[str, Callable[[], str]]):
        CombatPhaseAction.__init__(self, phase)
        self.__message = message

    def _get_description(self) -> str:
        return f'[NotificationAction message={self.__message}, self={self}]'

    def _phase_prepared(self):
        pass

    def __get_text(self) -> str:
        if isinstance(self.__message, str):
            return self.__message
        return self.__message()

    def _phase_started(self):
        msg = f'SCRIPT STARTED: {self.__get_text()}'
        self.get_runtime().notification_service.post_notification(msg)
        self.get_runtime().overlay.display_warning('SCRIPT', 2.0)
        self.get_runtime().tts.say(msg)

    def _phase_stopped(self):
        pass


class FlagSettingAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, flag: MutableFlags, value: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__flag = flag
        self.__value = value
        self.__old_value: Optional[bool] = None

    def _get_description(self) -> str:
        return f'[FlagSettingAction flag={self.__flag}, value={self.__value}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        self.__old_value = bool(self.__flag)
        if self.__value:
            self.__flag.true()
        else:
            self.__flag.false()

    def _phase_stopped(self):
        if self.__old_value is True:
            self.__flag.true()
        elif self.__old_value is False:
            self.__flag.false()


class GameSettingAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, on_command: str, off_command: str, local_player: bool, remote_players: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__on_command = on_command
        self.__off_command = off_command
        self.__local_player = local_player
        self.__remote_players = remote_players
        self.__applied_to_players = []

    def _get_description(self) -> str:
        return f'[GameSettingAction cmd={self.__on_command}/{self.__off_command}, local={self.__local_player}, remote={self.__remote_players}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        players = []
        participants = self.get_phase().get_phase_participants(include_local=True)
        for participant in participants:
            if participant.is_local() and self.__local_player:
                players.append(participant)
            elif participant.is_remote() and self.__remote_players:
                players.append(participant)
        for player in players:
            psf = self.get_phase().get_combat_script().get_player_scripting_framework(player)
            psf.command_async(self.__on_command)
        self.__applied_to_players = players

    def _phase_stopped(self):
        players = self.__applied_to_players
        for player in players:
            psf = self.get_phase().get_combat_script().get_player_scripting_framework(player)
            psf.command_async(self.__off_command)


class AutoattackModeAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, autoattack_mode: int):
        CombatPhaseAction.__init__(self, phase)
        self.__autoattack_mode = autoattack_mode
        self.__changed_players: Optional[IPlayerSelector] = None

    def _get_description(self) -> str:
        return f'[AutoattackModeAction autoattack_mode={self.__autoattack_mode}, self={self}]'

    def _phase_prepared(self):
        pass

    def _phase_started(self):
        changed_players = self.get_phase().get_phase_participants()
        cmd_script = RunCommand(changed_players, f'setautoattackmode {self.__autoattack_mode}')
        self.__changed_players = changed_players
        self.get_runtime().processor.run_auto(cmd_script)

    def _phase_stopped(self):
        changed_players = self.__changed_players
        if changed_players:
            cmd_script = RunCommand(changed_players, f'setautoattackmode {AutoattackMode.MEELEE}')
            self.get_runtime().processor.run_auto(cmd_script)
            self.__changed_players = None


class DelayedStartStopAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, delay: float, starting_trigger: bool, ending_trigger: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__delay = delay
        self.__starting_trigger = starting_trigger
        self.__ending_trigger = ending_trigger
        self.__future_start: Optional[RKAFuture] = None
        self.__future_stop: Optional[RKAFuture] = None

    def __cleanup(self):
        if self.__future_start:
            self.__future_start.cancel_future()
            self.__future_start = None
        if self.__future_stop:
            self.__future_stop.cancel_future()
            self.__future_stop = None

    def __start(self, _event: Event):
        self.__cleanup()
        logger.debug(f'Start phase {self.get_phase().get_description()} after {self.__delay}')
        self.get_phase().start()

    def __stop(self, _event: Event):
        self.__cleanup()
        logger.debug(f'Stop phase {self.get_phase().get_description()} after {self.__delay}')
        self.get_phase().stop()

    def _get_description(self) -> str:
        return f'[DelayedAction delay={self.__delay}, starting_trigger={self.__starting_trigger}, ending_trigger={self.__ending_trigger}, self={self}]'

    def _phase_prepared(self):
        self.__cleanup()
        if self.__starting_trigger:
            self.__future_start = self.get_combat_script().get_scheduler().schedule(self.__start, delay=self.__delay)

    def _phase_started(self):
        self.__cleanup()
        if self.__ending_trigger:
            self.__future_stop = self.get_combat_script().get_scheduler().schedule(self.__stop, delay=self.__delay)

    def _phase_stopped(self):
        self.__cleanup()


class MasterEventStartStopAction(CombatPhaseAction):
    def __init__(self, phase: ICombatPhase, event: Event, starting_trigger: bool, ending_trigger: bool):
        CombatPhaseAction.__init__(self, phase)
        self.__event = event
        self.__starting_trigger = starting_trigger
        self.__ending_trigger = ending_trigger

    def __cleanup(self):
        if self.__starting_trigger:
            EventSystem.get_main_bus().unsubscribe_all(type(self.__event), self.__start)
        if self.__ending_trigger:
            EventSystem.get_main_bus().unsubscribe_all(type(self.__event), self.__stop)

    def __start(self, event: Event):
        self.__cleanup()
        logger.debug(f'Start phase {self.get_phase().get_description()} due to {event}')
        self.get_phase().start()

    def __stop(self, event: Event):
        self.__cleanup()
        logger.debug(f'Stop phase {self.get_phase().get_description()} due to {event}')
        self.get_phase().stop()

    def _get_description(self) -> str:
        return f'[MasterEventAction event={self.__event}, starting_trigger={self.__starting_trigger}, ending_trigger={self.__ending_trigger}, self={self}]'

    def _phase_prepared(self):
        self.__cleanup()
        if self.__starting_trigger:
            EventSystem.get_main_bus().subscribe(self.__event, self.__start)

    def _phase_started(self):
        self.__cleanup()
        if self.__ending_trigger:
            EventSystem.get_main_bus().subscribe(self.__event, self.__stop)

    def _phase_stopped(self):
        self.__cleanup()


class ClientEventSubscriber:
    def __init__(self, phase: ICombatPhase, event: ClientEvent):
        self.__phase = phase
        self.__event = event
        self.__subscribed_players: List[IPlayer] = list()

    def _is_current_participant(self, event: ClientEvent) -> bool:
        player = self.__phase.get_runtime().player_mgr.get_player_by_client_id(event.get_client_id())
        return self.__phase.is_phase_participant(player)

    def _unsubscribe(self, callback: Callable[[Optional[ClientEvent]], None]):
        for player in self.__subscribed_players:
            client_id = player.get_client_id()
            bus = self.__phase.get_runtime().remote_client_event_system.get_bus(client_id)
            if bus:
                bus.unsubscribe_all(type(self.__event), callback)
        self.__subscribed_players = list()

    def _subscribe(self, callback: Callable[[Optional[ClientEvent]], None]):
        subscribed_players = list()
        runtime = self.__phase.get_runtime()
        for player in self.__phase.get_phase_participants(include_local=True).resolve_players():
            client_id = player.get_client_id()
            event = self.__event.clone()
            event.set_client_id(client_id)
            bus = runtime.remote_client_event_system.get_bus(client_id)
            if bus:
                bus.subscribe(event, callback)
                subscribed_players.append(player)
            else:
                logger.warn(f'Could not subscribe for {self.__event}')
        self.__subscribed_players = subscribed_players


class ClientEventStartStopAction(CombatPhaseAction, ClientEventSubscriber):
    def __init__(self, phase: ICombatPhase, event: ClientEvent, starting_trigger: bool, ending_trigger: bool):
        if isinstance(event, ClientEvents.PARSER_MATCH):
            logger.error(f'Dont use {ClientEventStartStopAction.__name__} for PARSER_MATCH, use {ParseTriggerStartStopAction.__name__}')
        CombatPhaseAction.__init__(self, phase)
        ClientEventSubscriber.__init__(self, phase, event)
        self.__event = event
        self.__starting_trigger = starting_trigger
        self.__ending_trigger = ending_trigger

    def __cleanup(self):
        if self.__starting_trigger:
            self._unsubscribe(self.__start)
        if self.__ending_trigger:
            self._unsubscribe(self.__stop)

    def __start(self, event: ClientEvent):
        if self._is_current_participant(event):
            self.__cleanup()
            logger.debug(f'Start phase {self.get_phase().get_description()} due to {event}')
            self.get_phase().start()

    def __stop(self, event: ClientEvent):
        if self._is_current_participant(event):
            self.__cleanup()
            logger.debug(f'Stop phase {self.get_phase().get_description()} due to {event}')
            self.get_phase().stop()

    def _get_description(self) -> str:
        return f'[ClientEventAction event={self.__event}, starting_trigger={self.__starting_trigger}, ending_trigger={self.__ending_trigger}, self={self}]'

    def _phase_prepared(self):
        self.__cleanup()
        if self.__starting_trigger:
            self._subscribe(self.__start)

    def _phase_started(self):
        self.__cleanup()
        if self.__ending_trigger:
            self._subscribe(self.__stop)

    def _phase_stopped(self):
        self.__cleanup()


class StopWhenNoMoreClientEventsAction(CombatPhaseAction, ClientEventSubscriber):
    def __init__(self, phase: ICombatPhase, event: ClientEvent, delay: float):
        CombatPhaseAction.__init__(self, phase)
        self.__event = event
        ClientEventSubscriber.__init__(self, phase, self.__event)
        self.__waiting_time = delay
        self.__stop_future: Optional[RKAFuture] = None

    def __cleanup(self):
        self._unsubscribe(self.__tick)
        if self.__stop_future:
            self.__stop_future.cancel_future()
            self.__stop_future = None

    def __stop(self):
        self.__cleanup()
        players = self.get_phase().get_phase_participants().resolve_players()
        logger.debug(f'Stop phase {self.get_phase().get_description()} due to no {self.__event}, participants: {players}')
        self.get_phase().stop()

    def __schedule_new_stop(self):
        if self.__stop_future:
            self.__stop_future.cancel_future()
        self.__stop_future = self.get_combat_script().get_scheduler().schedule(self.__stop, delay=self.__waiting_time)

    def __tick(self, event: ClientEvent):
        if self._is_current_participant(event):
            self.__schedule_new_stop()

    def _get_description(self) -> str:
        return f'[StopWhenNoMoreClientEventsAction event={self.__event}, self={self}]'

    def _phase_prepared(self):
        self.__cleanup()

    def _phase_started(self):
        self.__cleanup()
        self._subscribe(self.__tick)

    def _phase_stopped(self):
        self.__cleanup()
