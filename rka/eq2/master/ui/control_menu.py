from __future__ import annotations

import enum
import os
import time
from typing import Dict, List, Optional, Tuple, Union

import pyperclip
import regex as re

from rka.components.ai.graphs import Waypoint, Axis
from rka.components.concurrency.rkathread import RKAThread
from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService, LogLevel
from rka.components.ui.overlay import Severity, OvPlotHandler, OvPlotHandlerResult
from rka.eq2.datafiles.parser_tests import get_all_testlog_filepaths
from rka.eq2.master import IRuntime
from rka.eq2.master.game import is_unknown_zone
from rka.eq2.master.game.engine.task import Task
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.location.location_streams import LocationStreamConnector
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.combat.combat_script import CombatScriptTask, ECombatPhaseState
from rka.eq2.master.game.scripting.script_mgr import RegisteredGameScript, GameScriptManager
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.triggers import ITrigger
from rka.eq2.master.triggers.trigger_spec import TriggerSpec
from rka.eq2.master.ui import logger
from rka.eq2.master.ui.control_menu_ui import ControlMenuUIType, ControlMenuUI
from rka.eq2.master.ui.debug_helpers import print_ability_data, print_parser_data, print_player_effects, print_running_spells
from rka.eq2.parsing.parsing_util import EmoteInformation
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_scheduler

SCRIPT_STARTING_DELAY = 1.0


class ControlMenu:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__template_options = {' --- TRIGGERS --- ': self.__nop,
                                   'Create trigger from emote (minimum wildcarding)': lambda ui: self.__select_emote(ui, max_wildcarding=False),
                                   'Create trigger from emote (maximum wildcarding)': lambda ui: self.__select_emote(ui, max_wildcarding=True),
                                   'Create trigger from ability (any attacker)': lambda ui: self.__select_any_comatant_ability(ui),
                                   'Create trigger from ability (specific attacker)': lambda ui: self.__select_comatant_ability(ui),
                                   'Create trigger from killing enemy': lambda ui: self.__select_enemy_died(ui),
                                   'Create trigger from looting an item': lambda ui: self.__select_item_looted(ui),
                                   'Create trigger from player message': lambda ui: self.__select_player_message(ui),
                                   'Create trigger from friend login': lambda ui: self.__select_friend(ui),
                                   'Create trigger plain text': lambda ui: self.__input_trigger_pattern(ui),
                                   'Share trigger as ACT XML': lambda ui: self.__share_trigger(ui),
                                   'Disable trigger': lambda ui: self.__disable_trigger(ui),
                                   'Reload triggers': lambda ui: self.__reload_triggers(),
                                   ' --- NAVIGATION --- ': lambda ui: self.__nop(),
                                   'Use formation': lambda ui: self.__apply_formation(ui),
                                   'Show map': lambda ui: self.__show_map(ui),
                                   ' --- TESTS --- ': lambda ui: self.__nop(),
                                   'Inject test gamelog (local)': lambda ui: self.__select_file_gamelog_inject_for_local_player(ui),
                                   'Inject test gamelog (remote)': lambda ui: self.__select_remote_player_for_gamelog_inject(ui),
                                   'Stream test gamelog (local)': lambda ui: self.__stream_file_gamelog_inject_for_local_player(ui),
                                   'Input gamelog (local)': lambda ui: self.__input_gamelog_inject_for_local_player(ui),
                                   'Input gamelog (remote)': lambda ui: self.__input_gamelog_inject_for_remote_player(ui),
                                   'Change zone': lambda ui: self.__select_zone_to_change(ui),
                                   'Test trigger': lambda ui: self.__test_trigger(ui),
                                   'Start combat script': lambda ui: self.__start_combat_script(ui),
                                   'End combat script': lambda ui: self.__end_current_combat_scripts(ui),
                                   ' --- DEBUG --- ': lambda ui: self.__nop(),
                                   'Increase log verbosity': lambda ui: self.__select_logger_for_verbosity(ui),
                                   'Reset log levels': lambda ui: self.__reset_logs(),
                                   'Dump threads': lambda ui: self.__dump_threads(),
                                   'Dump ability': lambda ui: self.__dump_abilities(),
                                   'Dump triggers': lambda ui: self.__dump_triggers(),
                                   'Dump player effects': lambda ui: self.__dump_player_effects(),
                                   'Dump running spells': lambda ui: self.__dump_running_spells(),
                                   'Restore credential file': lambda ui: self.__runtime.credentials.recover_plain_file(),
                                   ' --- UTIL --- ': lambda ui: self.__nop(),
                                   'Select overlay slot': lambda ui: self.__select_overlay_slot(ui),
                                   }
        EventSystem.get_main_bus().subscribe(ChatEvents.ACT_TRIGGER_FOUND(), self.__act_trigger_found)
        self.__script_start_future: Optional[RKAFuture] = None

    # noinspection PyMethodMayBeStatic
    def __change_flag(self, ui: ControlMenuUI, flag: MutableFlags):
        dbgstr = f'{flag.name} = {bool(flag.toggle())}'
        ui.log_event(dbgstr, Severity.High)
        logger.info(dbgstr)

    def select_menu(self, ui_type: ControlMenuUIType):
        ui = ui_type.produce_ui(self.__runtime)
        menu_options = dict()
        menu_options.update(self.__template_options)
        ui.select_option(title='Actions', options=menu_options.keys(), result_cb=lambda option: menu_options[option](ui))

    def select_flag(self, ui_type: ControlMenuUIType):
        ui = ui_type.produce_ui(self.__runtime)
        flags = dict()
        for flag in MutableFlags:
            flag_text = f'{flag.name} [{bool(flag)}]'
            flags[flag_text] = lambda p_ui, p_flag=flag: self.__change_flag(p_ui, p_flag)
        ui.select_option(title='Flags', options=flags.keys(), result_cb=lambda option: flags[option](ui))

    def __nop(self):
        pass

    ### ================ Menus for TRIGGERS ================
    def __share_trigger_to_clipboard(self, trigger_spec: TriggerSpec):
        # replace zone with current zone, because here zone tier is not used
        if trigger_spec.zone:
            trigger_spec.zone = self.__runtime.zonemaps.get_current_zone_name()
        trigger_xml_str = trigger_spec.to_act_trigger_xml()
        if not trigger_xml_str:
            return
        pyperclip.copy(trigger_xml_str)

    def __get_all_trigger_specs(self) -> Optional[Dict[str, Tuple[ITrigger, TriggerSpec]]]:
        main_player = self.__runtime.playerstate.get_main_player()
        if main_player is None:
            return None
        result_triggers: Dict[str, Tuple[ITrigger, TriggerSpec]] = dict()
        client_triggers = self.__runtime.client_ctrl_mgr.get_client_triggers(main_player)
        current_zone = self.__runtime.zonemaps.get_current_zone_name()
        for trigger in client_triggers:
            zone_specific_trigger = self.__runtime.trigger_mgr.is_current_zone_trigger(main_player, trigger)
            if zone_specific_trigger:
                zone = current_zone
            else:
                zone = None
            trigger_specs = TriggerSpec.from_trigger(trigger, zone_name=zone)
            for trigger_spec in trigger_specs:
                trigger_descr = '~' + trigger_spec.short_str()
                result_triggers[trigger_descr] = (trigger, trigger_spec)
        for trigger in self.__runtime.trigger_mgr.get_current_zone_triggers(main_player):
            trigger_specs = TriggerSpec.from_trigger(trigger, zone_name=current_zone)
            for trigger_spec in trigger_specs:
                trigger_descr = trigger_spec.short_str()
                result_triggers[trigger_descr] = (trigger, trigger_spec)
        return result_triggers

    def __share_trigger(self, ui: ControlMenuUI):
        all_triggers = self.__get_all_trigger_specs()
        if not all_triggers:
            return
        options = sorted(all_triggers.keys())
        if len(all_triggers) > 0:
            ui.select_option(title='Export trigger as XML', options=options,
                             result_cb=lambda option: self.__share_trigger_to_clipboard(all_triggers[option][1]))

    def __disable_trigger(self, ui: ControlMenuUI):
        all_triggers = self.__get_all_trigger_specs()
        if not all_triggers:
            return
        options = sorted(all_triggers.keys())
        if len(all_triggers) > 0:
            ui.select_option(title='Temporarily disable a trigger', options=options,
                             result_cb=lambda option: all_triggers[option][0].cancel_trigger())

    def __test_trigger(self, ui: ControlMenuUI):
        all_triggers = self.__get_all_trigger_specs()
        if not all_triggers:
            return
        options = sorted(all_triggers.keys())

        def inner(option):
            trigger = all_triggers[option][0]
            if not trigger.test_trigger():
                logger.warn(f'Could not test trigger {trigger.describe()}')

        if len(all_triggers) > 0:
            ui.select_option(title='Test a trigger', options=options, result_cb=inner)

    def __select_emote(self, ui: ControlMenuUI, max_wildcarding: bool):
        if max_wildcarding:
            emotes = self.__runtime.zonestate.get_emotes_max_wildcarding()
        else:
            emotes = self.__runtime.zonestate.get_emotes_min_wildcarding()
        formatted_emotes = {ei.readable_with_timestamp(): ei for ei in emotes.values()}
        ui.select_option(title='Select emote', options=sorted(formatted_emotes.keys()),
                         result_cb=lambda formatted_emote: self.__create_trigger_from_emote(ui, formatted_emotes[formatted_emote]))

    def __select_comatant_ability(self, ui: ControlMenuUI):
        sorted_combatant_names = sorted(self.__runtime.current_dps.get_combatant_names())
        ui.select_option(title=f'Select combatant', options=sorted_combatant_names,
                         result_cb=lambda combatant_name: self.__select_ability(ui, combatant_name))

    def __select_any_comatant_ability(self, ui: ControlMenuUI):
        combatant_names = self.__runtime.current_dps.get_combatant_names()
        self.__select_ability(ui, combatant_names)

    def __select_ability(self, ui: ControlMenuUI, combatant_names: Union[List[str], str]):
        all_ability_names = set()
        one_combatant_name = None
        if isinstance(combatant_names, str):
            one_combatant_name = combatant_names
            combatant_names = [combatant_names]
        for combatant_name in combatant_names:
            combatant_ability_names = self.__runtime.current_dps.get_all_ability_names(combatant_name)
            all_ability_names.update(combatant_ability_names)
        sorted_ability_names = sorted(all_ability_names)
        title = f'Select ability of {one_combatant_name}' if one_combatant_name else f'Select ability'
        ui.select_option(title=title, options=sorted_ability_names,
                         result_cb=lambda ability_name: self.__create_trigger_from_ability(ui, ability_name, one_combatant_name))

    def __select_enemy_died(self, ui: ControlMenuUI):
        enemies = list(self.__runtime.zonestate.get_killed_enemies())
        ui.select_option(title='Enemy list', options=enemies, result_cb=lambda enemy: self.__create_trigger_from_kill(ui, enemy))

    def __select_item_looted(self, ui: ControlMenuUI):
        items = list(self.__runtime.zonestate.get_items_looted())
        ui.select_option(title='Item list', options=items, result_cb=lambda item: self.__create_trigger_from_loot(ui, item))

    def __select_player_message(self, ui: ControlMenuUI):
        tells = list(self.__runtime.zonestate.get_player_tells())
        tells_map = {f'{tell.tell} @ {tell.tell_type.value} ({"local" if tell.to_local else "remote"})': tell for tell in tells}
        ui.select_option(title='Tells list', options=tells_map.keys(), result_cb=lambda tell_key: self.__create_trigger_from_tell(ui, tells_map[tell_key]))

    def __select_friend(self, ui: ControlMenuUI):
        ui.get_text(title='Friend name', result_cb=lambda friend_name: self.__create_trigger_from_friend_login(ui, friend_name))

    def __input_trigger_pattern(self, ui: ControlMenuUI):
        ui.get_text(title='Match pattern', result_cb=lambda pattern: self.__create_trigger_from_pattern(ui, pattern))

    class TriggerScope(enum.Enum):
        ADD_PERSISTENT_THIS_ZONE = 'Add, current zone'
        ADD_PERSISTENT_ANY_ZONE = 'Add, dont set zone'
        ADD_TEMPORARY_THIS_ZONE = 'Add temporarily, current zone'
        ADD_TEMPORARY_ANY_ZONE = 'Add temporarily, dont set zone'
        CANCEL = 'Cancel'

        def __str__(self):
            return self.value

    @staticmethod
    def get_trigger_scopes() -> List[ControlMenu.TriggerScope]:
        # noinspection PyTypeChecker
        return list(ControlMenu.TriggerScope)

    def __save_trigger_with_tts(self, tts: Optional[str], trig_spec: TriggerSpec, save_in_db: bool):
        if tts is None:
            return
        if tts:
            if tts.lower() == 'beep':
                trig_spec.action_alert = True
            else:
                trig_spec.action_tts = tts
                trig_spec.action_log = 'TRIGGER: ' + tts
        self.__runtime.trigger_mgr.add_trigger_for_main_player(trig_spec, save_in_db=save_in_db)

    def __select_trigger_options(self, ui: ControlMenuUI, scope: TriggerScope, trig_spec: TriggerSpec):
        if scope is ControlMenu.TriggerScope.CANCEL:
            return
        temporary = scope in (ControlMenu.TriggerScope.ADD_TEMPORARY_ANY_ZONE, ControlMenu.TriggerScope.ADD_TEMPORARY_THIS_ZONE)
        require_zone = scope in (ControlMenu.TriggerScope.ADD_PERSISTENT_THIS_ZONE, ControlMenu.TriggerScope.ADD_TEMPORARY_THIS_ZONE)
        main_zone = self.__runtime.playerstate.get_main_player_zone()
        if not is_unknown_zone(main_zone) and require_zone:
            trig_spec.zone = main_zone
        if trig_spec.zone is None and require_zone:
            temporary = True
            logger.warn(f'cannot save/add trigger to zone, current zone unknown')
            return
        if not trig_spec.action_tts:
            ui.get_text('TTS sentence or "beep"', lambda tts: self.__save_trigger_with_tts(tts, trig_spec, not temporary))
        else:
            self.__runtime.trigger_mgr.add_trigger_for_main_player(trig_spec, save_in_db=not temporary)

    def __save_trigger_dialog(self, ui: ControlMenuUI, trigger_spec: TriggerSpec):
        ui.select_option(title=f'Trigger: {trigger_spec.short_str()}', options=ControlMenu.get_trigger_scopes(),
                         result_cb=lambda option: self.__select_trigger_options(ui, option, trigger_spec))

    def __act_trigger_found(self, event: ChatEvents.ACT_TRIGGER_FOUND):
        from_player = self.__runtime.player_mgr.get_player_by_name(event.from_player_name)
        is_from_local_player = from_player.is_local() if from_player else False
        if not MutableFlags.PARSE_OWN_ACT_TRIGGER_TELLS and is_from_local_player:
            return
        trigger_spec = TriggerSpec.from_act_trigger_xml(event.actxml)
        subscribe_event = trigger_spec.get_subscribe_event()
        if not isinstance(subscribe_event, ClientEvents.PARSER_MATCH):
            logger.warn(f'invalid ACT trigger')
            return
        ui = ControlMenuUIType.OVERLAY.produce_ui(self.__runtime)
        self.__save_trigger_dialog(ui, trigger_spec)

    def __create_trigger_from_emote(self, ui: ControlMenuUI, emote_info: EmoteInformation):
        trigger_spec = TriggerSpec()
        trigger_spec.set_subscribe_event(ClientEvents.PARSER_MATCH(parse_filter=emote_info.wildcarded, preparsed_log=False))
        trigger_spec.action_log = f'TRIGGER: {emote_info.readable}'
        self.__save_trigger_dialog(ui, trigger_spec)

    def __create_trigger_from_pattern(self, ui: ControlMenuUI, pattern: Optional[str]):
        if not pattern:
            return
        if not pattern.startswith('.*'):
            pattern = '.*' + pattern
        if not pattern.endswith('.*'):
            pattern = pattern + '.*'
        trigger_spec = TriggerSpec()
        trigger_spec.set_subscribe_event(ClientEvents.PARSER_MATCH(parse_filter=pattern, preparsed_log=True))
        trigger_spec.action_log = f'MATCH: {pattern}'
        self.__save_trigger_dialog(ui, trigger_spec)

    def __create_trigger_from_ability(self, ui: ControlMenuUI, ability_name: str, attacker_name: Optional[str]):
        def dialog_cb(scope: ControlMenu.TriggerScope):
            trigger_spec = TriggerSpec()
            trigger_spec.action_log = '{$ability_name} HIT {$target_name}'
            if attacker_name:
                trigger_spec.set_subscribe_event(CombatParserEvents.COMBAT_HIT(attacker_name=attacker_name, ability_name=ability_name, is_multi=False))
            else:
                trigger_spec.set_subscribe_event(CombatParserEvents.COMBAT_HIT(ability_name=ability_name, is_multi=False))
            self.__select_trigger_options(ui, scope, trigger_spec)

        ui.select_option(title=f'Trigger: ability hit {ability_name}', options=ControlMenu.get_trigger_scopes(), result_cb=dialog_cb)

    def __create_trigger_from_kill(self, ui: ControlMenuUI, enemy: str):
        def dialog_cb(scope: ControlMenu.TriggerScope):
            trigger_spec = TriggerSpec()
            trigger_spec.action_log = '{$killer_name} KILL {$enemy_name}'
            trigger_spec.set_subscribe_event(CombatEvents.ENEMY_KILL(enemy_name=enemy))
            self.__select_trigger_options(ui, scope, trigger_spec)

        ui.select_option(title=f'Trigger: {enemy} killed', options=ControlMenu.get_trigger_scopes(), result_cb=dialog_cb)

    def __create_trigger_from_loot(self, ui: ControlMenuUI, item: str):
        def dialog_cb(scope: ControlMenu.TriggerScope):
            trigger_spec = TriggerSpec()
            trigger_spec.action_log = '{$player} LOOT {$item_name}'
            trigger_spec.set_subscribe_event(PlayerInfoEvents.ITEM_RECEIVED(item_name=item))
            self.__select_trigger_options(ui, scope, trigger_spec)

        ui.select_option(title=f'Trigger: {item} looted', options=ControlMenu.get_trigger_scopes(), result_cb=dialog_cb)

    def __create_trigger_from_tell(self, ui: ControlMenuUI, tell: ChatEvents.PLAYER_TELL):
        def dialog_cb(scope: ControlMenu.TriggerScope):
            trigger_spec = TriggerSpec()
            trigger_spec.action_log = '{$player_name} SAY {$tell}'
            subscribe_event = ChatEvents.PLAYER_TELL(tell=tell.tell, tell_type=tell.tell_type, channel_name=tell.channel_name, to_local=tell.to_local)
            trigger_spec.set_subscribe_event(subscribe_event)
            self.__select_trigger_options(ui, scope, trigger_spec)

        ui.select_option(title=f'Trigger: got {tell}', options=ControlMenu.get_trigger_scopes(), result_cb=dialog_cb)

    def __create_trigger_from_friend_login(self, _ui: ControlMenuUI, friend_name: Optional[str]):
        if not friend_name:
            return
        trigger_spec = TriggerSpec()
        trigger_spec.action_log = '{$friend_name} LOGIN'
        trigger_spec.action_tts = trigger_spec.action_log
        trigger_spec.set_subscribe_event(PlayerInfoEvents.FRIEND_LOGGED(friend_name=friend_name, login=True))
        self.__runtime.trigger_mgr.add_trigger_for_main_player(trigger_spec=trigger_spec, save_in_db=True)

    def __reload_triggers(self):
        self.__runtime.trigger_db.empty_cached_triggers()
        self.__runtime.client_ctrl_mgr.reload_all_triggers()

    ### ================ Menus for DEBUG ================
    def __select_logger_for_verbosity(self, ui: ControlMenuUI):
        all_loggers = LogService.loggers
        logger_infos = [f'{name}: {log.get_level().name}' for name, log in all_loggers.items()]
        logger_mappings = {f'{name}: {log.get_level().name}': log for name, log in all_loggers.items()}
        ui.select_option(title='Menu', options=sorted(logger_infos),
                         result_cb=lambda logger_info: self.__verbose_logger(ui, logger_info, logger_mappings))

    def __verbose_logger(self, ui: ControlMenuUI, logger_info: str, user_arg: Dict[str, LogService]):
        log = user_arg[logger_info]
        level = log.get_level()
        if level > LogLevel.DETAIL:
            log.set_level(LogLevel.DETAIL)
        elif level == LogLevel.DETAIL:
            log.set_level(LogLevel.INFO)
        ui.log_event(f'Log verbosity {logger_info} = {log.get_level().name}', severity=Severity.Normal)
        self.__select_logger_for_verbosity(ui)

    # noinspection PyMethodMayBeStatic
    def __reset_logs(self):
        for log in list(LogService.loggers.values()):
            log.reset_level()

    # noinspection PyMethodMayBeStatic
    def __dump_threads(self):
        RKAThread.dump_threads()

    def __dump_abilities(self):
        print_ability_data(self.__runtime)

    def __dump_triggers(self):
        print_parser_data(self.__runtime)

    def __dump_player_effects(self):
        print_player_effects(self.__runtime)

    def __dump_running_spells(self):
        print_running_spells(self.__runtime)

    def __inject_gamelog_from_text(self, logline: Optional[str], client_id: str):
        if not logline:
            return
        if not re.match(r'\(\d{10}\)\[[\p{L}0-9: ]{24}\] ', logline):
            logline = '(0124567890)[Thu Jan  1  0:00:00 1970] ' + logline
        loginjector = self.__runtime.parser_mgr.get_loginjector(client_id)
        loginjector.write_log(logline)

    def __inject_gamelog_from_file(self, testlogfile: str, client_id: str, stream: bool):
        def action():
            remaining_duration = 60.0 if stream else 0.0
            remaining_iterations = 1
            repeat_rate = 1.0
            while remaining_iterations > 0 or remaining_duration > 0.0:
                start = time.time()
                f = open(testlogfile, mode='rt', encoding='utf-8')
                for line in f:
                    if not line:
                        continue
                    if line.startswith('period='):
                        repeat_rate = float(line.split('=')[1])
                        continue
                    self.__inject_gamelog_from_text(line, client_id)
                    if stream:
                        time.sleep(repeat_rate)
                f.close()
                remaining_iterations -= 1
                remaining_duration -= time.time() - start

        thread = RKAThread('Gamelog inject', action)
        thread.start()

    def __inject_gamelog_test(self, ui: ControlMenuUI, testlogfile: str, client_id: str, stream: bool):
        self.__inject_gamelog_from_file(testlogfile, client_id, stream)
        if not stream:
            self.__select_gamelog_test(ui, client_id, stream=False)

    def __select_gamelog_test(self, ui: ControlMenuUI, client_id: str, stream: bool):
        test_logfile_paths = get_all_testlog_filepaths()
        test_logfiles = {os.path.basename(logfile_path): logfile_path for logfile_path in test_logfile_paths}
        ui.select_option(title='Select test file', options=test_logfiles.keys(),
                         result_cb=lambda testlogfile: self.__inject_gamelog_test(ui, test_logfiles[testlogfile], client_id, stream=stream))

    def __select_file_gamelog_inject_for_local_player(self, ui: ControlMenuUI):
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            logger.warn(f'__select_file_gamelog_inject_for_local_player: no main player')
            return
        self.__select_gamelog_test(ui, main_player.get_client_id(), stream=False)

    def __stream_file_gamelog_inject_for_local_player(self, ui: ControlMenuUI):
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            logger.warn(f'__stream_file_gamelog_inject_for_local_player: no main player')
            return
        self.__select_gamelog_test(ui, main_player.get_client_id(), stream=True)

    def __input_gamelog_inject_for_player(self, ui: ControlMenuUI, player: IPlayer):
        ui.get_text(f'Input whole log line for {player}', lambda logline: self.__inject_gamelog_from_text(logline, player.get_client_id()))

    def __input_gamelog_inject_for_local_player(self, ui: ControlMenuUI):
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            logger.warn(f'__inject_gamelog: no main player')
            return
        self.__input_gamelog_inject_for_player(ui, main_player)

    def __input_gamelog_inject_for_remote_player(self, ui: ControlMenuUI):
        remote_players = {str(p): p for p in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)}
        if not remote_players:
            logger.warn(f'__inject_gamelog: no remote players online')
            return
        ui.select_option(title='Select remote player', options=sorted(remote_players.keys()),
                         result_cb=lambda player_name: self.__input_gamelog_inject_for_player(ui, remote_players[player_name]))

    def __select_remote_player_for_gamelog_inject(self, ui: ControlMenuUI):
        remote_players = {str(p): p for p in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)}
        if not remote_players:
            logger.warn(f'__inject_gamelog: no remote players online')
            return
        ui.select_option(title='Select remote player', options=sorted(remote_players.keys()),
                         result_cb=lambda player_name: self.__select_gamelog_test(ui, remote_players[player_name].get_client_id(), stream=False))

    def __change_zone(self, zone_name: str):
        self.__runtime.playerstate.notify_main_player_zoned(zone_name)

    def __select_zone_to_change(self, ui: ControlMenuUI):
        zone_names = sorted(self.__runtime.trigger_db.get_all_known_zone_names())
        ui.select_option(title='Select test file', options=zone_names, result_cb=self.__change_zone)

    def __get_player_locs(self) -> Dict[str, Waypoint]:
        from rka.eq2.master.game.scripting.scripts.location_scripts import ReadLocation
        player_locs = dict()
        for player in self.__runtime.player_mgr.get_players(min_status=PlayerStatus.Zoned):
            sink = LocationStreamConnector()
            sink.set_max_pop_wait(3.0)
            script = ReadLocation(player, sink)
            self.__runtime.processor.run_auto(script)
            location = sink.pop_location()
            if location:
                player_locs[player.get_player_name()] = location.to_waypoint()
        return player_locs

    def __show_map(self, ui: ControlMenuUI):
        if not ui.is_onscreen():
            return
        zone_name = self.__runtime.zonemaps.get_current_zone_name()
        zone_map = self.__runtime.zonemaps.get_current_zone_map()
        if not zone_map:
            ui.log_event(f'No map for {zone_name}', Severity.Normal)
            return
        player_locs = self.__get_player_locs()
        runtime = self.__runtime

        class PlotHandler(OvPlotHandler):
            def __init__(self):
                self.start_drag_waypoint = None
                self.drag_started = False
                self.axes = [Axis.X, Axis.Z]
                self.changes_made = False

            @staticmethod
            def _get_waypoint(loc_x: float, loc_y: float) -> Waypoint:
                return Waypoint(x=loc_x, z=loc_y, y=0.0)

            def on_mouse_double_click(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
                waypoint = PlotHandler._get_waypoint(loc_x, loc_y)
                closest_waypoint = zone_map.get_graph().get_closest_waypoint(waypoint, self.axes)
                waypoint[Axis.Y] = closest_waypoint[Axis.Y]
                if not closest_waypoint:
                    ui.log_event(f'No nearby point at {waypoint}', Severity.Normal)
                    return OvPlotHandlerResult.Continue
                player = runtime.player_mgr.get_online_player_by_overlay_id(runtime.overlay.get_selection_id())
                if not player:
                    return OvPlotHandlerResult.Continue
                ui.log_event(f'Move {player} to {waypoint}', Severity.Normal)
                if player:
                    location = Location.from_waypoint(waypoint)
                    runtime.automation.autopilot.player_move_to_location(player, location)
                    if player.is_local():
                        return OvPlotHandlerResult.Close
                return OvPlotHandlerResult.Continue

            def on_mouse_button_press(self, loc_x: float, loc_y: float, button) -> OvPlotHandlerResult:
                waypoint = PlotHandler._get_waypoint(loc_x, loc_y)
                closest_waypoint = zone_map.get_graph().get_closest_waypoint(waypoint, self.axes)
                waypoint[Axis.Y] = closest_waypoint[Axis.Y]
                if button == 1:
                    self.drag_started = False
                    if closest_waypoint and runtime.zonemaps.merge_rule.is_near(waypoint, closest_waypoint):
                        self.start_drag_waypoint = closest_waypoint
                    else:
                        self.start_drag_waypoint = None
                        ui.log_event(f'No nearby point at {waypoint}', Severity.Normal)
                    return OvPlotHandlerResult.Continue
                elif button == 3:
                    if closest_waypoint and runtime.zonemaps.merge_rule.is_near(waypoint, closest_waypoint):
                        ui.log_event(f'Remove waypoint at {closest_waypoint}', Severity.Normal)
                        zone_map.remove_closest_waypoint(closest_waypoint)
                    else:
                        ui.log_event(f'Add waypoint at {waypoint}', Severity.Normal)
                        zone_map.add_waypoint(waypoint)
                    self.changes_made = True
                    return OvPlotHandlerResult.Refresh
                return OvPlotHandlerResult.Continue

            def on_mouse_button_release(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
                if not self.start_drag_waypoint or not self.drag_started:
                    return OvPlotHandlerResult.Continue
                start_drag_waypoint = self.start_drag_waypoint
                self.start_drag_waypoint = None
                self.drag_started = False
                end_drag_waypoint = PlotHandler._get_waypoint(loc_x, loc_y)
                end_drag_waypoint[Axis.Y] = start_drag_waypoint[Axis.Y]
                ui.log_event(f'Drag waypoint from {start_drag_waypoint} to {end_drag_waypoint}', Severity.Normal)
                if zone_map.remove_closest_waypoint(start_drag_waypoint, self.axes):
                    zone_map.add_waypoint(end_drag_waypoint)
                    self.changes_made = True
                    return OvPlotHandlerResult.Refresh
                return OvPlotHandlerResult.Continue

            def on_mouse_move(self, loc_x: float, loc_y: float) -> OvPlotHandlerResult:
                if self.start_drag_waypoint:
                    waypoint = PlotHandler._get_waypoint(loc_x, loc_y)
                    if runtime.zonemaps.merge_rule.is_near_by_axes(self.start_drag_waypoint, waypoint, self.axes):
                        return OvPlotHandlerResult.Continue
                    self.drag_started = True
                return OvPlotHandlerResult.Continue

            def plot(self, axes):
                zone_graph = zone_map.get_graph()
                zone_graph.draw_graph(y_axis=Axis.Z, axes=axes)
                zone_graph.tag_graph(player_locs, y_axis=Axis.Z, axes=axes)
                axes.invert_xaxis()
                axes.invert_yaxis()
                zone_graph.show_graph(axes=axes)

            # noinspection PyMethodMayBeStatic
            def __save_changes(self, confirm: bool):
                if confirm:
                    runtime.zonemaps.update_current_map(zone_map)

            def on_close(self):
                if self.changes_made:
                    ui.get_confirm('Save changes?', self.__save_changes)

        self.__runtime.overlay.display_plot(title=f'{zone_name}: drag, edit (rclk), move player (dbclk)', handler=PlotHandler())

    def __apply_formation(self, ui: ControlMenuUI):
        formations = self.__runtime.zonemaps.load_formations()
        ui.select_option(title='Apply formation', options=formations.keys(),
                         result_cb=lambda formation_id: self.__runtime.automation.autopilot.apply_formation(formation_id))

    ### ================ Menus for UTIL ================
    def __select_overlay_slot(self, ui: ControlMenuUI):
        max_slots = self.__runtime.overlay.get_max_selection_id()

        def set_slot(slot_str: str):
            slot = int(slot_str)
            if slot < 0 or slot >= max_slots:
                logger.warn(f'Cannot set overlay slot ({slot}), out of range (1 - {max_slots - 1})')
                return
            self.__runtime.overlay.set_selection_id(slot)
            ui.log_event(f'Selected player: {self.__runtime.player_mgr.get_online_player_by_overlay_id(slot)}', Severity.Normal)

        ui.get_text(f'Slot number (0-{max_slots - 1})', set_slot)

    ### ================ Menus for SCRIPTS ================
    def __run_script(self, script):
        self.__runtime.processor.run_task(script)

    def __schedule_script(self, ui: ControlMenuUI, script_name: str, menu_items: Dict[str, Union[ScriptCategory, RegisteredGameScript]]):
        script_reg = menu_items[script_name]
        script = script_reg.create()
        ui.show_timer(name='SCRIPT', duration=SCRIPT_STARTING_DELAY, severity=Severity.Critical)
        self.__script_start_future = shared_scheduler.schedule(lambda: self.__run_script(script), delay=SCRIPT_STARTING_DELAY + 0.1)

    def __select_or_schedule_script(self, ui: ControlMenuUI, item_name: str, menu_items: Dict[str, Union[ScriptCategory, RegisteredGameScript]]):
        item = menu_items[item_name]
        if isinstance(item, ScriptCategory):
            self.select_script(ui, item)
            return
        self.__schedule_script(ui, item_name, menu_items)

    def select_script(self, ui: Union[ControlMenuUIType, ControlMenuUI], category=ScriptCategory.QUICKSTART):
        menu_items: Dict[str, Union[ScriptCategory, RegisteredGameScript]] = {}
        script_regs = GameScriptManager.get_game_scripts(category)
        menu_items.update({script_reg.name: script_reg for script_reg in script_regs})
        if category == ScriptCategory.QUICKSTART:
            menu_items.update(ScriptCategory.__members__)
        if isinstance(ui, ControlMenuUIType):
            ui = ui.produce_ui(self.__runtime)
        ui.select_option(title='Select script', options=list(menu_items.keys()),
                         result_cb=lambda item_name: self.__select_or_schedule_script(ui, item_name, menu_items))

    def cancel_script_start(self):
        future = self.__script_start_future
        if future:
            future.cancel_future()
            self.__script_start_future = None
            ui = ControlMenuUIType.OVERLAY.produce_ui(self.__runtime)
            ui.hide_timer('SCRIPT')

    def stop_scripts(self):
        def stop_script(task: Task):
            if isinstance(task, ScriptTask) and not task.is_persistent():
                task.expire()

        self.__runtime.processor.visit_tasks(stop_script)

    def control_scripts(self, ui_type: ControlMenuUIType):
        task_list = dict()

        def add_scripts_to_list(task: Task):
            if isinstance(task, ScriptTask):
                task_list[str(task)] = task

        self.__runtime.processor.visit_tasks(add_scripts_to_list)
        ui = ui_type.produce_ui(self.__runtime)
        ui.select_option(title='Select script to stop', options=task_list.keys(), result_cb=lambda task_str: task_list[task_str].expire())

    def __start_combat_script(self, ui: ControlMenuUI):
        task_list = dict()
        current_zone = self.__runtime.playerstate.get_main_player_zone()

        def add_scripts_to_list(task: Task):
            if isinstance(task, CombatScriptTask):
                if task.get_zone_name() == current_zone:
                    task_list[task.get_name()] = task

        def test_script(task: CombatScriptTask):
            task.root_phase().start()

        self.__runtime.processor.visit_tasks(add_scripts_to_list)
        ui.select_option(title='Select script to test', options=task_list.keys(), result_cb=lambda task_str: test_script(task_list[task_str]))

    def __end_current_combat_scripts(self, _ui: ControlMenuUI):
        current_zone = self.__runtime.playerstate.get_main_player_zone()

        def add_scripts_to_list(task: Task):
            if isinstance(task, CombatScriptTask):
                if task.get_zone_name() == current_zone and task.root_phase().get_state() == ECombatPhaseState.STARTED:
                    task.root_phase().stop()

        self.__runtime.processor.visit_tasks(add_scripts_to_list)
