from __future__ import annotations

import time
from threading import RLock
from typing import Callable, Optional, List, Dict, Iterable, Set

from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.workthread import RKAWorkerThread
from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayerSelector, IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.scripting.combat import logger, ICombatScript, ECombatPhaseState, ICombatPhase, CombatPhaseAction, CombatPhaseActions, IActionBuilderFactory
from rka.eq2.master.game.scripting.combat.combat_action_builder import CombatPhaseActionBuilder
from rka.eq2.master.game.scripting.combat.combat_actions import SchedulerTaskAction, AddMapLocationsAction
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.shared.shared_workers import shared_worker, shared_scheduler


class CombatPhase(ICombatPhase):
    def __init__(self, name: str, combat_script: ICombatScript, parent_phase: Optional[ICombatPhase]):
        ICombatPhase.__init__(self, combat_script)
        self.__name = name
        self.__combat_script = combat_script
        self.__parent_phase = parent_phase
        self.__state = ECombatPhaseState.READY
        self.__started_at = time.time()
        self.__subphases: Dict[str, ICombatPhase] = dict()
        self.__actions = CombatPhaseActions(self, False)
        self.__temporary_actions = CombatPhaseActions(self, True)
        self.__excluded_participants: Set[IPlayer] = set()
        self.__participating_local_player: Optional[IPlayer] = None

    def get_phase_name(self) -> str:
        return self.__name

    def get_description(self) -> str:
        return f'[{self.__combat_script.get_name()}->{self.__name}({self.__state.name})]'

    def get_duration(self) -> Optional[float]:
        if self.__state != ECombatPhaseState.STARTED:
            return None
        return time.time() - self.__started_at

    def get_combat_script(self) -> ICombatScript:
        return self.__combat_script

    def subphase(self, name: str) -> ICombatPhase:
        if name in self.__subphases:
            return self.__subphases[name]
        logger.debug(f'CombatPhase of {self.get_description()} new subphase {name}')
        phase = CombatPhase(name, self.__combat_script, self)
        self.__subphases[name] = phase
        if self.__state == ECombatPhaseState.STARTED:
            phase.prepare()
        return phase

    def iter_subphases(self) -> Iterable[ICombatPhase]:
        yield self
        for phase in self.__subphases.values():
            yield from phase.iter_subphases()

    def get_state(self) -> ECombatPhaseState:
        return self.__state

    def __set_state(self, from_state: ECombatPhaseState, to_state: ECombatPhaseState) -> bool:
        description = self.get_description()
        if self.__state != from_state:
            logger.warn(f'Invalid transition in {description}: {self.__state.name} -> {to_state.name}, required {from_state.name}')
            return False
        self.__state = to_state
        logger.info(f'Transition in {description}: {from_state.name} -> {to_state.name}')
        return True

    def is_phase_participant(self, player: IPlayer) -> bool:
        if player in self.__excluded_participants:
            return False
        return self.__combat_script.is_script_participant(player)

    def get_local_player(self) -> Optional[IPlayer]:
        if not self.__participating_local_player:
            self.__participating_local_player = self.get_runtime().playerselectors.local_online().resolve_first_player()
        return self.__participating_local_player

    def get_phase_participants(self, include_local=False) -> IPlayerSelector:
        def exclude_filter(player: IPlayer) -> bool:
            return player not in self.__excluded_participants

        script_participants = self.__combat_script.get_script_participants(include_local)
        return self.get_runtime().playerselectors.by_result(lambda: filter(exclude_filter, script_participants.resolve_players()))

    def exclude_phase_participant(self, player: IPlayer) -> bool:
        if player not in self.__excluded_participants:
            logger.debug(f'Phase [{self.get_description()}] exclude participant {player}')
            self.__excluded_participants.add(player)
            return True
        return False

    def clear_excluded_phase_participants(self):
        self.__excluded_participants.clear()

    def __add_phase_action(self, action: CombatPhaseAction, collection: List[CombatPhaseAction]):
        if self.__state == ECombatPhaseState.STOPPED:
            action.phase_prepared()
        elif self.__state == ECombatPhaseState.STARTED:
            action.phase_started()
        collection.append(action)

    def phase_actions(self) -> CombatPhaseActions:
        return self.__actions

    def temporary_phase_actions(self) -> CombatPhaseActions:
        return self.__temporary_actions

    class _Decorators:
        @classmethod
        def sync(cls, state_change_fn: Callable[[CombatPhase], None]):
            def wrapper(self, *_args, **_kwargs):
                shared_worker.push_task(lambda: state_change_fn(self))

            return wrapper

    @_Decorators.sync
    def prepare(self):
        if not self.__set_state(ECombatPhaseState.READY, ECombatPhaseState.STOPPED):
            return
        parcitipants = self.get_phase_participants(include_local=True).resolve_players()
        logger.info(f'Phase prepare: {self.get_description()}, current participants: {[str(p) for p in parcitipants]}')
        self.__actions.phase_prepared()
        self.__temporary_actions.phase_prepared()

    @_Decorators.sync
    def start(self):
        if not self.__set_state(ECombatPhaseState.STOPPED, ECombatPhaseState.STARTED):
            return
        parcitipants = self.get_phase_participants(include_local=True).resolve_players()
        logger.info(f'Phase start: {self.get_description()}, current participants: {[str(p) for p in parcitipants]}')
        self.__started_at = time.time()
        self.__participating_local_player = self.get_runtime().playerselectors.local_online().resolve_first_player()
        self.__actions.phase_started()
        self.__temporary_actions.phase_started()
        for phase in self.__subphases.values():
            phase.prepare()

    @_Decorators.sync
    def stop(self):
        if not self.__set_state(ECombatPhaseState.STARTED, ECombatPhaseState.STOPPED):
            return
        parcitipants = self.get_phase_participants(include_local=True).resolve_players()
        logger.info(f'Phase stop: {self.get_description()}, current participants: {[str(p) for p in parcitipants]}')
        self.__participating_local_player = None
        for phase in self.__subphases.values():
            phase.finish()
        self.__actions.phase_stopped()
        self.__temporary_actions.phase_stopped()
        self.clear_excluded_phase_participants()
        self.__actions.phase_prepared()

    @_Decorators.sync
    def finish(self):
        if self.__state == ECombatPhaseState.STOPPED:
            self.__set_state(ECombatPhaseState.STOPPED, ECombatPhaseState.READY)
            self.__actions.phase_stopped()
            self.__temporary_actions.phase_stopped()
            return
        if not self.__set_state(ECombatPhaseState.STARTED, ECombatPhaseState.READY):
            return
        parcitipants = self.get_phase_participants().resolve_players()
        logger.info(f'Phase finish: {self.get_description()}, current participants: {[str(p) for p in parcitipants]}')
        for phase in self.__subphases.values():
            phase.finish()
        self.__actions.phase_stopped()
        self.__temporary_actions.phase_stopped()


class CombatScriptTask(ICombatScript, IActionBuilderFactory, PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'{self.__class__}', -1.0)
        self.__name = 'unknown'
        self.__zone_name = 'unknown'
        self.__combatant_name = 'unknown'
        self.__built_for_local_player = True
        self.__root_phase = CombatPhase('root', self, None)
        self.__location_timestamps: List[Location] = list()
        self.__participants: Set[IPlayer] = set()
        self.__participants_lock = RLock()
        self.__scheduler = shared_scheduler
        self.__worker = shared_worker
        self.set_persistent()
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__player_zone_changed)

    def initialize_combat_script(self, runtime: IRuntime, name: str, zone_name: str, combatant_name: str, local_player: bool):
        self.__name = name
        self.__zone_name = zone_name
        self.__combatant_name = combatant_name
        self.__built_for_local_player = local_player
        self.set_description(name)
        self.root_phase().phase_actions().add(AddMapLocationsAction(self.__root_phase, self.__location_timestamps))
        if local_player:
            self._standard_local_player_start_actions()
            self._standard_local_player_end_actions()
            self.builder().add_single_task(lambda: runtime.overlay.log_event(f'CS Started: {self.__combatant_name}', Severity.Normal), delay=0.0)
            self.builder().add_single_task(lambda: runtime.overlay.log_event(f'CS Prepared: {self.__combatant_name}', Severity.Normal), delay=0.0,
                                           baseline=SchedulerTaskAction.SchedulingBaseline.FROM_PREPARED)
        else:
            self._standard_remote_player_start_actions()
            self._standard_remote_player_end_actions()
            self.builder().add_script_stopper()

    def get_player_scripting_framework(self, player: IPlayer) -> PlayerScriptingFramework:
        return PlayerScriptTask.get_player_scripting_framework(self, player)

    def get_local_player_scripting_framework(self) -> Optional[PlayerScriptingFramework]:
        player = self.root_phase().get_local_player()
        if not player:
            return None
        return PlayerScriptTask.get_player_scripting_framework(self, player)

    def get_name(self) -> str:
        return self.__name

    def get_zone_name(self) -> str:
        return self.__zone_name

    def get_combatant_name(self) -> str:
        return self.__combatant_name

    def is_built_for_local_player(self) -> bool:
        return self.__built_for_local_player

    def get_scheduler(self) -> RKAScheduler:
        return self.__scheduler

    def get_worker(self) -> RKAWorkerThread:
        return self.__worker

    def add_location(self, location_name: str, location: Location):
        if not location_name:
            logger.warn(f'Cannot add location({location}) without name')
            return
        logger.info(f'CombatScript [{self.__name}] add location {location_name} ({location})')
        location.info = location_name
        self.__location_timestamps.append(location)

    def get_location(self, location_name: str) -> Optional[Location]:
        if not location_name:
            logger.warn(f'Cannot get location without name')
            return None
        logger.detail(f'CombatScript [{self.__name}] get location {location_name}')
        locations = list(self.__location_timestamps)
        for location in locations:
            if location_name.lower() == location.info.lower():
                return location
        return self.get_runtime().zonemaps.get_location_by_name(location_name)

    def add_script_participant(self, player: IPlayer) -> bool:
        added = False
        with self.__participants_lock:
            if player not in self.__participants:
                logger.info(f'CombatScript [{self.__name}] add script participant {player}')
                self.__participants.add(player)
                added = True
        if added:
            self._on_participant_added(player)
        return added

    def remove_script_participant(self, player: IPlayer) -> bool:
        removed = False
        removed_last = False
        with self.__participants_lock:
            if player in self.__participants:
                logger.info(f'CombatScript [{self.__name}] remove script participant {player}')
                self.__participants.remove(player)
                removed = True
                if not self.__participants:
                    removed_last = True
        if removed:
            self._on_participant_removed(player)
        if removed_last:
            self.expire()
        return removed

    def is_script_participant(self, player: IPlayer) -> bool:
        with self.__participants_lock:
            return player in self.__participants

    def __get_script_participants(self, include_local=False, include_remote=True) -> List[IPlayer]:
        with self.__participants_lock:
            return list(filter(lambda player: (player.is_local() and include_local) or (player.is_remote() and include_remote), self.__participants))

    def get_script_participants(self, include_local=False, include_remote=True) -> IPlayerSelector:
        return self.get_runtime().playerselectors.by_result(lambda: self.__get_script_participants(include_local, include_remote))

    def get_script_participant_by_name(self, player_name: str) -> Optional[IPlayer]:
        with self.__participants_lock:
            for player in self.__participants:
                if player.get_player_name() == player_name:
                    return player
        return None

    def root_phase(self) -> ICombatPhase:
        return self.__root_phase

    def create_action_builder(self, phase: ICombatPhase, phase_actions: CombatPhaseActions) -> object:
        return CombatPhaseActionBuilder(phase, phase_actions)

    def builder(self, actions: Optional[CombatPhaseActions] = None) -> CombatPhaseActionBuilder:
        if not actions:
            actions = self.root_phase().phase_actions()
        builder = actions.action_builder(self)
        return builder

    def __player_zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        if event.to_zone == self.__zone_name:
            self.add_script_participant(event.player)
        elif event.from_zone == self.__zone_name:
            self.remove_script_participant(event.player)

    def _init_combat_script(self):
        raise NotImplementedError()

    def _run(self, runtime: IRuntime):
        self._init_combat_script()
        self.root_phase().prepare()
        self.wait_until_completed()

    def _on_participant_added(self, player: IPlayer):
        pass

    def _on_participant_removed(self, player: IPlayer):
        pass

    def _on_expire(self):
        logger.info(f'CombatScript [{self.__name}] _on_expire')
        EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.PLAYER_ZONE_CHANGED, self.__player_zone_changed)
        self.__root_phase.finish()
        with self.__participants_lock:
            self.__participants.clear()
        PlayerScriptTask._on_expire(self)

    def _standard_local_player_start_actions(self):
        self.builder().start_by_combatant(self.get_combatant_name())

    def _standard_local_player_end_actions(self):
        self.builder().end_by_master_event(ObjectStateEvents.COMBAT_STATE_END())
        self.builder().end_by_master_event(CombatEvents.ENEMY_KILL(enemy_name=self.get_combatant_name()))

    def _standard_remote_player_start_actions(self):
        self.builder().start_by_combatant(self.get_combatant_name())

    def _standard_remote_player_end_actions(self):
        self.builder().end_by_client_combat_expire()
