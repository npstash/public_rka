from typing import Optional, Type
from rka.components.ui.capture import Capture
from rka.components.events import Event
from rka.eq2.master.game.interfaces import IPlayer
from typing import List
from rka.components.ui.capture import Rect


class DetrimentReaderEvents:
	# noinspection PyPep8Naming
	class PERSONAL_DETRIMENT_FOUND(Event):
		detriment_tag: Optional[str]
		player: Optional[IPlayer]
		detrim_rect: Optional[Rect]
		inspect_capture: Optional[Capture]
		since_previous: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, detriment_tag: Optional[str] = None, player: Optional[IPlayer] = None, detrim_rect: Optional[Rect] = None, inspect_capture: Optional[Capture] = None, since_previous: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class RAID_DETRIMENT_FOUND(Event):
		detriment_tag: Optional[str]
		player_names: Optional[List[str]]
		since_previous: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, detriment_tag: Optional[str] = None, player_names: Optional[List[str]] = None, since_previous: Optional[float] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

