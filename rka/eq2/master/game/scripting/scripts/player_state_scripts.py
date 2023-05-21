from typing import Optional, Callable

from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import ALT1_NAME, ALT2_NAME, ALT3_NAME, ALT5_NAME, ALT4_NAME
from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.shared import Groups, ClientFlags


class AsyncLoginScript(PlayerScriptTask):
    def __init__(self, player_filter: Optional[Callable[[IPlayer], bool]] = None):
        PlayerScriptTask.__init__(self, None, 10000.0)
        self.player_filter = player_filter

    def __login_player(self, psf: PlayerScriptingFramework, target_player: Optional[IPlayer]):
        psf.player_processing_start_random_wait()
        # self.sleep(10000.0)
        _, login_success = psf.login_async(target_player)
        if login_success:
            self.get_runtime().overlay.log_event(f'Player {target_player} logged in', Severity.Normal)
        else:
            self.get_runtime().overlay.log_event(f'Player {target_player} failed to log in', Severity.High)

    def __player_filter(self, player: IPlayer) -> bool:
        if self.player_filter:
            return self.player_filter(player)
        return True

    def _run(self, runtime: IRuntime):
        can_login = runtime.playerselectors.can_login(self.__player_filter).resolve_players()
        for player in can_login:
            self.run_concurrent_task(self.__login_player, self.get_player_scripting_framework(player), player)
        cant_login = runtime.playerselectors.cant_login(self.__player_filter).resolve_players()
        exclude_players = list(can_login)
        for player in cant_login:
            can_relog_into = runtime.playerselectors.can_relog_into(player).resolve_players()
            if not can_relog_into:
                logger.warn(f'No host to login {player}')
                continue
            # exclude conflicts with players already logged in
            for can_relog_into_1 in can_relog_into:
                if can_relog_into_1 not in exclude_players:
                    self.run_concurrent_task(self.__login_player, self.get_player_scripting_framework(can_relog_into_1), player)
                    exclude_players.append(player)
                    exclude_players.append(can_relog_into_1)
                    break


@GameScriptManager.register_game_script([ScriptCategory.PLAYERSTATE, ScriptCategory.QUICKSTART], 'Login (selected player)')
class SelectedPlayersLogin(AsyncLoginScript):
    def __init__(self):
        AsyncLoginScript.__init__(self, player_filter=self.__player_filter)

    def __player_filter(self, player: IPlayer) -> bool:
        return player.get_client_config_data().overlay_id == self.get_runtime().overlay.get_selection_id()


class GroupLogin(AsyncLoginScript):
    def __init__(self, group_id: Groups):
        AsyncLoginScript.__init__(self, player_filter=self.__player_filter)
        self.group_id = group_id

    def __player_filter(self, player: IPlayer) -> bool:
        return player.get_client_config_data().group_id == self.group_id


@GameScriptManager.register_game_script([ScriptCategory.PLAYERSTATE, ScriptCategory.QUICKSTART], 'Login (group 1 remote players)')
class Login1stGroup(GroupLogin):
    def __init__(self):
        GroupLogin.__init__(self, group_id=Groups.MAIN_1)


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Login (group 1 alt remote players)')
class Login1stAltGroup(GroupLogin):
    def __init__(self):
        GroupLogin.__init__(self, group_id=Groups.MAIN_2)


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Login (group 2 remote players)')
class Login2ndGroup(GroupLogin):
    def __init__(self):
        GroupLogin.__init__(self, group_id=Groups.RAID_2)


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Login (ascensions farming group)')
class LoginAscensionFarmGroup(AsyncLoginScript):
    def __init__(self):
        AsyncLoginScript.__init__(self, player_filter=self.__player_filter)

    def __player_filter(self, player: IPlayer) -> bool:
        return player.get_player_name() in [ALT1_NAME, ALT2_NAME, ALT3_NAME, ALT4_NAME, ALT5_NAME]


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Logout (hidden players)')
class HiddenPlayersLogout(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Logout players', 25.0)

    def _run_player(self, psf: PlayerScriptingFramework):
        psf.logout()

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote | ClientFlags.Hidden)
        self.run_concurrent_players(players)


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Fix alive status (zoned remote players)')
class RemotePlayersFixAliveStatus(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'fix alive status', -1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned):
            if player.is_alive():
                player.set_alive(False)
            player.set_alive(True)


@GameScriptManager.register_game_script(ScriptCategory.PLAYERSTATE, 'Fix group assignment (all remote players)')
class RemotePlayersFixGroupAssignment(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'fix group assignment', -1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Offline):
            player.get_client_config_data().restore_group()
