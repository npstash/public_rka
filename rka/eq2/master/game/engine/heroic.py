from __future__ import annotations

from typing import Optional, List, Union, Dict

from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.eq2.master import IRuntime, HasRuntime
from rka.eq2.master.game.ability import HOIcon
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.engine import HOStage
from rka.eq2.master.game.engine.task import Task, FilterTask
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.interfaces import TAbilityFilter
from rka.log_configs import LOG_SPECIAL_REQUESTS

TTriggerIcons = Union[None, HOIcon, List[HOIcon]]

logger = LogService(LOG_SPECIAL_REQUESTS)


class HeroicOpportunity(HasRuntime):
    DEFAULT_MAX_HITS = 4

    def __init__(self, chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons):
        self.__HO_name: Optional[str] = None
        self.__HO_chain_icon = chain_icon
        self.__HO_chain_starter: Optional[str] = None
        self.__HO_trigger_icons = [trigger_icons] if isinstance(trigger_icons, HOIcon) else trigger_icons
        self.__HO_triggerer: Optional[str] = None
        self.__HO_stage = HOStage.NONE
        self.__HO_advances = 0
        self.__runtime: Optional[IRuntime] = None
        self.__tasks: List[Task] = list()
        self.__filters: List[Task] = list()

    def _get_HO_chain_icon(self) -> Optional[HOIcon]:
        return self.__HO_chain_icon

    def _get_HO_trigger_icons(self) -> TTriggerIcons:
        return self.__HO_trigger_icons

    def _get_HO_advances(self) -> int:
        return self.__HO_advances

    def _get_HO_stage(self) -> HOStage:
        return self.__HO_stage

    def _add_task(self, task: Task):
        self.__tasks.append(task)

    def _add_filter(self, except_icon: HOIcon.Sword):
        flt = FilterTask(AbilityFilter().not_heroic_op(except_icon), description=f'No {except_icon.name}', duration=10.0)
        self._add_task(flt)
        self.__filters.append(flt)
        self.__runtime.processor.run_filter(flt)

    def _clear_filters(self):
        for flt in self.__filters:
            flt.expire()
        self.__filters.clear()

    def _request_HO(self, ho_icon: HOIcon, max_hits: Optional[int] = None, ability_filter: Optional[TAbilityFilter] = None,
                    delay: Optional[float] = None):
        logger.info(f'HO requested: {ho_icon.name}')
        if not max_hits:
            max_hits = HeroicOpportunity.DEFAULT_MAX_HITS
        request = self.__runtime.request_ctrl.request_HO_advance(ho_icon, max_hits, ability_filter, delay)
        self._add_task(request)

    def _expire_tasks(self):
        for task in self.__tasks:
            task.expire()
        self.__tasks.clear()

    def has_runtime(self) -> bool:
        return self.__runtime is not None

    def get_runtime(self) -> IRuntime:
        assert self.__runtime
        return self.__runtime

    def clone(self) -> HeroicOpportunity:
        return HeroicOpportunity(self.__HO_chain_icon, self.__HO_trigger_icons)

    def init(self, runtime: IRuntime, HO_name: str):
        self.__runtime = runtime
        self.__HO_name = HO_name

    def get_name(self) -> str:
        return self.__HO_name

    def request_chain(self):
        if self.__HO_chain_icon:
            self._request_HO(self.__HO_chain_icon, max_hits=1)

    def request_trigger(self):
        if self.__HO_trigger_icons:
            delay = 0.0
            for trigger_icon in self.__HO_trigger_icons:
                self._request_HO(trigger_icon, max_hits=1, delay=delay)
                delay += 2.0

    def __stage_change_event(self, caster_name: str, hint: Optional[str]):
        event = CombatEvents.HO_STAGE_CHANGED(ho_name=self.__HO_name, caster_name=caster_name,
                                              new_stage=self.__HO_stage, advances=self.__HO_advances, hint=hint)
        EventSystem.get_main_bus().post(event)

    def chain_started(self, HO_chain_starter: str, hint: Optional[str] = None):
        logger.info(f'HO chain start: {HO_chain_starter}')
        self.__HO_stage = HOStage.STARTED
        self.__HO_advances = 0
        self.__HO_chain_starter = HO_chain_starter
        self._expire_tasks()
        self.__stage_change_event(HO_chain_starter, hint)

    def continue_from_chain(self, ho: HeroicOpportunity):
        self.__HO_stage = HOStage.STARTED
        self.__HO_advances = 0
        self.__HO_chain_starter = ho.__HO_chain_starter
        self._expire_tasks()
        self.__stage_change_event(self.__HO_chain_starter, None)

    def triggered(self, HO_triggerer: str, hint: Optional[str] = None):
        logger.info(f'HO triggered: {HO_triggerer}, {self.__HO_name}, {hint}')
        self.__HO_stage = HOStage.TRIGGERED
        self.__HO_advances = 0
        self.__HO_triggerer = HO_triggerer
        self._expire_tasks()
        self.__stage_change_event(HO_triggerer, hint)

    def advanced(self, HO_advancer: str, hint: Optional[str] = None):
        self.__HO_advances += 1
        logger.info(f'HO advanced: {HO_advancer}, {hint}, #{self.__HO_advances}')
        self.__HO_stage = HOStage.TRIGGERED
        self.__stage_change_event(HO_advancer, hint)

    def completed(self, HO_completer: str, hint: Optional[str] = None):
        logger.info(f'HO completed: {HO_completer}, {hint}')
        self.__HO_stage = HOStage.COMPLETED
        self._expire_tasks()
        self._clear_filters()
        self.__stage_change_event(HO_completer, hint)

    def cancel(self):
        self._expire_tasks()
        self._clear_filters()


class HeroicOpportunityChain(HeroicOpportunity):
    def __init__(self, chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons):
        HeroicOpportunity.__init__(self, chain_icon, trigger_icons)
        self.__icons: List[HOIcon] = list()

    def clone(self) -> HeroicOpportunityChain:
        prototype = HeroicOpportunityChain(self._get_HO_chain_icon(), self._get_HO_trigger_icons())
        prototype.__icons = self.__icons.copy()
        return prototype

    def then(self, ho_icon: HOIcon) -> HeroicOpportunityChain:
        self.__icons.append(ho_icon)
        return self

    def triggered(self, HO_triggerer: str, hint: Optional[str] = None):
        super().triggered(HO_triggerer, hint)
        self._request_HO(self.__icons[self._get_HO_advances()])

    def advanced(self, HO_advancer: str, hint: Optional[str] = None):
        super().advanced(HO_advancer, hint)
        self._expire_tasks()
        if self._get_HO_advances() >= len(self.__icons):
            return
        self._request_HO(self.__icons[self._get_HO_advances()])


class HeroicOpportunityCombine(HeroicOpportunity):
    def __init__(self, chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons):
        HeroicOpportunity.__init__(self, chain_icon, trigger_icons)
        self.__icons: List[HOIcon] = list()

    def clone(self) -> HeroicOpportunityCombine:
        prototype = HeroicOpportunityCombine(self._get_HO_chain_icon(), self._get_HO_trigger_icons())
        prototype.__icons = self.__icons.copy()
        return prototype

    def plus(self, ho_icon: HOIcon) -> HeroicOpportunityCombine:
        self.__icons.append(ho_icon)
        return self

    def triggered(self, HO_triggerer: str, hint: Optional[str] = None):
        super().triggered(HO_triggerer, hint)
        for ho_icon in self.__icons:
            self._request_HO(ho_icon)


class HeroicOpportunityFinisher(HeroicOpportunity):
    def __init__(self, chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons):
        HeroicOpportunity.__init__(self, chain_icon, trigger_icons)
        self.__icons: List[HOIcon] = list()
        self.__finisher: Optional[HOIcon] = None

    def clone(self) -> HeroicOpportunityFinisher:
        prototype = HeroicOpportunityFinisher(self._get_HO_chain_icon(), self._get_HO_trigger_icons())
        prototype.__icons = self.__icons.copy()
        prototype.__finisher = self.__finisher
        return prototype

    def plus(self, ho_icon: HOIcon) -> HeroicOpportunityFinisher:
        self.__icons.append(ho_icon)
        return self

    def finish(self, ho_icon: HOIcon) -> HeroicOpportunityFinisher:
        self.__finisher = ho_icon
        return self

    def triggered(self, HO_triggerer: str, hint: Optional[str] = None):
        super().triggered(HO_triggerer, hint)
        self._add_filter(self.__finisher)
        for ho_icon in self.__icons:
            self._request_HO(ho_icon)

    def advanced(self, HO_advancer: str, hint: Optional[str] = None):
        super().advanced(HO_advancer, hint)
        if self._get_HO_advances() >= len(self.__icons):
            self._expire_tasks()
            self._request_HO(self.__finisher)


class HOs:
    @staticmethod
    def seq(chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons) -> HeroicOpportunityChain:
        return HeroicOpportunityChain(chain_icon, trigger_icons)

    @staticmethod
    def all(chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons) -> HeroicOpportunityCombine:
        return HeroicOpportunityCombine(chain_icon, trigger_icons)

    @staticmethod
    def last(chain_icon: Optional[HOIcon], trigger_icons: TTriggerIcons) -> HeroicOpportunityFinisher:
        return HeroicOpportunityFinisher(chain_icon, trigger_icons)

    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__heroics: Dict[str, HeroicOpportunity] = dict()

    def get_blank_HO(self) -> HeroicOpportunity:
        ho = HeroicOpportunity(chain_icon=None, trigger_icons=None)
        ho.init(self.__runtime, 'Unknown HO')
        return ho

    def get_HO(self, HO_name: str) -> HeroicOpportunity:
        if HO_name not in self.__heroics:
            logger.warn(f'Not found HO {HO_name}, use blank')
            return self.get_blank_HO()
        ho = self.__heroics[HO_name].clone()
        assert isinstance(ho, self.__heroics[HO_name].__class__)
        ho.init(self.__runtime, HO_name)
        return ho

    def install_HO(self, HO_name: str, handler: HeroicOpportunity):
        logger.info(f'Installing HO: {HO_name}')
        self.__heroics[HO_name] = handler
