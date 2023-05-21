import json
from json import JSONDecodeError
from threading import RLock
from typing import Dict, List, Set, Optional

from rka.components.cleanup import Closeable
from rka.eq2.datafiles import ability_saved_shared_data_filepath
from rka.eq2.master.game.ability import logger
from rka.eq2.master.game.ability.ability_data import AbilitySharedVars
from rka.eq2.master.game.interfaces import IAbility, IAbilityLocator, IAbilityRegistry, IPlayer, TAbilityFilter


class AbilityRegistry(IAbilityRegistry, Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__lock = RLock()
        self.__shared_vars_registry: Dict[str, AbilitySharedVars] = dict()
        self.__shared_vars_db_filepath = ability_saved_shared_data_filepath()
        self.__ability_names: Dict[str, IAbilityLocator] = dict()
        self.__ability_registry: Dict[str, List[IAbility]] = dict()
        self.__ability_effect_names: Dict[str, str] = dict()
        self.__restore_ability_data()
        # quick access for certain conditions
        self.__indexed_expire_on_attack: Dict[IPlayer, List[IAbility]] = dict()
        self.__indexed_expire_on_move: Dict[IPlayer, List[IAbility]] = dict()
        self.__indexed_maps_by_player_name: Dict[str, Dict[str, IAbility]] = dict()

    def __store_ability_data(self):
        try:
            with open(fr'{self.__shared_vars_db_filepath}', 'w') as file:
                with self.__lock:
                    json.dump(self.__shared_vars_registry, file, cls=AbilitySharedVars.SharedVarsJSONEncoder, indent=4)
        except IOError as e:
            logger.error(f'error {e} saving to file {self.__shared_vars_db_filepath}')

    def __restore_ability_data(self):
        try:
            with open(fr'{self.__shared_vars_db_filepath}', 'r') as file:
                shared_vars_registry_dict = json.load(file)
        except IOError as e:
            print(f'error {e} loading from {self.__shared_vars_db_filepath}')
            return
        except JSONDecodeError as e:
            print(f'error {e} loading from {self.__shared_vars_db_filepath}')
            return
        for ability_key, shared_vars_dict in shared_vars_registry_dict.items():
            shared_vars = AbilitySharedVars()
            shared_vars.set_shared_vars(shared_vars_dict)
            self.__shared_vars_registry[ability_key] = shared_vars

    def find_abilities(self, condition: TAbilityFilter) -> List[IAbility]:
        result = []
        with self.__lock:
            for variants in self.__ability_registry.values():
                for ability in variants:
                    if condition(ability):
                        result.append(ability)
        return result

    def find_first_ability(self, condition: TAbilityFilter) -> Optional[IAbility]:
        with self.__lock:
            for variants in self.__ability_registry.values():
                for ability in variants:
                    if condition(ability):
                        return ability
        return None

    def find_ability_map_for_player_name(self, player_name: str) -> Dict[str, IAbility]:
        with self.__lock:
            if player_name in self.__indexed_maps_by_player_name:
                return self.__indexed_maps_by_player_name[player_name]
            return dict()

    def find_abilities_expire_on_attack(self, player: IPlayer) -> List[IAbility]:
        with self.__lock:
            if player in self.__indexed_expire_on_attack:
                return self.__indexed_expire_on_attack[player]
            return []

    def find_abilities_expire_on_move(self, player: IPlayer) -> List[IAbility]:
        with self.__lock:
            if player in self.__indexed_expire_on_move:
                return self.__indexed_expire_on_move[player]
            return []

    def get_all_ability_names(self) -> Set[str]:
        with self.__lock:
            return {variants[0].ext.ability_name for variants in self.__ability_registry.values() if variants}

    def register_ability(self, ability: IAbility):
        logger.debug(f'registering ability {ability}')
        ability_unique_key = ability.ability_unique_key()
        ability_shared_key = ability.ability_shared_key()
        with self.__lock:
            assert ability_shared_key in self.__shared_vars_registry.keys(), ability
            assert self.__shared_vars_registry[ability_shared_key] is not None, ability
            assert ability.shared is not None, ability
            if ability_unique_key not in self.__ability_registry.keys():
                # one-time registrations
                effect_name_lower = ability.ext.effect_name.lower()
                self.__ability_effect_names[effect_name_lower] = ability.ext.ability_name
                name_lower = ability.ext.ability_name.lower()
                self.__ability_names[name_lower] = ability.locator
            else:
                variants = self.__ability_registry[ability_unique_key]
                for variant in variants:
                    if variant.ability_variant_key() == ability.ability_variant_key():
                        assert False, f'ability already in registry {ability}'
            # add to variants
            self.__ability_registry.setdefault(ability_unique_key, list()).append(ability)
            # special indexes
            if ability.ext.expire_on_move:
                self.__indexed_expire_on_move.setdefault(ability.player, list()).append(ability)
            if ability.ext.expire_on_attack:
                self.__indexed_expire_on_attack.setdefault(ability.player, list()).append(ability)
            self.__indexed_maps_by_player_name.setdefault(ability.player.get_player_name(), dict())[ability.locator.get_canonical_name()] = ability

    def get_ability_shared_vars(self, player_id: str, ability_shared_name: str):
        key = IAbility.make_ability_shared_key(player_id, ability_shared_name)
        with self.__lock:
            if key not in self.__shared_vars_registry.keys():
                self.__shared_vars_registry[key] = AbilitySharedVars()
            return self.__shared_vars_registry[key]

    def get_ability_name_by_effect_name(self, effect_name_lower: str) -> Optional[str]:
        with self.__lock:
            assert effect_name_lower.islower(), effect_name_lower
            if effect_name_lower in self.__ability_effect_names.keys():
                return self.__ability_effect_names[effect_name_lower]
        return None

    def get_ability_locator_by_name(self, ability_name_lower: str) -> Optional[IAbilityLocator]:
        with self.__lock:
            assert ability_name_lower.islower(), ability_name_lower
            if ability_name_lower in self.__ability_names.keys():
                return self.__ability_names[ability_name_lower]
        return None

    def close(self):
        self.__store_ability_data()
        Closeable.close(self)
        AbilityRegistry.__instance = None
