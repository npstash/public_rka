from typing import Optional, Type
from rka.components.events import Event
from rka.eq2.master.parsing import IDPSParser


class MasterEvents:
	# noinspection PyPep8Naming
	class CLIENT_REGISTERED(Event):
		client_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class CLIENT_UNREGISTERED(Event):
		client_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class CLIENT_CONFIGURED(Event):
		client_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class NEW_DPS_PARSER(Event):
		dps_parser: Optional[IDPSParser]

		# noinspection PyMissingConstructor
		def __init__(self, dps_parser: Optional[IDPSParser] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

