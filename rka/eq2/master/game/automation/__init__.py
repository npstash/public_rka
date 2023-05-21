from typing import Optional

from rka.components.io.log_service import LogService
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import TellType
from rka.eq2.master.game.scripting.framework import PlayerScriptingFramework
from rka.log_configs import LOG_AUTOMATION

logger = LogService(LOG_AUTOMATION)


class ChatMessage:
    def __init__(self, from_player_name: Optional[str] = None,
                 tell_type: Optional[TellType] = None,
                 channel_name: Optional[str] = None,
                 tell: Optional[str] = None,
                 to_player: Optional[IPlayer] = None,
                 to_local: Optional[bool] = None):
        self.from_player_name = from_player_name
        self.tell_type = tell_type
        self.channel_name = channel_name
        self.tell = tell
        self.to_player = to_player
        self.to_local = to_local

    def __str__(self) -> str:
        return f'Message: {self.from_player_name} to {self.to_player}: "{self.tell}"'

    @staticmethod
    def from_event(event: ChatEvents.PLAYER_TELL):
        return ChatMessage(from_player_name=event.from_player_name,
                           tell_type=event.tell_type,
                           tell=event.tell,
                           to_player=event.to_player,
                           to_local=event.to_local)


class IChatCommand:
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        raise NotImplementedError()
