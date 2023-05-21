from __future__ import annotations

import enum
from enum import auto
from typing import Optional, Iterable, List

from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.workthread import RKAWorkerThread
from rka.components.io.log_service import LogService
from rka.eq2.master import HasRuntime, TakesRuntime
from rka.eq2.master.game.interfaces import IPlayer, IPlayerSelector
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.scripting.framework import PlayerScriptingFramework
from rka.log_configs import LOG_COMBAT_SCRIPTING_FRAMEWORK

logger = LogService(LOG_COMBAT_SCRIPTING_FRAMEWORK)


# noinspection PyAbstractClass
class ICombatScript(HasRuntime):
    def get_name(self) -> str:
        raise NotImplementedError()

    def get_zone_name(self) -> str:
        raise NotImplementedError()

    def get_combatant_name(self) -> str:
        raise NotImplementedError()

    def is_built_for_local_player(self) -> bool:
        raise NotImplementedError()

    def get_scheduler(self) -> RKAScheduler:
        raise NotImplementedError()

    def get_worker(self) -> RKAWorkerThread:
        raise NotImplementedError()

    def add_location(self, location_name: str, location: Location):
        raise NotImplementedError()

    def get_location(self, location_name: str) -> Optional[Location]:
        raise NotImplementedError()

    def add_script_participant(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def remove_script_participant(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def is_script_participant(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def get_script_participants(self, include_local=False) -> IPlayerSelector:
        raise NotImplementedError()

    def get_script_participant_by_name(self, player_name: str) -> Optional[IPlayer]:
        raise NotImplementedError()

    def get_player_scripting_framework(self, player: IPlayer) -> PlayerScriptingFramework:
        raise NotImplementedError()

    def get_local_player_scripting_framework(self) -> Optional[PlayerScriptingFramework]:
        raise NotImplementedError()


class ECombatPhaseState(enum.IntEnum):
    READY = auto()
    STOPPED = auto()
    STARTED = auto()


class ICombatPhase(TakesRuntime):
    def __init__(self, runtime: HasRuntime):
        TakesRuntime.__init__(self, runtime)

    def get_phase_name(self) -> str:
        raise NotImplementedError()

    def get_description(self) -> str:
        raise NotImplementedError()

    def get_duration(self) -> Optional[float]:
        raise NotImplementedError()

    def get_combat_script(self) -> ICombatScript:
        raise NotImplementedError()

    def subphase(self, name: str) -> ICombatPhase:
        raise NotImplementedError()

    def iter_subphases(self) -> Iterable[ICombatPhase]:
        raise NotImplementedError()

    def get_local_player(self) -> Optional[IPlayer]:
        raise NotImplementedError()

    def is_phase_participant(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def get_phase_participants(self, include_local=False) -> IPlayerSelector:
        raise NotImplementedError()

    def exclude_phase_participant(self, player: IPlayer) -> bool:
        raise NotImplementedError()

    def clear_excluded_phase_participants(self):
        raise NotImplementedError()

    def phase_actions(self) -> CombatPhaseActions:
        raise NotImplementedError()

    def temporary_phase_actions(self) -> CombatPhaseActions:
        raise NotImplementedError()

    def get_state(self) -> ECombatPhaseState:
        raise NotImplementedError()

    def prepare(self):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def finish(self):
        raise NotImplementedError()


class CombatPhaseAction(TakesRuntime):
    def __init__(self, phase: ICombatPhase):
        TakesRuntime.__init__(self, phase)
        self.__phase = phase
        self.__cached_description: Optional[str] = None

    def get_phase(self) -> ICombatPhase:
        return self.__phase

    def get_combat_script(self) -> ICombatScript:
        return self.__phase.get_combat_script()

    def get_description(self) -> str:
        if self.__cached_description is None:
            self.__cached_description = self._get_description()
        return self.__cached_description

    def phase_prepared(self):
        logger.debug(f'phase_prepared({self.__phase.get_phase_name()}) action: {self.get_description()}')
        self._phase_prepared()

    def phase_started(self):
        logger.debug(f'phase_started({self.__phase.get_phase_name()}) action: {self.get_description()}')
        self._phase_started()

    def phase_stopped(self):
        logger.debug(f'phase_stopped({self.__phase.get_phase_name()}) action: {self.get_description()}')
        self._phase_stopped()

    def _get_description(self) -> str:
        raise NotImplementedError()

    def _phase_prepared(self):
        raise NotImplementedError()

    def _phase_started(self):
        raise NotImplementedError()

    def _phase_stopped(self):
        raise NotImplementedError()


class IActionBuilderFactory:
    def create_action_builder(self, phase: ICombatPhase, phase_actions: CombatPhaseActions) -> object:
        raise NotImplementedError()


class CombatPhaseActions:
    def __init__(self, combat_phase: ICombatPhase, temporary: bool):
        self.__combat_phase = combat_phase
        self.__temporary = temporary
        self.__actions: List[CombatPhaseAction] = list()
        self.__cached_builder_object = None

    def add(self, action: CombatPhaseAction):
        if self.__temporary:
            logger.debug(f'CombatPhase of {self.__combat_phase.get_description()} add temporary action {action.get_description()}')
        else:
            logger.detail(f'CombatPhase of {self.__combat_phase.get_description()} add action {action.get_description()}')
        if self.__combat_phase.get_state() == ECombatPhaseState.STOPPED:
            action.phase_prepared()
        elif self.__combat_phase.get_state() == ECombatPhaseState.STARTED:
            action.phase_started()
        action_str = action.get_description()
        for current_action in self.__actions:
            if action_str == current_action.get_description():
                logger.warn(f'Adding existing action {action_str}')
                break
        self.__actions.append(action)

    def phase_prepared(self):
        logger.detail(f'CombatPhase of {self.__combat_phase.get_description()} prepares actions')
        for action in self.__actions:
            action.phase_prepared()

    def phase_started(self):
        logger.detail(f'CombatPhase of {self.__combat_phase.get_description()} starts actions')
        for action in self.__actions:
            action.phase_started()

    def phase_stopped(self):
        logger.detail(f'CombatPhase of {self.__combat_phase.get_description()} stops actions')
        for action in self.__actions:
            action.phase_stopped()
        if self.__temporary:
            self.__actions.clear()

    def action_builder(self, action_builder_factory: IActionBuilderFactory) -> object:
        if not self.__cached_builder_object:
            self.__cached_builder_object = action_builder_factory.create_action_builder(self.__combat_phase, self)
        return self.__cached_builder_object
