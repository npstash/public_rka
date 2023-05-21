from __future__ import annotations

import datetime
import enum
from enum import auto
from typing import Union, List, Callable, Optional, Tuple, Iterable

from rka.eq2.master.game.ability import AbilityPriority
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, TAbilityFilter, TOptionalTarget, TValidTarget


class AbilityResolver:
    def __init__(self):
        pass

    def _resolve_ability(self, ability: IAbility) -> List[IAbility]:
        return [ability]

    def _resolve_ability_locator(self, ability_locator: IAbilityLocator) -> List[IAbility]:
        return ability_locator.resolve()

    def _resolve_combine(self, combine: Combine) -> ResolvedCombine:
        return combine.resolve_combine(self)

    def resolve_abilities(self, abilities: TAbilities) -> List[IAbility]:
        if not isinstance(abilities, Iterable):
            abilities = [abilities]
        extracted_abilities: List[IAbility] = list()
        for item in abilities:
            if isinstance(item, IAbility):
                extracted_abilities += self._resolve_ability(item)
            elif isinstance(item, IAbilityLocator):
                extracted_abilities += self._resolve_ability_locator(item)
            elif isinstance(item, List):
                extracted_abilities += self.resolve_abilities(item)
            elif isinstance(item, Iterable):
                extracted_abilities += self.resolve_abilities(list(item))
            elif isinstance(item, Combine):
                resolved_combine = self._resolve_combine(item)
                accepted, resolved_abilities = resolved_combine.get_by_condition(CommonCombineConditions.is_reusable_or_running)
                if accepted:
                    extracted_abilities += resolved_abilities
            elif item is None:
                continue
            else:
                assert False, item
        return extracted_abilities

    @staticmethod
    def reduce_variants(abilities: List[IAbility]) -> List[IAbility]:
        # keep one ability of given locator per player, reduce variants
        reduced_abilities = {ability.ability_unique_key(): ability for ability in abilities}
        return list(reduced_abilities.values())

    def prototype(self, target: TOptionalTarget = None,
                  priority: Optional[AbilityPriority] = None,
                  priority_adjust: Optional[int] = None,
                  target_factory: Optional[Callable[[IAbility], TValidTarget]] = None,
                  priority_factory: Optional[Callable[[IAbility], AbilityPriority]] = None) -> AbilityResolver:
        return _PrototypeAbilityResolver(self, target=target,
                                         priority=priority,
                                         priority_adjust=priority_adjust,
                                         target_factory=target_factory,
                                         priority_factory=priority_factory)

    def filtered(self, ability_filter: TAbilityFilter) -> AbilityResolver:
        return _FilteredAbilityResolver(self, ability_filter)


class _FilteredAbilityResolver(AbilityResolver):
    def __init__(self, filter_from: AbilityResolver, ability_filter: Optional[TAbilityFilter]):
        AbilityResolver.__init__(self)
        self.__filter_from = filter_from
        self.__ability_filter = ability_filter

    def __filter(self, abilities: List[IAbility]) -> List[IAbility]:
        return list(filter(self.__ability_filter, abilities))

    def _resolve_ability(self, ability: IAbility) -> List[IAbility]:
        resolved_abilities = self.__filter_from._resolve_ability(ability)
        return self.__filter(resolved_abilities)

    def _resolve_ability_locator(self, ability_locator: IAbilityLocator) -> List[IAbility]:
        resolved_abilities = self.__filter_from._resolve_ability_locator(ability_locator)
        return self.__filter(resolved_abilities)


class _PrototypeAbilityResolver(AbilityResolver):
    def __init__(self, prototype_from: AbilityResolver,
                 target: TOptionalTarget,
                 priority: Optional[AbilityPriority],
                 priority_adjust: Optional[int],
                 target_factory: Optional[Callable[[IAbility], TValidTarget]],
                 priority_factory: Optional[Callable[[IAbility], AbilityPriority]]):
        AbilityResolver.__init__(self)
        self.__prototype_from = prototype_from
        self.__target = target
        self.__priority = priority
        self.__priority_adjust = priority_adjust
        self.__target_factory = target_factory
        self.__priority_factory = priority_factory

    def has_target_modifier(self) -> bool:
        return self.__target is not None or self.__target_factory is not None

    def has_priority_modifier(self) -> bool:
        return self.__priority is not None or self.__priority_factory is not None

    def get_target(self, ability: IAbility) -> TOptionalTarget:
        target = self.__target
        if self.__target_factory:
            target = self.__target_factory(ability)
        return target

    def get_priority(self, ability: IAbility) -> AbilityPriority:
        priority = self.__priority
        if priority and self.__priority_adjust:
            priority += self.__priority_adjust
        if self.__priority_factory:
            priority = self.__priority_factory(ability)
        return priority

    def __prototype(self, abilities: List[IAbility]) -> List[IAbility]:
        if self.has_target_modifier() and self.has_priority_modifier():
            abilities = AbilityResolver.reduce_variants(abilities)
            return [ability.prototype(target=self.get_target(ability), priority=self.get_priority(ability)) for ability in abilities]
        elif self.has_priority_modifier():
            return [ability.prototype(priority=self.get_priority(ability)) for ability in abilities]
        elif self.has_target_modifier():
            abilities = self.reduce_variants(abilities)
            return [ability.prototype(target=self.get_target(ability)) for ability in abilities]
        if isinstance(abilities, list):
            return abilities
        return list(abilities)

    def _resolve_ability(self, ability: IAbility) -> List[IAbility]:
        resolved_abilities = self.__prototype_from._resolve_ability(ability)
        return self.__prototype(resolved_abilities)

    def _resolve_ability_locator(self, ability_locator: IAbilityLocator) -> List[IAbility]:
        resolved_abilities = self.__prototype_from._resolve_ability_locator(ability_locator)
        return self.__prototype(resolved_abilities)


class ICombineReducer:
    def reduce(self, abilities: List[IAbility], limit: int) -> List[IAbility]:
        raise NotImplementedError()


# noinspection PyPep8Naming
def AND(items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.AND, items, reducer=reducer)


# noinspection PyPep8Naming
def XOR(items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.ATMOST, items, limit=1, reducer=reducer)


# noinspection PyPep8Naming
def OR(items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.ATLEAST, items, limit=1, reducer=reducer)


# noinspection PyPep8Naming
def EXACT(limit: int, items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.EXACT, items, limit=limit, reducer=reducer)


# noinspection PyPep8Naming
def ATLEAST(limit: int, items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.ATLEAST, items, limit=limit, reducer=reducer)


# noinspection PyPep8Naming
def ATMOST(limit: int, items: TCombineItems, reducer: Optional[ICombineReducer] = None) -> Combine:
    return Combine(_CombineOps.ATMOST, items, limit=limit, reducer=reducer)


class _CombineOps(enum.Enum):
    AND = ' & '
    EXACT = ' &! '
    ATLEAST = ' | '
    ATMOST = ' |! '


class VisitResult(enum.Enum):
    ACCEPT = auto()
    IGNORE = auto()
    ACCEPT_AND_SKIP = auto()
    REJECT = auto()
    REJECT_ALL = auto()


class _BasicCombineReducer(ICombineReducer):
    def reduce(self, abilities: List[IAbility], limit: int) -> List[IAbility]:
        return abilities[:limit]


_basic_combine_reducer = _BasicCombineReducer()


class Combine:
    def __init__(self, combine_op: _CombineOps, items: TCombineItems, limit=0, reducer: Optional[ICombineReducer] = None):
        self.combine_op = combine_op
        self.__items = items
        self.__limit = limit
        self.__reducer = reducer if reducer is not None else _basic_combine_reducer
        self.__debug_str = str(items)

    def resolve_combine(self, resolver: AbilityResolver, parent_reducer: Optional[ICombineReducer] = None) -> ResolvedCombine:
        resolved_items = list()
        reducer = parent_reducer if parent_reducer is not None else self.__reducer
        if isinstance(self.__items, IAbilityLocator):
            resolved_items += resolver.resolve_abilities([self.__items])
        else:
            for item in self.__items:
                if isinstance(item, IAbilityLocator):
                    combine = XOR(resolver.resolve_abilities([item]))
                    resolved_items.append(combine.resolve_combine(resolver, parent_reducer=reducer))
                elif isinstance(item, IAbility):
                    resolved_items.append(item)
                elif isinstance(item, Combine):
                    resolved_items.append(item.resolve_combine(resolver, parent_reducer=reducer))
                elif item is None:
                    continue
                else:
                    assert False, item
        return ResolvedCombine(self.combine_op, resolved_items, self.__limit, reducer)


class CommonCombineConditions:
    @staticmethod
    def is_running(ability: IAbility, now: datetime.datetime) -> VisitResult:
        running = not ability.is_duration_expired(now)
        return VisitResult.ACCEPT if running else VisitResult.REJECT

    @staticmethod
    def is_reusable(ability: IAbility, now: datetime.datetime) -> VisitResult:
        running = ability.is_reusable(now)
        return VisitResult.ACCEPT if running else VisitResult.REJECT

    @staticmethod
    def is_reusable_or_running(ability: IAbility, now: datetime.datetime) -> VisitResult:
        running = not ability.is_duration_expired(now)
        if running:
            return VisitResult.ACCEPT_AND_SKIP
        reusable = ability.is_reusable(now)
        return VisitResult.ACCEPT if reusable else VisitResult.REJECT

    @staticmethod
    def is_reusable_and_not_running(ability: IAbility, now: datetime.datetime) -> VisitResult:
        running = not ability.is_duration_expired(now)
        if running:
            return VisitResult.REJECT_ALL
        reusable = ability.is_reusable(now)
        return VisitResult.ACCEPT if reusable else VisitResult.REJECT


class ResolvedCombine:
    def __init__(self, combine_op: _CombineOps, resolved_items: List[Union[IAbility, ResolvedCombine]], limit: int, reducer: ICombineReducer):
        self.__combine_op = combine_op
        self.__debug_str = combine_op.name + '('
        for item in resolved_items:
            self.__debug_str += str(item) + ','
        self.__debug_str += ')'
        self.__items = resolved_items
        self.__limit = limit
        self.__reducer = reducer
        self.__predicate_ability_filter: Optional[TAbilityFilter] = None

    def __str__(self) -> str:
        return self.__debug_str

    def set_condition_filter(self, ability_filter: Optional[TAbilityFilter]):
        self.__predicate_ability_filter = ability_filter
        for item in self.__items:
            if isinstance(item, ResolvedCombine):
                item.set_condition_filter(ability_filter)

    def __accept_ability(self, ability: IAbility) -> bool:
        if not self.__predicate_ability_filter:
            return True
        return self.__predicate_ability_filter(ability)

    def check_condition(self, condition: CombineVisitor, now: Optional[datetime.datetime] = None) -> bool:
        if not now:
            now = datetime.datetime.now()
        accepted_count = 0
        accept_final_result = False
        for item in self.__items:
            # visit
            if isinstance(item, IAbility):
                if not self.__accept_ability(item):
                    continue
                predicate_result = condition(item, now)
                if predicate_result == VisitResult.IGNORE:
                    continue
                elif predicate_result == VisitResult.ACCEPT:
                    accept_result = True
                elif predicate_result == VisitResult.ACCEPT_AND_SKIP:
                    accept_result = True
                elif predicate_result == VisitResult.REJECT:
                    accept_result = False
                elif predicate_result == VisitResult.REJECT_ALL:
                    return False
                else:
                    assert False, predicate_result
            elif isinstance(item, ResolvedCombine):
                accept_result = item.check_condition(condition, now)
            else:
                assert False, item
            # update amount of abilities accepted in this loop
            if accept_result:
                accepted_count += 1
            # update overall result
            if self.__combine_op == _CombineOps.AND:
                if not accept_result:
                    return False
                accept_final_result = True
            elif self.__combine_op == _CombineOps.ATMOST:
                if accepted_count >= 1:
                    accept_final_result = True
            elif self.__combine_op == _CombineOps.ATLEAST or self.__combine_op == _CombineOps.EXACT:
                if accepted_count >= self.__limit:
                    accept_final_result = True
            else:
                assert False, self.__combine_op
        return accept_final_result

    # may return True, [] if condition returned ACCEPT_AND_SKIP
    # for example: condition is met, but no ability needs to be cast
    def get_by_condition(self, condition: CombineVisitor, now: Optional[datetime.datetime] = None) -> Tuple[bool, List[IAbility]]:
        if not now:
            now = datetime.datetime.now()
        result = list()
        accepted_count = 0
        accept_final_result = False
        for item in self.__items:
            item_result = []
            # visit
            if isinstance(item, IAbility):
                if not self.__accept_ability(item):
                    continue
                predicate_result = condition(item, now)
                if predicate_result == VisitResult.IGNORE:
                    continue
                elif predicate_result == VisitResult.ACCEPT:
                    item_result.append(item)
                    accept_result = True
                elif predicate_result == VisitResult.ACCEPT_AND_SKIP:
                    accept_result = True
                elif predicate_result == VisitResult.REJECT:
                    accept_result = False
                elif predicate_result == VisitResult.REJECT_ALL:
                    return False, []
                else:
                    assert False, predicate_result
            elif isinstance(item, ResolvedCombine):
                accept_result, item_result = item.get_by_condition(condition, now)
            else:
                assert False, item
            # update abilities accepted in this loop
            if accept_result:
                accepted_count += 1
                result += item_result
            # update overall result
            if self.__combine_op == _CombineOps.AND:
                if not accept_result:
                    return False, []
                result += item_result
                accept_final_result = True
            elif self.__combine_op == _CombineOps.ATMOST:
                if accepted_count >= 1:
                    accept_final_result = True
            elif self.__combine_op == _CombineOps.ATLEAST:
                if accepted_count >= self.__limit:
                    accept_final_result = True
            elif self.__combine_op == _CombineOps.EXACT:
                if accepted_count >= self.__limit:
                    accept_final_result = True
            else:
                assert False, self.__combine_op
        if accept_final_result and (self.__combine_op == _CombineOps.ATMOST or self.__combine_op == _CombineOps.EXACT):
            result = self.__reducer.reduce(result, self.__limit)
        return accept_final_result, result


CombineVisitor = Callable[[IAbility, datetime.datetime], VisitResult]
TAbilities = Union[IAbility, IAbilityLocator, Iterable[Union[IAbility, IAbilityLocator]]]
TCombineItems = Union[IAbilityLocator, List[Union[IAbility, IAbilityLocator, Combine]]]
