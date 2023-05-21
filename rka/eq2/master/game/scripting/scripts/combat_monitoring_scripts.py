import time
from enum import Enum, auto
from threading import RLock
from typing import Optional, Dict, Union, List, Callable, Tuple

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.parsing import IDPSParserHook, ShortTermDpsMeasure, CombatantType, get_dps_str, DpsMeasure
from rka.services.api.ps_connector import IPSConnector
from rka.services.api.ps_connector_events import PSEvents
from rka.services.broker import ServiceBroker


class PeriodicAnnouncement(PlayerScriptTask):
    class ControlMessage(Enum):
        CONTROL_MESSAGE_SKIP = auto()
        CONTROL_MESSAGE_END = auto()

    DESTINATION_RAID = 'raidsay'
    DESTINATION_GROUP = 'gsay'
    DESTINATION_SAY = 'say'
    DESTINATION_TELL = 'tell '
    DESTINATION_OVERLAY = 'overlay'

    def __init__(self, announcement_cb: Callable[[IRuntime], Union[str, List[str], ControlMessage]], repeat_rate: float,
                 destination: str, auto_expire=False):
        PlayerScriptTask.__init__(self, f'Raid announcement', duration=-1.0)
        self.__announcement_cb = announcement_cb
        self.__repeat_rate = repeat_rate
        self.__auto_expire = auto_expire
        self.__destination = destination
        self.set_singleton(override_previous=True)
        self.set_persistent()
        self.set_silent()

    def __on_combat_end(self, _event: ObjectStateEvents.COMBAT_STATE_END):
        EventSystem.get_main_bus().unsubscribe_all(ObjectStateEvents.COMBAT_STATE_END, self.__on_combat_end)
        self.expire()

    def _run(self, runtime: IRuntime):
        if self.__auto_expire:
            EventSystem.get_main_bus().subscribe(ObjectStateEvents.COMBAT_STATE_END(), self.__on_combat_end)
        psf = self.get_player_scripting_framework(runtime.playerstate.get_main_player())
        while not self.is_expired():
            self.sleep(self.__repeat_rate)
            message = self.__announcement_cb(runtime)
            if message == PeriodicAnnouncement.ControlMessage.CONTROL_MESSAGE_SKIP:
                continue
            if message == PeriodicAnnouncement.ControlMessage.CONTROL_MESSAGE_END:
                return
            if self.__destination in [PeriodicAnnouncement.DESTINATION_RAID, PeriodicAnnouncement.DESTINATION_GROUP, PeriodicAnnouncement.DESTINATION_SAY]:
                cmd = psf.build_multicommand(message, self.__destination)
                psf.player_bool_action(cmd)
            elif self.__destination.startswith(PeriodicAnnouncement.DESTINATION_TELL):
                cmd = psf.build_multicommand(message, self.__destination)
                psf.player_bool_action(cmd)
            elif self.__destination == PeriodicAnnouncement.DESTINATION_OVERLAY:
                severity = Severity.Low if self.__repeat_rate <= 5.0 else Severity.Normal
                if isinstance(message, str):
                    message = message.splitlines()
                for line in message:
                    runtime.overlay.log_event(line, severity)


class MeasureAbilityDps(ScriptTask):
    class MeasureHoook(IDPSParserHook):
        def __init__(self, attacker_name: Optional[str], target_name: Optional[str], ability_name: Optional[str],
                     max_entries: int, period: float, min_value: int):
            self.attacker_name = attacker_name
            self.target_name = target_name
            self.ability_name = ability_name
            self.max_entries = max_entries
            self.period = period
            self.min_value = min_value
            self.ranking: Dict[str, ShortTermDpsMeasure] = dict()
            self.ranking_lock = RLock()
            self.measure_target = ability_name if ability_name else attacker_name if attacker_name else target_name
            self.combatant_type: Optional[CombatantType] = None
            self.relation = 'of' if ability_name else 'by' if attacker_name else 'on'

        def record_damage(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                          ability_name: str, damage: int, damage_type: str, is_autoattack: bool, timestamp: float):
            if self.ability_name is not None:
                if self.ability_name != ability_name:
                    return
                measure_record_name = target_name
            elif self.attacker_name is not None:
                if self.attacker_name != attacker_name:
                    return
                measure_record_name = ability_name
            elif self.target_name is not None:
                if self.target_name != target_name:
                    return
                if self.combatant_type is None:
                    self.combatant_type = target_type
                if CombatantType.is_npc(self.combatant_type):
                    measure_record_name = attacker_name
                else:
                    measure_record_name = ability_name
            else:
                measure_record_name = attacker_name
            if measure_record_name not in self.ranking:
                measure = ShortTermDpsMeasure(self.period, measure_record_name)
                with self.ranking_lock:
                    self.ranking[measure_record_name] = measure
            else:
                measure = self.ranking[measure_record_name]
            measure.add_hit(damage, timestamp)

        def format_ranking(self) -> Union[str, List[str], PeriodicAnnouncement.ControlMessage]:
            now = time.time()
            with self.ranking_lock:
                all_dps = {measure.description: measure.get_dps(now) for measure in self.ranking.values()}
            if not all_dps:
                return PeriodicAnnouncement.ControlMessage.CONTROL_MESSAGE_SKIP
            minimum_dps = {description: dps for description, dps in all_dps.items() if dps >= self.min_value and dps > 0}
            if not minimum_dps:
                return PeriodicAnnouncement.ControlMessage.CONTROL_MESSAGE_SKIP
            sorted_dps = {description: dps for description, dps in sorted(minimum_dps.items(), key=lambda descr_dps: descr_dps[1], reverse=True)}
            result = [f'~~ DPS {self.relation} {self.measure_target[:14]} ~~']
            for i, item in enumerate(sorted_dps.items()):
                if self.max_entries and i >= self.max_entries:
                    break
                result.append(f'{i + 1}.{item[0][:7]:7} | {get_dps_str(item[1])}')
            return result

    def __init__(self, attacker_name: Optional[str], target_name: Optional[str], ability_name: Optional[str],
                 max_entries: int, period: float, min_value: int, repeat_rate: float, destination: str):
        self.__measure_target = ability_name if ability_name else attacker_name if attacker_name else target_name
        ScriptTask.__init__(self, f'Measure dps of {self.__measure_target}', duration=-1.0)
        self.__repeat_rate = repeat_rate
        self.__destination = destination
        self.__dps_hook = MeasureAbilityDps.MeasureHoook(attacker_name, target_name, ability_name, max_entries, period, min_value)
        self.set_singleton(override_previous=True)
        self.set_silent()

    def __get_ranking_message(self, _runtime: IRuntime) -> Union[str, List[str], PeriodicAnnouncement.ControlMessage]:
        if self.is_expired():
            return PeriodicAnnouncement.ControlMessage.CONTROL_MESSAGE_END
        return self.__dps_hook.format_ranking()

    def _run(self, runtime: IRuntime):
        runtime.overlay.log_event(f'Measure DPS: {self.__measure_target} -> {self.__destination} every {self.__repeat_rate}s', Severity.Normal)
        runtime.current_dps.install_parser_hook(self.__dps_hook)
        anouncement_script = PeriodicAnnouncement(repeat_rate=self.__repeat_rate, announcement_cb=self.__get_ranking_message, destination=self.__destination)
        self.add_subscript(anouncement_script)
        self.wait_until_completed()

    def _on_expire(self):
        self.get_runtime().current_dps.uninstall_parser_hook(self.__dps_hook)
        super()._on_expire()


@GameScriptManager.register_game_script(ScriptCategory.COMBAT, 'Measure rending performance')
class CheckDebuffingPerformance(ScriptTask):
    class RendingCounter(IDPSParserHook):
        def __init__(self, debuffs: Dict[str, Tuple[float, float]]):
            self.debuffs = debuffs
            self.debuff_hit_counts: Dict[str, Dict[str, int]] = {debuff_name: dict() for debuff_name in debuffs.keys()}
            self.debuff_durations: Dict[str, Dict[str, float]] = {debuff_name: dict() for debuff_name in debuffs.keys()}
            self.debuff_timestamps: Dict[str, Dict[str, float]] = {debuff_name: dict() for debuff_name in debuffs.keys()}

        def restart(self):
            for debuff_hit_count in self.debuff_hit_counts.values():
                debuff_hit_count.clear()
            for debuff_duration in self.debuff_durations.values():
                debuff_duration.clear()

        def record_damage(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                          ability_name: str, damage: int, damage_type: str, is_autoattack: bool, timestamp: float):
            if not CombatantType.is_npc(target_type):
                return
            if not CombatantType.is_player(attacker_type):
                return
            # print(f'[{datetime.datetime.fromtimestamp(timestamp).time()}] HIT: {attacker_name}->{ability_name}')
            if ability_name not in self.debuffs:
                return
            if attacker_name not in self.debuff_hit_counts[ability_name]:
                self.debuff_hit_counts[ability_name][attacker_name] = 0
                self.debuff_durations[ability_name][attacker_name] = 0.0
                self.debuff_timestamps[ability_name][attacker_name] = 0.0
            # update total hits
            self.debuff_hit_counts[ability_name][attacker_name] += 1
            previous_timestamp = self.debuff_timestamps[ability_name][attacker_name]
            # exclude multi-attack
            if timestamp < previous_timestamp + 0.9:
                return
            self.debuff_timestamps[ability_name][attacker_name] = timestamp
            debuff_duration = self.debuffs[ability_name][1]
            # debuff restart
            if timestamp < previous_timestamp + debuff_duration:
                duration_penalty = debuff_duration - (timestamp - previous_timestamp)
            else:
                duration_penalty = 0.0
            debuff_duration -= duration_penalty
            # print(f'[{datetime.datetime.fromtimestamp(timestamp).time()}] DEBUFF: {attacker_name}->{ability_name} duration: {debuff_duration:.1f}s (penalty: {duration_penalty:.1f}s)')
            self.debuff_durations[ability_name][attacker_name] += debuff_duration

        def record_drain(self, attacker_name: str, attacker_type: CombatantType, target_name: str, target_type: CombatantType,
                         ability_name: str, power_amount: int, drain_type: str, timestamp: float):
            pass

    def __init__(self):
        ScriptTask.__init__(self, f'Check debuffing performance', duration=-1.0)
        self.__debuffs = {
            'elemental rending': (0.03, 8.0),
            'rending torrent': (0.02, 2.0),
            'anguish': (0.009, 1.0),
        }
        self.__hook = CheckDebuffingPerformance.RendingCounter(self.__debuffs)
        EventSystem.get_main_bus().subscribe(ObjectStateEvents.COMBAT_STATE_END(), self.__combat_end)
        self.set_singleton(True)

    def _on_expire(self):
        EventSystem.get_main_bus().unsubscribe_all(ObjectStateEvents.COMBAT_STATE_END, self.__combat_end)
        self.get_runtime().current_dps.uninstall_parser_hook(self.__hook)

    def __combat_end(self, _event: ObjectStateEvents.COMBAT_STATE_END):
        self.__print_ranking(self.get_runtime())
        self.__hook.restart()

    def __print_ranking(self, runtime: IRuntime):
        combat_duration = runtime.current_dps.get_duration()
        if not combat_duration:
            return
        total_damage = 0.0
        damage_debuffed_by_players: Dict[str, float] = dict()
        for combatant_record in runtime.current_dps.iter_combatant_records():
            if CombatantType.is_npc(combatant_record.get_combatant_type()):
                total_damage += combatant_record.get_incoming_damage(DpsMeasure.TOTAL)
                continue
            if CombatantType.is_other_player(combatant_record.get_combatant_type()):
                damage_debuffed_by_players[combatant_record.get_combatant_name()] = 0.0
        if not total_damage or not damage_debuffed_by_players:
            return
        average_dps_to_bosses = total_damage / combat_duration
        debuff_durations = dict(self.__hook.debuff_durations)
        debuff_hit_counts = dict(self.__hook.debuff_hit_counts)
        for debuff_name, (debuff_pct, _) in self.__debuffs.items():
            for player_name, debuff_duration in debuff_durations[debuff_name].items():
                debuff_value = debuff_duration * average_dps_to_bosses * debuff_pct
                damage_debuffed_by_players[player_name] = damage_debuffed_by_players.setdefault(player_name, 0.0) + debuff_value
        sorted_debuffers = sorted(damage_debuffed_by_players.keys(), key=lambda name: damage_debuffed_by_players[name], reverse=True)
        header = 'DPS increase% by ELEMENTAL RENDING & ANGUISH:'
        detail_logs = ['', header]
        simple_logs = ['', header]
        total_debuffing = 0.0
        max_debuffing = 0.0
        for i, player_name in enumerate(sorted_debuffers, start=1):
            # detailed information
            debuff_per_sec = damage_debuffed_by_players[player_name] / combat_duration
            debuf__per_sec_str = get_dps_str(int(debuff_per_sec))
            detail_log_abilities = []
            for debuff_name in self.__debuffs.keys():
                hit_count = debuff_hit_counts[debuff_name][player_name] if player_name in debuff_hit_counts[debuff_name] else 0
                debuff_duration = debuff_durations[debuff_name][player_name] if player_name in debuff_durations[debuff_name] else 0.0
                detail_log_abilities.append(f'{debuff_name}: {hit_count} hits / {int(debuff_duration)}s')
            detail_log_abilities_str = ', '.join(detail_log_abilities)
            detail_logs.append(f'{i:2}. {player_name[:8]:8} {debuf__per_sec_str} ({detail_log_abilities_str})')
            # % ranking for sharing
            debuff_pct = damage_debuffed_by_players[player_name] / total_damage * 100
            if debuff_pct > max_debuffing:
                max_debuffing = debuff_pct
            total_debuffing += debuff_pct
            simple_logs.append(f'{i:2}. {player_name[:8]:8} {debuff_pct:.2f}%')
        print('\n'.join(detail_logs))
        print('\n'.join(simple_logs))
        print('\n')
        debuffing_values = [debuff_value for debuff_value in damage_debuffed_by_players.values()]
        print(f'Total debuffing: {total_debuffing:.2f}%')
        print(f'Possible debuffing: {max_debuffing * len(debuffing_values):.2f}%')

    def _run(self, runtime: IRuntime):
        runtime.current_dps.install_parser_hook(self.__hook)
        while self.is_running():
            self.sleep(30.0)
            if runtime.combatstate.is_combat():
                self.__print_ranking(runtime)


@GameScriptManager.register_game_script(ScriptCategory.COMBAT, 'Start Apha PS service')
class AphaPSConnectorScript(ScriptTask):
    def __init__(self):
        ScriptTask.__init__(self, description='Apha PS connector', duration=-1.0)
        self.set_persistent()
        self.set_singleton(override_previous=False)
        self.__connector: Optional[IPSConnector] = None
        EventSystem.get_main_bus().subscribe(PSEvents.DISCONNECTED(), self.__diconnected)

    def _run(self, runtime: IRuntime):
        self.__connector: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
        self.__connector.start_connector()
        self.wait_until_completed()

    def __diconnected(self, _event: PSEvents.DISCONNECTED):
        self.expire()

    def _on_expire(self):
        if self.__connector:
            self.__connector.close_connector()
