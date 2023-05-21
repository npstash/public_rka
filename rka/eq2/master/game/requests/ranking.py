from typing import List, Set

from rka.components.io.log_service import LogLevel
from rka.eq2.master.game.engine import ICombatantFilter, ITargetRanking
from rka.eq2.master.game.requests import logger
from rka.eq2.master.parsing import ICombatantRecord, DpsMeasure, IDPSParser


class AbstractCombatantRanking(ITargetRanking):
    def __init__(self, max_targets: int):
        self.__max_targets = max_targets

    def _sort_accepted_combatants(self, accepted_combatants: Set[ICombatantRecord]) -> List[ICombatantRecord]:
        raise NotImplementedError()

    def get_ranked_combatants(self, dps_parser: IDPSParser, combatant_filter: ICombatantFilter) -> List[ICombatantRecord]:
        accepted_combatants: Set[ICombatantRecord] = set()
        rejected_combatants: Set[ICombatantRecord] = set()
        for combatant in dps_parser.iter_combatant_records():
            if not combatant_filter.accept_combatant(combatant):
                if logger.get_level() <= LogLevel.DETAIL:
                    rejected_combatants.add(combatant)
                continue
            accepted_combatants.add(combatant)
        sorted_combatants = self._sort_accepted_combatants(accepted_combatants)
        sorted_combatants = sorted_combatants[:self.__max_targets]
        if logger.get_level() <= LogLevel.DEBUG:
            ranking_str = str([f'{c.get_combatant_name()} | {c.get_hitpoints_damage(DpsMeasure.RECENT)}\n' for c in sorted_combatants])
            logger.debug(f'ranking: {ranking_str}')
        if logger.get_level() <= LogLevel.DETAIL:
            logger.detail(f'rejected combatants: {[t.get_combatant_name() for t in rejected_combatants]}')
        return sorted_combatants


class RankingByIncDamage(AbstractCombatantRanking):
    def __init__(self, max_targets: int):
        AbstractCombatantRanking.__init__(self, max_targets)

    def _sort_accepted_combatants(self, accepted_combatants: Set[ICombatantRecord]) -> List[ICombatantRecord]:
        sorted_combatants = sorted(accepted_combatants, key=lambda c: c.get_hitpoints_damage(DpsMeasure.RECENT), reverse=True)
        return sorted_combatants


class RankingByHealNeed(AbstractCombatantRanking):
    def __init__(self, max_targets: int):
        AbstractCombatantRanking.__init__(self, max_targets)

    @staticmethod
    def __score(combatant: ICombatantRecord) -> float:
        received_damage = combatant.get_hitpoints_damage(DpsMeasure.RECENT)
        received_wards = combatant.get_consumed_wards(DpsMeasure.RECENT)
        return (received_damage + 1) / (received_wards + 1)

    def _sort_accepted_combatants(self, accepted_combatants: Set[ICombatantRecord]) -> List[ICombatantRecord]:
        sorted_combatants = sorted(accepted_combatants, key=RankingByHealNeed.__score, reverse=True)
        return sorted_combatants
