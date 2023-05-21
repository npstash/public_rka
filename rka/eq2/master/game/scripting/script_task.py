from __future__ import annotations

import time
import traceback
from threading import Condition, RLock
from typing import Optional, List, Type, Dict, Callable

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime, RequiresRuntime, HasRuntime
from rka.eq2.master.game.engine.task import Task
from rka.eq2.master.game.scripting import ScriptGuard, ScriptException, logger
from rka.eq2.master.game.scripting.toolkit import ScriptingToolkit
from rka.eq2.shared.shared_workers import shared_scheduler


class ScriptTask(Task, ScriptingToolkit, Closeable, RequiresRuntime, ScriptGuard):
    __singleton_instances: Dict[Type, ScriptTask] = dict()
    __singletons_lock = RLock()

    def __init__(self, description: Optional[str], duration: float):
        Task.__init__(self, description=description, duration=duration)
        ScriptingToolkit.__init__(self, self)
        Closeable.__init__(self, explicit_close=True)
        RequiresRuntime.__init__(self)
        self.__script_thread = None
        self.__started = False
        self.__completed = False
        self.__completed_callbacks: List[Callable[[], None]] = list()
        self.__flag_lock = Condition()
        self.__silent_script = False
        self.__persistent = False
        self.__singleton = False
        self.__singleton_override = False
        self.__subscripts: List[ScriptTask] = list()

    def is_script_action_allowed(self) -> bool:
        return self.is_running() and not self.is_expired()

    def set_silent(self):
        self.__silent_script = True

    def set_persistent(self):
        self.__persistent = True

    def is_persistent(self) -> bool:
        return self.__persistent

    def set_singleton(self, override_previous: bool):
        self.__singleton = True
        self.__singleton_override = override_previous

    def callback_when_completed(self, callback: Callable[[], None]):
        self.__completed_callbacks.append(callback)

    def add_subscript(self, script: ScriptTask):
        self.__subscripts.append(script)
        if self.is_running() and not script.is_running():
            self.get_runtime().processor.run_auto(script)

    def get_runtime(self) -> IRuntime:
        assert self.__started
        return RequiresRuntime.get_runtime(self)

    def is_running(self) -> bool:
        with self.__flag_lock:
            return self.__started and not self.__completed

    def __alert_fail(self):
        if not self.__silent_script:
            self.get_runtime().alerts.major_trigger()
            time.sleep(0.2)
            self.get_runtime().alerts.major_trigger()

    def __run_loop(self):
        runtime = self.get_runtime()
        self.__completed_result = None
        try:
            if not self.__silent_script:
                runtime.overlay.log_event(f'Start: {self}', Severity.Normal)
            if self.__singleton:
                script_type = type(self)
                with ScriptTask.__singletons_lock:
                    if script_type in ScriptTask.__singleton_instances:
                        script = ScriptTask.__singleton_instances[script_type]
                        if script.is_running():
                            if not self.__singleton_override:
                                return
                            else:
                                script.expire()
                    ScriptTask.__singleton_instances[script_type] = self
            for script in self.__subscripts:
                if not script.is_running():
                    runtime.processor.run_auto(script)
            self._run(runtime)
            self._on_run_completed()
            for cb in self.__completed_callbacks:
                cb()
        except ScriptException as e:
            logger.info(f'Script: {self} stopped by: {e}')
            if not self.__silent_script:
                runtime.overlay.log_event(f'Script cancelled: {self}', Severity.Normal)
        except Exception as e:
            logger.warn(f'Script: {self} stopped by: {e}')
            traceback.print_exc()
            if not self.__silent_script:
                runtime.overlay.log_event(f'Script failed: {self}', Severity.High)
            self.__alert_fail()
        finally:
            if not self.__silent_script:
                runtime.overlay.log_event(f'Script done: {self}', Severity.Normal)
            if self.__singleton:
                script_type = type(self)
                with ScriptTask.__singletons_lock:
                    if script_type in ScriptTask.__singleton_instances and ScriptTask.__singleton_instances[script_type] == self:
                        del ScriptTask.__singleton_instances[script_type]
            for script in self.__subscripts:
                script.expire()
            # this also sets the __complete flag by expiring self
            self.close()

    def _on_start(self):
        with self.__flag_lock:
            if self.__started:
                logger.warn(f'start_script: {self} already started')
                return
            if self.__completed:
                logger.warn(f'start_script: {self} already completed')
                return
            self.__started = True
            self.__flag_lock.notify_all()
        self.__script_thread = RKAThread(name=f'Script {self}', target=self.__run_loop)
        self.__script_thread.start()
        logger.debug(f'the script {self} has been started')

    def _on_expire(self):
        self.__cancel_waiting()

    def wait_until_started(self, timeout: Optional[float] = None) -> bool:
        with self.__flag_lock:
            while not self.__started or not self.__completed:
                if timeout is not None:
                    if timeout < 0.0:
                        return False
                wait_start = time.time()
                self.__flag_lock.wait(timeout)
                if timeout is not None:
                    timeout -= time.time() - wait_start
            return self.__started

    def wait_until_completed(self, timeout: Optional[float] = None) -> bool:
        with self.__flag_lock:
            while not self.__completed:
                if timeout is not None:
                    if timeout < 0.0:
                        return False
                wait_start = time.time()
                self.__flag_lock.wait(timeout)
                if timeout is not None:
                    timeout -= time.time() - wait_start
            return self.__completed

    def __cancel_waiting(self):
        logger.debug(f'expiring the script {self}')
        with self.__flag_lock:
            self.__completed = True
            self.__flag_lock.notify_all()

    def expire(self):
        self.__cancel_waiting()
        Task.expire(self)

    def fail_script(self, reason):
        self.expire()
        ScriptingToolkit.fail_script(self, reason)

    def close(self):
        self.__completed_callbacks.clear()
        self.expire()
        Closeable.close(self)

    def _run(self, runtime: IRuntime):
        raise NotImplementedError()

    def _on_run_completed(self):
        pass


class IScriptQueue:
    def start_next_script(self, script: ScriptTask):
        raise NotImplementedError()


class ScriptExclusionGuard(IScriptQueue):
    def __init__(self, has_runtime: HasRuntime, restart_delay: float):
        self.__has_runtime = has_runtime
        self.__restart_delay = restart_delay
        self.__current_script = None
        self.__current_script_future = None

    def start_next_script(self, script: ScriptTask):
        if self.__current_script_future:
            self.__current_script_future.cancel_future()
        delay = 0.0
        if self.__current_script:
            self.__current_script.expire()
            delay = self.__restart_delay
        self.__current_script = script
        self.__current_script.callback_when_completed(lambda: self.__script_completed(script))
        runtime = self.__has_runtime.get_runtime()
        self.__current_script_future = shared_scheduler.schedule(lambda: runtime.processor.run_auto(self.__current_script), delay=delay)

    def __script_completed(self, script: ScriptTask):
        if script == self.__current_script:
            self.__current_script = None


class ScriptMultiExclusionGuard:
    def __init__(self, has_runtime: HasRuntime):
        self.__has_runtime = has_runtime
        self.__guards: Dict[str, ScriptExclusionGuard] = dict()

    def get_guard(self, key: str, restart_delay: float) -> ScriptExclusionGuard:
        if key not in self.__guards:
            guard = ScriptExclusionGuard(self.__has_runtime, restart_delay)
            self.__guards[key] = guard
        else:
            guard = self.__guards[key]
        return guard

    def start_next_script(self, key: str, script: ScriptTask, restart_delay: float):
        guard = self.get_guard(key, restart_delay)
        guard.start_next_script(script)


class ScriptQueue(IScriptQueue):
    def __init__(self, has_runtime: HasRuntime):
        self.__has_runtime = has_runtime
        self.__pending_scripts = []
        self.__current_script = None

    def start_next_script(self, script: ScriptTask):
        if self.__current_script:
            self.__pending_scripts.append(script)
            return
        self.__current_script = script
        self.__current_script.callback_when_completed(lambda: self.__script_completed(script))
        runtime = self.__has_runtime.get_runtime()
        runtime.processor.run_auto(self.__current_script)

    def __script_completed(self, script: ScriptTask):
        if script in self.__pending_scripts:
            self.__pending_scripts.remove(script)
            return
        if script == self.__current_script:
            self.__current_script = None
            if self.__pending_scripts:
                new_script = self.__pending_scripts[0]
                self.start_next_script(new_script)
            return
        logger.warn(f'Unknown script completed {script} for queue {self}')


class ScriptMultiQueue:
    def __init__(self, has_runtime: HasRuntime):
        self.__has_runtime = has_runtime
        self.__queues: Dict[str, ScriptQueue] = dict()

    def get_queue(self, key: str) -> ScriptQueue:
        if key not in self.__queues:
            queue = ScriptQueue(self.__has_runtime)
            self.__queues[key] = queue
        else:
            queue = self.__queues[key]
        return queue

    def start_next_script(self, key: str, script: ScriptTask):
        queue = self.get_queue(key)
        queue.start_next_script(script)


class IScriptTaskFactory:
    def create_script(self, key: Optional[str] = None) -> Optional[ScriptTask]:
        raise NotImplementedError()

    @staticmethod
    def simple_script_factory(script_type_callable: Callable[[], Optional[ScriptTask]]) -> IScriptTaskFactory:
        class _Factory(IScriptTaskFactory):
            def create_script(self, key: Optional[str] = None) -> Optional[ScriptTask]:
                return script_type_callable()

        return _Factory()
