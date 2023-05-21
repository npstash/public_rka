from typing import Optional, Iterable, Union

from rka.components.resources import Resource
from rka.components.ui.capture import CaptureArea
from rka.eq2.master.control import IHasClient
from rka.services.api import IService


# noinspection PyAbstractClass
class IScreenReader(IService):
    def subscribe(self, client_ids: Iterable[Union[str, IHasClient]], subscriber_id: str, tag: Resource, area: Optional[CaptureArea] = None,
                  check_period: Optional[int] = None, event_period: Optional[float] = None, max_matches: Optional[int] = None):
        raise NotImplementedError()

    def unsubscribe(self, subscriber_id: str, tag: Optional[Resource] = None, area: Optional[CaptureArea] = None):
        raise NotImplementedError()
