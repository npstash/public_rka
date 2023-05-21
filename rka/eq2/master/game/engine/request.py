from __future__ import annotations

import datetime
import time
from typing import Dict, List, Optional, Set, Iterable, Callable, Tuple

from rka.components.io.log_service import LogLevel, LogService
from rka.eq2.master import IRuntime, RequiresRuntime
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.engine import logger, ITargetRanking, ICombatantFilter
from rka.eq2.master.game.engine.abilitybag import AbilityBag, EMPTY_BAG
from rka.eq2.master.game.engine.resolver import Combine, TAbilities, AbilityResolver, ResolvedCombine, CommonCombineConditions, ICombineReducer
from rka.eq2.master.game.engine.task import Task, IAbilityCastingObserver
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IPlayer, TAbilityFilter, AbilityVariantKey, AbilityRecord, IAbilityRecordFilter
from rka.eq2.shared import Groups
from rka.log_configs import LOG_REQUESTS

rotation_request_logger = LogService(LOG_REQUESTS)


class Request(Task, IAbilityCastingObserver):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float, description=''):
        abilities = resolver.resolve_abilities(abilities)
        if not description:
            description = ', '.join(str(ability) for ability in abilities)
        Task.__init__(self, description=description, duration=duration)
        self.__resolved_abilities_list = abilities
        self.__resolved_abilities_map = {ability.ability_variant_key(): ability for ability in abilities}
        self.__ability_filter: Optional[TAbilityFilter] = None

    def set_ability_filter(self, ability_filter: Optional[TAbilityFilter]):
        self.__ability_filter = ability_filter

    def set_ability_filter_from(self, request: Request):
        self.set_ability_filter(request.__ability_filter)

    def _debug_filters(self, ability: IAbility):
        flt = self.__ability_filter
        logger.debug(f'filtered is empty, filter is: {flt}')
        if isinstance(flt, AbilityFilter):
            flt.print_debug(ability)
        else:
            accepted = flt(ability)
            logger.debug(f'tested {ability}, filter: {flt}, result {accepted}')

    def _set_ability_filter_on_bag(self, bag: AbilityBag) -> AbilityBag:
        bag.set_filter(self.__ability_filter)
        return bag

    def _accept_ability(self, ability: IAbility) -> bool:
        return self.__ability_filter(ability)

    def _filter_abilities(self, abilities: Iterable[IAbility]) -> List[IAbility]:
        return list(filter(self.__ability_filter, abilities))

    def get_resolved_abilities_list(self) -> List[IAbility]:
        return self.__resolved_abilities_list

    def get_resolved_abilities_map(self) -> Dict[str, IAbility]:
        return self.__resolved_abilities_map

    def is_ability_in_resolved(self, ability: IAbility) -> bool:
        return ability.ability_variant_key() in self.__resolved_abilities_map

    def get_available_ability_bag(self) -> AbilityBag:
        return AbilityBag(self._filter_abilities(self.__resolved_abilities_map.values()))


# proxy for retrieving ability from other request; keeps own duration management
class DynamicRequestProxy(Request, RequiresRuntime):
    def __init__(self, description: str, duration=-1.0):
        Request.__init__(self, abilities=[], resolver=AbilityResolver(), description=description, duration=duration)
        RequiresRuntime.__init__(self)
        self.__request: Optional[Request] = None
        self.__condition: Optional[Callable[[], bool]] = None

    def set_request(self, request: Optional[Request]):
        self.__request = request
        if request:
            if isinstance(request, RequiresRuntime) and self.has_runtime():
                request.set_runtime(self.get_runtime())
            self.set_duration(request.get_duration())

    def set_condition(self, condition: Callable[[], bool]):
        self.__condition = condition

    # override from RequiresRuntime
    def set_runtime(self, runtime: IRuntime):
        RequiresRuntime.set_runtime(self, runtime)
        if isinstance(self.__request, RequiresRuntime):
            self.__request.set_runtime(runtime)

    # override from Duration
    def start(self):
        Request.start(self)
        request = self.__request
        if request:
            request.start()

    # override from Duration
    def restart(self):
        Request.restart(self)
        request = self.__request
        if request:
            request.restart()

    # override from Duration
    def extend(self, duration: Optional[float] = None):
        Request.extend(self, duration)
        request = self.__request
        if request:
            request.extend(duration)

    # override from Duration
    def notify_expired(self):
        Request.notify_expired(self)
        request = self.__request
        if request:
            if not request.is_expired():
                request.expire()
            request.notify_expired()

    # override from Duration
    def notify_started(self):
        Request.notify_started(self)
        request = self.__request
        if request:
            request.notify_started()

    # override from Request
    def get_resolved_abilities_map(self) -> Dict[str, IAbility]:
        request = self.__request
        if request:
            return request.get_resolved_abilities_map()
        return dict()

    def is_ability_in_resolved(self, ability: IAbility) -> bool:
        request = self.__request
        if request:
            return request.is_ability_in_resolved(ability)
        return False

    # override from Request
    def set_ability_filter(self, ability_filter: Optional[TAbilityFilter]):
        Request.set_ability_filter(self, ability_filter)
        request = self.__request
        if request:
            request.set_ability_filter(ability_filter)

    # override from Request
    def notify_casting(self, ability: IAbility):
        Request.notify_casting(self, ability)
        request = self.__request
        if request:
            request.notify_casting(ability)

    # override from Request
    def get_available_ability_bag(self) -> AbilityBag:
        request = self.__request
        if not request:
            return EMPTY_BAG
        if self.__condition is not None and not self.__condition():
            return EMPTY_BAG
        return self.__request.get_available_ability_bag()


class AbstractCompositeRequest(Request, RequiresRuntime):
    def __init__(self, description: str, requests: List[Request], duration: Optional[float] = None):
        if not duration:
            if requests:
                duration = max([r.get_duration() for r in requests])
            else:
                duration = -1.0
        for request in requests:
            request.set_duration(duration)
        Request.__init__(self, abilities=[], resolver=AbilityResolver(), description=description, duration=duration)
        RequiresRuntime.__init__(self)
        self._requests = list(requests)

    def add_request(self, request: Request):
        request.set_duration(self.get_duration())
        request.set_ability_filter_from(self)
        if not self.is_expired():
            request.start()
            request._on_start()
        new_requests = list(self._requests)
        new_requests.append(request)
        if isinstance(request, RequiresRuntime) and self.has_runtime():
            request.set_runtime(self.get_runtime())
        self._requests = new_requests

    def clear_expired_requests(self):
        new_requests = [request for request in self._requests if not request.is_expired()]
        self._requests = new_requests

    def clear_all_requests(self):
        self._requests = []

    # override from RequiresRuntime
    def set_runtime(self, runtime: IRuntime):
        super().set_runtime(runtime)
        for request in self._requests:
            if isinstance(request, RequiresRuntime):
                request.set_runtime(runtime)

    # override from Task
    def start(self):
        super().start()
        for request in self._requests:
            request.start()

    # override from Task
    def restart(self):
        super().restart()
        for request in self._requests:
            request.restart()

    # override from Task
    def extend(self, duration: Optional[float] = None):
        super().extend(duration)
        for request in self._requests:
            request.extend(duration)

    # override from Task
    def expire(self):
        super().expire()
        for request in self._requests:
            request.expire()

    # override from Task
    def notify_expired(self):
        super().notify_expired()
        for request in self._requests:
            request.notify_expired()

    # override from Task
    def notify_started(self):
        super().notify_started()
        for request in self._requests:
            request.notify_started()

    # override from Request
    def get_resolved_abilities_map(self) -> Dict[str, IAbility]:
        resolved_abilities = dict()
        for request in self._requests:
            resolved_abilities.update(request.get_resolved_abilities_map())
        return resolved_abilities

    def is_ability_in_resolved(self, ability: IAbility) -> bool:
        for request in self._requests:
            if request.is_ability_in_resolved(ability):
                return True
        return False

    # override from Request
    def set_ability_filter(self, ability_filter: Optional[TAbilityFilter]):
        super().set_ability_filter(ability_filter)
        for request in self._requests:
            request.set_ability_filter(ability_filter)

    # override from Request
    def notify_casting(self, ability: IAbility):
        super().notify_casting(ability)
        for request in self._requests:
            request.notify_casting(ability)


# aggregate request aligns all tasks and cascades all calls to aggregated requests
class CompositeRequest(AbstractCompositeRequest, RequiresRuntime):
    def __init__(self, description: str, requests: List[Request], duration: Optional[float] = None):
        AbstractCompositeRequest.__init__(self, description, requests, duration)

    # override from Request
    def get_available_ability_bag(self) -> AbilityBag:
        result = None
        for request in self._requests:
            if request.is_expired():
                continue
            request_result = request.get_available_ability_bag()
            if request_result.is_empty():
                continue
            if result is None:
                result = AbilityBag()
            result.add_bag(request_result)
        if result is None:
            return EMPTY_BAG
        return result


class CascadeRequest(AbstractCompositeRequest, RequiresRuntime):
    def __init__(self, description: str, requests: List[Request], duration: Optional[float] = None):
        AbstractCompositeRequest.__init__(self, description, requests, duration)

    # override from Request
    def get_available_ability_bag(self) -> AbilityBag:
        for request in self._requests:
            if request.is_expired():
                continue
            request_result = request.get_available_ability_bag()
            if request_result.is_empty():
                continue
            reusable_request_result = request_result.get_bag_by_reusable()
            if reusable_request_result.is_empty():
                continue
            return reusable_request_result
        return EMPTY_BAG


# fire a single ability, if only possible, and expire
class CastOneAndExpire(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__finished = False

    def _on_expire(self):
        self.__finished = False

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.__finished = True
            self.expire()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__finished:
            self.expire()
            return EMPTY_BAG
        return super().get_available_ability_bag().one_of_least_busy_player()


# fire a single ability, if only possible, and expire
class CastNAndExpire(Request):
    def __init__(self, abilities: TAbilities, n: int, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__n = n
        self.__remaining_casts = n

    def _on_expire(self):
        self.__remaining_casts = self.__n

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.__remaining_casts -= 1
        if self.__remaining_casts <= 0:
            self.expire()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__remaining_casts <= 0:
            self.expire()
            return EMPTY_BAG
        return super().get_available_ability_bag().one_of_least_busy_player()


# fire any of the ability, if only possible, in any order, for the duration of request
class CastAnyWhenReady(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)


# fire any of the ability, every few seconds, in any order, for the duration of request
class CastAnyWhenReadyEveryNSec(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, delay: float, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__last_cast: Optional[float] = None
        self.__delay = delay

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.__last_cast = time.time()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__last_cast is None or time.time() - self.__last_cast > self.__delay:
            return super().get_available_ability_bag()
        return EMPTY_BAG


# fire all of ability, if only possible, in any order; restart possible after expire
class CastAllAndExpire(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__remaining_abilities = dict(self.get_resolved_abilities_map())

    def _on_expire(self):
        self.__remaining_abilities = dict(self.get_resolved_abilities_map())

    def notify_casting(self, ability: IAbility):
        if ability.ability_variant_key() in self.__remaining_abilities:
            del self.__remaining_abilities[ability.ability_variant_key()]

    def is_expired(self) -> bool:
        if super().is_expired():
            return True
        return self.get_available_ability_bag().is_empty()

    def get_available_ability_bag(self) -> AbilityBag:
        filtered_abilities = self._filter_abilities(self.__remaining_abilities.values())
        if not filtered_abilities:
            self.expire()
            return EMPTY_BAG
        return AbilityBag(filtered_abilities)


# fire all of ability, then expire and never restart; for use in scripts etc.
class CastAllAndExpirePermanently(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__remaining_abilities = dict(self.get_resolved_abilities_map())
        self.__expired_permanently = False

    def start(self):
        if self.__expired_permanently:
            return
        super().start()

    def restart(self):
        if self.__expired_permanently:
            return
        super().restart()

    def extend(self, duration: Optional[float] = None):
        if self.__expired_permanently:
            return
        super().extend(duration)

    def notify_started(self):
        if self.__expired_permanently:
            return
        super().notify_started()

    def notify_casting(self, ability: IAbility):
        if self.__expired_permanently:
            return
        if ability.ability_variant_key() in self.__remaining_abilities:
            del self.__remaining_abilities[ability.ability_variant_key()]

    def is_expired(self) -> bool:
        if self.__expired_permanently:
            return True
        return super().is_expired()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__expired_permanently:
            return EMPTY_BAG
        result = self._filter_abilities(self.__remaining_abilities.values())
        if not result:
            self.expire()
            self.__expired_permanently = True
            return EMPTY_BAG
        return AbilityBag(result)


# fire all of ability, if only possible, in any order, and restart automatically when all had been cast
class CastAllAndRestart(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__remaining_abilities = dict(self.get_resolved_abilities_map())

    def notify_casting(self, ability: IAbility):
        if ability.ability_variant_key() in self.__remaining_abilities:
            del self.__remaining_abilities[ability.ability_variant_key()]

    def get_available_ability_bag(self) -> AbilityBag:
        filtered_remaining = self._filter_abilities(self.__remaining_abilities.values())
        if not filtered_remaining:
            logger.detail(f'Resetting request {self}')
            self.__remaining_abilities = dict(self.get_resolved_abilities_map())
            filtered_remaining = self._filter_abilities(self.__remaining_abilities.values())
        return AbilityBag(filtered_remaining)


# cast all ability and do not skip any filtered out
class CastStrictSequenceAndExpire(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__remaining_sequence = list(self.get_resolved_abilities_list())

    def _on_expire(self):
        self.__remaining_sequence = list(self.get_resolved_abilities_list())

    def notify_casting(self, ability: IAbility):
        if self.__remaining_sequence and ability.ability_variant_key() == self.__remaining_sequence[0].ability_variant_key():
            self.__remaining_sequence.pop(0)
        if not self.__remaining_sequence:
            self.expire()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__remaining_sequence:
            next_ability = self.__remaining_sequence[0]
            return AbilityBag([next_ability])
        self.expire()
        return EMPTY_BAG


# cast all ability in a sequence, skip filtered.
class CastSequenceAndExpire(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__remaining_sequence = list(self.get_resolved_abilities_list())
        self.__remaining_abilities = {ability.ability_variant_key() for ability in self.__remaining_abilities}

    def _on_expire(self):
        self.__remaining_sequence = list(self.get_resolved_abilities_list())
        self.__remaining_abilities = {ability.ability_variant_key() for ability in self.__remaining_abilities}

    def notify_casting(self, ability: IAbility):
        if ability.ability_variant_key() in self.__remaining_abilities:
            idx = 0
            for i, remaining_ability in enumerate(self.__remaining_sequence):
                if remaining_ability.ability_variant_key() == ability.ability_variant_key():
                    idx = i
                    break
            self.__remaining_sequence = self.__remaining_sequence[idx + 1:]
            self.__remaining_abilities = {ability.ability_variant_key() for ability in self.__remaining_abilities}

    def get_available_ability_bag(self) -> AbilityBag:
        available_abilities = self._filter_abilities(self.__remaining_sequence)
        if available_abilities:
            return AbilityBag([available_abilities[0]])
        self.expire()
        return EMPTY_BAG


# maintain multiple ability, not recasting until duration is expired
class RecastWhenDurationExpired(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)

    def get_available_ability_bag(self) -> AbilityBag:
        return super().get_available_ability_bag().get_bag_by_duration_expired()


# maintain only one ability, to avoid overlaps
class NonOverlappingDuration(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, overlap: float, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__overlap_dt = datetime.timedelta(seconds=overlap)

    def get_available_ability_bag(self) -> AbilityBag:
        all_abilities = super().get_available_ability_bag()
        now = datetime.datetime.now()
        now_overlap = now + self.__overlap_dt
        in_duration = all_abilities.get_bag_by_in_duration_or_casting(now=now_overlap)
        if not in_duration.is_empty():
            return EMPTY_BAG
        reusable = all_abilities.get_bag_by_reusable(now=now)
        # filter off players that do not have reusable ability
        players_with_reusable_abilities = reusable.get_all_players()
        # return ready ability of the least busy player
        least_busy_player: Optional[IPlayer] = None
        result: List[IAbility] = list()
        for player in players_with_reusable_abilities:
            if least_busy_player is None or least_busy_player.is_busier_than(player):
                least_busy_player = player
        for ability in reusable.get_abilities():
            if ability.player is least_busy_player:
                result.append(ability)
        return AbilityBag(result)


class NonOverlappingDurationReducer(ICombineReducer):
    def reduce(self, abilities: List[IAbility], limit: int) -> List[IAbility]:
        all_abilities = AbilityBag(abilities)
        now = datetime.datetime.now()
        reusable = all_abilities.get_bag_by_reusable(now=now)
        # filter off players that do not have reusable ability
        players_with_reusable_abilities = reusable.get_all_players()
        # return ready ability of the least busy player
        least_busy_player: Optional[IPlayer] = None
        for player in players_with_reusable_abilities:
            if least_busy_player is None or least_busy_player.is_busier_than(player):
                least_busy_player = player
        result = [ability for ability in reusable.get_abilities() if ability.player is least_busy_player]
        return result[:limit]


# maintain only one ability, to avoid overlaps; abilities may belong to casters in different groups
class NonOverlappingDurationByGroup(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, overlap: float, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)
        self.__overlap_dt = datetime.timedelta(seconds=overlap)

    @staticmethod
    def __merge_main_group(groups: Set[Groups]) -> Set[Groups]:
        merged_groups = {Groups.MAIN if group_id & Groups.MAIN else group_id for group_id in groups}
        return merged_groups

    def get_available_ability_bag(self) -> AbilityBag:
        available_abilities = super().get_available_ability_bag()
        available_players = available_abilities.get_all_players()
        available_groups = {player.get_client_config_data().group_id for player in available_players}
        available_groups = NonOverlappingDurationByGroup.__merge_main_group(available_groups)
        # get abilities which are running, players and groups
        now = datetime.datetime.now()
        now_overlap = now + self.__overlap_dt
        abilities_in_duration = available_abilities.get_bag_by_in_duration_or_casting(now=now_overlap)
        players_with_abilities_in_duration = abilities_in_duration.get_all_players()
        groups_with_abilities_in_duration = {player.get_client_config_data().group_id for player in players_with_abilities_in_duration}
        groups_with_abilities_in_duration = NonOverlappingDurationByGroup.__merge_main_group(groups_with_abilities_in_duration)
        # which groups need to have an ability cast to maintain cycle
        groups_to_cast = available_groups - groups_with_abilities_in_duration
        if not groups_to_cast:
            return EMPTY_BAG
        # only one ability per group needs to be returned, otherwise multiple will get cast (on different players)
        reusable_abilities = available_abilities.get_bag_by_reusable(now=now)
        result: List[IAbility] = list()
        for group_id in groups_to_cast:
            abilities_to_cast = reusable_abilities.get_bag_by_filter(AbilityFilter().casters_by_group(group_id))
            if abilities_to_cast.is_empty():
                continue
            abilities = abilities_to_cast.get_abilities()
            ability = max(abilities, key=lambda a: a.get_priority())
            result.append(ability)
        return AbilityBag(result)


# cast only a single ability from a master, then expire the request, by preference
class CastBestAndExpire(Request):
    def __init__(self, abilities: TAbilities, resolver: AbilityResolver, duration: float):
        Request.__init__(self, abilities=abilities, resolver=resolver, duration=duration)

    def notify_casting(self, ability: IAbility):
        if self.is_ability_in_resolved(ability):
            self.expire()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.is_expired():
            return EMPTY_BAG
        all_abilities = super().get_available_ability_bag()
        # filter out ability that have reuse time not expired, but are do not need to wait for it
        abilities_ready_to_cast = all_abilities.get_bag_by_reusable()
        if abilities_ready_to_cast.is_empty():
            return EMPTY_BAG
        abilities_by_player: Dict[IPlayer, AbilityBag] = abilities_ready_to_cast.get_map_by_player()
        # shortest casting time
        select_from = AbilityBag()
        for player, abilities in abilities_by_player.items():
            recently_cast_ability = player.get_last_cast_ability()
            castable_abilities = abilities.get_bag_by_can_override(recently_cast_ability)
            if not castable_abilities.is_empty():
                select_from.add_bag(castable_abilities)
        if select_from.is_empty():
            return EMPTY_BAG
        best = select_from.get_bag_by_general_preference()
        return best


class RequestCombine(CompositeRequest):
    def __init__(self, combine: Combine, resolver: AbilityResolver, duration: float):
        CompositeRequest.__init__(self, description=str(combine), requests=[], duration=duration)
        self.__resolved_combine = combine.resolve_combine(resolver)
        self.__resolved_combine.set_condition_filter(self._accept_ability)
        self.__current_casting_request: Optional[Request] = None
        self.__casting_request_resolver = AbilityResolver()

    def _test_for_recast(self, combine: ResolvedCombine) -> bool:
        raise NotImplementedError()

    def _get_for_recast(self, combine: ResolvedCombine) -> Tuple[bool, List[IAbility]]:
        raise NotImplementedError()

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__current_casting_request and not self.__current_casting_request.is_expired():
            logger.debug('Previous request still casting')
            return super().get_available_ability_bag()
        if self.__current_casting_request:
            self.clear_all_requests()
            self.__current_casting_request = None
        if not self._test_for_recast(self.__resolved_combine):
            logger.debug('Previous request still running')
            return EMPTY_BAG
        accept, new_abilities_to_cast = self._get_for_recast(self.__resolved_combine)
        logger.debug(f'new_abilities_to_cast: {[str(ability) for ability in new_abilities_to_cast]}')
        if not accept:
            logger.debug('Cannot accept')
            return EMPTY_BAG
        if not new_abilities_to_cast:
            logger.debug('No ability to cast')
            return EMPTY_BAG
        request = CastAllAndExpirePermanently(abilities=new_abilities_to_cast, resolver=self.__casting_request_resolver, duration=self.get_duration())
        self.__current_casting_request = request
        self.add_request(request)
        result_bag = super().get_available_ability_bag()
        return result_bag


class RequestCombineLazyRecasting(RequestCombine):
    def __init__(self, combine: Combine, resolver: AbilityResolver, duration: float):
        RequestCombine.__init__(self, combine, resolver, duration)

    def _test_for_recast(self, combine: ResolvedCombine) -> bool:
        return not combine.check_condition(CommonCombineConditions.is_running)

    def _get_for_recast(self, combine: ResolvedCombine) -> Tuple[bool, List[IAbility]]:
        return combine.get_by_condition(CommonCombineConditions.is_reusable_or_running)


class RequestCombineGreedyRecasting(RequestCombine):
    def __init__(self, combine: Combine, resolver: AbilityResolver, duration: float):
        RequestCombine.__init__(self, combine, resolver, duration)

    def _test_for_recast(self, combine: ResolvedCombine) -> bool:
        # example: OR [
        #     XOR(ability_1) - positive when none is running and at least one is reusabe
        #     XOR(ability_2)
        #    ]
        return combine.check_condition(CommonCombineConditions.is_reusable_and_not_running)

    def _get_for_recast(self, combine: ResolvedCombine) -> Tuple[bool, List[IAbility]]:
        return combine.get_by_condition(CommonCombineConditions.is_reusable_and_not_running)


class RequestBuffsAndDps(CompositeRequest):
    def __init__(self, buffs: Combine, buffs_resolver: AbilityResolver, dps: Combine, dps_resolver: AbilityResolver, duration: float):
        CompositeRequest.__init__(self, description=str(buffs), requests=[], duration=duration)
        self.__resolved_buffs = buffs.resolve_combine(buffs_resolver)
        self.__resolved_buffs.set_condition_filter(self._accept_ability)
        self.__resolved_dps = dps.resolve_combine(dps_resolver)
        self.__resolved_dps.set_condition_filter(self._accept_ability)
        self.__buffs_casting_request: Optional[Request] = None
        self.__dps_casting_request: Optional[Request] = None

    def __check_if_casting(self) -> bool:
        if self.__buffs_casting_request and not self.__buffs_casting_request.is_expired():
            return True
        if self.__dps_casting_request and not self.__dps_casting_request.is_expired():
            return True
        return False

    def __clear_expired_requests(self):
        self.clear_expired_requests()
        self.__buffs_casting_request = None
        self.__dps_casting_request = None

    def __request_buffs(self):
        logger.debug('Requesting buffs')
        accept, new_abilities_to_cast = self.__resolved_buffs.get_by_condition(CommonCombineConditions.is_reusable_or_running)
        logger.debug(f'New buffs to cast: {[str(ability) for ability in new_abilities_to_cast]}')
        if not accept:
            logger.debug('Cannot accept')
            return EMPTY_BAG
        if not new_abilities_to_cast:
            logger.debug('No ability to cast')
            return EMPTY_BAG

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__check_if_casting():
            logger.debug('Previous requests still casting')
            return super().get_available_ability_bag()
        self.__clear_expired_requests()
        dps_ready = self.__resolved_dps.check_condition(CommonCombineConditions.is_reusable)
        if not dps_ready:
            return EMPTY_BAG
        buffs_ready = self.__resolved_buffs.check_condition(CommonCombineConditions.is_reusable_or_running)
        if not buffs_ready:
            return EMPTY_BAG
        buffs_running = self.__resolved_buffs.check_condition(CommonCombineConditions.is_running)
        if not buffs_running:
            accept_buffs, buffs_to_cast = self.__resolved_buffs.get_by_condition(CommonCombineConditions.is_reusable_or_running)
            if not accept_buffs:
                logger.warn(f'Expected Buffs to be ready to cast')
                return EMPTY_BAG
            if not buffs_to_cast:
                logger.warn(f'Expected ready Buff ability')
                return EMPTY_BAG
            request = CastAllAndExpirePermanently(abilities=buffs_to_cast, resolver=AbilityResolver(),
                                                  duration=self.get_duration())
            self.__buffs_casting_request = request
            self.add_request(request)
            return super().get_available_ability_bag()
        accept_dps, dps_to_cast = self.__resolved_dps.get_by_condition(CommonCombineConditions.is_reusable)
        if not accept_dps:
            logger.warn(f'Expected DPS to be ready to cast')
            return EMPTY_BAG
        if not dps_to_cast:
            logger.warn(f'Expected ready DPS ability')
            return EMPTY_BAG
        request = CastAllAndExpirePermanently(abilities=dps_to_cast, resolver=AbilityResolver(),
                                              duration=self.get_duration())
        self.__dps_casting_request = request
        self.add_request(request)
        return super().get_available_ability_bag()


class TargetRotationRecast(CastAllAndRestart):
    def __init__(self, ability_to_rotate: IAbilityLocator, targets: Iterable, resolver: AbilityResolver, duration: float):
        resolved_abilities = AbilityResolver.reduce_variants(resolver.resolve_abilities(ability_to_rotate))
        abilities_with_targets = [ability.prototype(target=target) for target in targets for ability in resolved_abilities]
        CastAllAndRestart.__init__(self, abilities=abilities_with_targets, resolver=resolver, duration=duration)


class TargetRotationDuration(RecastWhenDurationExpired):
    def __init__(self, ability_to_rotate: IAbilityLocator, targets: Iterable, resolver: AbilityResolver, duration: float):
        resolved_abilities = AbilityResolver.reduce_variants(resolver.resolve_abilities(ability_to_rotate))
        abilities_with_targets = [ability.prototype(target=target) for target in targets for ability in resolved_abilities]
        RecastWhenDurationExpired.__init__(self, abilities=abilities_with_targets, resolver=resolver, duration=duration)


class RequestAbilityUtil:
    def __init__(self, ability_locators: List[IAbilityLocator], resolver: AbilityResolver):
        self.__ability_locators = ability_locators
        self.__abilities = AbilityResolver.reduce_variants(resolver.resolve_abilities(ability_locators))
        self.__lowest_reuse_time_sec: Optional[float] = None

    def match_ability(self, ability: IAbility) -> bool:
        for ability_locator in self.__ability_locators:
            if ability_locator.match_ability(ability):
                return True
        return False

    def get_lowest_reuse_time_sec(self) -> float:
        if self.__lowest_reuse_time_sec is None:
            sorted_abilities = sorted(self.__abilities, key=lambda a: a.census.reuse)
            if not sorted_abilities:
                return 0.0
            self.__lowest_reuse_time_sec = sorted_abilities[0].census.reuse
        return self.__lowest_reuse_time_sec

    def resolve_all_permitted(self) -> List[IAbility]:
        return AbilityFilter().permitted_caster_state().apply(self.__abilities)

    def resolve_all_reusable(self) -> List[IAbility]:
        now = datetime.datetime.now()
        return AbilityFilter().permitted_caster_state().reusable(now).apply(self.__abilities)


# cache is maintained only until the ability is cast
# the purpose of the cache is to use ability info during evaluations in processor
class RequestWithShortCache(Request):
    def __init__(self, description: str, duration: float):
        Request.__init__(self, abilities=[], resolver=AbilityResolver(), duration=duration, description=description)
        self.__cached_abilities: Optional[List[IAbility]] = None
        self.__cached_abilities_keys: Optional[Set[str]] = None
        self.logger = rotation_request_logger

    def notify_casting(self, ability: IAbility):
        if self.__cached_abilities_keys and ability.ability_variant_key() in self.__cached_abilities_keys:
            self.__cached_abilities = None
            self.__cached_abilities_keys = None

    def get_available_ability_bag(self) -> AbilityBag:
        if self.__cached_abilities:
            filtered_cached = self._filter_abilities(self.__cached_abilities)
            if not filtered_cached:
                self.__cached_abilities = None
                self.__cached_abilities_keys = None
            else:
                return AbilityBag(filtered_cached)
        self.__cached_abilities = self._build_cache()
        if not self.__cached_abilities:
            return EMPTY_BAG
        self.__cached_abilities_keys = {ability.ability_variant_key() for ability in self.__cached_abilities}
        filtered_abilities = self._filter_abilities(self.__cached_abilities)
        if self.logger.get_level() <= LogLevel.DETAIL:
            if not filtered_abilities and self.__cached_abilities:
                self._debug_filters(self.__cached_abilities[0])
            else:
                self.logger.debug(f'filtered_abilities: {", ".join([str(ability) for ability in filtered_abilities])}')
        return AbilityBag(filtered_abilities)

    def _build_cache(self) -> List[IAbility]:
        raise NotImplementedError()


class RotationWithTargetRanking(RequestWithShortCache, RequiresRuntime):
    def __init__(self, abilities_to_rotate: List[IAbilityLocator], ranker: ITargetRanking, exclude_self: bool,
                 combatant_filter: ICombatantFilter, ability_record_filter: IAbilityRecordFilter,
                 resolver: AbilityResolver, duration: float, description: Optional[str] = None):
        if not description:
            abilities_str = ', '.join([str(ability) for ability in abilities_to_rotate])
            description = f'{self.__class__.__name__}: [{abilities_str}]'
        RequestWithShortCache.__init__(self, description, duration)
        RequiresRuntime.__init__(self)
        self.__abilities_produced: Dict[str, AbilityRecord] = dict()
        self.__ability_util = RequestAbilityUtil(abilities_to_rotate, resolver)
        self.__target_ranker = ranker
        self.__combatant_filter = combatant_filter
        self.__ability_record_filter = ability_record_filter
        self.__exclude_self = exclude_self
        self.__allow_stacking = False
        self.__allow_recasting = False
        self.logger = rotation_request_logger

    def allow_stacking(self):
        self.__allow_stacking = True

    def allow_recasting(self):
        self.__allow_recasting = True

    def notify_casting(self, ability: IAbility):
        RequestWithShortCache.notify_casting(self, ability)
        if self.__ability_util.match_ability(ability):
            for ability_record in self.__abilities_produced.values():
                if ability.ability_variant_key() == ability_record.ability.ability_variant_key():
                    self.__ability_record_filter.notify_casting_record(ability_record)
                    break

    def __add_other_targets(self, ranked_targets: List[str], all_casters: Iterable[IPlayer]):
        # also add zoned players; keep in list to retain sorting order
        # there is a large assumption here that all casters are in the same zone!
        # which is can be only true with player_switcher in request_controller
        # TODO probably resolve cache separately for every zone of casters
        zoned_players = set()
        for caster in all_casters:
            players_zoned_with_caster = self.get_runtime().player_mgr.find_players(lambda p: caster.get_zone() == p.get_zone() and p.is_logged())
            zoned_players.update(players_zoned_with_caster)
        for zoned_player in zoned_players:
            if zoned_player.get_player_name() not in ranked_targets:
                ranked_targets.append(zoned_player.get_player_name())

    def _build_cache(self) -> Optional[List[IAbility]]:
        all_reusable = self.__ability_util.resolve_all_reusable()
        if not all_reusable:
            return None
        all_permitted = self.__ability_util.resolve_all_permitted()
        all_casters: Set[IPlayer] = {ability.player for ability in all_permitted}
        self.logger.debug(f'reusable {[str(ability) for ability in all_reusable]}')
        target_names = self.__target_ranker.get_ranked_combatant_names(self.get_runtime().current_dps, self.__combatant_filter)
        self.__add_other_targets(target_names, all_casters)
        if not target_names:
            return None
        new_abilities = self.__get_abilities_for_targets(target_names, all_permitted, all_casters)
        self.logger.debug(f'new for cache: {[str(ability) for ability in new_abilities]}')
        return new_abilities

    def __get_abilities_for_targets(self, target_names: List[str], all_permitted: List[IAbility], all_casters: Iterable[IPlayer]) -> List[IAbility]:
        if not target_names:
            return []
        now = datetime.datetime.now()
        available_casters: Set[IPlayer] = {caster for caster in all_casters if not caster.is_busy()}
        ready_abilities_by_target: Dict[str, Set[AbilityVariantKey]] = dict()
        running_abilities_by_target: Dict[str, Set[AbilityVariantKey]] = dict()
        ready_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]] = dict()
        running_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]] = dict()
        for target_name in target_names:
            ready_abilities_by_target[target_name] = set()
            running_abilities_by_target[target_name] = set()
        for caster in all_casters:
            ready_abilities_by_caster[caster] = set()
            running_abilities_by_caster[caster] = set()
        ability_scores: Dict[AbilityVariantKey, float] = dict()
        for ability in all_permitted:
            caster = ability.player
            for target_name in target_names:
                if self.__exclude_self and target_name == caster.get_player_name():
                    continue
                ability_variant_key = IAbility.make_ability_variant_key(caster.get_player_id(), ability.ext.ability_id, target_name)
                if ability_variant_key not in self.__abilities_produced:
                    targeted_ability = ability.prototype(target=target_name)
                    targeted_ability_str = str(targeted_ability)
                    ability_record = AbilityRecord(targeted_ability)
                    self.__abilities_produced[ability_variant_key] = ability_record
                    self.logger.detail(f'targeted_ability: new {targeted_ability_str}')
                else:
                    ability_record = self.__abilities_produced[ability_variant_key]
                    targeted_ability = ability_record.ability
                    targeted_ability_str = str(targeted_ability)
                    self.logger.detail(f'targeted_ability: cached {targeted_ability_str}')
                if not self.__ability_record_filter.accept_ability_record(ability_record):
                    self.logger.debug(f'ability not accepted: {targeted_ability_str}')
                    continue
                score = max(0.0, targeted_ability.get_remaining_duration_sec(now))
                ability_key = AbilityVariantKey(targeted_ability)
                ability_scores[ability_key] = score
                is_running = targeted_ability.is_casting(now) or score > 0.0
                if not is_running and ability.is_reusable(now):
                    self.logger.detail(f'adding {targeted_ability_str} to ready_abilities')
                    ready_abilities_by_target[target_name].add(ability_key)
                    ready_abilities_by_caster[caster].add(ability_key)
                elif is_running:
                    self.logger.detail(f'adding {targeted_ability_str} to running_abilities')
                    running_abilities_by_target[target_name].add(ability_key)
                    running_abilities_by_caster[caster].add(ability_key)
        # apply the hell flags
        if self.__allow_stacking and not self.__allow_recasting:
            candidates = self.__extract_candidates(available_casters, ready_abilities_by_caster)
        elif self.__allow_stacking and self.__allow_recasting:
            # if player has nothing to do, recast one of its already running abilities, one with shortest remaining duration
            self.__use_best_running_ability_if_none_is_ready(available_casters, now, ready_abilities_by_caster, ready_abilities_by_target,
                                                             running_abilities_by_caster, ability_scores)
            candidates = self.__extract_candidates(available_casters, ready_abilities_by_caster)
        elif not self.__allow_stacking and not self.__allow_recasting:
            for target_name in target_names:
                # if anything is running on the target, remove all of its ready abilities
                # also remove from lists of ready by player
                self.__remove_ready_abilities_if_any_is_running(ready_abilities_by_caster, ready_abilities_by_target, running_abilities_by_target, target_name)
                # for each target, keep only abilities from one caster
                self.__keep_only_one_caster_per_target(ability_scores, ready_abilities_by_caster, ready_abilities_by_target, target_name)
            candidates = self.__extract_candidates(available_casters, ready_abilities_by_caster)
        else:  # not self.__allow_stacking and self.__allow_recasting
            for target_name in target_names:
                # if anything is running on the target, remove all of its ready abilities
                # also remove from lists of ready by player
                self.__remove_ready_abilities_if_any_is_running(ready_abilities_by_caster, ready_abilities_by_target, running_abilities_by_target, target_name)
                # if player has nothing to do, recast one of its already running abilities, one with shortest remaining duration
                # stacking is not a problem here - it was already prevented BEFORE those running abilities were cast
                self.__use_best_running_ability_if_none_is_ready(available_casters, now, ready_abilities_by_caster, ready_abilities_by_target,
                                                                 running_abilities_by_caster, ability_scores)
                if not ready_abilities_by_target[target_name]:
                    continue
                # for each target, keep only abilities from one caster
                # running abilities should get lowest priority in selecting a caster
                self.__keep_only_one_caster_per_target(ability_scores, ready_abilities_by_caster, ready_abilities_by_target, target_name)
            candidates = self.__extract_candidates(available_casters, ready_abilities_by_caster)
        return candidates

    # noinspection PyMethodMayBeStatic
    def __keep_only_one_caster_per_target(self, ability_scores: Dict[AbilityVariantKey, float],
                                          ready_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]],
                                          ready_abilities_by_target: Dict[str, Set[AbilityVariantKey]], target_name: str):
        caster = None
        best_score = None
        for ability_key in ready_abilities_by_target[target_name]:
            score = ability_scores[ability_key]
            if caster is None or score < best_score:
                caster = ability_key.ability.player
                best_score = score
        removed_abilities = set()
        kept_abilities = set()
        for ability_key in ready_abilities_by_target[target_name]:
            if ability_key.ability.player == caster:
                kept_abilities.add(ability_key)
            else:
                removed_abilities.add(ability_key)
        ready_abilities_by_target[target_name] = kept_abilities
        for ability_key in removed_abilities:
            ready_abilities_by_caster[ability_key.ability.player].remove(ability_key)

    # noinspection PyMethodMayBeStatic
    def __remove_ready_abilities_if_any_is_running(self,
                                                   ready_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]],
                                                   ready_abilities_by_target: Dict[str, Set[AbilityVariantKey]],
                                                   running_abilities_by_target: Dict[str, Set[AbilityVariantKey]], target_name: str):
        if running_abilities_by_target[target_name]:
            for ability_key in ready_abilities_by_target[target_name]:
                ready_abilities_by_caster[ability_key.ability.player].remove(ability_key)
            ready_abilities_by_target[target_name].clear()

    # noinspection PyMethodMayBeStatic
    def __use_best_running_ability_if_none_is_ready(self,
                                                    available_casters: Set[IPlayer],
                                                    now: datetime.datetime,
                                                    ready_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]],
                                                    ready_abilities_by_target: Dict[str, Set[AbilityVariantKey]],
                                                    running_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]],
                                                    ability_scores: Dict[AbilityVariantKey, float]):
        for caster in available_casters:
            if ready_abilities_by_caster[caster]:
                continue
            reusable_running = [ability_key for ability_key in running_abilities_by_caster[caster] if ability_key.ability.is_reusable(now)]
            if reusable_running:
                best_ability_key = min(running_abilities_by_caster[caster], key=lambda ability_key: ability_scores[ability_key])
                target = best_ability_key.ability.get_target()
                if target:
                    ready_abilities_by_target[target.get_target_name()].add(best_ability_key)
                    ready_abilities_by_caster[caster].add(best_ability_key)

    # noinspection PyMethodMayBeStatic
    def __extract_candidates(self, available_casters: Set[IPlayer],
                             ready_abilities_by_caster: Dict[IPlayer, Set[AbilityVariantKey]]) -> List[IAbility]:
        candidates = set()
        for caster in available_casters:
            candidates = candidates.union(ready_abilities_by_caster[caster])
        if self.logger.get_level() <= LogLevel.DETAIL:
            candidates_str = ', '.join([str(candidate) for candidate in candidates])
            self.logger.detail(f'candidates: {candidates_str}')
        return [ability_key.ability for ability_key in candidates]
