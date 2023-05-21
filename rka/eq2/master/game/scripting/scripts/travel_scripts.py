from __future__ import annotations

from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability.ability_locator import AbilityLocator
from rka.eq2.master.game.ability.generated_abilities import CommonerAbilities, ItemsAbilities
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared import ClientFlags


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'COV to main player (non-zoned logged remote players)')
class NonZonedPlayersCovToMain(PlayerScriptTask):
    ac_wait_for_cov = action_factory.new_action().delay(1.5)
    ac_mouse_cov_flash_1 = action_factory.new_action().mouse(572, 180).delay(0.5)
    ac_mouse_cov_flash_2 = action_factory.new_action().mouse(529, 297).delay(0.5)
    ac_mouse_cov_flash_3 = action_factory.new_action().mouse(519, 339).delay(0.5)
    ac_mouse_cov_call_to = action_factory.new_action().mouse(339, 358).delay(0.5)
    ac_mouse_cov_accept_callto = action_factory.new_action().mouse(450, 547).delay(0.5)
    ac_mouse_cov_select_char = action_factory.new_action().mouse(342, 346).delay(0.5)
    ac_mouse_cov_accept_char = action_factory.new_action().mouse(450, 522).delay(0.5)

    def __init__(self):
        PlayerScriptTask.__init__(self, 'Remote players CoV', -1.0)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, max_status=PlayerStatus.Logged)
        for player in players:
            psf = self.get_player_scripting_framework(player)
            psf.recenter_camera()
            psf.cast_ability_sync(ItemsAbilities.call_of_the_veteran)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_wait_for_cov)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_flash_1)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_flash_2)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_flash_3)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_call_to)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_accept_callto)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_select_char)
            psf.player_bool_action(NonZonedPlayersCovToMain.ac_mouse_cov_accept_char)


class HiddenPlayersDisbandAndCall(PlayerScriptTask):
    def __init__(self, ability_locator: AbilityLocator):
        PlayerScriptTask.__init__(self, f'Disband and {ability_locator}', -1.0)
        self.__ability_locator = ability_locator

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.stop_follow()
        psf.stop_combat()
        request = psf.get_ready_ability_request(self.__ability_locator)
        if not request:
            return
        psf.leave_group()
        self.get_runtime().processor.run_request(request)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote | ClientFlags.Hidden, min_status=PlayerStatus.Zoned)
        self.run_concurrent_players(players)


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'Call to GH (zoned hidden players)')
class HiddenPlayersDisbandAndCallToGuildHall(HiddenPlayersDisbandAndCall):
    def __init__(self):
        HiddenPlayersDisbandAndCall.__init__(self, CommonerAbilities.call_to_guild_hall)


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'Call to Home City (zoned hidden players)')
class HiddenPlayersDisbandAndCallToCity(HiddenPlayersDisbandAndCall):
    def __init__(self):
        HiddenPlayersDisbandAndCall.__init__(self, CommonerAbilities.call_to_home)


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'Guild Hall (remote players)')
class GuildHallCall(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, self.__class__.__name__, -1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players(ClientFlags.Remote):
            self.get_player_scripting_framework(player).cast_ability_async(CommonerAbilities.call_to_guild_hall)
