from typing import Optional, Type
from rka.eq2.shared.client_event import ClientEvent
from rka.components.events import Event
from rka.eq2.shared.client_event import ParserEvent


class ClientEvents:
	# noinspection PyPep8Naming
	class CLIENT_REQUEST(ClientEvent):
		client_id: Optional[str]
		request: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, request: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class PARSER_MATCH(ParserEvent):
		client_id: Optional[str]
		parse_filter: Optional[str]
		preparsed_log: Optional[bool]
		matched_text: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, parse_filter: Optional[str] = None, preparsed_log: Optional[bool] = None, matched_text: Optional[str] = None, timestamp: Optional[float] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

