from typing import Optional, Type
from rka.components.events import Event
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import TellType


class ChatEvents:
	# noinspection PyPep8Naming
	class EMOTE(Event):
		player: Optional[IPlayer]
		emote: Optional[str]
		min_wildcarding: Optional[str]
		max_wildcarding: Optional[str]
		to_local: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, emote: Optional[str] = None, min_wildcarding: Optional[str] = None, max_wildcarding: Optional[str] = None, to_local: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class ACT_TRIGGER_FOUND(Event):
		actxml: Optional[str]
		from_player_name: Optional[str]
		to_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, actxml: Optional[str] = None, from_player_name: Optional[str] = None, to_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class POINT_AT_PLAYER(Event):
		pointing_player: Optional[IPlayer]
		pointed_player_name: Optional[str]
		pointed_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, pointing_player: Optional[IPlayer] = None, pointed_player_name: Optional[str] = None, pointed_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_TELL(Event):
		from_player_name: Optional[str]
		teller_is_you: Optional[bool]
		tell_type: Optional[TellType]
		channel_name: Optional[str]
		tell: Optional[str]
		to_player: Optional[IPlayer]
		to_player_name: Optional[str]
		to_local: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, from_player_name: Optional[str] = None, teller_is_you: Optional[bool] = None, tell_type: Optional[TellType] = None, channel_name: Optional[str] = None, tell: Optional[str] = None, to_player: Optional[IPlayer] = None, to_player_name: Optional[str] = None, to_local: Optional[bool] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

