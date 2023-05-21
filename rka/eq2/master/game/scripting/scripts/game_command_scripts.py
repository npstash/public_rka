from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import IPlayerSelector
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.shared import ClientFlags


class RunCommand(PlayerScriptTask):
    def __init__(self, player_selector: IPlayerSelector, command: str):
        PlayerScriptTask.__init__(self, f'Run command {command}', -1.0)
        self.__player_selector = player_selector
        self.__command = command
        self.set_silent()

    def _run(self, runtime: IRuntime):
        for player in self.__player_selector.resolve_players():
            psf = self.get_player_scripting_framework(player)
            action = psf.build_multicommand(self.__command)
            psf.player_bool_action(action)


class RemotePlayersResetZones(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'reset zones', -1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.player_mgr.get_players(and_flags=ClientFlags.Remote):
            psf = self.get_player_scripting_framework(player)
            psf.reset_zones()
