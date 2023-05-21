from typing import Callable, Dict, Any, List, Optional, Union, Type

import regex as re

from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import LINK_ABILITY_ID
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IAction
from rka.eq2.master.game.ability import AbilityPriority, HOIcon, AbilityEffectTarget, AbilitySpecial, AbilityType
from rka.eq2.master.game.ability.ability_builder import AbilityBuilder
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import WardenAbilities, InquisitorAbilities, MysticAbilities, ConjurorAbilities, ClericAbilities, \
    ShamanAbilities, GeomancerAbilities, DirgeAbilities, TroubadorAbilities, IllusionistAbilities, EtherealistAbilities, BardAbilities, \
    ElementalistAbilities, PriestAbilities, ThaumaturgistAbilities, MageAbilities, MonkAbilities, FighterAbilities, SummonerAbilities, ScoutAbilities, \
    RemoteAbilities, LocalAbilities, BrawlerAbilities, DefilerAbilities, BrigandAbilities, DruidAbilities, ThugAbilities, ItemsAbilities, EnchanterAbilities, \
    CommonerAbilities, CoercerAbilities, FuryAbilities, PaladinAbilities
from rka.eq2.master.game.engine.request import Request, RecastWhenDurationExpired, NonOverlappingDuration, CastAnyWhenReady, CompositeRequest, \
    TargetRotationRecast, CastAnyWhenReadyEveryNSec, CastAllAndExpire, CastOneAndExpire, CastBestAndExpire, RequestCombineLazyRecasting, RequestBuffsAndDps, \
    NonOverlappingDurationByGroup, DynamicRequestProxy, CastNAndExpire, CastStrictSequenceAndExpire
from rka.eq2.master.game.engine.resolver import XOR, AND, OR, ATLEAST, AbilityResolver, ATMOST
from rka.eq2.master.game.gameclass import GameClasses, GameClass
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IPlayer, TAbilityFilter, TOptionalPlayer, TValidTarget
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.requests import logger
from rka.eq2.master.game.requests.special_request import HeroicOpportunityRequest, Boneshattering, CombinationClosure
from rka.eq2.master.game.requests.special_request import WardRotation, InterceptRotation, PeckingOrder, HoTRotation
from rka.eq2.shared import Groups, GROUP_LIST, ClientFlags
from rka.eq2.shared.flags import MutableFlags


class RequestCache:
    def get_request_cache(self) -> Dict[Callable, Request]:
        raise NotImplementedError()

    def clear_cache(self):
        raise NotImplementedError()


def _reusable_request(factory_method: Callable[[Any], Request]) -> Callable[[], Request]:
    def factory_method_delegate(cache: RequestCache) -> Request:
        request_cache = cache.get_request_cache()
        if factory_method in request_cache:
            return request_cache[factory_method]
        new_request = factory_method(cache)
        new_request.set_description(factory_method.__name__)
        request_cache[factory_method] = new_request
        return new_request

    return factory_method_delegate


class RequestFactory(RequestCache):
    LOCAL_PLAYER_REQUEST_DURATION = 3.0
    SHORT_COMBAT_DURATION = 3.0
    DEFAULT_COMBAT_DURATION = 6.0
    EXTENDED_COMBAT_DURATION = 10.0
    LONG_COMBAT_DURATION = 15.0
    EMERGENCIES_DURATION = 7.0
    KEEP_REPEATING_DURATION = 60.0
    HO_DURATION = 10.0

    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__reusable_request_cache: Dict[Callable, Request] = dict()
        self.__resolver_all = AbilityResolver()
        self.__resolver_all_local = AbilityResolver().filtered(AbilityFilter().local_casters())
        self.__resolver_all_automated = AbilityResolver().filtered(AbilityFilter().automated_casters())
        self.__resolver_all_remote_automated = AbilityResolver().filtered(AbilityFilter().by_all_client_flags(ClientFlags.Remote | ClientFlags.Automated))
        self.__resolver_main_group_remote_automated = AbilityResolver().filtered(AbilityFilter().remote_casters_by_group(Groups.MAIN))
        self.__resolver_remote_automated_can_affect_main_player = AbilityResolver().filtered(AbilityFilter().remote_casters().can_affect_main_player())
        self.__per_player_ability_cache: Dict[IAbilityLocator, Dict[IPlayer, IAbility]] = dict()
        self.__per_player_custom_ability_cache: Dict[str, Dict[IPlayer, IAbility]] = dict()
        self.__per_player_request_cache: Dict[IAbilityLocator, Dict[Type[Request], Dict[IPlayer, Request]]] = dict()
        self.__empty_request = Request([], self.__resolver_all, duration=0.0)

    def get_request_cache(self) -> Dict[Callable, Request]:
        return self.__reusable_request_cache

    def clear_cache(self):
        self.__reusable_request_cache.clear()

    def __get_per_player_ability_cache(self, ability_locator: IAbilityLocator) -> Dict[IPlayer, IAbility]:
        if ability_locator not in self.__per_player_ability_cache:
            self.__per_player_ability_cache[ability_locator] = dict()
        return self.__per_player_ability_cache[ability_locator]

    def __per_player_get_custom_ability_cache(self, ability_name: str) -> Dict[IPlayer, IAbility]:
        if ability_name not in self.__per_player_custom_ability_cache:
            self.__per_player_custom_ability_cache[ability_name] = dict()
        return self.__per_player_custom_ability_cache[ability_name]

    def __get_per_player_request_cache(self, ability_locator: IAbilityLocator, request_type: Type[Request]) -> Dict[IPlayer, Request]:
        if ability_locator not in self.__per_player_request_cache:
            self.__per_player_request_cache[ability_locator] = dict()
        if request_type not in self.__per_player_request_cache[ability_locator]:
            self.__per_player_request_cache[ability_locator][request_type] = dict()
        return self.__per_player_request_cache[ability_locator][request_type]

    @staticmethod
    def create_multiple_nonoverlapping_request(abilities: List[IAbilityLocator], duration: float, resolver: AbilityResolver, overlap=0.0) -> List[Request]:
        requests = [NonOverlappingDuration(abilities=ability_loc, resolver=resolver, overlap=overlap, duration=duration) for ability_loc in abilities]
        return requests

    # ================================================ HEALS =================================================
    @_reusable_request
    def group_heal_now(self) -> Request:
        request = CastAnyWhenReady([WardenAbilities.winds_of_growth,
                                    WardenAbilities.healstorm,
                                    WardenAbilities.winds_of_healing,
                                    FuryAbilities.autumns_kiss,
                                    FuryAbilities.untamed_regeneration,
                                    ShamanAbilities.ancestral_channeling,
                                    MysticAbilities.transcendence,
                                    DefilerAbilities.carrion_warding,
                                    DefilerAbilities.wild_accretion,
                                    InquisitorAbilities.alleviation,
                                    CommonerAbilities.salve,
                                    DirgeAbilities.support,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def reactive_heals(self) -> Request:
        request = NonOverlappingDurationByGroup([MysticAbilities.spirit_tap,
                                                 ShamanAbilities.totemic_protection,
                                                 TroubadorAbilities.bagpipe_solo,
                                                 DirgeAbilities.exuberant_encore,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.5,
                                                duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def single_target_heals_default_target(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.torpor,
                                             MysticAbilities.oberon,
                                             InquisitorAbilities.chilling_invigoration,
                                             InquisitorAbilities.fanatics_inspiration,
                                             InquisitorAbilities.penance,
                                             WardenAbilities.natures_embrace,
                                             DefilerAbilities.death_cries,
                                             ],
                                            resolver=self.__resolver_remote_automated_can_affect_main_player,
                                            duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def single_target_heals_rotate_target(self) -> Request:
        # single target wards
        heals_1 = WardRotation([MysticAbilities.ancestral_ward,
                                DefilerAbilities.ancient_shroud,
                                ],
                               max_targets=6, exclude_self=False,
                               resolver=self.__resolver_all_automated,
                               duration=RequestFactory.DEFAULT_COMBAT_DURATION,
                               description='Shaman primary ward rotation')
        # single target protection/ward/HoT
        heals_2 = WardRotation([WardenAbilities.clearwater_current,
                                InquisitorAbilities.fanatics_protection,
                                DefilerAbilities.wraithwall,
                                ],
                               max_targets=6, exclude_self=False,
                               resolver=self.__resolver_all_automated,
                               duration=RequestFactory.DEFAULT_COMBAT_DURATION,
                               description='Healer extra heals rotation')
        # splash heal HoT
        heals_3 = HoTRotation([FuryAbilities.regrowth,
                               WardenAbilities.photosynthesis,
                               ],
                              max_targets=3, exclude_self=False,
                              resolver=self.__resolver_all_automated,
                              duration=RequestFactory.DEFAULT_COMBAT_DURATION,
                              description='Splash heals rotation')
        combined = CompositeRequest('single-target heals rotations', requests=[heals_1, heals_2, heals_3],
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return combined

    @_reusable_request
    def common_group_heals(self) -> Request:
        duration = RequestFactory.DEFAULT_COMBAT_DURATION
        heals_1 = NonOverlappingDurationByGroup([ClericAbilities.divine_waters,
                                                 ClericAbilities.divine_guidance,
                                                 InquisitorAbilities.inquisition,
                                                 ShamanAbilities.totemic_protection,
                                                 WardenAbilities.healstorm,
                                                 FuryAbilities.autumns_kiss,
                                                 ],
                                                resolver=self.__resolver_all_automated,
                                                overlap=2.0,
                                                duration=duration)
        heals_2 = RecastWhenDurationExpired([InquisitorAbilities.malevolent_diatribe,
                                             ],
                                            resolver=self.__resolver_all_automated,
                                            duration=duration)
        wards = NonOverlappingDurationByGroup([MysticAbilities.umbral_barrier,
                                               DefilerAbilities.carrion_warding,
                                               ],
                                              resolver=self.__resolver_all_automated,
                                              overlap=2.0,
                                              duration=duration)
        combined = CompositeRequest('common group heals', requests=[heals_1, heals_2, wards],
                                    duration=duration)
        return combined

    @_reusable_request
    def advanced_group_heals(self) -> Request:
        duration = RequestFactory.DEFAULT_COMBAT_DURATION
        # complementary to common heal rotation
        heals_1 = NonOverlappingDurationByGroup([ClericAbilities.divine_waters,
                                                 ClericAbilities.divine_guidance,
                                                 InquisitorAbilities.inquisition,
                                                 WardenAbilities.winds_of_healing,
                                                 FuryAbilities.hibernation,
                                                 FuryAbilities.untamed_regeneration,  # with some duration added
                                                 InquisitorAbilities.alleviation,  # with some duration added
                                                 MysticAbilities.transcendence,  # with some duration added
                                                 DefilerAbilities.wild_accretion,  # with some duration added
                                                 ],
                                                resolver=self.__resolver_all_automated,
                                                overlap=0.0,
                                                duration=duration)
        # additional heals of lesser importance
        heals_2 = NonOverlappingDurationByGroup([DruidAbilities.rage_of_the_wild,  # with some duration added
                                                 FuryAbilities.porcupine,
                                                 WardenAbilities.winds_of_growth,
                                                 DefilerAbilities.nightmares,
                                                 ],
                                                resolver=self.__resolver_all_automated,
                                                overlap=0.0,
                                                duration=duration)
        # complementary to common wards rotation
        wards_1 = NonOverlappingDurationByGroup([ShamanAbilities.spirit_aegis,
                                                 ShamanAbilities.ancestral_palisade,
                                                 ClericAbilities.bulwark_of_faith,
                                                 DruidAbilities.woodward,
                                                 GeomancerAbilities.xenolith,
                                                 ],
                                                resolver=self.__resolver_all_automated,
                                                overlap=1.0,
                                                duration=duration)
        # additional wards of lesser importance
        wards_2 = NonOverlappingDurationByGroup([WardenAbilities.ward_of_the_untamed,
                                                 MysticAbilities.prophetic_ward,
                                                 ],
                                                resolver=self.__resolver_all_automated,
                                                overlap=0.0,
                                                duration=duration)
        # heals/wards with additional benefits - recast as soon as possible
        extras = RecastWhenDurationExpired([ShamanAbilities.soul_shackle,
                                            MysticAbilities.lunar_attendant,
                                            DefilerAbilities.phantasmal_barrier,
                                            DefilerAbilities.spiritual_circle,
                                            CoercerAbilities.intellectual_remedy,
                                            TroubadorAbilities.chaos_anthem,
                                            ],
                                           resolver=self.__resolver_all_automated,
                                           duration=duration)
        combined = CompositeRequest('advanced group heals', requests=[heals_1, heals_2, wards_1, wards_2, extras],
                                    duration=duration)
        return combined

    @_reusable_request
    def advanced_group_power(self) -> Request:
        power_1 = NonOverlappingDurationByGroup([WardenAbilities.healing_grove,
                                                 DefilerAbilities.maelstrom,
                                                 IllusionistAbilities.manatap,
                                                 CoercerAbilities.cannibalize_thoughts,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.0,
                                                duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        power_2 = CastAnyWhenReady([TroubadorAbilities.reverberation,
                                    IllusionistAbilities.chromatic_illusion,
                                    CoercerAbilities.ether_balance,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        power_3 = NonOverlappingDurationByGroup([DefilerAbilities.cannibalize,
                                                 DefilerAbilities.soul_cannibalize,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.0,
                                                duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        combined = CompositeRequest('advanced group power', requests=[power_1, power_2, power_3],
                                    duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return combined

    @_reusable_request
    def common_group_protections(self) -> Request:
        request = CastAnyWhenReady([ConjurorAbilities.stoneskin,
                                    ConjurorAbilities.stoneskins,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def immunities(self) -> Request:
        request = NonOverlappingDurationByGroup([MysticAbilities.immunization,
                                                 MysticAbilities.ancestral_support,
                                                 ConjurorAbilities.elemental_barrier,
                                                 GeomancerAbilities.obsidian_mind,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.5,
                                                duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # ================================================ POWER =================================================
    @_reusable_request
    def group_power_now(self) -> Request:
        request = NonOverlappingDurationByGroup([MysticAbilities.spirit_tap.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                                 TroubadorAbilities.bagpipe_solo.boost_resolved(AbilityPriority.MANUAL_REQUEST, 2),
                                                 DirgeAbilities.exuberant_encore.boost_resolved(AbilityPriority.MANUAL_REQUEST, 1),
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.5,
                                                duration=RequestFactory.LONG_COMBAT_DURATION)
        return request

    @_reusable_request
    def group_weak_power_once(self) -> Request:
        request = CastOneAndExpire([EnchanterAbilities.manasoul,
                                    IllusionistAbilities.chromatic_illusion,
                                    IllusionistAbilities.manatap,
                                    IllusionistAbilities.savante,
                                    CoercerAbilities.channel,
                                    TroubadorAbilities.tap_essence,
                                    ConjurorAbilities.sacrifice,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def group_strong_power(self) -> Request:
        request = NonOverlappingDurationByGroup([MysticAbilities.spirit_tap,
                                                 DefilerAbilities.maelstrom,
                                                 TroubadorAbilities.bagpipe_solo,
                                                 DirgeAbilities.exuberant_encore,
                                                 # as a last resort - strong single target power
                                                 WardenAbilities.hierophantic_genesis,
                                                 TroubadorAbilities.energizing_ballad,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=0.5,
                                                duration=RequestFactory.LONG_COMBAT_DURATION)
        return request

    @_reusable_request
    def main_player_power(self) -> Request:
        request = CastOneAndExpire([TroubadorAbilities.energizing_ballad,
                                    WardenAbilities.hierophantic_genesis,
                                    DirgeAbilities.oration_of_sacrifice,
                                    EnchanterAbilities.mana_flow,
                                    CoercerAbilities.mind_control,
                                    ],
                                   resolver=self.__resolver_remote_automated_can_affect_main_player,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def drain_power_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Drain)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReady(abilities=abilities,
                                   resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def drain_power_once(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Drain)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastNAndExpire(abilities=abilities,
                                 n=2,
                                 resolver=self.__resolver_all_remote_automated,
                                 duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    # ================================================ CURES =================================================
    # not cached
    def specific_group_cure_now(self, group_id: Groups) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Group).by_max_priority(AbilityPriority.GROUP_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        resolver = AbilityResolver().filtered(AbilityFilter().automated_casters_by_group(group_id)).prototype(priority=AbilityPriority.MANUAL_REQUEST)
        request = CastBestAndExpire(abilities=abilities, resolver=resolver, duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def group_cure_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Group).by_max_priority(AbilityPriority.GROUP_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        requests = []
        for group_id in GROUP_LIST:
            resolver = AbilityResolver().filtered(AbilityFilter().automated_casters_by_group(group_id)).prototype(priority=AbilityPriority.MANUAL_REQUEST)
            request = CastBestAndExpire(abilities=abilities,
                                        resolver=resolver,
                                        duration=RequestFactory.DEFAULT_COMBAT_DURATION)
            if request.get_resolved_abilities_map():
                requests.append(request)
        combined = CompositeRequest('cure in each group', requests=requests, duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return combined

    @_reusable_request
    def raid_group_cure_now(self) -> Request:
        flt_1 = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Group).by_max_priority(AbilityPriority.GROUP_CURE)
        flt_2 = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Raid).by_max_priority(AbilityPriority.GROUP_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt_1.op_or(flt_2))
        requests = []
        for group_id in GROUP_LIST:
            resolver = AbilityResolver().filtered(AbilityFilter().automated_casters_by_group(group_id)).prototype(priority=AbilityPriority.MANUAL_REQUEST)
            request = CastBestAndExpire(abilities=abilities,
                                        resolver=resolver,
                                        duration=RequestFactory.DEFAULT_COMBAT_DURATION)
            if request.get_resolved_abilities_map():
                requests.append(request)
        combined = CompositeRequest('cure raid or in each group', requests=requests, duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return combined

    @_reusable_request
    def urgent_group_cure_now(self) -> Request:
        flt_1 = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Group)
        flt_2 = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Raid)
        abilities = self.__runtime.ability_reg.find_abilities(flt_1.op_or(flt_2))
        request = CastAnyWhenReady(abilities=abilities,
                                   resolver=self.__resolver_all_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def cure_curse_default_target_now(self) -> Request:
        request = CastAllAndExpire([PriestAbilities.cure_curse.boost_resolved(AbilityPriority.MANUAL_REQUEST)],
                                   resolver=self.__resolver_main_group_remote_automated,
                                   duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def cure_default_target_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Ally).by_max_priority(AbilityPriority.SINGLE_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        # default target is normally set to all local players
        request = CastBestAndExpire(abilities=abilities,
                                    resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                    duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def confront_fear_default_target_now(self) -> Request:
        request = CastOneAndExpire(DirgeAbilities.confront_fear.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    # not cached
    def cure_target(self, target_name: str) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Ally).by_max_priority(AbilityPriority.SINGLE_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastBestAndExpire(abilities=abilities,
                                    resolver=self.__resolver_all_automated.prototype(target=target_name),
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'cure {target_name}')
        return request

    # not cached
    # noinspection PyMethodMayBeStatic
    def cure_target_by_caster(self, target_name: str, caster: IPlayer) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Ally).by_max_priority(AbilityPriority.SINGLE_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        resolver = AbilityResolver().filtered(AbilityFilter().caster_is_one_of([caster]))
        request = CastBestAndExpire(abilities=abilities,
                                    resolver=resolver.prototype(target=target_name),
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'cure {target_name}')
        return request

    # not cached
    def mage_cure_target(self, target_name: str) -> Request:
        request = CastBestAndExpire(abilities=[MageAbilities.cure_magic],
                                    resolver=self.__resolver_all_automated.prototype(target=target_name),
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'mage cure {target_name}')
        return request

    # not cached
    def priest_cure_target(self, target_name: str) -> Request:
        request = CastBestAndExpire(abilities=[PriestAbilities.cure],
                                    resolver=self.__resolver_all_automated.prototype(target=target_name),
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'priest cure {target_name}')
        return request

    # not cached
    def cure_curse_target(self, target_name: str) -> Request:
        if MutableFlags.CAST_ALL_CURE_CURSES:
            request_type = CastAllAndExpire
        else:
            request_type = CastBestAndExpire
        request = request_type(abilities=PriestAbilities.cure_curse,
                               resolver=self.__resolver_all_remote_automated.prototype(target=target_name),
                               duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'cure curse {target_name}')
        return request

    # not cached
    def cure_curse_target_list(self, target_names: List[str]) -> Request:
        abilities: List[List[IAbility]] = list()
        cure_curses = [PriestAbilities.cure_curse]
        for target_name in target_names:
            resolver = self.__resolver_all_remote_automated.prototype(target=target_name)
            one_target_cures = resolver.resolve_abilities(cure_curses)
            if not one_target_cures:
                logger.warn(f'no cure curse for targe {target_name}')
                break
            abilities.append(one_target_cures)
        request = PeckingOrder(pecking_choices=abilities, resolver=self.__resolver_all, rate=3.0, duration=RequestFactory.LONG_COMBAT_DURATION)
        request.set_description(description=f'cure curse {"->".join(target_names)}')
        return request

    # not cached
    def stoneskin_target(self, target: TValidTarget) -> Request:
        request = CastBestAndExpire(abilities=[WardenAbilities.infuriating_thorns,
                                               ClericAbilities.perseverance_of_the_divine,
                                               DirgeAbilities.sonic_barrier,
                                               ],
                                    resolver=self.__resolver_all_automated.prototype(target=target),
                                    duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description=f'stoneskin {target}')
        return request

    # not cached
    def deathsave_target(self, target: TValidTarget) -> Request:
        selector = XOR([
            WardenAbilities.cyclone,
            OR([
                XOR([
                    WardenAbilities.infuriating_thorns,
                    FuryAbilities.natural_regeneration,
                    ClericAbilities.perseverance_of_the_divine,
                    DirgeAbilities.sonic_barrier,
                ]),
                XOR([
                    MysticAbilities.ancestral_savior,
                    DefilerAbilities.ancestral_avenger,
                    InquisitorAbilities.redemption,
                    WardenAbilities.natures_renewal,
                    WardenAbilities.tunares_watch,
                    FuryAbilities.feral_tenacity,
                ]),
            ]),
            ATMOST(2, [
                WardenAbilities.infuriating_thorns,
                WardenAbilities.tunares_watch,
                WardenAbilities.natures_renewal,
                FuryAbilities.feral_tenacity,
                MysticAbilities.ancestral_savior,
                DefilerAbilities.ancestral_avenger,
                ClericAbilities.perseverance_of_the_divine,
                InquisitorAbilities.redemption,
                DirgeAbilities.sonic_barrier,
                TroubadorAbilities.countersong,
            ])
        ])
        ability_filter = AbilityFilter().remote_casters().can_affect_ally_target(self.__runtime, target)
        resolver = AbilityResolver().filtered(ability_filter).prototype(target=target)
        request = RequestCombineLazyRecasting(combine=selector, resolver=resolver, duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    # ================================================ BUFFS =================================================
    @_reusable_request
    def common_buffs(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.bolster,
                                             MysticAbilities.ritual_of_alacrity,
                                             FuryAbilities.fae_fire,
                                             FuryAbilities.animal_form,
                                             DirgeAbilities.confront_fear,
                                             InquisitorAbilities.fanatics_protection,
                                             TroubadorAbilities.jesters_cap,
                                             IllusionistAbilities.flash_of_brilliance,
                                             IllusionistAbilities.prismatic_chaos,
                                             ],
                                            resolver=self.__resolver_all_automated,
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def uncommon_buffs(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.stampede_of_the_herd,
                                             MysticAbilities.ancestral_bolster,
                                             WardenAbilities.storm_of_shale,
                                             FuryAbilities.energy_vortex,
                                             InquisitorAbilities.divine_recovery,
                                             InquisitorAbilities.divine_provenance,
                                             DirgeAbilities.anthem_of_war,
                                             DirgeAbilities.peal_of_battle,
                                             BrigandAbilities.deceit,
                                             TroubadorAbilities.countersong,
                                             TroubadorAbilities.demoralizing_processional,
                                             TroubadorAbilities.maelstrom_of_sound,
                                             TroubadorAbilities.perfection_of_the_maestro,
                                             TroubadorAbilities.energizing_ballad,
                                             EnchanterAbilities.peace_of_mind,
                                             EnchanterAbilities.touch_of_empathy,
                                             EnchanterAbilities.aura_of_power,
                                             IllusionistAbilities.illusionary_instigation,
                                             IllusionistAbilities.savante,
                                             IllusionistAbilities.illusory_barrier,
                                             IllusionistAbilities.time_warp,
                                             IllusionistAbilities.phantom_troupe,
                                             CoercerAbilities.mind_control,
                                             CoercerAbilities.lethal_focus,
                                             CoercerAbilities.manaward,
                                             CoercerAbilities.mindbend,
                                             ConjurorAbilities.world_ablaze,
                                             ConjurorAbilities.plane_shift,
                                             ],
                                            resolver=self.__resolver_all_automated,
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def consumable_buffs_debuffs(self) -> Request:
        duration = RequestFactory.EXTENDED_COMBAT_DURATION
        abilities = [ItemsAbilities.quelule_cocktail,
                     ]
        requests = RequestFactory.create_multiple_nonoverlapping_request(abilities=abilities, duration=duration, resolver=self.__resolver_all_remote_automated)
        request = CompositeRequest(description='short_strong_debuffs', requests=requests, duration=duration)
        return request

    @_reusable_request
    def non_overlapping_main_group_buffs(self) -> Request:
        duration = RequestFactory.DEFAULT_COMBAT_DURATION
        abilities = [GeomancerAbilities.earthen_phalanx,
                     GeomancerAbilities.bastion_of_iron,
                     GeomancerAbilities.obsidian_mind,
                     ElementalistAbilities.frost_pyre,
                     ElementalistAbilities.thermal_depletion,
                     EtherealistAbilities.ethereal_gift,
                     EtherealistAbilities.essence_of_magic,
                     EtherealistAbilities.ethereal_conduit,
                     BardAbilities.requiem,
                     BardAbilities.songspinners_note,
                     ItemsAbilities.critical_thinking,
                     ]
        requests = RequestFactory.create_multiple_nonoverlapping_request(abilities=abilities, duration=duration, resolver=self.__resolver_main_group_remote_automated)
        request = CompositeRequest(description='non_overlapping_main_group_buffs', requests=requests, duration=duration)
        return request

    @_reusable_request
    def prepull_buffs(self) -> Request:
        duration = 20.0
        group_abilities = [DirgeAbilities.peal_of_battle,
                           DirgeAbilities.confront_fear,
                           DirgeAbilities.anthem_of_war,
                           TroubadorAbilities.jesters_cap,
                           InquisitorAbilities.divine_provenance,
                           InquisitorAbilities.divine_recovery,
                           EnchanterAbilities.peace_of_mind,
                           EnchanterAbilities.aura_of_power,
                           IllusionistAbilities.time_warp,
                           IllusionistAbilities.flash_of_brilliance,
                           ElementalistAbilities.frost_pyre,
                           GeomancerAbilities.earthen_phalanx,
                           GeomancerAbilities.bastion_of_iron,
                           GeomancerAbilities.obsidian_mind,
                           EtherealistAbilities.essence_of_magic,
                           EtherealistAbilities.ethereal_gift,
                           ]
        raid_abilities = [MysticAbilities.bolster,
                          MysticAbilities.ancestral_bolster,
                          MysticAbilities.umbral_barrier,
                          MysticAbilities.torpor,
                          DefilerAbilities.carrion_warding,
                          DefilerAbilities.death_cries,
                          DefilerAbilities.wraithwall,
                          WardenAbilities.clearwater_current,
                          WardenAbilities.healstorm,
                          WardenAbilities.storm_of_shale,
                          InquisitorAbilities.fanatics_protection,
                          ]
        group_requests = RequestFactory.create_multiple_nonoverlapping_request(abilities=group_abilities, duration=duration, resolver=self.__resolver_main_group_remote_automated)
        raid_requests = RequestFactory.create_multiple_nonoverlapping_request(abilities=raid_abilities, duration=duration, resolver=self.__resolver_all_remote_automated)
        all_requests = group_requests + raid_requests
        combined = CompositeRequest('prepull buffs', requests=all_requests, duration=duration)
        return combined

    @_reusable_request
    def rebuff_other_player(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.ancestry,
                                             MysticAbilities.premonition,
                                             DruidAbilities.spirit_of_the_bat,
                                             WardenAbilities.aspect_of_the_forest,
                                             WardenAbilities.regenerating_spores,
                                             WardenAbilities.thorncoat,
                                             FuryAbilities.lucidity,
                                             FuryAbilities.thornskin,
                                             FuryAbilities.pact_of_nature,
                                             FuryAbilities.wraths_blessing,
                                             FuryAbilities.force_of_nature,
                                             InquisitorAbilities.divine_armor,
                                             InquisitorAbilities.inquest,
                                             BrigandAbilities.thieves_guild,
                                             BardAbilities.song_of_shielding,
                                             DirgeAbilities.battle_cry,
                                             DirgeAbilities.hyrans_seething_sonata,
                                             TroubadorAbilities.upbeat_tempo,
                                             EnchanterAbilities.enchanted_vigor,
                                             IllusionistAbilities.synergism,
                                             IllusionistAbilities.arms_of_imagination,
                                             IllusionistAbilities.time_compression,
                                             CoercerAbilities.enraging_demeanor,
                                             CoercerAbilities.sirens_stare,
                                             ConjurorAbilities.fire_seed,
                                             ConjurorAbilities.flameshield,
                                             ThaumaturgistAbilities.oblivion_link,
                                             EtherealistAbilities.recapture,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=30.0)
        return request

    @_reusable_request
    def rebuff_other_player_essentials(self) -> Request:
        request = RecastWhenDurationExpired([WardenAbilities.regenerating_spores,
                                             FuryAbilities.lucidity,
                                             FuryAbilities.force_of_nature,
                                             FuryAbilities.pact_of_nature,
                                             InquisitorAbilities.inquest,
                                             DirgeAbilities.battle_cry,
                                             TroubadorAbilities.upbeat_tempo,
                                             EnchanterAbilities.enchanted_vigor,
                                             ConjurorAbilities.fire_seed,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=30.0)
        return request

    @_reusable_request
    def rebuff_self(self) -> Request:
        request = RecastWhenDurationExpired([PriestAbilities.reprieve,
                                             PriestAbilities.undaunted,
                                             MysticAbilities.ancestral_avatar,
                                             DefilerAbilities.harbinger,
                                             DefilerAbilities.invective,
                                             DefilerAbilities.tendrils_of_horror,
                                             WardenAbilities.instinct,
                                             FuryAbilities.primal_fury,
                                             InquisitorAbilities.tenacity,
                                             InquisitorAbilities.fanaticism,
                                             ScoutAbilities.dozekars_resilience,
                                             ScoutAbilities.persistence,
                                             BrigandAbilities.safehouse,
                                             DirgeAbilities.dirges_refrain,
                                             MageAbilities.scaled_protection,
                                             MageAbilities.undeath,
                                             IllusionistAbilities.rapidity,
                                             CoercerAbilities.coercive_healing,
                                             CoercerAbilities.velocity,
                                             CoercerAbilities.peaceful_link,
                                             ConjurorAbilities.servants_intervention,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=30.0)
        return request

    @_reusable_request
    def rebuff_self_essentials(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.ancestral_avatar,
                                             CoercerAbilities.coercive_healing,
                                             DirgeAbilities.dirges_refrain,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=30.0)
        return request

    @_reusable_request
    def rebuff_persistent_passive_buffs(self) -> Request:
        abilities = self.__runtime.ability_reg.find_abilities(AbilityFilter().persistent_passive_buffs())
        request = RecastWhenDurationExpired(abilities=abilities,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=60.0)
        return request

    # ============================================== DEBUFFS =================================================
    @_reusable_request
    def common_debuffs(self) -> Request:
        request = RecastWhenDurationExpired([ShamanAbilities.umbral_trap,
                                             MysticAbilities.echoes_of_the_ancients,
                                             MysticAbilities.haze,
                                             MysticAbilities.lamenting_soul,
                                             DefilerAbilities.malicious_spirits,
                                             DefilerAbilities.abhorrent_seal,
                                             DefilerAbilities.abomination,
                                             DefilerAbilities.hexation,
                                             DefilerAbilities.bane_of_warding,
                                             InquisitorAbilities.divine_righteousness,
                                             InquisitorAbilities.condemn,
                                             InquisitorAbilities.deny,
                                             InquisitorAbilities.forced_obedience,
                                             InquisitorAbilities.strike_of_flames,
                                             FuryAbilities.intimidation,
                                             FuryAbilities.death_swarm,
                                             ScoutAbilities.trick_of_the_hunter,
                                             ThugAbilities.shadow,
                                             ThugAbilities.change_of_engagement,
                                             ThugAbilities.traumatic_swipe,
                                             ThugAbilities.torporous_strike,
                                             ThugAbilities.thieving_essence,
                                             BrigandAbilities.dispatch,
                                             BrigandAbilities.debilitate,
                                             BrigandAbilities.entangle,
                                             BrigandAbilities.will_to_survive,
                                             BrigandAbilities.murderous_rake,
                                             BrigandAbilities.battery_and_assault,
                                             BrigandAbilities.mug,
                                             BrigandAbilities.holdup,
                                             BrigandAbilities.deft_disarm,
                                             BrigandAbilities.desperate_thrust,
                                             DirgeAbilities.claras_chaotic_cacophony,
                                             DirgeAbilities.verliens_keen_of_despair,
                                             DirgeAbilities.daros_sorrowful_dirge,
                                             TroubadorAbilities.depressing_chant,
                                             TroubadorAbilities.vexing_verses,
                                             TroubadorAbilities.dancing_blade,
                                             TroubadorAbilities.sonic_interference,
                                             EnchanterAbilities.chronosiphoning,
                                             EnchanterAbilities.nullifying_staff,
                                             IllusionistAbilities.paranoia,
                                             IllusionistAbilities.nightmare,
                                             CoercerAbilities.obliterated_psyche,
                                             CoercerAbilities.tashiana,
                                             CoercerAbilities.asylum,
                                             CoercerAbilities.medusa_gaze,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def non_overlapping_debuffs(self) -> Request:
        duration = RequestFactory.DEFAULT_COMBAT_DURATION
        abilities = [ElementalistAbilities.brittle_armor,
                     ElementalistAbilities.glacial_freeze,
                     ElementalistAbilities.dominion_of_fire,
                     ElementalistAbilities.scorched_earth,
                     GeomancerAbilities.erosion,
                     ThaumaturgistAbilities.exsanguination,
                     ThaumaturgistAbilities.tainted_mutation,
                     BardAbilities.zanders_choral_rebuff,
                     BardAbilities.disheartening_descant,
                     ]
        requests = RequestFactory.create_multiple_nonoverlapping_request(abilities=abilities, duration=duration, resolver=self.__resolver_all_remote_automated)
        request = CompositeRequest(description='non_overlapping_debuffs', requests=requests, duration=duration)
        return request

    # =============================================== COMBAT =================================================
    @_reusable_request
    def combat(self) -> Request:
        request = CastAllAndExpire([RemoteAbilities.combat,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def combat_autoface(self) -> Request:
        request = CastAllAndExpire([RemoteAbilities.combat_autoface,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def solo_dps(self) -> Request:
        request = CastAllAndExpire([RemoteAbilities.dps,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def support(self) -> Request:
        request = RecastWhenDurationExpired([DirgeAbilities.support,
                                             TroubadorAbilities.support,
                                             IllusionistAbilities.support,
                                             CoercerAbilities.support,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def aoe_dps(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.circle_of_the_ancients,
                                             InquisitorAbilities.litany_circle,
                                             DruidAbilities.wrath_of_nature,
                                             WardenAbilities.winds_of_permafrost,
                                             FuryAbilities.stormbearers_fury,
                                             FuryAbilities.raging_whirlwind,
                                             FuryAbilities.heart_of_the_storm,
                                             ScoutAbilities.dagger_storm,
                                             BardAbilities.melody_of_affliction,
                                             DirgeAbilities.darksong_spin,
                                             DirgeAbilities.echoing_howl,
                                             TroubadorAbilities.thunderous_overture,
                                             ThugAbilities.danse_macabre,
                                             BrigandAbilities.double_up,
                                             BrigandAbilities.forced_arbitration,
                                             BrigandAbilities.crimson_swath,
                                             BrigandAbilities.cornered,
                                             BrigandAbilities.blinding_dust,
                                             MageAbilities.unda_arcanus_spiritus,
                                             EnchanterAbilities.id_explosion,
                                             EnchanterAbilities.blinding_shock,
                                             CoercerAbilities.shock_wave,
                                             SummonerAbilities.elemental_toxicity,
                                             SummonerAbilities.blightfire,
                                             ConjurorAbilities.earthquake,
                                             ElementalistAbilities.frozen_heavens,
                                             GeomancerAbilities.domain_of_earth,
                                             EtherealistAbilities.etherflash,
                                             EtherealistAbilities.implosion,
                                             ThaumaturgistAbilities.blood_parasite,
                                             ThaumaturgistAbilities.necrotic_consumption,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def ascension_nukes(self) -> Request:
        request = CastAnyWhenReady([ThaumaturgistAbilities.anti_life,
                                    ThaumaturgistAbilities.septic_strike,
                                    ThaumaturgistAbilities.blood_contract,
                                    ThaumaturgistAbilities.bonds_of_blood,
                                    ThaumaturgistAbilities.bloatfly,
                                    ThaumaturgistAbilities.desiccation,
                                    ElementalistAbilities.fiery_incineration,
                                    ElementalistAbilities.blistering_waste,
                                    ElementalistAbilities.elemental_amalgamation,
                                    ElementalistAbilities.wildfire,
                                    GeomancerAbilities.mudslide,
                                    GeomancerAbilities.stone_hammer,
                                    EtherealistAbilities.levinbolt,
                                    EtherealistAbilities.focused_blast,
                                    EtherealistAbilities.mana_schism,
                                    EtherealistAbilities.cascading_force,
                                    EtherealistAbilities.implosion,
                                    ThaumaturgistAbilities.necrotic_consumption,
                                    ThaumaturgistAbilities.revocation_of_life,
                                    ThaumaturgistAbilities.virulent_outbreak,
                                    GeomancerAbilities.granite_protector,
                                    GeomancerAbilities.terrestrial_coffin,
                                    EtherealistAbilities.compounding_force,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=20.0)
        return request

    @_reusable_request
    def profession_nukes(self) -> Request:
        request = CastAnyWhenReady([MysticAbilities.polar_fire,
                                    FuryAbilities.devour,
                                    BrigandAbilities.vital_strike,
                                    BrigandAbilities.gut_rip,
                                    BrigandAbilities.perforate,
                                    BardAbilities.hungering_lyric,
                                    EnchanterAbilities.ego_whip,
                                    EnchanterAbilities.temporal_mimicry,
                                    ConjurorAbilities.elemental_blast,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # not cached
    def spam_attacks(self, players: List[IPlayer]) -> Request:
        foe_targets = [AbilityEffectTarget.Enemy, AbilityEffectTarget.Encounter, AbilityEffectTarget.AOE]
        abilities = self.__runtime.ability_reg.find_abilities(lambda ability_: not ability_.census.beneficial
                                                                               and ability_.census.casting <= 1.5
                                                                               and ability_.census.duration >= 0.0
                                                                               and not ability_.ext.maintained
                                                                               and ability_.ext.effect_target in foe_targets)
        resolver = AbilityResolver().filtered(AbilityFilter().caster_is_one_of(players)).prototype(priority=AbilityPriority.GREATER_DIRECT_DPS)
        request = CastAnyWhenReady(abilities, resolver=resolver, duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # ================================================ EMERGENCIES =================================================
    @_reusable_request
    def group_aoe_blockers(self) -> Request:
        request = NonOverlappingDurationByGroup([BardAbilities.bladedance,
                                                 DruidAbilities.tortoise_shell,
                                                 TroubadorAbilities.countersong,
                                                 WardenAbilities.sandstorm,
                                                 BrigandAbilities.blinding_dust,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=1.0,
                                                duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def group_strong_heals(self) -> Request:
        request = NonOverlappingDurationByGroup([ShamanAbilities.totemic_protection,
                                                 ShamanAbilities.ancestral_channeling,
                                                 WardenAbilities.sylvan_embrace,
                                                 FuryAbilities.feral_pulse,
                                                 InquisitorAbilities.evidence_of_faith,
                                                 DefilerAbilities.purulence,
                                                 MysticAbilities.wards_of_the_eidolon,
                                                 # include power+heals
                                                 DirgeAbilities.exuberant_encore,
                                                 TroubadorAbilities.bagpipe_solo,
                                                 MysticAbilities.spirit_tap,
                                                 # and best protections
                                                 FuryAbilities.pact_of_the_cheetah,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=1.0,
                                                duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def group_deathsave(self) -> Request:
        request = NonOverlappingDurationByGroup([WardenAbilities.tunares_watch,
                                                 FuryAbilities.pact_of_the_cheetah,
                                                 ClericAbilities.equilibrium,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=1.0,
                                                duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def group_emergency_extras(self) -> Request:
        request = CastAnyWhenReady([ShamanAbilities.malady,
                                    ClericAbilities.light_of_devotion,
                                    BardAbilities.dodge_and_cover,
                                    BardAbilities.veil_of_notes,
                                    ThugAbilities.pris_de_fer,
                                    BrigandAbilities.beg_for_mercy,
                                    ClericAbilities.immaculate_revival,
                                    InquisitorAbilities.divine_aura,
                                    DruidAbilities.rebirth,
                                    EnchanterAbilities.channeled_focus,
                                    CoercerAbilities.mind_control,
                                    CoercerAbilities.channel,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def tank_deathsave(self) -> Request:
        tanks = self.__runtime.player_mgr.resolve_targets(GameClasses.Fighter)
        requests = []
        for tank in tanks:
            return self.deathsave_target(target=tank)
        return CompositeRequest(f'Tank deathsave', requests)

    @_reusable_request
    def tank_stoneskin(self) -> Request:
        tanks = self.__runtime.player_mgr.resolve_targets(GameClasses.Fighter)
        requests = []
        for tank in tanks:
            requests.append(self.stoneskin_target(target=tank))
        return CompositeRequest(f'Tank stoneskin', requests)

    @_reusable_request
    def tank_strong_heals(self) -> Request:
        request = NonOverlappingDuration([DirgeAbilities.oration_of_sacrifice,
                                          WardenAbilities.hierophantic_genesis,
                                          DruidAbilities.sylvan_touch,
                                          ShamanAbilities.eidolic_ward,
                                          ],
                                         resolver=self.__resolver_remote_automated_can_affect_main_player,
                                         overlap=1.0,
                                         duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def self_immunities(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.ancestral_support,
                                             DruidAbilities.howling_with_the_pack,
                                             DruidAbilities.serenity,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.EMERGENCIES_DURATION)
        return request

    @_reusable_request
    def emergency_rez(self) -> Request:
        request_1 = CastOneAndExpire([ClericAbilities.immaculate_revival,
                                      DruidAbilities.rebirth,
                                      ],
                                     resolver=self.__resolver_all_remote_automated,
                                     duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return CompositeRequest('Emergency rezzes', [request_1])

    # ================================================ MAINTAINED ACTIONS =================================================
    @_reusable_request
    def keep_curing_me(self) -> Request:
        request = RecastWhenDurationExpired([MysticAbilities.ancestral_balm,
                                             ],
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    @_reusable_request
    def keep_drain_power(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Drain)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReady(abilities=abilities,
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # not cached
    def repeated_group_curing(self, period: float) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Cure).target_type(AbilityEffectTarget.Group).by_max_priority(AbilityPriority.GROUP_CURE)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReadyEveryNSec(abilities=abilities,
                                            delay=period,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    @_reusable_request
    def keep_group_curing(self) -> Request:
        return self.repeated_group_curing(2.0)

    @_reusable_request
    def keep_dispelling(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Dispel)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReadyEveryNSec(abilities=abilities,
                                            delay=1.0,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    @_reusable_request
    def keep_stunning(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Stun)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReadyEveryNSec(abilities=abilities,
                                            delay=2.0,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    @_reusable_request
    def keep_feeding_power(self) -> Request:
        request = CastAnyWhenReadyEveryNSec([EnchanterAbilities.manasoul,
                                             IllusionistAbilities.manatap,
                                             CoercerAbilities.cannibalize_thoughts,
                                             TroubadorAbilities.reverberation,
                                             TroubadorAbilities.tap_essence,
                                             TroubadorAbilities.sandras_deafening_strike,
                                             ConjurorAbilities.sacrifice,
                                             DefilerAbilities.soul_cannibalize,
                                             DefilerAbilities.cannibalize,
                                             DefilerAbilities.maelstrom,
                                             ],
                                            delay=4.0,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    @_reusable_request
    def keep_interrupting(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Interrupt)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReadyEveryNSec(abilities=abilities,
                                            delay=1.0,
                                            resolver=self.__resolver_all_remote_automated,
                                            duration=RequestFactory.KEEP_REPEATING_DURATION)
        return request

    # not cached
    def keep_intercepting(self, target_name: str) -> Request:
        request = CastAnyWhenReady([FighterAbilities.intercept],
                                   resolver=self.__resolver_all.prototype(target=target_name, priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # ================================================ INDIVIDUAL / LOCAL =========================================
    @_reusable_request
    def prepare(self) -> Request:
        request = RecastWhenDurationExpired(LocalAbilities.prepare,
                                            resolver=self.__resolver_all_local,
                                            duration=30.0)
        return request

    @_reusable_request
    def smart_monk_intercept(self) -> Request:
        request = InterceptRotation(abilities_to_rotate=[FighterAbilities.intercept],
                                    max_targets=4, exclude_self=True, max_hits=15, threshold=0,
                                    resolver=self.__resolver_all,
                                    duration=RequestFactory.LOCAL_PLAYER_REQUEST_DURATION,
                                    description='Monk Intercept rotation')
        request.allow_recasting()
        return request

    @_reusable_request
    def standard_monk_intercept(self) -> Request:
        request = TargetRotationRecast(ability_to_rotate=FighterAbilities.intercept,
                                       targets=['g2', 'g3', 'g4', 'g5', 'g6'],
                                       resolver=self.__resolver_all,
                                       duration=RequestFactory.LOCAL_PLAYER_REQUEST_DURATION)
        return request

    @_reusable_request
    def local_monk_player_combat(self) -> Request:
        duration = RequestFactory.LOCAL_PLAYER_REQUEST_DURATION
        interrupts = DynamicRequestProxy(description='Opt Challenge', duration=duration)
        interrupts.set_request(CastAnyWhenReady([MonkAbilities.challenge], resolver=self.__resolver_all_local, duration=duration))
        interrupts.set_condition(MutableFlags.ENABLE_SPAM_INTERRUPT.__bool__)
        smart_combination = DynamicRequestProxy(description='Smart Combination', duration=duration)
        smart_combination.set_request(CombinationClosure(duration=duration))
        smart_combination.set_condition(MutableFlags.ENABLE_SMART_COMBINATION.__bool__)
        smart_intercept = DynamicRequestProxy(description='Smart Intercept', duration=duration)
        smart_intercept.set_request(self.smart_monk_intercept())
        smart_intercept.set_condition(MutableFlags.ENABLE_SMART_INTERCEPT.__bool__)
        debuffs = DynamicRequestProxy(description='Smart Debuffs', duration=duration)
        debuffs.set_request(RecastWhenDurationExpired([BrawlerAbilities.mantis_star,
                                                       ],
                                                      resolver=self.__resolver_all_local,
                                                      duration=duration))
        debuffs.set_condition(self.__runtime.combatstate.combat_has_nameds)
        boneshattering = Boneshattering(duration=duration)
        combined = CompositeRequest(description='Monk main player', duration=duration,
                                    requests=[interrupts,
                                              smart_combination,
                                              smart_intercept,
                                              debuffs,
                                              boneshattering,
                                              ])
        return combined

    @_reusable_request
    def local_fury_player_combat(self) -> Request:
        # nothing here, yet
        combined = CompositeRequest(description='Fury main player', requests=[], duration=RequestFactory.LOCAL_PLAYER_REQUEST_DURATION)
        return combined

    @_reusable_request
    def local_paladin_player_combat(self) -> Request:
        duration = RequestFactory.LOCAL_PLAYER_REQUEST_DURATION
        interrupts = DynamicRequestProxy(description='Opt Judgment', duration=duration)
        interrupts.set_request(CastAnyWhenReady([PaladinAbilities.judgment], resolver=self.__resolver_all_local, duration=duration))
        interrupts.set_condition(MutableFlags.ENABLE_SPAM_INTERRUPT.__bool__)
        controls = DynamicRequestProxy(description='Opt Controls', duration=duration)
        controls.set_request(CastAnyWhenReady([PaladinAbilities.penitent_kick,
                                               PaladinAbilities.heroic_dash],
                                              resolver=self.__resolver_all_local, duration=duration))
        controls.set_condition(MutableFlags.ENABLE_SPAM_CONTROL.__bool__)
        combined = CompositeRequest(description='Paladin main player', requests=[interrupts,
                                                                                 controls],
                                    duration=RequestFactory.LOCAL_PLAYER_REQUEST_DURATION)
        return combined

    # not cached
    def monk_defense_rotation(self) -> Request:
        rotation = XOR([
            BrawlerAbilities.tag_team,
            MonkAbilities.bob_and_weave,
            MonkAbilities.tsunami,
            AND([
                XOR([
                    BrawlerAbilities.brawlers_tenacity,
                    MonkAbilities.provoking_stance,
                ]),
                OR([
                    BrawlerAbilities.stone_cold,
                    BrawlerAbilities.inner_focus,
                    MonkAbilities.mountain_stance,
                    MonkAbilities.body_like_mountain,
                ]),
            ]),
        ])
        request = RequestCombineLazyRecasting(combine=rotation,
                                              resolver=self.__resolver_all_local,
                                              duration=-1.0)
        return request

    # not cached
    def monk_buffed_dps_rotation(self) -> Request:
        buffs = ATLEAST(2, [
            EtherealistAbilities.ethereal_conduit,
            EtherealistAbilities.essence_of_magic,
            MonkAbilities.perfect_form,
        ])
        buffed_dps = ATLEAST(6, [
            BrawlerAbilities.devastation_fist,
            MonkAbilities.flying_scissors,
            EtherealistAbilities.mana_schism,
            EtherealistAbilities.levinbolt,
            EtherealistAbilities.focused_blast,
            EtherealistAbilities.cascading_force,
            EtherealistAbilities.compounding_force,
            EtherealistAbilities.implosion,
            EtherealistAbilities.etherflash,
            EtherealistAbilities.ethershadow_assassin,
        ])
        always_dps_request = CastAnyWhenReady([MonkAbilities.dragonfire,
                                               EtherealistAbilities.feedback_loop,
                                               BrawlerAbilities.combat_mastery
                                               ],
                                              resolver=self.__resolver_all_local,
                                              duration=-1.0)
        player = self.__runtime.playerstate.get_main_player()
        ability_filter = AbilityFilter().can_affect_target_player(player) if player else self.__resolver_all_local
        buffs_resolver = AbilityResolver().filtered(ability_filter)
        buffed_dps_request = RequestBuffsAndDps(buffs=buffs, buffs_resolver=buffs_resolver,
                                                dps=buffed_dps, dps_resolver=self.__resolver_all_local,
                                                duration=-1.0)
        request = CompositeRequest(description='monk dps',
                                   requests=[always_dps_request, buffed_dps_request],
                                   duration=-1.0)
        return request

    # ================================================ UTILITY =================================================
    @_reusable_request
    def dispel_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Dispel)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastBestAndExpire(abilities=abilities,
                                    resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                    duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def mage_dispel_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Dispel).casters_by_class(GameClasses.Mage)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastBestAndExpire(abilities,
                                    resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                    duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def priest_dispel_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Dispel).casters_by_class(GameClasses.Priest)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastBestAndExpire(abilities,
                                    resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                    duration=RequestFactory.EXTENDED_COMBAT_DURATION)
        return request

    @_reusable_request
    def stun_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Stun)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReady(abilities=abilities,
                                   resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def interrupt_now(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Interrupt)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastAnyWhenReady(abilities=abilities,
                                   resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    def interrupt_now_short(self) -> Request:
        flt = AbilityFilter().ability_special(AbilitySpecial.Interrupt)
        abilities = self.__runtime.ability_reg.find_abilities(flt)
        request = CastNAndExpire(abilities=abilities, n=2,
                                 resolver=self.__resolver_all_remote_automated.prototype(priority=AbilityPriority.MANUAL_REQUEST),
                                 duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    def intercept_now(self, target_name: str) -> Request:
        request = CastOneAndExpire([FighterAbilities.intercept],
                                   resolver=self.__resolver_all.prototype(target=target_name, priority=AbilityPriority.MANUAL_REQUEST),
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def summon_pets(self) -> Request:
        request = CastAllAndExpire([ShamanAbilities.summon_spirit_companion,
                                    WardenAbilities.tunares_chosen,
                                    ConjurorAbilities.earthen_avatar,
                                    IllusionistAbilities.personae_reflection,
                                    CoercerAbilities.possess_essence,
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=15.0)
        return request

    @_reusable_request
    def free_move(self) -> Request:
        request = NonOverlappingDurationByGroup([BardAbilities.quick_tempo,
                                                 BardAbilities.deadly_dance,
                                                 PriestAbilities.cloak_of_divinity,
                                                 ],
                                                resolver=self.__resolver_all_remote_automated,
                                                overlap=1.0,
                                                duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def timelord_now(self) -> Request:
        request = CastOneAndExpire(abilities=IllusionistAbilities.timelord.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def balanced_synergy_remote_players_now(self) -> Request:
        request = CastAnyWhenReady([FighterAbilities.balanced_synergy.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    MageAbilities.balanced_synergy.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    PriestAbilities.balanced_synergy.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    ScoutAbilities.balanced_synergy.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    ],
                                   resolver=AbilityResolver().filtered(AbilityFilter().casters_by_group(Groups.MAIN).remote_casters()),
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def balanced_synergy_all_players(self) -> Request:
        request = RecastWhenDurationExpired([FighterAbilities.balanced_synergy,
                                             MageAbilities.balanced_synergy,
                                             PriestAbilities.balanced_synergy,
                                             ScoutAbilities.balanced_synergy,
                                             ],
                                            resolver=AbilityResolver().filtered(AbilityFilter().casters_by_group(Groups.MAIN)),
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def strikes_of_consistency(self):
        request = CastAnyWhenReady([FighterAbilities.strike_of_consistency,
                                    ScoutAbilities.strike_of_consistency,
                                    MageAbilities.smite_of_consistency,
                                    PriestAbilities.smite_of_consistency,
                                    ],
                                   resolver=self.__resolver_all,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def bulwark(self) -> Request:
        request = CastOneAndExpire(abilities=FighterAbilities.bulwark_of_order,
                                   resolver=self.__resolver_all,
                                   duration=6.0)
        return request

    @_reusable_request
    def verdict_now(self) -> Request:
        request = CastAnyWhenReady([InquisitorAbilities.verdict.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    ThaumaturgistAbilities.tainted_mutation.boost_resolved(AbilityPriority.MANUAL_REQUEST),
                                    ],
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # noinspection PyMethodMayBeStatic
    def aggro_to(self, player: IPlayer) -> Request:
        request = CastAllAndExpire([DirgeAbilities.magnetic_note,
                                    TroubadorAbilities.abhorrent_verse,
                                    ],
                                   resolver=AbilityResolver().prototype(target=player),
                                   duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    @_reusable_request
    def tank_snap_now(self) -> Request:
        request = CastOneAndExpire([MonkAbilities.hidden_openings.boost_resolved(AbilityPriority.MANUAL_REQUEST, 4),
                                    BrawlerAbilities.sneering_assault.boost_resolved(AbilityPriority.MANUAL_REQUEST, 3),
                                    FighterAbilities.provocation.boost_resolved(AbilityPriority.MANUAL_REQUEST, 2),
                                    MonkAbilities.peel.boost_resolved(AbilityPriority.MANUAL_REQUEST, 1),
                                    FighterAbilities.rescue,
                                    ],
                                   resolver=self.__resolver_all,
                                   duration=3.0)
        return request

    @_reusable_request
    def stop_attack(self) -> Request:
        request = CastAllAndExpire(RemoteAbilities.stop_combat,
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=2.0)
        return request

    # noinspection PyMethodMayBeStatic
    def discover_zone(self, for_player: IPlayer) -> Request:
        request = CastAnyWhenReady(CommonerAbilities.who,
                                   resolver=AbilityResolver().filtered(AbilityFilter().caster_is(for_player)),
                                   duration=2.0)
        return request

    # not cached
    def follow_default_target(self, players: List[IPlayer]) -> Request:
        filtered_resolver = self.__resolver_all_remote_automated.filtered(AbilityFilter().caster_is_one_of(players))
        prototype_resolver = filtered_resolver.prototype(target_factory=lambda ability: self.__runtime.playerstate.get_follow_target(ability.player))
        request = CastAllAndExpire(abilities=RemoteAbilities.follow, resolver=prototype_resolver, duration=2.0)
        return request

    # only abilities are cached
    def set_targets(self, add_player: IPlayer, target_name: Optional[str], repeat_ratio: float, optional_targets: Optional[List[str]] = None) -> Request:
        ability_cache = self.__get_per_player_ability_cache(CommonerAbilities.set_target)
        base_ability = CommonerAbilities.set_target.resolve_for_player(add_player)
        if base_ability and target_name:
            if optional_targets:
                targets_str = ';'.join([target_name] + optional_targets)
                action = base_ability.get_action().prototype(target=targets_str)
                ability_cache[add_player] = base_ability.prototype(action=action, target=target_name)
            else:
                ability_cache[add_player] = base_ability.prototype(target=target_name)
        elif add_player in ability_cache:
            del ability_cache[add_player]
        request = CastAnyWhenReadyEveryNSec(abilities=ability_cache.values(),
                                            resolver=self.__resolver_all,
                                            delay=repeat_ratio,
                                            duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        request.set_description(description='players set targets')
        return request

    # cached manually
    def custom_ability(self, player: IPlayer, casting: float, reuse: float, recovery=1.0, duration=0.0,
                       ability_name: Optional[str] = None, ability_type: Optional[AbilityType] = None, priority=AbilityPriority.MANUAL_REQUEST,
                       action: Optional[IAction] = None, ability_crc: Optional[int] = None, item_id: Optional[int] = None,
                       min_state=PlayerStatus.Zoned, cannot_modify=False) -> IAbility:
        if action:
            custom_ability_name = f'ability with action {action}'
            custom_ability_type = AbilityType.ability
        elif ability_crc:
            custom_ability_name = f'ability_crc {ability_crc}'
            custom_ability_type = AbilityType.spells
        elif item_id:
            custom_ability_name = f'item_id {item_id}'
            custom_ability_type = AbilityType.item
        else:
            assert False, f'{player}, {ability_name}'
        if not ability_name:
            ability_name = custom_ability_name
        if not ability_type:
            ability_type = custom_ability_type
        ability_cache = self.__per_player_get_custom_ability_cache(ability_name)
        if player in ability_cache:
            return ability_cache[player]
        builder = AbilityBuilder(CommonerAbilities.abstract_ability)
        if action:
            builder.action(action)
        elif ability_crc:
            builder.modify_set('crc', ability_crc)
        elif item_id:
            builder.item_id(item_id)
            builder.modify_set('cannot_modify', True)
        if cannot_modify:
            builder.modify_set('cannot_modify', True)
        builder.census_data(casting=casting, reuse=reuse, recovery=recovery, duration=duration)
        builder.modify_set('name', ability_name)
        builder.modify_set('type', ability_type)
        builder.modify_set('ability_name', ability_name)
        builder.modify_set('ability_id', re.sub('[^a-zA-Z0-9]', '_', ability_name))
        builder.modify_set('priority', priority)
        builder.modify_set('cast_min_state', min_state)
        ability_factory = self.__runtime.custom_ability_factory
        abilities = builder.build_ability(player, builder_tools=self.__runtime, ability_factory=ability_factory)
        ability = abilities[0]
        ability_cache[player] = ability
        return ability

    # not cached
    def custom_ability_request(self, ability: IAbility) -> Request:
        return CastOneAndExpire(ability, resolver=self.__resolver_all, duration=RequestFactory.EXTENDED_COMBAT_DURATION)

    # not cached
    def powerpainforce_links(self, prefix: str, link_type: str, players: List[IPlayer]) -> Optional[Request]:
        assert link_type in LINK_ABILITY_ID
        item_name = f'{prefix} {link_type}'
        item_id = self.__runtime.census_cache.get_item_id(item_name)
        if not item_id:
            return None
        all_requests = []
        duration = 15.0
        for player in players:
            use_item_ability = self.custom_ability(player, ability_name=item_name, casting=4.0, reuse=20.0, recovery=2.0, item_id=item_id)
            use_item_ability.ext.log_severity = Severity.Low
            link_ability = self.custom_ability(player, ability_name=link_type, casting=4.0, reuse=10.0, recovery=1.0, duration=60 * 60.0,
                                               ability_crc=LINK_ABILITY_ID[link_type], cannot_modify=True)
            link_ability.ext.log_severity = Severity.Low
            request = CastStrictSequenceAndExpire([use_item_ability, link_ability], self.__resolver_all_remote_automated, duration)
            all_requests.append(request)
        return CompositeRequest(link_type, all_requests)

    # not cached
    def heroic_opportunity_starter(self, caster: Union[GameClass, IPlayer]) -> Request:
        class_to_ability = {
            GameClasses.Scout: ScoutAbilities.lucky_break,
            GameClasses.Fighter: FighterAbilities.fighting_chance,
            GameClasses.Mage: MageAbilities.arcane_augur,
            GameClasses.Priest: PriestAbilities.divine_providence,
        }
        if isinstance(caster, IPlayer):
            caster_class = caster.get_adventure_class().get_archetype()
        else:
            caster_class = caster
        assert caster_class in class_to_ability.keys(), caster_class
        abilities = class_to_ability[caster_class].boost_resolved(AbilityPriority.COMBO)
        if isinstance(caster, IPlayer):
            resolver = AbilityResolver().filtered(AbilityFilter().caster_is(caster))
        else:
            resolver = self.__resolver_all
        request = CastBestAndExpire(abilities, resolver, duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        return request

    # not cached
    def heroic_opportunity_solo_trigger(self, archetype: GameClass) -> Request:
        ho_icon = {
            GameClasses.Scout: HOIcon.Coin,
            GameClasses.Fighter: HOIcon.Sword,
            GameClasses.Mage: HOIcon.Lightning,
            GameClasses.Priest: HOIcon.Hammer,
        }[archetype]
        request = self.heroic_opportunity_advance(ho_icon, max_hits=2)
        return request

    # not cached
    def heroic_opportunity_advance(self, ho_icons: Union[HOIcon, List[HOIcon]], max_hits: int, ability_filter: Optional[TAbilityFilter] = None) -> Request:
        if isinstance(ho_icons, HOIcon):
            ho_icons = [ho_icons]
        all_requests = list()
        for ho_icon in ho_icons:
            flt = AbilityFilter().heroic_op(ho_icon).casters_by_group(Groups.MAIN).permitted_caster_state().not_maintained().local_allowed_for_HO()
            if ability_filter:
                flt = flt.op_and(ability_filter)
            abilities = self.__runtime.ability_reg.find_abilities(flt)
            boosted_abilities = [ability.prototype(priority=AbilityPriority.COMBO) for ability in abilities]
            request = HeroicOpportunityRequest(abilities=boosted_abilities,
                                               resolver=AbilityResolver(),
                                               max_hits=max_hits,
                                               ho_icon=ho_icon,
                                               duration=RequestFactory.HO_DURATION)
            all_requests.append(request)
        if len(all_requests) == 1:
            return all_requests[0]
        return CompositeRequest(f'HO: {ho_icons}', all_requests)

    # cached manually
    def cached_request(self, ability_locator: IAbilityLocator, players: List[IPlayer], duration: float,
                       request_type: Type[Request] = CastAllAndExpire) -> Request:
        request_cache = self.__get_per_player_request_cache(ability_locator, request_type)
        requests = list()
        for player in players:
            if player not in request_cache:
                abilities = ability_locator.resolve_for_player_default_all(player)
                request = request_type(abilities=abilities, resolver=self.__resolver_all, duration=duration)
                request_cache[player] = request
            request = request_cache[player]
            requests.append(request)
        return CompositeRequest(description=ability_locator.get_canonical_name(), requests=requests, duration=duration)

    # TODO if_none_then_all_zoned_remote ruins OOZC scripts; use list of players from PlayerSwitcher instead
    # convenience method
    def zoned_cast_one(self, ability_locator: IAbilityLocator, player: TOptionalPlayer, duration: float) -> Request:
        players = self.__runtime.playerselectors.if_none_then_all_zoned_remote(player).resolve_players()
        return self.cached_request(ability_locator=ability_locator, players=players, request_type=CastAllAndExpire, duration=duration)

    # not cached
    def custom_request(self, ability_locator: IAbilityLocator, players: Union[IPlayer, List[IPlayer]], duration: float,
                       target_name: Optional[str] = None, priority: Optional[AbilityPriority] = None,
                       request_type: Type[Request] = CastAllAndExpire) -> Request:
        if isinstance(players, IPlayer):
            players = [players]
        resolver = self.__resolver_all.filtered(AbilityFilter().caster_is_one_of(players)).prototype(target=target_name, priority=priority)
        request = request_type(abilities=ability_locator, resolver=resolver, duration=duration)
        request.set_description(description=f'cast {ability_locator} on {target_name}')
        return request

    # ================================================ ASCENSION COMBOS =================================================
    def __make_combo_request(self, combo: IAbilityLocator) -> Request:
        request = CastOneAndExpire(combo,
                                   resolver=self.__resolver_all_remote_automated,
                                   duration=RequestFactory.SHORT_COMBAT_DURATION)
        return request

    @_reusable_request
    def combo_implosion(self) -> Request:
        combo = GeomancerAbilities.terrestrial_coffin.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_levinbolt(self) -> Request:
        combo = GeomancerAbilities.granite_protector.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_manaschism(self) -> Request:
        combo = ElementalistAbilities.elemental_overlord.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_ethershadow(self) -> Request:
        combo = ElementalistAbilities.brittle_armor.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_etherflash(self) -> Request:
        combo = ThaumaturgistAbilities.virulent_outbreak.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_compounding_foce(self) -> Request:
        combo = EtherealistAbilities.compounding_force.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)

    @_reusable_request
    def combo_cascading(self) -> Request:
        combo = ThaumaturgistAbilities.revocation_of_life.boost_resolved(AbilityPriority.COMBO)
        return self.__make_combo_request(combo)
