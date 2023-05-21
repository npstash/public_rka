from typing import Optional, Type
from rka.eq2.master.parsing import CTConfirmRule
from rka.eq2.master.parsing import CombatantType
from rka.components.events import Event


class CombatParserEvents:
	# noinspection PyPep8Naming
	class DPS_PARSE_START(Event):
		attacker_name: Optional[str]
		target_name: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, attacker_name: Optional[str] = None, target_name: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class DPS_PARSE_TICK(Event):
		combat_flag: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, combat_flag: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class DPS_PARSE_END(Event):
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class COMBATANT_CONFIRMED(Event):
		combatant_name: Optional[str]
		combatant_type: Optional[CombatantType]
		confirm_rule: Optional[CTConfirmRule]

		# noinspection PyMissingConstructor
		def __init__(self, combatant_name: Optional[str] = None, combatant_type: Optional[CombatantType] = None, confirm_rule: Optional[CTConfirmRule] = None): ...

	# noinspection PyPep8Naming
	class COMBAT_HIT(Event):
		attacker_name: Optional[str]
		attacker_type: Optional[int]
		target_name: Optional[str]
		target_type: Optional[int]
		ability_name: Optional[str]
		damage: Optional[int]
		damage_type: Optional[str]
		is_autoattack: Optional[bool]
		is_drain: Optional[bool]
		is_multi: Optional[bool]
		is_dot: Optional[bool]
		is_aoe: Optional[bool]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, attacker_name: Optional[str] = None, attacker_type: Optional[int] = None, target_name: Optional[str] = None, target_type: Optional[int] = None, ability_name: Optional[str] = None, damage: Optional[int] = None, damage_type: Optional[str] = None, is_autoattack: Optional[bool] = None, is_drain: Optional[bool] = None, is_multi: Optional[bool] = None, is_dot: Optional[bool] = None, is_aoe: Optional[bool] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class DETRIMENT_RELIEVED(Event):
		by_combatant: Optional[str]
		by_combatant_type: Optional[int]
		from_combatant: Optional[str]
		from_combatant_type: Optional[int]
		ability_name: Optional[str]
		detriment_name: Optional[str]
		is_curse: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, by_combatant: Optional[str] = None, by_combatant_type: Optional[int] = None, from_combatant: Optional[str] = None, from_combatant_type: Optional[int] = None, ability_name: Optional[str] = None, detriment_name: Optional[str] = None, is_curse: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class EFFECT_DISPELLED(Event):
		by_combatant: Optional[str]
		by_combatant_type: Optional[int]
		from_combatant: Optional[str]
		from_combatant_type: Optional[int]
		ability_name: Optional[str]
		effect_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, by_combatant: Optional[str] = None, by_combatant_type: Optional[int] = None, from_combatant: Optional[str] = None, from_combatant_type: Optional[int] = None, ability_name: Optional[str] = None, effect_name: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class WARD_EXPIRED(Event):
		caster_name: Optional[str]
		caster_type: Optional[int]
		target_name: Optional[str]
		target_type: Optional[int]
		ability_name: Optional[str]
		timestamp: Optional[float]

		# noinspection PyMissingConstructor
		def __init__(self, caster_name: Optional[str] = None, caster_type: Optional[int] = None, target_name: Optional[str] = None, target_type: Optional[int] = None, ability_name: Optional[str] = None, timestamp: Optional[float] = None): ...

	# noinspection PyPep8Naming
	class CRITICAL_STONESKIN(Event):
		amount: Optional[int]
		amount_readable: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, amount: Optional[int] = None, amount_readable: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class PLAYER_INTERRUPTED(Event):
		player_name: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, player_name: Optional[str] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

