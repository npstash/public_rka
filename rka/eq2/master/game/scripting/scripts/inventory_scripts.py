from typing import Optional

from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability.generated_abilities import ArtisanAbilities, CommonerAbilities
from rka.eq2.master.game.interfaces import IPlayer, TOptionalPlayer, IAbilityLocator, TValidPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.procedures.equipment import ApplyAdornsProcedure
from rka.eq2.master.game.scripting.procedures.tradeskill import ProcessBagsOfItems, BuyItems
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared import ClientFlags


class UseTemporaryAdorns(PlayerScriptTask):
    def __init__(self, player: Optional[IPlayer]):
        PlayerScriptTask.__init__(self, f'{player} use temporary adorns', -1.0)
        self.__player = player

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.try_close_all_windows()
        adorner = ApplyAdornsProcedure(psf)
        adorner.apply_adorns()

    def _run(self, runtime: IRuntime):
        selected_player = self.resolve_player(self.__player)
        if not self.__player or not selected_player:
            players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Logged)
        else:
            players = [selected_player]
        self.run_concurrent_players(players)


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Use temp adorns (remote players or selected player)')
class RemotePlayersUseTemporaryHPAdorns(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Remote players use temp adorns', -1.0)

    def _run(self, runtime: IRuntime):
        player = self.resolve_player(None)
        player = None if not player or player.is_local() else player
        # Player being None will cause selecting all remote players
        script = UseTemporaryAdorns(player)
        runtime.processor.run_auto(script)
        script.wait_until_completed()


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Use temp adorns (local player)')
class LocalPlayerUseAllTemporaryAdorns(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Local player use temp adorns', -1.0)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        assert main_player
        script = UseTemporaryAdorns(main_player)
        runtime.processor.run_auto(script)
        script.wait_until_completed()


class ProcessFirstBagOfItems(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer, ability_locator: IAbilityLocator, max_items: Optional[int]):
        PlayerScriptTask.__init__(self, f'Apply {ability_locator} to bag contents, player {player}', duration=-1.0)
        self.player = player
        self.max_items = max_items
        self.ability_locator = ability_locator

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        transmuter = ProcessBagsOfItems(psf, self.ability_locator, self.max_items)
        psf.try_close_all_windows()
        transmuter.toggle_bags()
        transmuter.process_bag_of_items()
        transmuter.toggle_bags()
        psf.try_close_all_windows()


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Salvage items in first bag (selected player)')
class SalvageFirstBagOfItems(ProcessFirstBagOfItems):
    def __init__(self, player: TOptionalPlayer = None, max_items: Optional[int] = None):
        ProcessFirstBagOfItems.__init__(self, player, ArtisanAbilities.salvage, max_items)


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Transute items in first bag (selected player)')
class TransmuteFirstBagOfItems(ProcessFirstBagOfItems):
    def __init__(self, player: TOptionalPlayer = None, max_items: Optional[int] = None):
        ProcessFirstBagOfItems.__init__(self, player, CommonerAbilities.transmute, max_items)


class ProcessFirstBagAllRemotePlayers(PlayerScriptTask):
    def __init__(self, ability_locator: IAbilityLocator):
        PlayerScriptTask.__init__(self, f'Apply {ability_locator} to bag contents all players', duration=-1.0)
        self.ability_locator = ability_locator

    def _run_player(self, psf: PlayerScriptingFramework):
        script = ProcessFirstBagOfItems(psf.get_player(), self.ability_locator, None)
        psf.run_script(script)

    def _run(self, runtime: IRuntime):
        remote_players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)
        self.run_concurrent_players(remote_players)


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Salvage items in first bag (remote players)')
class SalvageFirstBagAllRemotePlayers(ProcessFirstBagAllRemotePlayers):
    def __init__(self):
        ProcessFirstBagAllRemotePlayers.__init__(self, ArtisanAbilities.salvage)


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Transmute items in first bag (remote players)')
class TransmuteFirstBagAllRemotePlayers(ProcessFirstBagAllRemotePlayers):
    def __init__(self):
        ProcessFirstBagAllRemotePlayers.__init__(self, CommonerAbilities.transmute)


@GameScriptManager.register_game_script(ScriptCategory.INVENTORY, 'Buy from broker and transmute - one round (selected player)')
class RoundOfBuyAndTransmute(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer = None, max_items: Optional[int] = None):
        PlayerScriptTask.__init__(self, f'Transmute bag contents: {player}', duration=-1.0)
        self.max_items = max_items
        self.player = player

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        buyer = BuyItems(psf)
        buyer.buy_bag_of_items_from_open_broker(self.max_items)
        transmuter = ProcessBagsOfItems(psf, CommonerAbilities.transmute)
        transmuter.toggle_bags()
        transmuter.process_bag_of_items(self.max_items)
        transmuter.toggle_bags()


class DestroyItemInBags(PlayerScriptTask):
    def __init__(self, player: TValidPlayer, item_name: str, open_bags=True, count=1):
        PlayerScriptTask.__init__(self, f'Destroy {item_name} of {player}', duration=15.0)
        self.item_name = item_name
        self.open_bags = open_bags
        self.count = count
        self.player = player
        self.destroyed_succesfully = False
        self.set_silent()

    def _run(self, runtime: IRuntime):
        runtime.overlay.log_event(f'{self.player.get_player_name()} destroy {self.item_name}', Severity.Normal)
        psf = self.get_player_scripting_framework(self.player)
        destroyed_count = psf.destroy_item_in_bags(self.item_name, open_bags=self.open_bags, count=self.count)
        self.destroyed_succesfully = destroyed_count > 0


class UseItem(PlayerScriptTask):
    def __init__(self, player: TValidPlayer, item_id: int, casting: Optional[float] = None):
        PlayerScriptTask.__init__(self, f'Use {item_id} of {player}', duration=15.0)
        self.item_id = item_id
        self.casting = casting
        self.player = player
        self.set_silent()

    def _run(self, runtime: IRuntime):
        self.get_player_scripting_framework(self.player).use_item_by_id(self.item_id, casting=self.casting)
