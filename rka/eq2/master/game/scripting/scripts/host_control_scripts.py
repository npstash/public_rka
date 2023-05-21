import os

from rka.eq2.configs.shared.game_constants import EQ2_LAUNCHER_BATCH_SLAVE_PATH, EQ2_REMOTE_SLAVE_TOOLBAR_PATH, EQ2_LOCAL_SLAVE_TOOLBAR_PATH
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared import ClientFlags


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Run EQ2 Launchpad (remote clients)')
class RemotePlayersRunLauncher(PlayerScriptTask):
    ac_run_launcher = action_factory.new_action().process(fr'C:\Windows\System32\cmd.exe', f'/C {EQ2_LAUNCHER_BATCH_SLAVE_PATH}')

    def __init__(self):
        PlayerScriptTask.__init__(self, None, 30.0)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)
        for player in players:
            client_id = player.get_client_id()
            self.post_client_action(RemotePlayersRunLauncher.ac_run_launcher, client_id)


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Run EQ2 executable (remote clients)')
class RemotePlayersRunEverquest(PlayerScriptTask):
    @staticmethod
    def get_launcher_action(launcher_batch: str):
        launcher_batch_path = os.path.join(EQ2_REMOTE_SLAVE_TOOLBAR_PATH, launcher_batch)
        return action_factory.new_action().process(os.path.normpath('C:/Windows/System32/cmd.exe'), f'/C {launcher_batch_path}')

    def __init__(self):
        PlayerScriptTask.__init__(self, 'Run Everquest', 90.0)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        if main_player is None:
            return
        for player in runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Online):
            if player.get_server() != main_player.get_server():
                continue
            launcher_batch = player.get_client_config_data().launcher_batch
            ac_launch_eq2 = RemotePlayersRunEverquest.get_launcher_action(launcher_batch)
            self.post_client_action(ac_launch_eq2, player.get_client_id())


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Put hosts to sleep (remote clients)')
class PutRemoteClientsToSleep(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Remote PC\'s go sleep', duration=-1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players():
            if player.is_local():
                continue
            path = os.path.join(EQ2_REMOTE_SLAVE_TOOLBAR_PATH, 'sleep.bat')
            action = action_factory.new_action().process(os.path.normpath(fr'C:/Windows/System32/cmd.exe'), f'/C {path}')
            action.post_async(player.get_client_id())


@GameScriptManager.register_game_script([ScriptCategory.HOST_CONTROL, ScriptCategory.QUICKSTART], 'Put hosts to sleep (working subset)')
class PutRemoteClientsToSleep(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Remote PC\'s go sleep (subset)', duration=-1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players():
            if player.is_local():
                continue
            if player.get_host_id() not in [1, 2, 3, 4, 5]:
                continue
            path = os.path.join(EQ2_REMOTE_SLAVE_TOOLBAR_PATH, 'sleep.bat')
            action = action_factory.new_action().process(os.path.normpath(fr'C:/Windows/System32/cmd.exe'), f'/C {path}')
            action.post_async(player.get_client_id())


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Hibernate hosts (remote clients)')
class PutRemoteClientsToHibernation(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Remote PC\'s hibernate', duration=-1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players():
            if player.is_local():
                continue
            action = action_factory.new_action().process(os.path.normpath(fr'C:/Windows/System32/shutdown.exe'), f'/h')
            action.post_async(player.get_client_id())


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Put host to sleep (local client)')
class PutLocalClientToSleep(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Local PC\'s go sleep', duration=-1.0)

    def _run(self, runtime: IRuntime):
        path = os.path.join(EQ2_LOCAL_SLAVE_TOOLBAR_PATH, 'sleep.bat')
        for player in runtime.player_mgr.get_players():
            if not player.is_local():
                continue
            action = action_factory.new_action().process(os.path.normpath(fr'C:/Windows/System32/cmd.exe'), f'/C {path}')
            action.post_async(player.get_client_id())


@GameScriptManager.register_game_script(ScriptCategory.HOST_CONTROL, 'Reboot host (selected player\'s client)')
class RebootClient(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Reboot client', duration=-1.0)

    def _run(self, runtime: IRuntime):
        player = self.resolve_player(None)
        if player:
            if player.is_local():
                return
            action = action_factory.new_action().process(os.path.normpath(fr'C:/Windows/System32/shutdown.exe'), f'/r')
            action.post_async(player.get_client_id())
