from typing import Optional, Type
from rka.eq2.master.game.effect import EffectScopeType
from rka.eq2.master.game.effect import EffectType
from rka.components.events import Event
from rka.eq2.master.game.interfaces import IAbility
from rka.eq2.master.game.interfaces import IEffect
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus


class ObjectStateEvents:
	# noinspection PyPep8Naming
	class COMBAT_STATE_START(Event):
		pass

	# noinspection PyPep8Naming
	class COMBAT_STATE_END(Event):
		pass

	# noinspection PyPep8Naming
	class ABILITY_EXPIRED(Event):
		ability: Optional[IAbility]
		ability_name: Optional[str]
		ability_shared_key: Optional[str]
		ability_unique_key: Optional[str]
		ability_variant_key: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, ability: Optional[IAbility] = None, ability_name: Optional[str] = None, ability_shared_key: Optional[str] = None, ability_unique_key: Optional[str] = None, ability_variant_key: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class ABILITY_CASTING_CONFIRMED(Event):
		ability: Optional[IAbility]
		ability_name: Optional[str]
		ability_shared_key: Optional[str]
		ability_unique_key: Optional[str]
		ability_variant_key: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, ability: Optional[IAbility] = None, ability_name: Optional[str] = None, ability_shared_key: Optional[str] = None, ability_unique_key: Optional[str] = None, ability_variant_key: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_STATUS_CHANGED(Event):
		player: Optional[IPlayer]
		from_status: Optional[PlayerStatus]
		to_status: Optional[PlayerStatus]

		# noinspection PyMissingConstructor
		def __init__(self, player: Optional[IPlayer] = None, from_status: Optional[PlayerStatus] = None, to_status: Optional[PlayerStatus] = None): ...

	# noinspection PyPep8Naming
	class EFFECT_STARTED(Event):
		effect_type: Optional[EffectType]
		effect_scope_type: Optional[EffectScopeType]
		effect: Optional[IEffect]

		# noinspection PyMissingConstructor
		def __init__(self, effect_type: Optional[EffectType] = None, effect_scope_type: Optional[EffectScopeType] = None, effect: Optional[IEffect] = None): ...

	# noinspection PyPep8Naming
	class EFFECT_CANCELLED(Event):
		effect_type: Optional[EffectType]
		effect_scope_type: Optional[EffectScopeType]
		effect: Optional[IEffect]

		# noinspection PyMissingConstructor
		def __init__(self, effect_type: Optional[EffectType] = None, effect_scope_type: Optional[EffectScopeType] = None, effect: Optional[IEffect] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

