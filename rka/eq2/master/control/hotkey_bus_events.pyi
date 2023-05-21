from typing import Optional, Type
from rka.components.events import Event


class HotkeyEvents:
	# noinspection PyPep8Naming
	class FUNCTION_KEY(Event):
		function_num: Optional[int]

		# noinspection PyMissingConstructor
		def __init__(self, function_num: Optional[int] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

