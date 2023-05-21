from __future__ import annotations

import time
from typing import Optional, Dict, Type

from rka.components.cleanup import Closeable
from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.rka_constants import AUTOCOMBAT_TICK
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.automation import logger
from rka.eq2.master.game.engine.request import Request
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.ui import PermanentUIEvents


class AutocombatScript(ScriptTask):
    def __init__(self):
        ScriptTask.__init__(self, description=self.__class__.__name__, duration=-1.0)
        self.keep_running = True

    def _run(self, runtime: IRuntime):
        raise NotImplementedError()

    def expire(self):
        self.keep_running = False
        ScriptTask.expire(self)

    def close(self):
        self.expire()
        Closeable.close(self)


class GroupAutocombatScript(AutocombatScript):
    def _run(self, runtime: IRuntime):
        try:
            runtime.overlay.log_event('Group autocombat', Severity.Critical, PermanentUIEvents.GROUP_AUTOCOMBAT.str())
            while self.keep_running:
                runtime.request_ctrl.request_group_normal_combat()
                self.sleep(2.0)
        finally:
            runtime.overlay.log_event(None, Severity.Critical, PermanentUIEvents.GROUP_AUTOCOMBAT.str())


class AfkAutocombatScript(AutocombatScript):
    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        if main_player is None:
            return
        ac = action_factory.new_action().key('1')
        try:
            runtime.overlay.log_event('AFK autocombat', Severity.Critical, PermanentUIEvents.AFK_AUTOCOMBAT.str())
            while self.keep_running:
                ac.post_async(main_player.get_client_id())
                self.sleep(0.5)
        finally:
            runtime.overlay.log_event(None, Severity.Critical, PermanentUIEvents.AFK_AUTOCOMBAT.str())


class Autocombat:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__last_combat_sustain_timestamp = time.time()
        self.__autocombat_scripts: Dict[Type[AutocombatScript], AutocombatScript] = dict()
        self.__defense_request: Optional[Request] = None
        self.__dps_request: Optional[Request] = None
        EventSystem.get_main_bus().subscribe(CombatParserEvents.DPS_PARSE_END(), self.__battle_timeout)

    # =============== MAIN PLAYER AUTOCOMBAT ===============
    def sustain_clicking(self):
        now = time.time()
        diff = now - self.__last_combat_sustain_timestamp
        logger.detail(f'sustain_autocombat last sustain: {diff}')
        if diff < AUTOCOMBAT_TICK:
            logger.detail(f'sustain_autocombat skip')
            return
        self.__last_combat_sustain_timestamp = time.time()
        if diff > 2 * AUTOCOMBAT_TICK:
            logger.detail(f'sustain_autocombat postpone')
            return
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            return
        logger.detail(f'sustain_autocombat send key')
        ac = action_factory.new_action().key('divide')
        ac.post_async(main_player.get_client_id())

    # =============== GROUP AUTOCOMBAT ===============
    def disable_autocombat_script(self, script_class: Type[AutocombatScript]) -> bool:
        if script_class in self.__autocombat_scripts and not self.__autocombat_scripts[script_class].is_expired():
            self.__autocombat_scripts[script_class].expire()
            del self.__autocombat_scripts[script_class]
            return True
        return False

    def toggle_autocombat_script(self, script_class: Type[AutocombatScript]):
        logger.info(f'toggle {script_class} autocombat')
        if self.disable_autocombat_script(script_class):
            return
        new_script = script_class()
        self.__autocombat_scripts[script_class] = new_script
        self.__runtime.processor.run_task(new_script)

    def __battle_timeout(self, _event: CombatParserEvents.DPS_PARSE_END):
        self.disable_autocombat_script(GroupAutocombatScript)
        self.disable_autocombat_script(AfkAutocombatScript)

    def toggle_group_autocombat(self):
        self.toggle_autocombat_script(GroupAutocombatScript)

    def toggle_afk_autocombat(self):
        self.toggle_autocombat_script(AfkAutocombatScript)

    def toggle_defense_rotation(self):
        # TODO monk only for now
        if self.__defense_request is not None:
            self.__defense_request.expire()
            self.__defense_request = None
            self.__runtime.overlay.log_event(None, Severity.Critical, PermanentUIEvents.MONK_DEFENSE.str())
            return
        self.__defense_request = self.__runtime.request_factory.monk_defense_rotation()
        self.__runtime.request_ctrl.run_and_sustain(self.__defense_request, restart_when_expired=False)
        self.__runtime.overlay.log_event('Defense rotation enabled', Severity.Critical, PermanentUIEvents.MONK_DEFENSE.str())

    def toggle_dps_rotation(self):
        # TODO monk only for now
        if self.__dps_request is not None:
            self.__dps_request.expire()
            self.__dps_request = None
            self.__runtime.overlay.log_event(None, Severity.Critical, PermanentUIEvents.MONK_OFFENSE.str())
            return
        self.__dps_request = self.__runtime.request_factory.monk_buffed_dps_rotation()
        self.__runtime.request_ctrl.run_and_sustain(self.__dps_request, restart_when_expired=False)
        self.__runtime.overlay.log_event('DPS rotation enabled', Severity.Critical, PermanentUIEvents.MONK_OFFENSE.str())
