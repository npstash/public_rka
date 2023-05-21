from typing import List

from rka.components.events import Events, event
from rka.components.resources import Resource
from rka.components.ui.capture import CaptureArea, Rect


class ScreenReaderEvents(Events):
    SCREEN_OBJECT_FOUND = event(client_id=str, tag=Resource, area=CaptureArea, location_rects=List[Rect], since_previous=float, subscriber_id=str)


if __name__ == '__main__':
    ScreenReaderEvents.update_stub_file()
