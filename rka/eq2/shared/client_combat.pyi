from typing import Optional, Type
from rka.eq2.shared.client_event import ClientEvent
from rka.components.events import Event


class ClientCombatParserEvents:
	# noinspection PyPep8Naming
	class COMBAT_PARSE_START(ClientEvent):
		client_id: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class COMBAT_PARSE_TICK(ClientEvent):
		client_id: Optional[str]
		combat_flag: Optional[bool]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, combat_flag: Optional[bool] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class COMBAT_PARSE_END(ClientEvent):
		client_id: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class COMBATANT_JOINED(ClientEvent):
		client_id: Optional[str]
		combatant_name: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, client_id: Optional[str] = None, combatant_name: Optional[str] = None, timestamp: Optional[float] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

