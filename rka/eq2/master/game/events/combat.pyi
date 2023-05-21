from typing import Optional, Type
from rka.components.events import Event
from rka.eq2.master.game.engine import HOStage
from rka.eq2.master.game.interfaces import IPlayer


class CombatEvents:
	# noinspection PyPep8Naming
	class ENEMY_KILL(Event):
		killer_name: Optional[str]
		enemy_name: Optional[str]
		killer_you: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, killer_name: Optional[str] = None, enemy_name: Optional[str] = None, killer_you: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class READYUP(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_DIED(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_DEATHSAVED(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_REVIVED(Event):
		player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_SYNERGIZED(Event):
		caster_name: Optional[str]
		my_player: Optional[bool]
		reported_by_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, my_player: Optional[bool] = None, reported_by_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_SYNERGY_FADES(Event):
		caster_name: Optional[str]
		my_player: Optional[bool]
		reported_by_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, my_player: Optional[bool] = None, reported_by_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class GROUP_SYNERGY_COMPLETED(Event):
		reported_by_player: Optional[IPlayer]

		# noinspection PyMissingConstructor
		def __init__(self, reported_by_player: Optional[IPlayer] = None): ...

	# noinspection PyPep8Naming
	class BARRAGE_READIED(Event):
		caster_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class BARRAGE_PREPARED(Event):
		caster_name: Optional[str]
		target_name: Optional[str]
		your_group: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, target_name: Optional[str] = None, your_group: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class BARRAGE_CANCELLED(Event):
		caster_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class BARRAGE_RELEASED(Event):
		caster_name: Optional[str]
		target_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, target_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class BULWARK_APPLIED(Event):
		applied_by: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, applied_by: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class HO_CHAIN_STARTED(Event):
		caster_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class HO_CHAIN_BROKEN(Event):
		caster_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class HO_TRIGGERED(Event):
		caster_name: Optional[str]
		ho_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, ho_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class HO_ADVANCED(Event):
		caster_name: Optional[str]
		ho_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, ho_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class HO_COMPLETED(Event):
		caster_name: Optional[str]
		ho_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, ho_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class HO_STAGE_CHANGED(Event):
		ho_name: Optional[str]
		caster_name: Optional[str]
		new_stage: Optional[HOStage]
		advances: Optional[int]
		hint: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, ho_name: Optional[str] = None, caster_name: Optional[str] = None, new_stage: Optional[HOStage] = None, advances: Optional[int] = None, hint: Optional[str] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

