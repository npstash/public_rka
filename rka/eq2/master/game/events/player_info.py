from rka.components.events import event, Events
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location


class PlayerInfoEvents(Events):
    ITEM_RECEIVED = event(player=IPlayer, item_name=str, container=str)
    ITEM_FOUND_IN_INVENTORY = event(player=IPlayer, item_name=str, bag=int, slot=int)
    LOCATION = event(player=IPlayer, location=Location)

    COMMISSION_OFFERED = event(crafter_name=str, crafter_is_my_player=bool, offered_player=IPlayer, item_name=str)
    QUEST_OFFERED = event(player=IPlayer, accepted=bool, failed=bool)

    FRIEND_LOGGED = event(friend_name=str, login=bool)
    PLAYER_LINKDEAD = event(player=IPlayer)

    PLAYER_ZONE_CHANGED = event(player=IPlayer, from_zone=str, to_zone=str)
    PLAYER_JOINED_GROUP = event(player_name=str, my_player=bool, player=IPlayer)
    PLAYER_LEFT_GROUP = event(player_name=str, my_player=bool, player=IPlayer)
    PLAYER_GROUP_DISBANDED = event(main_player=IPlayer)

    AUTOFOLLOW_BROKEN = event(player=IPlayer, followed_player_name=str)
    AUTOFOLLOW_IMPOSSIBLE = event(player=IPlayer)


if __name__ == '__main__':
    PlayerInfoEvents.update_stub_file()
