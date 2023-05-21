from __future__ import annotations

import threading
from datetime import datetime
from typing import Dict, List, Optional

from rka.eq2.configs.shared.rka_constants import UI_REACT_DELAY
from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import TOptionalPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import RepeatMode, ScriptException
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.patterns.craft.bundle import craft_patterns
from rka.eq2.master.game.scripting.procedures.tradeskill import CraftProcedure, BuyRecipesProcedure, TradeskillWritProcedure, TradeskillTriggersProcedure
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.scripts.inventory_scripts import SalvageFirstBagOfItems
from rka.eq2.shared import ClientFlags


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Keep crafting - pristine stage (selected player)')
class KeepCrafting(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Keep crafting current item', duration=-1.0)

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(None)
        while True:
            crafter = CraftProcedure(psf)
            psf.try_close_all_access()
            crafter.craft_from_resources_view()
            psf.try_close_all_access()
            psf.assert_click_match(pattern=craft_patterns.PATTERN_GFX_START_CRAFTING, repeat=RepeatMode.DONT_REPEAT, delay=UI_REACT_DELAY)


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Keep tinkering - 4 sec (selected player)')
class KeepTinkering(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Keep crafting current item', duration=-1.0)

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(None)
        while True:
            crafter = CraftProcedure(psf)
            psf.try_close_all_access()
            crafter.craft_from_resources_view(time_limit=4.0)
            psf.try_close_all_access()
            psf.assert_click_match(pattern=craft_patterns.PATTERN_GFX_START_CRAFTING, repeat=RepeatMode.DONT_REPEAT, delay=UI_REACT_DELAY)


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Keep adorning - 30 sec (selected item)')
class KeepTinkering(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Keep crafting current item', duration=-1.0)

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(None)
        super().set_description(f'Keep crafting current item: {psf.get_player()}')
        while True:
            crafter = CraftProcedure(psf)
            psf.try_close_all_access()
            crafter.craft_from_resources_view(time_limit=30.0)
            psf.try_close_all_access()
            psf.assert_click_match(pattern=craft_patterns.PATTERN_GFX_START_CRAFTING, repeat=RepeatMode.DONT_REPEAT, delay=UI_REACT_DELAY)


class CraftingScript(PlayerScriptTask):
    __running_scripts: Dict[str, CraftingScript] = dict()
    __lock = threading.Lock()

    @staticmethod
    def _register_script(player_name: str, script: CraftingScript):
        with CraftingScript.__lock:
            CraftingScript.__running_scripts[player_name] = script

    @staticmethod
    def _unregister_script(player_name: str):
        with CraftingScript.__lock:
            if player_name in CraftingScript.__running_scripts.keys():
                del CraftingScript.__running_scripts[player_name]

    @staticmethod
    def get_script(player_name: str) -> Optional[CraftingScript]:
        with CraftingScript.__lock:
            if player_name in CraftingScript.__running_scripts.keys():
                return CraftingScript.__running_scripts[player_name]
        return None

    @staticmethod
    def get_script_players() -> List[str]:
        with CraftingScript.__lock:
            return list(CraftingScript.__running_scripts.keys())

    def __init__(self, description: str, player: TOptionalPlayer):
        PlayerScriptTask.__init__(self, description, -1.0)
        self._keep_crafting = True
        self.player = player

    def _run(self, runtime: IRuntime):
        raise NotImplementedError()

    def stop_crafting(self):
        self._keep_crafting = False


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Rush orders (selected player)')
class RushOrderCrafting(CraftingScript):
    def __init__(self, player: TOptionalPlayer = None):
        CraftingScript.__init__(self, f'Rush orders: {player}', player)

    def _run(self, runtime: IRuntime):
        player = self.player = self.resolve_player(self.player)
        player_name = player.get_player_name()
        guild_hall_config = player.get_player_info().guildhall_config
        assert guild_hall_config.guildhall_name in player.get_zone()
        crafter_class = player.get_crafter_class()
        recipe_merchant_name = guild_hall_config.recipe_merchant_name
        use_panic_mode = not guild_hall_config.private_guild
        script = CraftingScript.get_script(player_name)
        if script:
            script.expire()
            self.sleep(2.0)
        CraftingScript._register_script(player_name, self)
        psf = self.get_player_scripting_framework(player)
        triggers = TradeskillTriggersProcedure(psf, use_panic_mode)
        self._keep_crafting = True
        try:
            triggers.start_tradeskill_triggers()
            while self._keep_crafting:
                psf.recenter_camera()
                writ_runner = TradeskillWritProcedure(psf)
                psf.try_close_all_windows()
                try:
                    writ_runner.ts_writ_round()
                finally:
                    new_levels = triggers.retrieve_acquired_levels()
                    if new_levels:
                        recipe_buyer = BuyRecipesProcedure(psf, recipe_merchant_name, crafter_class.name)
                        if not recipe_buyer.acquire_recipes(new_levels):
                            raise ScriptException(f'Could not buy recipes for {new_levels}, player {player}')
        except Exception as e:
            now = datetime.now().strftime('%H:%M')
            runtime.notification_service.post_notification(f'{player}: Crafting failed at {now}, with {e}')
            raise
        finally:
            CraftingScript._unregister_script(player_name)
            triggers.cancel_tradeskill_triggers()


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Finish all current craft scripts')
class FinishCraftingScripts(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Finish all crafts', duration=-1.0)

    def _run(self, runtime: IRuntime):
        player_names = CraftingScript.get_script_players()
        for player_name in player_names:
            script = CraftingScript.get_script(player_name)
            if script is None:
                continue
            script.stop_crafting()


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Rush orders (online hidden players)')
class HiddenPlayersRushOrderCrafting(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Hidden players craft rush orders', duration=-1.0)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote | ClientFlags.Hidden)
        for player in players:
            script = RushOrderCrafting(player)
            runtime.processor.run_auto(script)
            self.sleep(1.0)


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Rush orders (logged remote players)')
class AllCraftersRushOrderCrafting(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'All logged crafters do rush orders', duration=-1.0)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Logged)
        for player in players:
            if not player.get_crafter_class():
                continue
            script = RushOrderCrafting(player)
            runtime.processor.run_auto(script)
            self.sleep(1.0)


@GameScriptManager.register_game_script(ScriptCategory.TRADESKILL, 'Produce uncommon materials (selected player)')
class CraftUncommonMaterial(CraftingScript):
    def __init__(self, player: TOptionalPlayer, item_name='uncommon material', items_per_round=30, max_rounds=-1):
        CraftingScript.__init__(self, f'Uncommon material crafting: {player} from {item_name}', player)
        self.__item_name = item_name
        self.__items_per_round = items_per_round
        self.__max_rounds = max_rounds

    def _run(self, runtime: IRuntime):
        player = self.player = self.resolve_player(self.player)
        guild_hall_config = player.get_player_info().guildhall_config
        panic_mode = not guild_hall_config.private_guild
        crafting_station_location = guild_hall_config.workstation_locations[player.get_crafter_class()]
        CraftingScript._register_script(player.get_player_name(), self)
        psf = self.get_player_scripting_framework(player)
        triggers = TradeskillTriggersProcedure(psf, panic_mode)
        triggers.start_tradeskill_triggers()
        try:
            psf.move_to_location(crafting_station_location, high_precision=True)
            crafter = CraftProcedure(psf)
            psf.try_close_all_windows()
            crafter.open_craft_station()
            tradeskilling = TradeskillWritProcedure(psf)
            tradeskilling.craft_items({self.__item_name: (self.__items_per_round, 1)})
            psf.try_close_all_windows()
        finally:
            CraftingScript._unregister_script(player.get_player_name())
            triggers.cancel_tradeskill_triggers()
            salvage_script = SalvageFirstBagOfItems(self.__player_name, self.__items_per_round)
            runtime.processor.run_auto(salvage_script)
            salvage_script.wait_until_completed()
        if self.__max_rounds != 0 and self._keep_crafting:
            next_round = CraftUncommonMaterial(self.player, self.__item_name, self.__items_per_round, self.__max_rounds - 1)
            runtime.processor.run_auto(next_round)
