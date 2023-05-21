from typing import Optional, Type
from rka.components.events import Event
from typing import List
from rka.services.api.ps_connector import PSTriggerEventData


class PSEvents:
	# noinspection PyPep8Naming
	class TRIGGER_RECEIVED(Event):
		trigger_event_data: Optional[PSTriggerEventData]

		# noinspection PyMissingConstructor
		def __init__(self, trigger_event_data: Optional[PSTriggerEventData] = None): ...

	# noinspection PyPep8Naming
	class COMMAND_RECEIVED(Event):
		command: Optional[str]
		params: Optional[List[str]]

		# noinspection PyMissingConstructor
		def __init__(self, command: Optional[str] = None, params: Optional[List[str]] = None): ...

	# noinspection PyPep8Naming
	class MESSAGE_RECEIVED(Event):
		message: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, message: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class CLIENTS_RECEIVED(Event):
		clients: Optional[List[str]]

		# noinspection PyMissingConstructor
		def __init__(self, clients: Optional[List[str]] = None): ...

	# noinspection PyPep8Naming
	class DISCONNECTED(Event):
		pass

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

