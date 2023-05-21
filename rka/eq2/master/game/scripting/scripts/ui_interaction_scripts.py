from __future__ import annotations

import time
from typing import Optional

import pyperclip
import regex as re

from rka.components.ui.overlay import Severity
from rka.components.ui.tts import ITTSSession
from rka.eq2.configs.shared.rka_constants import UI_REACT_DELAY, SERVER_REACT_DELAY
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.engine.filter_tasks import StopCastingFilter
from rka.eq2.master.game.interfaces import TOptionalPlayer, IPlayer, IPlayerSelector
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import RepeatMode, logger
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.patterns.detrims.bundle import detrim_patterns
from rka.eq2.master.game.scripting.procedures.common import ClickAtPointerProcedure
from rka.eq2.master.game.scripting.procedures.game_macro import MacroBuilder
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared import ClientFlags


class RemotePlayersAcceptInvite(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Accept invite', 20.0)

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.try_close_all_windows()
        psf.reset_zones()

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        players = []
        for player in runtime.player_mgr.get_players(and_flags=ClientFlags.Remote):
            if player.is_in_group_with(main_player):
                players.append(player)
        self.run_concurrent_players(players)


class RemotePlayersClickAccept(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer, repeats: int, close_windows: bool, externals=False):
        assert repeats > 0
        PlayerScriptTask.__init__(self, 'Click accept', duration=-1.0)
        self.__player = player
        self.__repeats = repeats
        self.__close_windows = close_windows
        self.__externals = externals

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.move_mouse_to_middle()
        for i in range(self.__repeats):
            if self.__close_windows:
                psf.try_close_all_windows(close_externals=self.__externals, click_delay=UI_REACT_DELAY)
            else:
                psf.try_click_accepts(click_delay=UI_REACT_DELAY)
            self.sleep(1.0)

    def _run(self, runtime: IRuntime):
        if not self.__player:
            logged_players = runtime.player_mgr.get_players(min_status=PlayerStatus.Online, and_flags=ClientFlags.Remote)
            switch_players = runtime.request_ctrl.player_switcher.resolve_players()
            players = runtime.playerselectors.intersection(logged_players, switch_players).resolve_players()
            self.run_concurrent_players(players)
        else:
            self._run_player(self.get_player_scripting_framework(self.__player))


class RemotePlayersClickAtPointerSmall(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Click pointed capture', -1.0)

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.recenter_camera()
        clicker = ClickAtPointerProcedure(psf)
        clicker.click(15, 0.7, scale_var=0.1)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        self.run_concurrent_players(players)


class RemotePlayersClickAtPointerLarge(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Click pointed capture large', -1.0)

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.recenter_camera()
        clicker = ClickAtPointerProcedure(psf)
        clicker.click(30, 0.63, scale_var=0.3)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        self.run_concurrent_players(players)


class RemotePlayersClickAtCenter(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer):
        PlayerScriptTask.__init__(self, 'Click middle', -1.0)
        self.__player = player

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.stop_all_noncontrol(3.0)
        psf.recenter_camera()
        psf.click_viewport_middle()
        psf.select_destination_zone(2)

    def _run(self, runtime: IRuntime):
        if self.__player is None:
            players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)
        else:
            players = [self.__player]
        self.run_concurrent_players(players)


class KeepClicking(PlayerScriptTask):
    def __init__(self, period=0.6):
        PlayerScriptTask.__init__(self, 'Keep clicking left button', -1.0)
        self.mouse_click = action_factory.new_action().mouse(None, None)
        self.period = period

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        psf = self.get_player_scripting_framework(main_player)
        while not self.is_expired():
            psf.post_player_action(self.mouse_click, delay=self.period)


class FillTextWhenAsked(PlayerScriptTask):
    def __init__(self, player: IPlayer, text: str, duration: float):
        PlayerScriptTask.__init__(self, f'{player} fill your name', duration)
        self.player = player
        self.text = text

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        duration = 10.0
        while not self.is_expired():
            if psf.click_match(ui_patterns.PATTERN_FIELD_ANY, repeat=RepeatMode.DONT_REPEAT, delay=0.0):
                self.extend(duration)
                runtime.overlay.log_event(f'{self.player} will type {self.text}')
                stop_abilities = StopCastingFilter(self.player, duration)
                runtime.processor.run_auto(stop_abilities)
                self.sleep(1.0)
                psf.call_player_action(action_factory.new_action().key('backspace', count=4))
                psf.call_player_action(action_factory.new_action().text(self.text))
                psf.try_click_accepts()
                stop_abilities.expire()
                return
            else:
                psf.sleep(1.0)


@GameScriptManager.register_game_script(ScriptCategory.UI_AUTOMATION, 'Keep accepting commissions (zoned remote players)')
class AcceptCommission(PlayerScriptTask):
    def __init__(self, player_sel: Optional[IPlayerSelector] = None, craft_count_limit: Optional[int] = None, time_limit: Optional[float] = None):
        PlayerScriptTask.__init__(self, f'Accept commissioning', duration=-1.0)
        self.__player_sel = player_sel
        self.__craft_count_limit = craft_count_limit
        self.__time_limit = time_limit

    def _run_player(self, psf: PlayerScriptingFramework):
        crafted_count = 0
        start_time = time.time()
        while True:
            if psf.click_match(pattern=ui_patterns.PATTERN_GFX_0_PLAT_COIN, repeat=RepeatMode.DONT_REPEAT, threshold=1.0):
                if psf.click_match(pattern=ui_patterns.PATTERN_BUTTON_1000_PLAT, repeat=RepeatMode.DONT_REPEAT):
                    if psf.click_match(pattern=ui_patterns.PATTERN_BUTTON_TEXT_OK_UPPERCASE, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY):
                        if psf.click_match(pattern=ui_patterns.PATTERN_BUTTON_TEXT_ACCEPT, repeat=RepeatMode.DONT_REPEAT):
                            crafted_count += 1
                            psf.get_runtime().overlay.log_event(f'{psf.get_player()} got {crafted_count}', Severity.High)
                            self.sleep(4.0)
            if self.__craft_count_limit and crafted_count >= self.__craft_count_limit:
                break
            if self.__time_limit and time.time() - start_time > self.__time_limit:
                break
            self.sleep(0.25)

    def _run(self, runtime: IRuntime):
        if self.__player_sel:
            players = self.__player_sel.resolve_players()
        else:
            players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        self.run_concurrent_players(players)


@GameScriptManager.register_game_script(ScriptCategory.UI_AUTOMATION, 'Create hotbar macros from export in clipboard (selected player)')
class BuildMacrosFromClipboard(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Build macros from clipboard', duration=-1.0)

    def _run(self, runtime: IRuntime):
        macros_from_clipboard = pyperclip.paste()
        if not isinstance(macros_from_clipboard, str):
            self.fail_script('No text in clipboard')
            return
        runtime.key_manager.pause(False)
        macro_started = False
        psf = self.get_player_scripting_framework(None)
        built_macro_names = set()
        builder = MacroBuilder(psf)
        for macro_line in macros_from_clipboard.split('\n'):
            if re.match(r'HOTKEYS .*', macro_line):
                continue
            if re.match(r'\d+ \d+ spell .*', macro_line):
                if macro_started:
                    builder.finish_current_macro()
                continue
            if re.match(r'\d+ \d+ inventory_hotkey .*', macro_line):
                if macro_started:
                    builder.finish_current_macro()
                continue
            if re.match(r'\d+ \d+ command .*', macro_line):
                if macro_started:
                    builder.finish_current_macro()
                continue
            match = re.match(r'(\d+) (\d+) macro -?\d+ \d+ \d+ (.*)', macro_line)
            if match:
                if macro_started:
                    builder.finish_current_macro()
                macro_started = True
                hotbar = int(match.group(1))
                slot = int(match.group(2))
                macro_name = match.group(3)
                if macro_name in built_macro_names:
                    continue
                if not builder.start_new_macro(hotbar, slot, macro_name):
                    self.fail_script(f'Cannot start new macro, line is: {macro_line}')
                built_macro_names.add(macro_name)
                continue
            if macro_started:
                builder.add_command_to_current_macro(macro_line.strip())
                continue
            self.fail_script(f'unexpected {macro_line}')
        if macro_started:
            builder.finish_current_macro()


class CureAnyVisibleCurses(PlayerScriptTask):
    def __init__(self, player_sel: IPlayerSelector, tts: Optional[ITTSSession] = None):
        PlayerScriptTask.__init__(self, 'Cure visible curses', -1.0)
        self.__player_sel = player_sel
        self.__tts = tts

    def _run_player(self, psf: PlayerScriptingFramework):
        player = psf.get_player()
        if psf.has_detriment_type(detrim_patterns.PERSONAL_ICON_CURSE_1):
            self.get_runtime().overlay.log_event(f'Found curse on: {player}', Severity.Normal)
            self.get_runtime().request_ctrl.request_cure_curse_target(player.get_player_name())
            tts = self.__tts
            # only one voice message can play at a time, no need to queue them up
            self.__tts = None
            if tts:
                tts.say(f'Cure {player.get_player_name()}')
        else:
            logger.info(f'No curse on: {player}')

    def _run(self, runtime: IRuntime):
        runtime.overlay.log_event(f'Find and cure all curses', Severity.Normal)
        players = self.__player_sel.resolve_players()
        self.run_concurrent_players(players)


class CureLastVisibleCurse(PlayerScriptTask):
    def __init__(self, player_sel: IPlayerSelector, recheck_period: float, attempts: int, tts: Optional[ITTSSession] = None):
        PlayerScriptTask.__init__(self, 'Cure visible curses', -1.0)
        self.__player_sel = player_sel
        self.__recheck_period = recheck_period if recheck_period > 1.0 else 1.0
        self.__attempts_left = attempts
        self.__tts = tts

    def _run(self, runtime: IRuntime):
        for _ in range(self.__attempts_left):
            players_with_curse = []
            for player in self.__player_sel:
                psf = self.get_player_scripting_framework(player)
                has_curse = psf.has_detriment_type(detrim_patterns.PERSONAL_ICON_CURSE_1)
                if has_curse:
                    players_with_curse.append(player)
                if len(players_with_curse) > 1:
                    break
            if not players_with_curse:
                return
            if len(players_with_curse) > 1:
                self.sleep(self.__recheck_period)
                continue
            runtime.request_ctrl.request_cure_curse_target(players_with_curse[0].get_player_name())
            break
