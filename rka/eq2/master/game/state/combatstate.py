import datetime
import time
from threading import RLock
from typing import List, Optional, Dict, Set, Union

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityEffectTarget
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.events.requesting import RequestEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.combat.combat_script_mgr import CombatScriptManager
from rka.eq2.master.game.state import logger
from rka.eq2.master.parsing import CombatantType
from rka.eq2.master.ui import PermanentUIEvents
from rka.eq2.parsing.parsing_util import ParsingHelpers


class CombatState:
    DEFAULT_TARGET_REFRESH_RATE = 5.0

    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__lock = RLock()
        self.__dps_flag = False
        self.__request_combat_flag = False
        self.__combat_flag = False
        self.__named_participants = set()
        self.__player_target_names: Dict[IPlayer, str] = dict()
        self.__optional_targets: Dict[IPlayer, List[str]] = dict()
        self.__targeting_locked: Set[IPlayer] = set()
        self.__bus = EventSystem.get_main_bus()
        self.__bus.subscribe(CombatParserEvents.DPS_PARSE_START(), self.__dps_start)
        self.__bus.subscribe(CombatParserEvents.DPS_PARSE_TICK(), self.__dps_fix_start)
        self.__bus.subscribe(CombatParserEvents.DPS_PARSE_END(), self.__dps_end)
        self.__bus.subscribe(CombatParserEvents.COMBATANT_CONFIRMED(combatant_type=CombatantType.NPC), self.__combatant_joined)
        self.__bus.subscribe(CombatEvents.ENEMY_KILL(), self.__unlock_current_target)
        self.__bus.subscribe(RequestEvents.COMBAT_REQUESTS_START(main_controller=True), self.__combat_requests_start)
        self.__bus.subscribe(RequestEvents.COMBAT_REQUESTS_END(main_controller=True), self.__combat_requests_end)
        self.__bus.subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__zone_changed)
        self.__bus.subscribe(ObjectStateEvents.COMBAT_STATE_END(), self.__combat_ended)
        self.combat_script_manager = CombatScriptManager(self.__runtime)

    def __zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        self.clear_player_targets(players=[event.player])

    def __combat_ended(self, _event: ObjectStateEvents.COMBAT_STATE_END):
        self.clear_player_targets(players=self.__runtime.playerselectors.all_zoned().resolve_players())

    def __combat_started(self):
        self.__combat_flag = True
        self.__bus.post(ObjectStateEvents.COMBAT_STATE_START())

    def __combat_stopped(self):
        self.__combat_flag = False
        self.__named_participants.clear()
        self.__bus.post(ObjectStateEvents.COMBAT_STATE_END())
        now_ts = time.time()
        now_dt = datetime.datetime.fromtimestamp(now_ts)
        for ability in self.__runtime.ability_reg.find_abilities(lambda a: a.player.get_status() >= PlayerStatus.Zoned):
            if ability.ext.effect_target != AbilityEffectTarget.Enemy and ability.ext.effect_target != AbilityEffectTarget.Encounter:
                continue
            ability.expire_duration(now_dt)

    def __check_flags(self):
        if self.__dps_flag and self.__request_combat_flag:
            self.__combat_started()
        elif not self.__dps_flag and not self.__request_combat_flag:
            self.__combat_stopped()

    def __combat_requests_start(self, _event: RequestEvents.COMBAT_REQUESTS_START):
        self.__request_combat_flag = True
        self.__check_flags()

    def __combat_requests_end(self, _event: RequestEvents.COMBAT_REQUESTS_END):
        self.__request_combat_flag = False
        self.__check_flags()

    def __dps_start(self, _event: CombatParserEvents.DPS_PARSE_START):
        self.__dps_flag = True
        self.__check_flags()

    def __dps_fix_start(self, _event: CombatParserEvents.DPS_PARSE_TICK):
        # in case DPS_PARSE_START is called before listener its subscribed
        self.__bus.unsubscribe_all(CombatParserEvents.DPS_PARSE_TICK, self.__dps_fix_start)
        self.__dps_flag = True
        self.__check_flags()

    def __dps_end(self, _event: CombatParserEvents.DPS_PARSE_END):
        self.__dps_flag = False
        self.__check_flags()

    def __combatant_joined(self, event: CombatParserEvents.COMBATANT_CONFIRMED):
        if not ParsingHelpers.is_boss(event.combatant_name):
            return
        self.__named_participants.add(event.combatant_name)

    def is_combat(self) -> bool:
        return self.__combat_flag

    def combat_has_nameds(self) -> bool:
        if not self.is_combat():
            return False
        if not self.__named_participants:
            return False
        return True

    def get_nameds(self) -> List[str]:
        return list(self.__named_participants)

    def is_requested_combat(self) -> bool:
        return self.__request_combat_flag

    def is_game_combat(self) -> bool:
        return self.__dps_flag

    def add_optional_players_target(self, players: Union[IPlayer, List[IPlayer]], opt_target_name: str, repeat_rate: Optional[float] = None):
        if repeat_rate is None:
            repeat_rate = CombatState.DEFAULT_TARGET_REFRESH_RATE
        if isinstance(players, IPlayer):
            players = [players]
        players_str = [p.get_player_name() for p in players]
        if players:
            self.__runtime.overlay.log_event(f'Opt target for {players_str} is {opt_target_name}', severity=Severity.Low)
        for player in players:
            if player not in self.__optional_targets:
                self.__optional_targets[player] = list()
            opt_target_names = self.__optional_targets[player]
            if opt_target_name in opt_target_names:
                continue
            opt_target_names.append(opt_target_name)
            # possibly the primary target was not set yet, in which case dont send the event yet - will be sent later when primart target is set
            if player not in self.__player_target_names:
                continue
            target_name = self.__player_target_names[player]
            EventSystem.get_main_bus().post(RequestEvents.REQUEST_PLAYER_SET_TARGET(player=player, target_name=target_name,
                                                                                    optional_targets=list(opt_target_names),
                                                                                    refresh_rate=repeat_rate))

    def set_players_target(self, players: Union[IPlayer, List[IPlayer]], target_name: Optional[str], lock_target=False, repeat_rate: Optional[float] = None):
        if repeat_rate is None:
            repeat_rate = CombatState.DEFAULT_TARGET_REFRESH_RATE
        one_player = False
        if isinstance(players, IPlayer):
            one_player = True
            players = [players]
        players_str = [p.get_player_name() for p in players]
        if players:
            self.__runtime.overlay.log_event(f'Target for {players_str} is {target_name}', severity=Severity.Low)
            if not one_player:
                self.__runtime.overlay.log_event(f'Recent target: {target_name}', severity=Severity.Critical, event_id=PermanentUIEvents.TARGET.str())
        for player in players:
            if player in self.__targeting_locked:
                continue
            player_target_name = target_name
            if not player_target_name:
                player_target_name = self.__runtime.playerstate.get_default_target(player)
            if player not in self.__player_target_names and not player_target_name:
                # nothing to do
                continue
            if player in self.__player_target_names and not player_target_name:
                # notify that target was removed
                EventSystem.get_main_bus().post(RequestEvents.REQUEST_PLAYER_SET_TARGET(player=player,
                                                                                        target_name=None,
                                                                                        optional_targets=None,
                                                                                        refresh_rate=repeat_rate))
                # remove cached target value
                del self.__player_target_names[player]
                continue
            if player in self.__player_target_names and self.__player_target_names[player] == player_target_name:
                # nothing has changed
                continue
            self.__player_target_names[player] = player_target_name
            if lock_target:
                self.lock_current_target(player)
            opt_target_names = list(self.__optional_targets[player]) if player in self.__optional_targets else []
            EventSystem.get_main_bus().post(RequestEvents.REQUEST_PLAYER_SET_TARGET(player=player,
                                                                                    target_name=player_target_name,
                                                                                    optional_targets=opt_target_names,
                                                                                    refresh_rate=repeat_rate))

    def target_through(self, through_players: List[IPlayer], players: List[IPlayer], target_name: str, lock_targets=True,
                       repeat_rate: Optional[float] = None) -> bool:
        if repeat_rate is None:
            repeat_rate = CombatState.DEFAULT_TARGET_REFRESH_RATE
        if not through_players:
            logger.warn('Cannot target through, through_players not resolved')
            return False
        if not players:
            logger.warn('Cannot target through, players not resolved')
            return False
        through_players_set = set(through_players)
        through_players = list(through_players_set)
        self.set_players_target(players=through_players, target_name=target_name, lock_target=lock_targets, repeat_rate=repeat_rate)
        through_first_player = through_players[0]
        players = list(set(players).difference(through_players_set))
        self.set_players_target(players=players, target_name=through_first_player.get_player_name(), lock_target=lock_targets, repeat_rate=repeat_rate)
        return True

    def __unlock_current_target(self, event: CombatEvents.ENEMY_KILL):
        player = self.__runtime.player_mgr.get_player_by_name(event.killer_name)
        if not player or player not in self.__targeting_locked or player not in self.__player_target_names:
            return
        if event.enemy_name != self.__player_target_names[player]:
            return
        self.__targeting_locked.remove(player)
        self.set_players_target(players=player, target_name=None)

    def lock_current_target(self, player: IPlayer):
        current_target = self.__player_target_names[player] if player in self.__player_target_names else 'None'
        self.__runtime.overlay.log_event(f'Target lock: {player} on {current_target}', severity=Severity.Low)
        if current_target:
            self.__targeting_locked.add(player)

    def clear_player_targets(self, players: Optional[List[IPlayer]] = None):
        if players is None:
            players = list(self.__player_target_names.keys())
        players_str = [p.get_player_name() for p in players]
        self.__runtime.overlay.log_event(f'Clear targets: {players_str}', severity=Severity.Low)
        for player in players:
            if player in self.__optional_targets:
                self.__optional_targets[player].clear()
            if player in self.__targeting_locked:
                self.__targeting_locked.remove(player)
        self.set_players_target(players=players, target_name=None)
