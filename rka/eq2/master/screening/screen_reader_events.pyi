from typing import Optional, Type
from rka.components.ui.capture import CaptureArea
from rka.components.events import Event
from typing import List
from rka.components.ui.capture import Rect
from rka.components.resources import Resource


class ScreenReaderEvents:
	# noinspection PyPep8Naming
	class SCREEN_OBJECT_FOUND(Event):
		client_id: Optional[str]
		tag: Optional[Resource]
		area: Optional[CaptureArea]
		location_rects: Optional[List[Rect]]
		since_previous: Optional[float]
		subscriber_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, tag: Optional[Resource] = None, area: Optional[CaptureArea] = None, location_rects: Optional[List[Rect]] = None, since_previous: Optional[float] = None, subscriber_id: Optional[str] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

