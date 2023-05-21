from itertools import chain
from typing import Set, Callable, List

from rka.eq2.master.game.engine.processor import Processor
from rka.eq2.master.game.engine.task import Task
from rka.eq2.shared.shared_workers import shared_worker


class Mode(Task):
    def __init__(self, processor: Processor, description: str, duration: float):
        Task.__init__(self, description=description, duration=duration)
        self.__processor = processor
        self.__starting_tasks: Set[Task] = set()
        self.__running_tasks: Set[Task] = set()
        self.__starting_and_expiring_at_close_tasks: Set[Task] = set()
        self.__extending_until_close_tasks: Set[Task] = set()
        self.__running_until_close_tasks: Set[Task] = set()
        self.__closing_tasks: Set[Task] = set()
        self.__starting_callbacks: List[Callable] = list()
        self.__closing_callbacks: List[Callable] = list()

    def add_task_for_starting(self, task: Task):
        self.__starting_tasks.add(task)

    def add_task_for_starting_and_expiring_at_close(self, task: Task):
        self.__starting_and_expiring_at_close_tasks.add(task)
        if self.is_running():
            self.__processor.run_auto(task)

    def add_task_for_running(self, task: Task):
        self.__running_tasks.add(task)
        if self.is_running():
            self.__processor.run_auto(task)

    def add_task_for_running_until_close(self, task: Task):
        self.__running_until_close_tasks.add(task)
        if self.is_running():
            self.__processor.run_auto(task)

    def add_task_for_extending_until_close(self, task: Task):
        self.__extending_until_close_tasks.add(task)

    def add_task_for_closing(self, task: Task):
        self.__closing_tasks.add(task)

    def add_callback_for_starting(self, callback: Callable):
        self.__starting_callbacks.append(callback)

    def add_callback_for_closing(self, callback: Callable):
        self.__closing_callbacks.append(callback)

    def _on_start(self):
        for task in chain(self.__starting_tasks, self.__running_tasks,
                          self.__starting_and_expiring_at_close_tasks, self.__running_until_close_tasks):
            self.__processor.run_auto(task)
        for task in self.__starting_callbacks:
            shared_worker.push_task(task)

    def _on_extend(self, remaining_duration: float):
        for task in chain(self.__running_tasks, self.__running_until_close_tasks):
            if task.is_expired():
                self.__processor.run_auto(task)
        for task in chain(self.__running_tasks, self.__running_until_close_tasks):
            task.extend(remaining_duration)
        expired_tasks_to_remove = list()
        for task in self.__extending_until_close_tasks:
            if task.is_expired():
                expired_tasks_to_remove.append(task)
            else:
                task.extend(remaining_duration)
        for task in expired_tasks_to_remove:
            self.__extending_until_close_tasks.remove(task)

    def _on_expire(self):
        for task in chain(self.__starting_tasks, self.__starting_and_expiring_at_close_tasks,
                          self.__running_tasks, self.__running_until_close_tasks,
                          self.__extending_until_close_tasks):
            task.expire()
        self.__starting_and_expiring_at_close_tasks.clear()
        self.__running_until_close_tasks.clear()
        self.__extending_until_close_tasks.clear()
        for task in self.__closing_tasks:
            self.__processor.run_auto(task)
        for task in self.__closing_callbacks:
            shared_worker.push_task(task)
