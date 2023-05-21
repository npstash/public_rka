from typing import Optional, Type
from rka.components.events import Event
from rka.eq2.master.game.interfaces import IPlayer
from typing import List


class RequestEvents:
	# noinspection PyPep8Naming
	class COMBAT_REQUESTS_START(Event):
		main_controller: Optional[bool]
		controller_instance: Optional[object]

		# noinspection PyMissingConstructor
		def __init__(self, main_controller: Optional[bool] = None, controller_instance: Optional[object] = None): ...

	# noinspection PyPep8Naming
	class COMBAT_REQUESTS_END(Event):
		main_controller: Optional[bool]
		controller_instance: Optional[object]

		# noinspection PyMissingConstructor
		def __init__(self, main_controller: Optional[bool] = None, controller_instance: Optional[object] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_BALANCED_SYNERGY(Event):
		player_name: Optional[str]
		local_player_request: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, player_name: Optional[str] = None, local_player_request: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_CURE_CURSE(Event):
		target_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, target_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_CURE(Event):
		target_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, target_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_DEATHSAVE(Event):
		target_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, target_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_INTERCEPT(Event):
		target_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, target_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class REQUEST_STUN(Event):
		pass

	# noinspection PyPep8Naming
	class REQUEST_INTERRUPT(Event):
		pass

	# noinspection PyPep8Naming
	class REQUEST_PLAYER_SET_TARGET(Event):
		player: Optional[IPlayer]
		target_name: Optional[str]
		optional_targets: Optional[List[str]]
		refresh_rate: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, target_name: Optional[str] = None, optional_targets: Optional[List[str]] = None, refresh_rate: Optional[float] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

