import traceback
from typing import Optional, List

from rka.components.cleanup import Closeable
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.census import logger, CensusTopFields
from rka.eq2.master.game.census.census_bridge import ICensusBridge
from rka.eq2.master.game.gameclass import GameClass, GameClasses
from rka.eq2.master.game.interfaces import IPlayer
from rka.services.api.census import ICensus, CensusOperand, TCensusStruct, CensusCacheOpts
from rka.services.broker import ServiceBroker


class CensusBridge(Closeable, ICensusBridge):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__max_known_hp = None

    def close(self):
        census_service: ICensus = ServiceBroker.get_broker().get_service(ICensus)
        if isinstance(census_service, Closeable):
            census_service.close()
        Closeable.close(self)

    def get_item_id(self, item_name: str) -> Optional[int]:
        census_service: ICensus = ServiceBroker.get_broker().get_service(ICensus)
        qb = census_service.new_query_builder('item')
        qb.add_parameter('displayname_lower', item_name.lower(), CensusOperand.EQ)
        q = qb.build()
        census_value = None
        try:
            for result in q.run_query():
                census_value = result.get_object_id()
                break
        except Exception as e:
            traceback.print_exception(e)
            logger.warn(f'Failed to query census service: get_item_id({item_name}), with {e}')
            return None
        return census_value

    def get_player_census_data(self, server_name: str, player_name: str) -> Optional[TCensusStruct]:
        census_service: ICensus = ServiceBroker.get_broker().get_service(ICensus)
        qb = census_service.new_query_builder('character')
        qb.add_parameter('name.first_lower', player_name.lower(), CensusOperand.EQ)
        qb.add_parameter('locationdata.world', server_name, CensusOperand.EQ)
        q = qb.build()
        census_value = None
        try:
            for result in q.run_query():
                census_value = result.get_object_map()
                break
        except Exception as e:
            traceback.print_exception(e)
            logger.warn(f'Failed to query census service: get_player_census_data({server_name}, {player_name}), with "{e}"')
            return None
        return census_value

    def get_max_known_player_hitpoints(self) -> Optional[int]:
        if self.__max_known_hp:
            return self.__max_known_hp
        census_service: ICensus = ServiceBroker.get_broker().get_service(ICensus)
        qb = census_service.new_query_builder('character')
        qb.add_option(CensusCacheOpts.FROM_CACHE_ONLY.value, 'true')
        q = qb.build()
        max_hp = 0
        try:
            for result in q.run_query():
                census_player = result.get_object_map()
                hp = census_player['stats']['health']['max']
                max_hp = max(max_hp, hp)
        except Exception as e:
            traceback.print_exception(e)
            logger.warn(f'Failed to query census service: get_max_known_player_hitpoints(), with "{e}"')
            return None
        self.__max_known_hp = max_hp
        return self.__max_known_hp

    # noinspection PyMethodMayBeStatic
    def __get_ability_base_name(self, name: str) -> str:
        suffix = name.split(' ')[-1]
        suffix_is_roman_number = False
        roman_number_chars = 'IVX'
        for letter in suffix:
            if letter not in roman_number_chars:
                suffix_is_roman_number = False
                break
            suffix_is_roman_number = True
        if suffix_is_roman_number:
            return name[:-len(suffix) - 1]
        return name

    def __match_ability_names(self, census_name: str, requested_name: str) -> bool:
        base_census_name = self.__get_ability_base_name(census_name).lower()
        base_requested_name = self.__get_ability_base_name(requested_name).lower()
        return base_census_name == base_requested_name

    # noinspection PyMethodMayBeStatic
    def __match_ability_class(self, census_obj: TCensusStruct, gameclass: GameClass) -> bool:
        if CensusTopFields.classes.value not in census_obj:
            return True
        for gameclass in GameClasses.get_subclasses(gameclass):
            if gameclass.name.lower() in census_obj[CensusTopFields.classes.value]:
                return True
        for census_game_class_name_lower in census_obj[CensusTopFields.classes.value].keys():
            census_game_class = GameClasses.get_class_by_name_lower(census_game_class_name_lower)
            if gameclass.is_subclass_of(census_game_class):
                return True
        return False

    # noinspection PyMethodMayBeStatic
    def __fetch_ability_census_datas(self, abilityname_lower: str) -> Optional[List[TCensusStruct]]:
        census_service: ICensus = ServiceBroker.get_broker().get_service(ICensus)
        qb = census_service.new_query_builder('spell')
        qb.add_parameter(CensusTopFields.name_lower.value, abilityname_lower, CensusOperand.STARTS_WITH)
        qb.add_parameter(CensusTopFields.type.value, 'pcinnates', CensusOperand.NOT_EQ)
        q = qb.build()
        matching_census_abilities = []
        try:
            for result in q.run_query():
                census_value = result.get_object_map()
                matching_census_abilities.append(census_value)
        except Exception as e:
            traceback.print_exception(e)
            logger.warn(f'Failed to query census service: __fetch_ability_census_datas({abilityname_lower}), with "{e}"')
            return None
        # find abilities that really match the name - query only finds starts_with
        matching_census_abilities_by_name = [acd for acd in matching_census_abilities if
                                             self.__match_ability_names(acd[CensusTopFields.name.value], abilityname_lower)]
        return matching_census_abilities_by_name

    # noinspection PyMethodMayBeStatic
    def __is_requires_membership(self, all_ability_variants: List[TCensusStruct], selected_ability: TCensusStruct) -> bool:
        actual_ability_source = selected_ability['given_by']
        if actual_ability_source in ['tradeskillclass', 'alternateadvancement']:
            return False
        actual_ability_level = selected_ability['level']
        # find all other abilities at this level, to see what tiers it has
        census_abilities_at_level = [ca for ca in all_ability_variants if ca['level'] == actual_ability_level]
        # only reduce to non-member tier if the spell is a level-able profession ability
        required_tiers = {
            AbilityTier.Apprentice: False,
            AbilityTier.Journeyman: False,
            AbilityTier.Adept: False,
            AbilityTier.Expert: False,
            AbilityTier.Master: False,
            AbilityTier.Grandmaster: False,
        }
        for ability in census_abilities_at_level:
            ability_tier_int = ability['tier']
            ability_tier = AbilityTier(ability_tier_int)
            if ability_tier in required_tiers:
                required_tiers[ability_tier] = True
        if all(required_tiers.values()):
            return True
        return False

    def get_ability_census_data_by_tier(self, gameclass: GameClass, player_level: int,
                                        abilityname_lower: str, ability_tier: AbilityTier) -> Optional[TCensusStruct]:
        abilityname_lower = self.__get_ability_base_name(abilityname_lower)
        matching_census_abilities = self.__fetch_ability_census_datas(abilityname_lower)
        if matching_census_abilities is None:
            # error already reported
            return None
        # and check if the is class attribute to match
        matching_census_abilities_by_class = [acd for acd in matching_census_abilities if self.__match_ability_class(acd, gameclass)]
        if not matching_census_abilities_by_class:
            logger.warn(f'Ability {abilityname_lower} ({gameclass}), not found in census')
            return None
        logger.debug(f'Total number of qualifying abilities for {abilityname_lower} is {len(matching_census_abilities_by_class)}')
        # find abilities as close to player_level as possible
        abilities_below_player_level = [ability for ability in matching_census_abilities_by_class if ability[CensusTopFields.level.value] <= player_level]
        highest_ability_level = max(abilities_below_player_level, key=lambda census_data: census_data[CensusTopFields.level.value])[CensusTopFields.level.value]
        abilities_for_highest_level = [ability for ability in abilities_below_player_level if ability[CensusTopFields.level.value] == highest_ability_level]
        if not abilities_for_highest_level:
            logger.warn(f'Ability {abilityname_lower} ({gameclass}), not available for player level {player_level}')
            return None
        # match to the tier requested
        if ability_tier == AbilityTier.UnknownLowest:
            ability_tier_int = min(abilities_for_highest_level, key=lambda acd: acd[CensusTopFields.tier.value])[CensusTopFields.tier.value]
        elif ability_tier == AbilityTier.UnknownHighest:
            ability_tier_int = max(abilities_for_highest_level, key=lambda acd: acd[CensusTopFields.tier.value])[CensusTopFields.tier.value]
        else:
            assert not ability_tier.is_wildcard(), f'Unsupported tier {ability_tier}'
            ability_tier_int = ability_tier.value if isinstance(ability_tier, AbilityTier) else int(ability_tier)
        ability_for_tier = None
        for ability in abilities_for_highest_level:
            if ability[CensusTopFields.tier.value] == ability_tier_int:
                ability_for_tier = ability
                break
        # check results
        if not ability_for_tier:
            logger.warn(f'Failed to find ability {abilityname_lower} ({gameclass}) at tier {ability_tier_int}')
            return None
        return ability_for_tier

    def get_ability_census_data_for_player(self, player: IPlayer, gameclass: GameClass, abilityname_lower: str) -> Optional[TCensusStruct]:
        server_name = player.get_server().servername
        player_name = player.get_player_name()
        player_census = self.get_player_census_data(server_name=server_name, player_name=player_name)
        if not player_census:
            logger.warn(f'No census data for player {player}')
            return None
        abilityname_lower = self.__get_ability_base_name(abilityname_lower)
        census_abilities = self.__fetch_ability_census_datas(abilityname_lower)
        if census_abilities is None:
            # error already reported
            return None
        player_ability_ids = set(player_census['spell_list'])
        # find abilities that the player actually has
        players_census_abilities = [ca for ca in census_abilities if ca['id'] in player_ability_ids]
        if not players_census_abilities:
            logger.info(f'Player {player} has no ability {abilityname_lower}')
            return None
        # find max level, max tier ability
        players_best_census_ability = max(players_census_abilities, key=lambda ca: ca['level'] * 100 + ca['tier'])
        actual_ability_crc = players_best_census_ability['crc']
        actual_ability_level = players_best_census_ability['level']
        actual_ability_tier_int = players_best_census_ability['tier']
        if self.__is_requires_membership(census_abilities, players_best_census_ability) \
                and not player.get_player_info().membership \
                and actual_ability_tier_int > AbilityTier.Master.value:
            logger.debug(f'Degrading ability tier for {abilityname_lower} of {player} from {AbilityTier(actual_ability_tier_int).name} to Master')
            actual_ability_tier_int = min(actual_ability_tier_int, AbilityTier.Master.value)
        # find the ability matching the CRC and effective tier
        effective_census_abilities = [ca for ca in census_abilities if ca['crc'] == actual_ability_crc
                                      and ca['level'] == actual_ability_level
                                      and ca['tier'] == actual_ability_tier_int]
        if len(effective_census_abilities) != 1:
            logger.error(f'Failed to find ability {abilityname_lower} for {player}; {len(effective_census_abilities)}, {effective_census_abilities}')
            return None
        return effective_census_abilities[0]
