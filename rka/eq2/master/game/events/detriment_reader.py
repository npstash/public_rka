from typing import List

from rka.components.events import event, Events
from rka.components.ui.capture import Rect, Capture
from rka.eq2.master.game.interfaces import IPlayer


class DetrimentReaderEvents(Events):
    # specialized screen readers
    PERSONAL_DETRIMENT_FOUND = event(detriment_tag=str, player=IPlayer, detrim_rect=Rect, inspect_capture=Capture, since_previous=float)
    RAID_DETRIMENT_FOUND = event(detriment_tag=str, player_names=List[str], since_previous=float)


if __name__ == '__main__':
    DetrimentReaderEvents.update_stub_file()
