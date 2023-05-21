import json
from json.encoder import JSONEncoder
from threading import RLock
from typing import Dict, Optional

from rka.components.cleanup import Closeable
from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.datafiles import saved_detriments_filename
from rka.eq2.master import IRuntime
from rka.eq2.master.game import is_unknown_zone, get_canonical_zone_name
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.requests.request_controller import RequestController
from rka.eq2.master.game.state import logger
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.master.parsing import CombatantType, IDPSParserHook
from rka.eq2.shared import Groups
from rka.eq2.shared.flags import MutableFlags


class DetrimInfo:
    class Encoder(JSONEncoder):
        def default(self, o):
            return o.__dict__

    @staticmethod
    def from_json(json_object):
        if 'curse' in json_object:
            return DetrimInfo(**json_object)
        return json_object

    def __init__(self, name: str, curse=False, autocure=True, mage_cure_only=False, priest_cure_only=False):
        self.name = name
        self.curse = curse
        self.autocure = autocure
        self.mage_cure_only = mage_cure_only
        self.priest_cure_only = priest_cure_only

    def __str__(self) -> str:
        return f'{"curse" if self.curse else "detriment"} {self.name}'

    def __hash__(self) -> int:
        return self.name.__hash__()

    def __eq__(self, other) -> bool:
        return self.name == other.name


class Autocure(IDPSParserHook):
    CURE_DETRIM_GLOBAL_PERIOD = 2.0
    CURE_CURSE_GLOBAL_PERIOD = 3.0
    GROUP_CURE_GLOBAL_PERIOD = 3.0
    CURE_CURSE_PLAYER_PERIOD = 10.0
    CURE_DETRIM_PLAYER_PERIOD = 3.0
    FORGET_DETRIM_PLAYER_TIME = 6.0

    def __init__(self, runtime: IRuntime, request_ctrl: RequestController):
        self.__runtime = runtime
        self.__request_ctrl = request_ctrl
        EventSystem.get_main_bus().subscribe(MasterEvents.NEW_DPS_PARSER(), self.__dps_parser_change)
        self.__last_cure_curse_global_time = 0.0
        self.__last_cure_global_time = 0.0
        self.__last_group_cure_time: Dict[Groups, float] = dict()
        self.__current_dps = self.__runtime.current_dps
        if self.__current_dps:
            self.__current_dps.install_parser_hook(self)

    def __notify(self, text: str):
        self.__runtime.overlay.log_event(text, Severity.Low)

    def __dps_parser_change(self, event: MasterEvents.NEW_DPS_PARSER):
        self.__current_dps = event.dps_parser
        self.__current_dps.install_parser_hook(self)

    def players_detrimented_in_last_time_by_group(self, now: float, period: float) -> Dict[Groups, int]:
        result = dict()
        players = self.__runtime.player_mgr.get_players(min_status=PlayerStatus.Logged)
        for player in players:
            player_grp_id = player.get_client_config_data().group_id
            players_last_time = player.aspects.last_detriment_time
            if now - players_last_time < period:
                count = result.get(player_grp_id, 0)
                result[player_grp_id] = count + 1
        return result

    def __handle_curse(self, _detrim_info: DetrimInfo, target_player: IPlayer, now: float):
        if now - self.__last_cure_curse_global_time < Autocure.CURE_CURSE_GLOBAL_PERIOD:
            return
        last_cure_curse_time = target_player.aspects.last_cure_curse_time
        if now - last_cure_curse_time < Autocure.CURE_CURSE_PLAYER_PERIOD:
            return
        target_player.aspects.last_cure_curse_time = now
        self.__notify(f'Autocure curse on {target_player}')
        self.__request_ctrl.request_cure_curse_target(target_player.get_player_name())

    def __handle_noncurse(self, detrim_info: DetrimInfo, target_player: IPlayer, now: float):
        if detrim_info.mage_cure_only:
            self.__notify(f'Autocure mage on {target_player}')
            self.__request_ctrl.request_mage_cure_target(target_player.get_player_name())
            return
        elif detrim_info.priest_cure_only:
            self.__notify(f'Autocure priest on {target_player}')
            self.__request_ctrl.request_priest_cure_target(target_player.get_player_name())
            return
        players_needing_cure_by_group = self.players_detrimented_in_last_time_by_group(now, 2.0)
        group_cure_used = False
        for group_id, player_count in players_needing_cure_by_group.items():
            since_last_cure = now - self.__last_group_cure_time.get(group_id, 0.0)
            if player_count > 1 and since_last_cure >= Autocure.GROUP_CURE_GLOBAL_PERIOD:
                self.__notify(f'Autocure group {group_id}')
                self.__last_group_cure_time[group_id] = now
                self.__request_ctrl.request_specific_group_cure_now(group_id)
                group_cure_used = True
        if group_cure_used:
            return
        last_detriment_time = target_player.aspects.last_detriment_time
        if now - last_detriment_time > Autocure.FORGET_DETRIM_PLAYER_TIME:
            # this will prevent from instant curing a detriment on a player, thus allowing group cures
            return
        if now - self.__last_cure_global_time < Autocure.CURE_DETRIM_GLOBAL_PERIOD:
            return
        last_cure_detriment_time = target_player.aspects.last_cure_detriment_time
        if now - last_cure_detriment_time < Autocure.CURE_DETRIM_PLAYER_PERIOD:
            return
        time_since_last_detriment_time = now - last_detriment_time
        self.__notify(f'Autocure on {target_player} after {time_since_last_detriment_time:1.1f}s')
        self.__last_cure_global_time = now
        target_player.aspects.last_cure_detriment_time = now
        self.__request_ctrl.request_cure_target(target_player.get_player_name())

    def __handle_detriment(self, target_name: str, ability_name: str, timestamp: float):
        target_player = self.__runtime.player_mgr.get_player_by_name(target_name)
        if not target_player:
            logger.warn(f'AUTOCURE: player not found {target_player}')
            return
        detrim_info = self.__runtime.detriments.get_detriment_info(target_player.get_zone(), ability_name)
        if not detrim_info:
            return
        if not detrim_info.autocure:
            return
        if MutableFlags.ENABLE_AUTOCURE:
            if detrim_info.curse:
                self.__handle_curse(detrim_info, target_player, timestamp)
            else:
                self.__handle_noncurse(detrim_info, target_player, timestamp)
        target_player.aspects.all_last_detriments_times[detrim_info.name] = timestamp
        target_player.aspects.last_detriment_time = timestamp

    def record_damage(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType, ability_name: str,
                      damage: int, damage_type: str, is_autoattack: bool, timestamp: float):
        if not CombatantType.is_npc(attacker_type) or not CombatantType.is_my_player(target_type):
            return
        if is_autoattack:
            return
        self.__handle_detriment(target_name, ability_name, timestamp)

    def record_drain(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                     ability_name: str, power_amount: int, drain_type: str, timestamp: float):
        if not CombatantType.is_npc(attacker_type) or not CombatantType.is_my_player(target_type):
            return
        self.__handle_detriment(target_name, ability_name, timestamp)


class Detriments(Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=False)
        self.__runtime = runtime
        self.__lock = RLock()
        self.__change_flags: Dict[str, bool] = dict()
        self.__known_effects: Dict[str, Dict[str, DetrimInfo]] = dict()
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__zone_changed)
        EventSystem.get_main_bus().subscribe(CombatParserEvents.DETRIMENT_RELIEVED(), self.__detriment_found)

    def get_detriment_info(self, zone_name: str, detriment_name: str) -> Optional[DetrimInfo]:
        if is_unknown_zone(zone_name):
            return None
        zone_name = get_canonical_zone_name(zone_name)
        with self.__lock:
            if zone_name not in self.__known_effects:
                return None
            detriment_name = detriment_name.lower()
            if detriment_name not in self.__known_effects[zone_name]:
                return None
            return self.__known_effects[zone_name][detriment_name]

    def __detriment_found(self, event: CombatParserEvents.DETRIMENT_RELIEVED):
        if not CombatantType.is_my_player(event.from_combatant_type):
            return
        player = self.__runtime.player_mgr.get_player_by_name(event.from_combatant)
        player_zone = player.get_zone()
        detrim_name = event.detriment_name
        if is_unknown_zone(player_zone):
            logger.info(f'Cannot add detriment {detrim_name}, unknown zone of {player}')
            return
        zone_name = get_canonical_zone_name(player_zone)
        with self.__lock:
            if zone_name not in self.__known_effects:
                self.__known_effects[zone_name] = dict()
                self.__change_flags[zone_name] = False
            if detrim_name in self.__known_effects[zone_name]:
                return
            logger.debug(f'Adding detriment {detrim_name} in {zone_name}')
            self.__known_effects[zone_name][detrim_name] = DetrimInfo(detrim_name, event.is_curse, True)
            self.__change_flags[zone_name] = True

    def __zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        with self.__lock:
            new_zone = event.to_zone
            current_zone = event.from_zone
            if not is_unknown_zone(current_zone):
                current_zone = get_canonical_zone_name(current_zone)
                if current_zone in self.__change_flags and self.__change_flags[current_zone]:
                    self.__store_detriments(current_zone)
                    self.__change_flags[current_zone] = False
            if is_unknown_zone(new_zone):
                return
            new_zone = get_canonical_zone_name(new_zone)
            if new_zone not in self.__change_flags:
                self.__load_detriments(new_zone)
                self.__change_flags[new_zone] = False

    def __load_detriments(self, canonical_zone_name: str):
        filename = saved_detriments_filename(canonical_zone_name)
        self.__known_effects[canonical_zone_name] = dict()
        try:
            with open(filename, 'r') as file:
                data = json.load(file, object_hook=DetrimInfo.from_json)
            if data is None:
                logger.error(f'loading detriments for {canonical_zone_name} returned None')
            else:
                self.__known_effects[canonical_zone_name] = data
        except FileNotFoundError:
            pass
        except IOError:
            logger.warn(f'Could not load detriments for {canonical_zone_name}')

    def __store_detriments(self, canonical_zone_name: str):
        filename = saved_detriments_filename(canonical_zone_name)
        try:
            with open(filename, 'w') as file:
                json.dump(self.__known_effects[canonical_zone_name], file, indent=2, cls=DetrimInfo.Encoder)
        except IOError:
            logger.warn(f'Could not save detriments for {canonical_zone_name}')

    def close(self):
        with self.__lock:
            for zone_name, changed in self.__change_flags.items():
                if changed:
                    self.__store_detriments(zone_name)
                    self.__change_flags[zone_name] = False
        super().close()
