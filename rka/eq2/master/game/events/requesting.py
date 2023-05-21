from typing import List

from rka.components.events import event, Events
from rka.eq2.master.game.interfaces import IPlayer


class RequestEvents(Events):
    # from request controller
    COMBAT_REQUESTS_START = event(main_controller=bool, controller_instance=object)
    COMBAT_REQUESTS_END = event(main_controller=bool, controller_instance=object)

    # events which indicate a request for action
    REQUEST_BALANCED_SYNERGY = event(player_name=str, local_player_request=bool)
    REQUEST_CURE_CURSE = event(target_name=str)
    REQUEST_CURE = event(target_name=str)
    REQUEST_DEATHSAVE = event(target_name=str)
    REQUEST_INTERCEPT = event(target_name=str)
    REQUEST_STUN = event()
    REQUEST_INTERRUPT = event()
    REQUEST_PLAYER_SET_TARGET = event(player=IPlayer, target_name=str, optional_targets=List[str], refresh_rate=float)


if __name__ == '__main__':
    RequestEvents.update_stub_file()
