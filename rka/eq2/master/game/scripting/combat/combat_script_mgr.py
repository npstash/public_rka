from threading import RLock
from typing import Type, Dict, List, Optional

import regex as re

from rka.components.events.event_system import EventSystem, CloseableSubscriber
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game import is_unknown_zone, get_canonical_zone_name_with_tier
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.combat import logger
from rka.eq2.master.game.scripting.combat.combat_script import CombatScriptTask
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.shared import ClientRequests
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.flags import MutableFlags


class CombatScriptBuilder:
    def __init__(self, zone_name_rgx: str, combatant_name: str, clazz: Type[CombatScriptTask], local_player: bool, remote_player: bool):
        self.zone_name_rgx = zone_name_rgx
        self.combatant_name = combatant_name
        self.clazz = clazz
        self.__use_for_local_player = local_player
        self.__use_for_remote_player = remote_player

    def filter_accept(self, local_player: bool) -> bool:
        return local_player and self.__use_for_local_player or not local_player and self.__use_for_remote_player

    def build_combat_script(self, runtime: IRuntime, local_player: bool, actual_zone_name: str) -> CombatScriptTask:
        script = self.clazz()
        script.initialize_combat_script(runtime, name=f'{self.combatant_name} in {actual_zone_name}',
                                        zone_name=actual_zone_name,
                                        combatant_name=self.combatant_name,
                                        local_player=local_player)
        return script


class CombatScriptManager(CloseableSubscriber):
    __registered_combat_scripts: Dict[str, List[CombatScriptBuilder]] = dict()
    __registered_combat_scripts_lock = RLock()

    @staticmethod
    def register_combat_script(zone_name_rgx: str, npc_name: str, local_player=True, remote_player=False, disabled=False):
        def combat_script_register_fn(clazz):
            if not disabled:
                if zone_name_rgx not in CombatScriptManager.__registered_combat_scripts:
                    CombatScriptManager.__registered_combat_scripts[zone_name_rgx] = list()
                record = CombatScriptBuilder(zone_name_rgx, npc_name, clazz, local_player, remote_player)
                CombatScriptManager.__registered_combat_scripts[zone_name_rgx].append(record)
            return clazz

        return combat_script_register_fn

    # noinspection PyUnresolvedReferences
    @staticmethod
    def __load_scripts():
        # make sure necessary scripts are registered by just importing them - they self-register
        import rka.eq2.master.game.scripting.scripts.combat

    @staticmethod
    def __get_combat_scripts(local_player: bool, zone_name: str) -> List[CombatScriptBuilder]:
        CombatScriptManager.__load_scripts()
        canonical_zone = get_canonical_zone_name_with_tier(zone_name)
        exact_match_scripts: Dict[str, CombatScriptBuilder] = dict()
        partial_match_scripts: Dict[str, CombatScriptBuilder] = dict()
        with CombatScriptManager.__registered_combat_scripts_lock:
            for zone_name_pattern, records in CombatScriptManager.__registered_combat_scripts.items():
                canonical_script_zone = get_canonical_zone_name_with_tier(zone_name_pattern)
                zone_name_rgx = zone_name_pattern + '$'
                if zone_name_pattern == zone_name or canonical_script_zone == canonical_zone:
                    filtered_records = list(filter(lambda _record: _record.filter_accept(local_player), records))
                    for record in filtered_records:
                        if record.combatant_name in exact_match_scripts:
                            logger.error(f'Duplicate combat script for {record.combatant_name} in {zone_name}')
                        exact_match_scripts[record.combatant_name] = record
                if re.match(zone_name_rgx, zone_name):
                    filtered_records = list(filter(lambda _record: _record.filter_accept(local_player), records))
                    for record in filtered_records:
                        if record.combatant_name in partial_match_scripts:
                            logger.warn(f'Duplicate combat script for {record.combatant_name} in {zone_name}')
                        partial_match_scripts[record.combatant_name] = record
        all_scripts = list(exact_match_scripts.values())
        for combatant_name, record in partial_match_scripts.items():
            if combatant_name not in exact_match_scripts:
                all_scripts.append(record)
        return all_scripts

    def __init__(self, runtime: IRuntime):
        self.__bus = EventSystem.get_main_bus()
        self.__runtime = runtime
        CloseableSubscriber.__init__(self, self.__bus)
        self.__active_scripts: Dict[str, Dict[Type[CombatScriptTask], CombatScriptTask]] = dict()
        self.__bus.subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__zone_changed)
        self.__bus.subscribe(ObjectStateEvents.PLAYER_STATUS_CHANGED(from_status=PlayerStatus.Offline, to_status=PlayerStatus.Online), self.__player_online)
        self.__general_oozc_script: Optional[ScriptTask] = None

    def __start_oozc(self, _event: ClientEvents.CLIENT_REQUEST):
        from rka.eq2.master.game.scripting.scripts.ooz_control_scripts import EnableOOZCombat
        script = EnableOOZCombat()
        self.__runtime.processor.run_auto(script)
        self.__general_oozc_script = script

    def __stop_oozc(self, _event: ClientEvents.CLIENT_REQUEST):
        if self.__general_oozc_script:
            self.__general_oozc_script.expire()

    def __player_online(self, event: ObjectStateEvents.PLAYER_STATUS_CHANGED):
        bus = self.__runtime.remote_client_event_system.get_bus(event.player.get_client_id())
        if not bus:
            logger.warn(f'__player_online: no bus to handle {event}')
            return
        bus.subscribe(ClientEvents.CLIENT_REQUEST(request=ClientRequests.START_OOZC), self.__start_oozc)
        bus.subscribe(ClientEvents.CLIENT_REQUEST(request=ClientRequests.STOP_OOZC), self.__stop_oozc)

    def __expire_local_player_combat_scripts(self):
        for zone_name, active_zone_scripts in self.__active_scripts.items():
            expired_scripts = list()
            for combat_script_type, combat_script in active_zone_scripts.items():
                if combat_script.is_built_for_local_player():
                    combat_script.expire()
                    expired_scripts.append(combat_script_type)
            for expired_script in expired_scripts:
                del active_zone_scripts[expired_script]

    def __expire_combat_scripts_in_zone(self, zone_name: str):
        if zone_name in self.__active_scripts:
            active_zone_scripts = self.__active_scripts[zone_name]
            for combat_script_type, combat_script in active_zone_scripts.items():
                combat_script.expire()
            active_zone_scripts.clear()

    def __launch_combat_scripts(self, main_player: Optional[IPlayer], new_zone: str, zone_combat_script_regs: List[CombatScriptBuilder]):
        for combat_script_reg in zone_combat_script_regs:
            new_script = combat_script_reg.build_combat_script(self.__runtime, main_player is not None, new_zone)
            if main_player:
                new_script.add_script_participant(main_player)
            for player in self.__runtime.playerselectors.all_remote_in_zone(new_zone).resolve_players():
                new_script.add_script_participant(player)
            self.__active_scripts[new_zone][combat_script_reg.clazz] = new_script
            self.__runtime.processor.run_auto(new_script)

    def __create_local_player_combat_scripts(self, main_player: IPlayer, new_zone: str):
        zone_combat_script_regs = CombatScriptManager.__get_combat_scripts(local_player=True, zone_name=new_zone)
        if zone_combat_script_regs:
            self.__runtime.overlay.log_event(f'{len(zone_combat_script_regs)} local combat scripts for {new_zone}', Severity.Normal)
        self.__launch_combat_scripts(main_player, new_zone, zone_combat_script_regs)

    def __create_remote_player_combat_scripts(self, new_zone: str):
        # create remote player combat scripts, if they aren't running yet
        zone_combat_script_regs = CombatScriptManager.__get_combat_scripts(local_player=False, zone_name=new_zone)
        for combat_script_reg in list(zone_combat_script_regs):
            if combat_script_reg.clazz in self.__active_scripts[new_zone]:
                existing_script = self.__active_scripts[new_zone][combat_script_reg.clazz]
                if not existing_script.is_expired():
                    zone_combat_script_regs.remove(combat_script_reg)
        if zone_combat_script_regs:
            self.__runtime.overlay.log_event(f'{len(zone_combat_script_regs)} new remote combat scripts for {new_zone}', Severity.Normal)
        self.__launch_combat_scripts(None, new_zone, zone_combat_script_regs)

    def __zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        main_player = self.__runtime.playerstate.get_main_player()
        if main_player:
            main_player_zone = main_player.get_zone()
        else:
            main_player_zone = None
        with CombatScriptManager.__registered_combat_scripts_lock:
            new_zone = event.to_zone
            if new_zone not in self.__active_scripts:
                self.__active_scripts[new_zone] = dict()
            if event.player.is_local():
                # expire all local player scripts
                self.__expire_local_player_combat_scripts()
                if not is_unknown_zone(new_zone):
                    # expire all scripts in the new zone (could have been created by remote player already)
                    self.__expire_combat_scripts_in_zone(new_zone)
                    # and launch all local player scripts
                    self.__create_local_player_combat_scripts(event.player, new_zone)
            elif new_zone != main_player_zone and MutableFlags.ENABLE_OFFZONE_COMBAT_SCRIPTS:
                # remote player scripts expire by themselves, when last participant is zoned out
                if not is_unknown_zone(new_zone):
                    self.__create_remote_player_combat_scripts(new_zone)
