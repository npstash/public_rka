import enum
from enum import auto
from typing import List

from rka.components.io.log_service import LogService
from rka.eq2.master.parsing import ICombatantRecord, IDPSParser, CombatantType
from rka.log_configs import LOG_REQUEST_PROCESSOR

logger = LogService(LOG_REQUEST_PROCESSOR)


class ICombatantFilter:
    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        raise NotImplementedError()


class PlayerCombatantFilter(ICombatantFilter):
    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        combatant_type = combatant.get_combatant_type()
        return CombatantType.is_player(combatant_type)


class AnyCombatantFilter(ICombatantFilter):
    def accept_combatant(self, combatant: ICombatantRecord) -> bool:
        return True


class ITargetRanking:
    def get_ranked_combatants(self, dps_parser: IDPSParser, combatant_filter: ICombatantFilter) -> List[ICombatantRecord]:
        raise NotImplementedError()

    def get_ranked_combatant_names(self, dps_parser: IDPSParser, combatant_filter: ICombatantFilter) -> List[str]:
        ranked_combatants = self.get_ranked_combatants(dps_parser, combatant_filter)
        return [c.get_combatant_name() for c in ranked_combatants]


class HOStage(enum.IntEnum):
    NONE = auto()
    STARTED = auto()
    TRIGGERED = auto()
    COMPLETED = auto()
