from typing import List

from rka.eq2.configs.master.keyspecs import DefaultMainPlayerHotkeySpec
from rka.eq2.configs.master.triggers.friend_triggers import FriendTriggers
from rka.eq2.master import IRuntime
from rka.eq2.master.control.client_controller import LocalClientController
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.triggers import ITrigger


def get_controller_class_name(server_name: str, player_name: str) -> str:
    return f'{__name__}.{server_name}_{player_name}'


class Servername_Playername(LocalClientController):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        LocalClientController.__init__(self, runtime, player, DefaultMainPlayerHotkeySpec(player))

    def _get_player_triggers(self) -> List[ITrigger]:
        all_triggers = []
        friend_triggers = FriendTriggers(self._get_runtime(), self.get_player())
        all_triggers.extend(friend_triggers.triggers__standard_warden_tells())
        return all_triggers
