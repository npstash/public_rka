import time
from threading import RLock
from typing import Set, Dict, List, Any, Optional

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.state import logger
from rka.eq2.master.parsing import CombatantType
from rka.eq2.parsing.parsing_util import EmoteInformation, EmoteParser
from rka.eq2.shared import Groups


class ZoneState:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__lock = RLock()
        self.__zone_emotes_min_wildcard: Dict[str, EmoteInformation] = dict()
        self.__zone_emotes_max_wildcard: Dict[str, EmoteInformation] = dict()
        self.__zone_killed_enemies: Set[str] = set()
        self.__zone_items_looted: Set[str] = set()
        self.__zone_player_tells: Set[ChatEvents.PLAYER_TELL] = set()
        self.__player_names_in_zone: Set[str] = set()
        self.__player_names_in_raid_timestamp = time.time()
        self.__player_names_in_raid: List[str] = list()
        self.__cached_raid_variables: Dict[str, Any] = dict()
        self.__player_names_in_main_group: Set[str] = set()
        EventSystem.get_main_bus().subscribe(CombatEvents.ENEMY_KILL(), self.__killed_enemy)
        EventSystem.get_main_bus().subscribe(ChatEvents.PLAYER_TELL(), self.__player_tell)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.ITEM_RECEIVED(), self.__item_found)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__player_changed_zone)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_JOINED_GROUP(), self.__player_joined_main_group)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_LEFT_GROUP(), self.__player_left_main_group)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_GROUP_DISBANDED(), self.__main_group_disbanded)

    def __clear_saved_zone_data(self):
        with self.__lock:
            self.__zone_emotes_min_wildcard.clear()
            self.__zone_emotes_max_wildcard.clear()
            self.__zone_killed_enemies.clear()
            self.__zone_items_looted.clear()
            self.__zone_player_tells.clear()
            self.__player_names_in_zone.clear()
            self.__player_names_in_raid.clear()
            self.__player_names_in_main_group.clear()

    def __player_changed_zone(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        add_to_zone = False
        if event.player.is_main_player():
            self.__clear_saved_zone_data()
            add_to_zone = True
        else:
            main_player_zone = self.__runtime.playerstate.get_main_player_zone()
            main_player_server = self.__runtime.playerstate.get_main_server()
            if event.player.get_zone() == main_player_zone and event.player.get_server() == main_player_server:
                add_to_zone = True
        if add_to_zone:
            self.add_player_in_zone(event.player.get_player_name())

    # ============ ZONE member tracking ==============
    def add_player_in_zone(self, player_name: str):
        with self.__lock:
            self.__player_names_in_zone.add(player_name)

    def get_players_in_zone(self) -> List[str]:
        with self.__lock:
            player_names = list(self.__player_names_in_zone)
        return player_names

    def is_player_in_zone(self, player_name: str) -> bool:
        with self.__lock:
            return player_name in self.__player_names_in_zone

    # ============ GROUP member tracking ==============
    def __add_main_group_player(self, player_name: str):
        with self.__lock:
            already_in_group = player_name in self.__player_names_in_main_group
            logger.info(f'__add_main_group_player: {player_name}, already in grp={already_in_group}')
            if not already_in_group:
                self.__runtime.overlay.log_event(f'Adding to main grp: {player_name}', Severity.Low)
                self.__player_names_in_main_group.add(player_name)
                player = self.__runtime.player_mgr.get_player_by_name(player_name)
                main_player = self.__runtime.playerstate.get_main_player()
                if player and main_player:
                    main_player_grp = main_player.get_client_config_data().group_id
                    if player.get_client_config_data().join_to_group(main_player_grp):
                        # need to clear this cache, it relies on group setups
                        self.__runtime.request_factory.clear_cache()
        self.add_player_in_zone(player_name)

    def __remove_main_group_player(self, player_name: str):
        with self.__lock:
            self.__runtime.overlay.log_event(f'Removing from main grp: {player_name}', Severity.Low)
            if player_name in self.__player_names_in_main_group:
                self.__player_names_in_main_group.remove(player_name)
                player = self.__runtime.player_mgr.get_player_by_name(player_name)
                if player:
                    if player.get_client_config_data().restore_group():
                        self.__runtime.request_factory.clear_cache()

    def __clear_main_group_players(self):
        with self.__lock:
            self.__runtime.overlay.log_event('Clearing main grp', Severity.Low)
            for player_name in self.__player_names_in_main_group:
                player = self.__runtime.player_mgr.get_player_by_name(player_name)
                if player:
                    if player.get_client_config_data().restore_group():
                        self.__runtime.request_factory.clear_cache()
            self.__player_names_in_main_group.clear()

    def __player_joined_main_group(self, event: PlayerInfoEvents.PLAYER_JOINED_GROUP):
        if event.my_player and event.player.is_local():
            self.__clear_main_group_players()
            self.__clear_cached_raid_info()
        self.__add_main_group_player(event.player_name)

    def __player_left_main_group(self, event: PlayerInfoEvents.PLAYER_LEFT_GROUP):
        if event.my_player and event.player.is_local():
            self.__clear_main_group_players()
            self.__clear_cached_raid_info()
            return
        self.__remove_main_group_player(event.player_name)

    def __main_group_disbanded(self, _event: PlayerInfoEvents.PLAYER_GROUP_DISBANDED):
        self.__clear_main_group_players()

    def player_found_in_main_group_with_who(self, player_name: str):
        self.__add_main_group_player(player_name)

    def get_players_in_main_group(self) -> List[str]:
        with self.__lock:
            return list(self.__player_names_in_main_group)

    def is_player_in_main_group(self, player_name: str) -> bool:
        if not player_name:
            return False
        with self.__lock:
            if player_name in self.__player_names_in_main_group:
                return True
        player = self.__runtime.player_mgr.get_player_by_name(player_name)
        if not player:
            return False
        return bool(player.get_client_config_data().group_id & Groups.MAIN)

    # ============ RAID member tracking ==============
    def __clear_cached_raid_info(self):
        self.__runtime.overlay.log_event('Clearing cached raid info', Severity.Low)
        self.__player_names_in_raid.clear()
        self.__cached_raid_variables.clear()

    def player_found_in_raid_with_who(self, player_name: str):
        with self.__lock:
            now = time.time()
            if now - self.__player_names_in_raid_timestamp > 2.0:
                self.__runtime.overlay.log_event('Updating raid members', Severity.Low)
                self.__clear_cached_raid_info()
            if player_name not in self.__player_names_in_raid:
                logger.info(f'{player_name} joined raid')
                self.__player_names_in_raid.append(player_name)
                self.__player_names_in_raid_timestamp = now

    def get_players_in_raid(self) -> List[str]:
        with self.__lock:
            return list(self.__player_names_in_raid)

    def cache_raidsetup_variable(self, title: str, variable: Any):
        with self.__lock:
            self.__cached_raid_variables[title] = variable

    def get_cached_raidsetup_variable(self, title: str) -> Optional[Any]:
        with self.__lock:
            if title not in self.__cached_raid_variables:
                return None
            return self.__cached_raid_variables[title]

    # ============ EMOTE tracking ==============
    def add_emote(self, player: IPlayer, emote: str):
        logger.debug(f'Adding emote {emote}')
        min_wildcarding = self.__get_min_wildcarded_emote(emote)
        max_wildcarding = self.__get_max_wildcarded_emote(emote)
        readable = min_wildcarding.readable
        logger.detail(f'Emote readable form: {readable}')
        logger.detail(f'Emote min wildcarding: {min_wildcarding.wildcarded}')
        logger.detail(f'Emote max wildcarding: {max_wildcarding.wildcarded}')
        with self.__lock:
            self.__zone_emotes_min_wildcard[readable] = min_wildcarding
            self.__zone_emotes_max_wildcard[readable] = max_wildcarding
        EventSystem.get_main_bus().post(ChatEvents.EMOTE(player=player, emote=emote, min_wildcarding=min_wildcarding.wildcarded,
                                                         max_wildcarding=max_wildcarding.wildcarded, to_local=player.is_local()))

    def __get_min_wildcarded_emote(self, emote: str) -> EmoteInformation:
        player_combatant_names = self.__runtime.current_dps.get_combatant_names(lambda combatant: CombatantType.is_player(combatant.get_combatant_type()))
        player_combatant_names = sorted(player_combatant_names, key=str.__len__, reverse=True)
        emote_parser = EmoteParser(emote)
        while emote_parser.emote_idx < len(emote):
            if emote_parser.replace_player_combatants(player_combatant_names):
                continue
            if emote_parser.replace_color():
                continue
            if emote_parser.replace_numbers():
                continue
            if emote_parser.replace_other():
                continue
            # nothing to replace; just escape any character
            emote_parser.escape_next_character()
        return emote_parser.finish()

    def __get_max_wildcarded_emote(self, emote: str) -> EmoteInformation:
        logger.debug(f'Processing emote {emote}')
        emote_parser = EmoteParser(emote)
        player_combatant_names = self.__runtime.current_dps.get_combatant_names(lambda combatant: CombatantType.is_player(combatant.get_combatant_type()))
        player_combatant_names = sorted(player_combatant_names, key=str.__len__, reverse=True)
        npc_combatant_names = self.__runtime.current_dps.get_combatant_names(lambda combatant: CombatantType.is_npc(combatant.get_combatant_type()))
        npc_combatant_names = sorted(npc_combatant_names, key=str.__len__, reverse=True)
        while emote_parser.emote_idx < len(emote):
            if emote_parser.replace_player_combatants(player_combatant_names):
                continue
            if emote_parser.replace_npc_combatants(npc_combatant_names):
                continue
            if emote_parser.replace_pronouns():
                continue
            if emote_parser.replace_color():
                continue
            if emote_parser.replace_numbers():
                continue
            if emote_parser.replace_other():
                continue
            # nothing to replace; just escape any character
            emote_parser.escape_next_character()
        return emote_parser.finish()

    def get_emotes_min_wildcarding(self) -> Dict[str, EmoteInformation]:
        with self.__lock:
            return self.__zone_emotes_min_wildcard.copy()

    def get_emotes_max_wildcarding(self) -> Dict[str, EmoteInformation]:
        with self.__lock:
            return self.__zone_emotes_max_wildcard.copy()

    # ============ KILLS/ITEMS/TELLS tracking ==============
    def __killed_enemy(self, event: CombatEvents.ENEMY_KILL):
        with self.__lock:
            self.__zone_killed_enemies.add(event.enemy_name)

    def get_killed_enemies(self) -> Set[str]:
        with self.__lock:
            return self.__zone_killed_enemies.copy()

    def __item_found(self, event: PlayerInfoEvents.ITEM_RECEIVED):
        with self.__lock:
            self.__zone_items_looted.add(event.item_name)

    def get_items_looted(self) -> Set[str]:
        with self.__lock:
            return self.__zone_items_looted.copy()

    def __player_tell(self, event: ChatEvents.PLAYER_TELL):
        with self.__lock:
            self.__zone_player_tells.add(event)

    def get_player_tells(self) -> Set[ChatEvents.PLAYER_TELL]:
        with self.__lock:
            return self.__zone_player_tells.copy()
