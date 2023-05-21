from rka.components.events import event, Events
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import TellType


class ChatEvents(Events):
    EMOTE = event(player=IPlayer, emote=str, min_wildcarding=str, max_wildcarding=str, to_local=bool)
    ACT_TRIGGER_FOUND = event(actxml=str, from_player_name=str, to_player=IPlayer)
    POINT_AT_PLAYER = event(pointing_player=IPlayer, pointed_player_name=str, pointed_player=IPlayer)
    PLAYER_TELL = event(from_player_name=str, teller_is_you=bool, tell_type=TellType, channel_name=str, tell=str, to_player=IPlayer, to_player_name=str, to_local=bool)


if __name__ == '__main__':
    ChatEvents.update_stub_file()
