from __future__ import annotations

import threading
import traceback
from typing import Dict, List, Callable

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogLevel
from rka.eq2.configs.shared.rka_constants import PROCESSOR_TICK
from rka.eq2.master import IRuntime, RequiresRuntime
from rka.eq2.master.game.ability import PRIORITY_SELECTION_MARGIN
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.snap import AbilitySnapshot
from rka.eq2.master.game.engine import logger
from rka.eq2.master.game.engine.abilitybag import AbilityBag
from rka.eq2.master.game.engine.request import Request
from rka.eq2.master.game.engine.task import Task, FilterTask, IAbilityCastingObserver
from rka.eq2.master.game.interfaces import IAbility, IPlayer


class TaskController(Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=True)
        self.__running_requests: List[Request] = list()
        self.__running_filters: List[FilterTask] = list()
        self.__running_othertasks: List[Task] = list()
        self.__delayed_requests: List[Request] = list()
        self.__delayed_filters: List[FilterTask] = list()
        self.__delayed_othertasks: List[Task] = list()
        # aggregates
        self.___all_tasks = [self.__running_requests, self.__delayed_requests,
                             self.__running_othertasks, self.__delayed_othertasks,
                             self.__running_filters, self.__delayed_filters]
        self.___all_requests_and_othertasks = [self.__running_requests, self.__delayed_requests,
                                               self.__running_othertasks, self.__delayed_othertasks]
        self.___all_running_tasks = [self.__running_requests, self.__running_othertasks, self.__running_filters]
        # for setting up in tasks
        self.__runtime = runtime

    def visit_requests_and_othertasks(self, cb: Callable[[Task], None]):
        for task_list in self.___all_requests_and_othertasks:
            for req in task_list:
                cb(req)

    def visit_all_running_tasks(self, cb: Callable[[Task], None]):
        for task_list in self.___all_running_tasks:
            for req in task_list:
                cb(req)

    def expire_requests_and_othertasks(self):
        for task_list in self.___all_requests_and_othertasks:
            for req in task_list:
                if not req.is_persistent():
                    req.expire()

    @staticmethod
    def __prepare_running_tasks(running_list: List[Task], delayed_list: List[Task]):
        for task in running_list:
            if task.is_in_delay():
                logger.warn(f'unexpected delay {task.get_delay()} found on {task}')
        ready_delayed = [task for task in delayed_list if not task.is_in_delay()]
        for ready_task in ready_delayed:
            delayed_list.remove(ready_task)
            running_list.append(ready_task)
            logger.debug(f'started: {ready_task.__class__.__name__} {ready_task}')
            ready_task.notify_started()
        expired_running = [task for task in running_list if task.is_expired()]
        for expired_task in expired_running:
            running_list.remove(expired_task)
            logger.debug(f'expired: {expired_task.__class__.__name__} {expired_task}')
            expired_task.notify_expired()

    def prepare_running_requests(self) -> List[Request]:
        i1 = len(self.__running_requests)
        i2 = len(self.__delayed_requests)
        TaskController.__prepare_running_tasks(self.__running_requests, self.__delayed_requests)
        i12 = len(self.__running_requests)
        i22 = len(self.__delayed_requests)
        if i1 != i12 or i2 != i22:
            logger.info(f'REQUESTS MOVED: running {i1} -> {i12} & delayed {i2} -> {i22}')
        return self.__running_requests

    def prepare_running_filters(self) -> List[FilterTask]:
        TaskController.__prepare_running_tasks(self.__running_filters, self.__delayed_filters)
        return self.__running_filters

    def prepare_running_tasks(self) -> List[Task]:
        TaskController.__prepare_running_tasks(self.__running_othertasks, self.__delayed_othertasks)
        return self.__running_othertasks

    def add_request(self, request: Request):
        self.__add_task(request, self.__running_requests, self.__delayed_requests)

    def add_filter(self, flt: FilterTask):
        self.__add_task(flt, self.__running_filters, self.__delayed_filters)

    def add_othertask(self, task: Task):
        self.__add_task(task, self.__running_othertasks, self.__delayed_othertasks)

    def __add_task(self, task: Task, running_list: List[Task], delayed_list: List[Task]):
        logger.debug(f'Adding task {task}')
        if isinstance(task, RequiresRuntime):
            task.set_runtime(self.__runtime)
        name = task.__class__.__name__
        task_in_running = task in running_list
        task_in_delayed = task in delayed_list
        if task_in_running and task_in_delayed:
            logger.warn(f'{name} was both in running and delayed lists')
            delayed_list.remove(task)
        if task_in_running or task_in_delayed:
            logger.detail(f'{name} /{task}/ restarted')
            task.restart()
        else:
            logger.debug(f'{name} /{task}/ started')
            task.start()
            # always add to delayed list, so start notification is simplified (in one place)
            # it will be moved to running list soon
            delayed_list.append(task)

    def print_debug(self):
        logger.warn(f'print_debug: __running_filters')
        for d in self.__running_filters:
            logger.warn(f'{d}')
        logger.warn(f'print_debug: __delayed_filters')
        for d in self.__delayed_filters:
            logger.warn(f'{d}')
        logger.warn(f'print_debug: __running_requests')
        for d in self.__running_requests:
            logger.warn(f'{d}')
        logger.warn(f'print_debug: __delayed_requests')
        for d in self.__delayed_requests:
            logger.warn(f'{d}')
        logger.warn(f'print_debug: __running_othertasks')
        for d in self.__running_othertasks:
            logger.warn(f'{d}')
        logger.warn(f'print_debug: __delayed_othertasks')
        for d in self.__delayed_othertasks:
            logger.warn(f'{d}')

    def close(self):
        for task_list in self.___all_tasks:
            for task in task_list:
                if not task.is_persistent():
                    task.expire()
                if isinstance(task, Closeable):
                    task.close()
        super().close()


class Processor(Closeable):
    MAX_ERROR_COUNT = 5

    def __init__(self, runtime: IRuntime, shared_lock: threading.Condition):
        Closeable.__init__(self, explicit_close=False)
        self.__runtime = runtime
        self.__lock = shared_lock
        self.__keep_running = True
        self.__paused = False
        self.__tasks = TaskController(runtime)
        RKAThread(name=f'Processor {self}', target=self.__main_loop).start()

    def __main_loop(self):
        error_count = 0
        with self.__lock:
            while self.__keep_running:
                try:
                    running_requests = self.__tasks.prepare_running_requests()
                    running_filters = self.__tasks.prepare_running_filters()
                    self.__tasks.prepare_running_tasks()
                    self.__process_running_requests(running_requests, running_filters)
                    error_count = 0
                except Exception as e:
                    logger.error(f'error occured {e}')
                    error_count += 1
                    traceback.print_exc()
                    if error_count == Processor.MAX_ERROR_COUNT:
                        raise
                    self.__lock.wait(2.0)
                self.__lock.wait(PROCESSOR_TICK)

    def __cast_and_notify(self, ability: IAbility, immediate: bool) -> bool:
        logger.debug(f'Try casting now: {ability}, immediate {immediate}')
        if isinstance(ability, AbilitySnapshot):
            ability = ability.unwrap()
        cast = ability.cast()
        if cast:
            self.__tasks.visit_all_running_tasks(lambda task: task.notify_casting(ability) if isinstance(task, IAbilityCastingObserver) else None)
        return cast

    def __process_new_requests(self, running_requests: List[Request], running_filters: List[FilterTask]):
        if self.__paused:
            return
        self.__process_requests(running_requests, running_filters, immediate=True)

    def __process_running_requests(self, running_requests: List[Request], running_filters: List[FilterTask]):
        if len(running_requests) == 0:
            return
        self.__process_requests(running_requests, running_filters, immediate=False)

    def __process_requests(self, running_requests: List[Request], running_filters: List[FilterTask], immediate: bool):
        if len(running_requests) == 0:
            return
        all_available_abilities = AbilityBag()
        ability_filter = AbilityFilter().op_and_all(running_filters)
        for request in running_requests:
            request.set_ability_filter(ability_filter)
            available_abilities = request.get_available_ability_bag()
            assert available_abilities is not None, request
            if not available_abilities.is_empty():
                all_available_abilities.add_bag(available_abilities)
        if all_available_abilities.is_empty():
            logger.detail(f'all_available_abilities is empty')
            return
        reusable_abilities = all_available_abilities.get_bag_by_reusable()
        if reusable_abilities.is_empty():
            logger.detail(f'reusable_abilities is empty')
            return
        abilities_by_player: Dict[IPlayer, AbilityBag] = reusable_abilities.get_map_by_player()
        abilities_to_cast: Dict[IPlayer, AbilityBag] = dict()
        for player, abilities in abilities_by_player.items():
            recently_cast_ability = player.get_last_cast_ability()
            abilities_can_be_cast = abilities.get_bag_by_can_override(recently_cast_ability)
            if abilities_can_be_cast.is_empty():
                if logger.get_level() <= LogLevel.DETAIL:
                    logger.detail(f'{player}: recently_cast_ability: {recently_cast_ability}')
                    logger.detail(f'{player}: abilities_ready_to_cast, none can be cast: {abilities}')
                continue
            max_priority_abilities = abilities_can_be_cast.get_bag_by_max_priority()
            max_priority = max_priority_abilities.get_first_ability().get_priority()
            priority_in_range_abilities = abilities_can_be_cast.get_bag_by_priority_in_range(max_priority=max_priority,
                                                                                             priority_range=PRIORITY_SELECTION_MARGIN)
            preferred_abilities = priority_in_range_abilities.get_bag_by_general_preference(3)
            abilities_to_cast[player] = preferred_abilities
            if logger.get_level() <= LogLevel.DETAIL:
                logger.detail(f'{player}: recently_cast_ability: {recently_cast_ability}')
                logger.detail(f'{player}: abilities_ready_to_cast: {abilities}')
                logger.detail(f'{player}: abilities_can_be_cast: {abilities_can_be_cast}')
                logger.detail(f'{player}: max_priority_abilities: {max_priority_abilities}')
                logger.detail(f'{player}: priority_in_range_abilities: {priority_in_range_abilities}')
                logger.detail(f'{player}: top N preferred_abilities: {preferred_abilities}')
        # included in critical section to avoid races in immediate ability casting
        for player, abilities in abilities_to_cast.items():
            for ability in abilities.get_abilities():
                # cast a single ability per player
                try:
                    if self.__cast_and_notify(ability, immediate=immediate):
                        break
                except Exception as e:
                    logger.warn(f'Failed to cast {ability} due to {e}')
                    traceback.print_exc()
                    break

    def apply_current_filters(self, abilities: AbilityBag) -> AbilityBag:
        with self.__lock:
            running_filters = self.__tasks.prepare_running_filters()
            filters = AbilityFilter().op_and_all(running_filters)
            return abilities.get_bag_by_filter(filters)

    def run_auto(self, any_request: Task):
        if isinstance(any_request, Request):
            self.run_request(any_request)
        elif isinstance(any_request, FilterTask):
            self.run_filter(any_request)
        elif isinstance(any_request, Task):
            self.run_task(any_request)
        else:
            logger.error(f'Wrong task type: {any_request}')

    def run_request(self, request: Request, immediate=False):
        with self.__lock:
            self.__tasks.add_request(request)
            if not immediate:
                return
            if request.is_in_delay():
                logger.debug(f'run_request {request}: in_delay = {request.is_in_delay()}')
                return
            try:
                # call prepare_running_requests in order to move the new request from delayed list to running list
                self.__tasks.prepare_running_requests()
                running_filters = self.__tasks.prepare_running_filters()
                self.__process_new_requests([request], running_filters)
            except Exception as e:
                logger.error(f'exception occured when processing request {request}, {e}')
                traceback.print_exc()
                raise e

    def run_filter(self, ability_filter: FilterTask):
        with self.__lock:
            self.__tasks.add_filter(ability_filter)

    def run_task(self, task: Task):
        if isinstance(task, FilterTask):
            logger.warn(f'run_task: {task} is a FilterTask!')
        with self.__lock:
            self.__tasks.add_othertask(task)

    def pause(self) -> bool:
        if self.__paused:
            return False
        self.__paused = True
        logger.info('pausing')
        return True

    def resume(self) -> bool:
        if not self.__paused:
            return False
        self.__paused = False
        logger.info('resuming')
        return True

    def is_paused(self) -> bool:
        return self.__paused

    def clear_processor(self):
        with self.__lock:
            self.__tasks.expire_requests_and_othertasks()

    def visit_tasks(self, cb: Callable[[Task], None]):
        with self.__lock:
            self.__tasks.visit_requests_and_othertasks(cb)

    def print_debug(self):
        with self.__lock:
            self.__tasks.print_debug()

    def close(self):
        with self.__lock:
            self.__keep_running = False
            self.__tasks.close()
            self.__lock.notify_all()
        super().close()


class ProcessorFactory:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__shared_lock = threading.Condition()

    def create_processor(self) -> Processor:
        return Processor(self.__runtime, self.__shared_lock)
