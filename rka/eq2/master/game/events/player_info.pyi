from typing import Optional, Type
from rka.components.events import Event
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location


class PlayerInfoEvents:
	# noinspection PyPep8Naming
	class ITEM_RECEIVED(Event):
		player: Optional[IPlayer]
		item_name: Optional[str]
		container: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, item_name: Optional[str] = None, container: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class ITEM_FOUND_IN_INVENTORY(Event):
		player: Optional[IPlayer]
		item_name: Optional[str]
		bag: Optional[int]
		slot: Optional[int]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, item_name: Optional[str] = None, bag: Optional[int] = None, slot: Optional[int] = None): ...

	# noinspection PyPep8Naming
	class LOCATION(Event):
		player: Optional[IPlayer]
		location: Optional[Location]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, location: Optional[Location] = None): ...

	# noinspection PyPep8Naming
	class COMMISSION_OFFERED(Event):
		crafter_name: Optional[str]
		crafter_is_my_player: Optional[bool]
		offered_player: Optional[IPlayer]
		item_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, crafter_name: Optional[str] = None, crafter_is_my_player: Optional[bool] = None, offered_player: Optional[IPlayer] = None, item_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class QUEST_OFFERED(Event):
		player: Optional[IPlayer]
		accepted: Optional[bool]
		failed: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, accepted: Optional[bool] = None, failed: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class FRIEND_LOGGED(Event):
		friend_name: Optional[str]
		login: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, friend_name: Optional[str] = None, login: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_LINKDEAD(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_ZONE_CHANGED(Event):
		player: Optional[IPlayer]
		from_zone: Optional[str]
		to_zone: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, from_zone: Optional[str] = None, to_zone: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_JOINED_GROUP(Event):
		player_name: Optional[str]
		my_player: Optional[bool]
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player_name: Optional[str] = None, my_player: Optional[bool] = None, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_LEFT_GROUP(Event):
		player_name: Optional[str]
		my_player: Optional[bool]
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player_name: Optional[str] = None, my_player: Optional[bool] = None, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_GROUP_DISBANDED(Event):
		main_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, main_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class AUTOFOLLOW_BROKEN(Event):
		player: Optional[IPlayer]
		followed_player_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, followed_player_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class AUTOFOLLOW_IMPOSSIBLE(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

