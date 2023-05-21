import math
import random
from threading import Condition
from typing import Optional, Union

from PIL.ImageDraw import ImageDraw

from rka.components.events.event_system import EventSystem
from rka.components.impl.factories import HotkeyServiceFactory, OCRServiceFactory
from rka.components.ui.capture import MatchPattern, CaptureArea, Capture, Rect, CaptureMode
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import ALT1_NAME, ALT2_NAME
from rka.eq2.datafiles.parser_tests import get_testlog_filepath
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import MysticAbilities, DirgeAbilities, BardAbilities, ShamanAbilities, FighterAbilities, \
    CoercerAbilities, FuryAbilities, DruidAbilities, CommonerAbilities
from rka.eq2.master.game.engine.request import NonOverlappingDuration, CastOneAndExpire, CastAnyWhenReady, Request
from rka.eq2.master.game.engine.resolver import AbilityResolver
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.player import PlayerStatus, TellType
from rka.eq2.master.game.scripting import RepeatMode, logger
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.patterns.detrims.bundle import detrim_patterns
from rka.eq2.master.game.scripting.procedures.items import ItemLootingCheckerProcedure, BagItemCheckerProcedure
from rka.eq2.master.game.scripting.procedures.movement import LocationCheckerProcedure
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.script_task import ScriptTask
from rka.eq2.master.screening import IScreenReader
from rka.eq2.master.screening.screen_reader_events import ScreenReaderEvents
from rka.eq2.master.triggers.trigger import Trigger
from rka.eq2.parsing import ILogInjector
from rka.eq2.parsing.log_io import LogUtil
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.client_combat import ClientCombatParserEvents
from rka.eq2.shared.flags import MutableFlags
from rka.services.api.ps_connector import IPSConnector
from rka.services.broker import ServiceBroker


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Combat with log files')
class CombatLogscriptTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.log_injector: Optional[ILogInjector] = None

    def __inject_logs(self, from_file: str, delay: float):
        f = open(from_file, mode='rt', encoding='utf-8')
        for line in f:
            self.log_injector.write_log(line)
        f.close()
        self.sleep(delay)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        self.log_injector = runtime.parser_mgr.get_loginjector(main_player.get_client_id())
        players_zone_in_1_file = get_testlog_filepath('zone_test_zone.txt')
        players_zone_in_2_file = get_testlog_filepath('who_maingrp_remotes.txt')
        combat_hits_1_file = get_testlog_filepath('combat_other_players_1.txt')
        balanced_synergy_file = get_testlog_filepath('balanced_synergy.txt')
        self.__inject_logs(players_zone_in_1_file, 1.0)
        self.__inject_logs(players_zone_in_2_file, 1.0)
        counter = 0
        while True:
            counter += 1
            self.__inject_logs(combat_hits_1_file, random.random() + 0.5)
            if counter % 30 == 0:
                self.__inject_logs(balanced_synergy_file, 0.5)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Combat events')
class TestCombatEvents(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.__runtime = None

    def __event_cb(self, event: Union[ClientCombatParserEvents.COMBAT_PARSE_START, ClientCombatParserEvents.COMBAT_PARSE_END]):
        if self.__runtime:
            player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
            self.__runtime.overlay.log_event(f'{event} for {player}', Severity.Normal)

    def _run(self, runtime: IRuntime):
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)
        self.__runtime = runtime
        try:
            for player in players:
                cid = player.get_client_id()
                bus = runtime.remote_client_event_system.get_bus(cid)
                bus.subscribe(ClientCombatParserEvents.COMBAT_PARSE_START(client_id=cid), subscriber=self.event_cb)
                bus.subscribe(ClientCombatParserEvents.COMBAT_PARSE_END(client_id=cid), subscriber=self.event_cb)
            self.wait_until_completed()
        finally:
            for player in players:
                cid = player.get_client_id()
                bus = runtime.remote_client_event_system.get_bus(cid)
                bus.unsubscribe(ClientCombatParserEvents.COMBAT_PARSE_START(client_id=cid), subscriber=self.event_cb)
                bus.unsubscribe(ClientCombatParserEvents.COMBAT_PARSE_END(client_id=cid), subscriber=self.event_cb)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Multi-capture')
class TestMultipleCapture(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        psf = self.get_player_scripting_framework(main_player)
        matches = psf.find_multiple_match_by_pattern(pattern=MatchPattern.by_tag(ui_patterns.PATTERN_BUTTON_X), repeat=RepeatMode.DONT_REPEAT)
        for tag, rect in matches:
            action = action_factory.new_action().mouse(x=rect.middle().x, y=rect.middle().y)
            psf.post_player_action(action)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Non-overlapping request')
class TestRequest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        request = NonOverlappingDuration([ShamanAbilities.spirit_aegis,
                                          MysticAbilities.oberon,
                                          MysticAbilities.torpor,
                                          DirgeAbilities.exuberant_encore,
                                          DirgeAbilities.oration_of_sacrifice,
                                          BardAbilities.requiem,
                                          ], resolver=AbilityResolver().filtered(AbilityFilter().remote_casters()), overlap=2.0, duration=180.0)
        runtime.processor.run_request(request)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Item-looting checker procedure')
class TestLootingTrigger(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        p = ItemLootingCheckerProcedure(self.get_player_scripting_framework(None))
        p.start_looting_tracking()
        item = p.wait_for_trigger(6000.0)
        print(f'looted item={item}')
        p.stop_looting_tracking()


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Location check')
class TestLocation(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        p = LocationCheckerProcedure(self.get_player_scripting_framework(None))
        p.start_movement_tracking()
        loc = p.wait_for_trigger(6000.0)
        print(f'location is ={loc}')
        p.stop_movement_tracking()


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Single-target ward rotation')
class TestWards(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        r = runtime.request_factory.single_target_heals_rotate_target()
        r.set_duration(60.0)
        runtime.processor.run_request(r)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Monk intercept')
class TestIntercept(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        for a in FighterAbilities.intercept.resolve():
            a.census.reuse = 5.0
            # a.census.duration = 15.0
        r = runtime.request_factory.smart_monk_intercept()
        r.set_duration(60.0)
        runtime.processor.run_request(r)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Manaward timer')
class TestManaward(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'test', -1.0)

    def _run(self, runtime: IRuntime):
        for a in CoercerAbilities.manaward.resolve():
            a.census.duration = 3000.0
        all_zoned_players = runtime.player_mgr.get_players(min_status=PlayerStatus.Zoned)
        request = runtime.request_factory.custom_request(CoercerAbilities.manaward, all_zoned_players, 60.0)
        runtime.processor.run_request(request)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Porcupine reset')
class TestPorcupineReset(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        request = CastAnyWhenReady([FuryAbilities.porcupine], resolver=AbilityResolver(), duration=60.0)
        runtime.request_ctrl.processor.run_auto(request)
        keyfilter_1 = HotkeyServiceFactory.create_filter()
        keyfilter_1.add_keys('space', self._next_1)
        keyfilter_1.add_keys('escape', self._end)
        self.get_runtime().key_manager.hotkey_service.set_filter(keyfilter_1)
        runtime.overlay_controller.start_timer()

    def _next_1(self):
        request = CastOneAndExpire([DruidAbilities.sylvan_touch], resolver=AbilityResolver(), duration=10.0)
        self.get_runtime().request_ctrl.processor.run_auto(request)
        self._end()

    def _end(self):
        self.get_runtime().key_manager.cycle_hotkeys('', self.get_runtime().key_manager.hotkey_service)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Salve (grantable fury ability)')
class TestSalve(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.__request: Optional[Request] = None

    def _run(self, runtime: IRuntime):
        self.__request = CastAnyWhenReady([CommonerAbilities.salve], resolver=AbilityResolver().filtered(AbilityFilter().remote_casters()), duration=-1.0)
        runtime.request_ctrl.processor.run_auto(self.__request)
        keyfilter_1 = HotkeyServiceFactory.create_filter()
        keyfilter_1.add_keys('1', self._next_1)
        keyfilter_1.add_keys('2', self._next_2)
        keyfilter_1.add_keys('escape', self._end)
        self.get_runtime().key_manager.hotkey_service.set_filter(keyfilter_1)
        runtime.overlay_controller.start_timer()

    def _next_1(self):
        request = CastOneAndExpire([FuryAbilities.pact_of_nature], resolver=AbilityResolver(), duration=10.0)
        self.get_runtime().request_ctrl.processor.run_auto(request)

    # noinspection PyMethodMayBeStatic
    def _next_2(self):
        for ability in FuryAbilities.pact_of_nature.resolve():
            ability.expire_duration()

    def _end(self):
        self.get_runtime().key_manager.cycle_hotkeys('', self.get_runtime().key_manager.hotkey_service)
        self.__request.expire()


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Simple combat')
class TestCombat(PlayerScriptTask):
    def __init__(self, enemy_name='The Grimling Zero', duration=10):
        PlayerScriptTask.__init__(self, None, duration * 1.0)
        self.__enemy_name = enemy_name

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        log_injector = runtime.parser_mgr.get_loginjector(main_player.get_client_id())
        while not self.is_expired():
            log_injector.write_log('(0124567890)[Thu Jan  1  0:00:00 1970] ' + f'''{self.__enemy_name} hits YOU for 31748858 crushing damage.''')
            self.sleep(1.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Boss combat')
class TestOverlapRequest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        log_injector = runtime.parser_mgr.get_loginjector(main_player.get_client_id())
        LogUtil.inject_gamelog_from_file(log_injector, get_testlog_filepath('zone_test_zone.txt'))
        LogUtil.inject_gamelog_from_file(log_injector, get_testlog_filepath('who_maingrp_remotes.txt'))
        self.sleep(3.0)
        # request = runtime.request_factory.non_overlapping_main_group_buffs()
        # runtime.processor.run_auto(request)
        while not self.is_expired():
            # request.extend()
            runtime.request_ctrl.request_group_normal_combat()
            runtime.request_ctrl.request_group_boss_combat()
            self.sleep(1.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Main group zone-in')
class ZoneMainGroup(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        log_injector = runtime.parser_mgr.get_loginjector(main_player.get_client_id())
        LogUtil.inject_gamelog_from_file(log_injector, get_testlog_filepath('zone_test_zone.txt'))
        LogUtil.inject_gamelog_from_file(log_injector, get_testlog_filepath('who_maingrp_remotes.txt'))


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Discord voice')
class DiscordVoiceTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def __speak(self, text: Optional[str]):
        if not text:
            return
        session = self.get_runtime().group_tts.open_session(keep_open_duration=0.0)
        session.say(text)
        self.get_runtime().notification_service.post_notification(text)
        self.sleep(20.0)
        session.close()

    def _run(self, runtime: IRuntime):
        self.get_runtime().overlay.get_text('what to say?', self.__speak)
        self.sleep(30.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Find an item in inventory')
class FindItemInBagsTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    players_items = {
        ALT1_NAME: 'Shadow Steed Strongbox',
        ALT2_NAME: 'Imperium I',
    }

    def _run_player(self, psf: PlayerScriptingFramework):
        bic = BagItemCheckerProcedure(psf, FindItemInBagsTest.players_items[psf.get_player().get_player_name()])
        for i in range(20):
            loc = bic.get_bag_location()
            print(loc)

    def _run(self, runtime: IRuntime):
        players = [
            runtime.player_mgr.get_player_by_name(ALT1_NAME),
            runtime.player_mgr.get_player_by_name(ALT2_NAME)
        ]
        self.run_concurrent_players(players)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Destroy an item in inventory')
class ItemDestroyTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        player = runtime.player_mgr.get_player_by_name(ALT1_NAME)
        psf = self.get_player_scripting_framework(player)
        psf.destroy_item_in_bags('smooth pledge stone', open_bags=True)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Capture detriment window')
class CaptureDetrimsScript(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        ocr = OCRServiceFactory.create_ocr_service()
        for player in self.get_runtime().playerselectors.all_zoned_remote().resolve_players():
            psf = self.get_player_scripting_framework(player)
            detrim_rect = player.get_inputs().screen.detrim_list_window
            capture = psf.capture_box(detrim_rect, mode=CaptureMode.COLOR)
            ocr.show_image(capture)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Chatbot')
class ChatbotTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.__condition = Condition()
        self.__text: Optional[str] = None

    def chat(self, message: Optional[str]):
        if not message:
            return
        with self.__condition:
            self.__text = message
            self.__condition.notify_all()

    def _run(self, runtime: IRuntime):
        with self.__condition:
            while not self.is_expired():
                runtime.overlay.get_text('Chat', self.chat)
                # noinspection PyTypeChecker
                self.wait(self.__condition, None)
                text = self.__text
                if not text:
                    break
                fake_event = ChatEvents.PLAYER_TELL(from_player_name=ALT2_NAME,
                                                    tell_type=TellType.tell,
                                                    tell=text,
                                                    to_player=runtime.player_mgr.get_player_by_name(ALT1_NAME),
                                                    to_local=False
                                                    )
                runtime.automation.conversation.player_message(fake_event)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Math wrath (detrims with 2-digit numbers)')
class MathWrathTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        self.sleep(1.0)
        MutableFlags.SAVE_OCR_IMAGES.true()
        player = runtime.playerstate.get_main_player()
        psf = self.get_player_scripting_framework(player)
        action_factory.new_action().window_activate('ocr_', set_default=True).call_action(player.get_client_id())
        from rka.eq2.master.game.scripting.patterns.expansions.ros.bundle import ros_patterns
        wrath_number = psf.detriment_read_number(ros_patterns.MATH_WRATH)
        print(wrath_number)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Spam Strikes Of Consistency')
class StrikesOfConsistency(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        while True:
            runtime.request_ctrl.request_strikes_of_consistency()
            self.sleep(3.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Spam attacts')
class SpamAttacks(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        while True:
            runtime.request_ctrl.request_spam_attacks(duration=30.0)
            self.sleep(25.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Detect detriments')
class DetectDetrimentTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        self.sleep(3.0)
        player = runtime.playerstate.get_main_player()
        # a = action_factory.new_action().window_activate('Photos')
        # a.call_action(player.get_client_id())
        # self.sleep(1.0)
        psf = self.get_player_scripting_framework(player)
        member_info = psf.get_raid_members_info()
        for info in member_info.values():
            print(info)
        runtime.overlay.log_event('DONE')


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Item receive/find events')
class ItemEventsTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.__trigger_1 = None
        self.__trigger_2 = None

    # noinspection PyMethodMayBeStatic
    def __found_in_bags(self, event: PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY):
        logger.info(f'IN BAGS: {event}')

    # noinspection PyMethodMayBeStatic
    def __looted(self, event: PlayerInfoEvents.ITEM_RECEIVED):
        logger.info(f'LOOTED: {event}')

    def _run(self, runtime: IRuntime):
        self.__trigger_1 = Trigger()
        self.__trigger_1.add_bus_event(PlayerInfoEvents.ITEM_FOUND_IN_INVENTORY())
        self.__trigger_1.add_action(self.__found_in_bags)
        self.__trigger_1.start_trigger()
        self.__trigger_2 = Trigger()
        self.__trigger_2.add_bus_event(PlayerInfoEvents.ITEM_RECEIVED())
        self.__trigger_2.add_action(self.__looted)
        self.__trigger_2.start_trigger()
        self.wait_until_completed()

    def _on_expire(self):
        self.__trigger_1.cancel_trigger()
        self.__trigger_2.cancel_trigger()


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Pattern capture test')
class CaptureTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        from rka.eq2.master.game.scripting.patterns.expansions.vov.bundle import vov_patterns
        markup_colors = {
            vov_patterns.ARCH_ENEMY_RED: 'red',
            vov_patterns.ARCH_ENEMY_YELLOW: 'yellow',
            vov_patterns.ARCH_ENEMY_BLUE: 'blue',
        }
        for resource in markup_colors.keys():
            print(f'{resource.resource_name}, {resource.resource_id}')
        window_title = 'Photos'
        resources = vov_patterns
        pattern = MatchPattern.by_tags(list(markup_colors.keys()))
        player = self.resolve_player(None)
        psf = self.get_player_scripting_framework(player)
        psf.activate_window(window_title)
        window_area = CaptureArea(mode=CaptureMode.COLOR, wintitle=window_title)
        results = psf.find_multiple_match_by_pattern(pattern=pattern, area=window_area, repeat=RepeatMode.DONT_REPEAT, threshold=0.60, max_matches=12)
        for tag, rect in results:
            print(f'tag={tag.split(".")[-1]}, rect={rect}')

        ### part of the Arch Enemy test
        if len(results) % 2 != 0:
            print(f'Odd number of matches ({len(results)})!')
            return
        # split colors into columns, sorted from the bottom
        columns = {
            resource.resource_id: list(sorted([rect for tag, rect in results if tag == resource.resource_id],
                                              key=lambda rect_: rect_.middle().y, reverse=True)) for resource in markup_colors.keys()
        }
        # look at one the columns and figure the tilt
        ref_column = columns[vov_patterns.ARCH_ENEMY_YELLOW.resource_id]
        if len(ref_column) >= 2:
            angle_anchor = ref_column[0].point1()
            angle_endpoint = ref_column[-1].point1()
            dx = angle_endpoint.x - angle_anchor.x
            # aplify the angle a bit
            # dx = dx + (1 if dx > 0 else -1 if dx < 0 else 0)
            dy = angle_endpoint.y - angle_anchor.y
            # expecting angle between points around -pi/2
            angle = math.atan2(dy, dx) + math.pi / 2
            # now rotate them all
            rotated_results = []
            print(f'rotating from {angle_anchor} to {angle_endpoint}, angle {angle}')
            for tag, rect in results:
                rotated_point_1 = rect.point1().rotate(angle_anchor, -angle)
                rotated_point_2 = rect.point2().rotate(angle_anchor, -angle)
                rotated_rect = Rect.from_points(rotated_point_1, rotated_point_2)
                rotated_results.append((tag, rotated_rect))
                print(f'rotating {tag}, {rect} to {rotated_rect}')
            results = rotated_results
        # pair symbols found, from bottom
        results_copy = list(results)
        i = 1
        while results_copy:
            # choose the color that starts as the lowest
            bottom_result = max(results_copy, key=lambda tag_rect_: tag_rect_[1].y2)
            results_copy.remove(bottom_result)
            bottom_tag, bottom_rect = bottom_result
            # and find the one that is closest to it horizontally
            closest_result = min(results_copy, key=lambda tag_rect_: abs(tag_rect_[1].y2 - bottom_rect.y2))
            results_copy.remove(closest_result)
            closest_tag, closest_rect = closest_result
            bottom_color = markup_colors[resources[bottom_tag]]
            closest_color = markup_colors[resources[closest_tag]]
            ordered_colors = list(sorted([bottom_color, closest_color]))
            print(f'{i}. {ordered_colors[0].upper()} {ordered_colors[1].upper()}')
            i += 1

        ac = action_factory.new_action().get_capture(capture_area=window_area)
        capture_str = ac.call_action(player.get_client_id())[1][0]
        capture = Capture.decode_capture(capture_str)
        # draw red boundaries around
        img_draw = ImageDraw(capture.image)
        for tag, rect in results:
            resource = resources[tag]
            img_draw.rectangle((rect.x1, rect.y1, rect.x2, rect.y2), outline=markup_colors[resource])
        capture.image.show()


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Trigger PS raid say test')
class AphaPSTest(ScriptTask):
    def __init__(self):
        ScriptTask.__init__(self, 'PS Test', -1.0)

    def _run(self, runtime: IRuntime):
        connector: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
        connector.send_tts('Stop Masturbate')


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Trigger PS raid say test (input)')
class AphaPSTest2(ScriptTask):
    def __init__(self):
        ScriptTask.__init__(self, 'PS Test 2', -1.0)

    # noinspection PyMethodMayBeStatic
    def __send(self, message: str):
        if message:
            connector: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
            connector.send_tts(message)

    def _run(self, runtime: IRuntime):
        runtime.overlay.get_text('Message', self.__send)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Detrim count area capture test')
class DetrimCountAreaCaptureTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        for player in runtime.get_runtime().player_mgr.get_players(and_flags=ClientFlags.Local, min_status=PlayerStatus.Zoned):
            psf = self.get_player_scripting_framework(player)
            psf.has_detriment_type(detriment_type_tag=detrim_patterns.PERSONAL_ICON_CURSE_1)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Target casting bar area capture test')
class TargetCastingBarAreaCaptureTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        ocr = OCRServiceFactory.create_ocr_service()
        for player in self.get_runtime().playerselectors.all_logged().resolve_players():
            runtime.overlay.start_timer(player.get_player_name(), duration=5.0, severity=Severity.High)
            self.sleep(5.0)
            psf = self.get_player_scripting_framework(player)
            detrim_rect = player.get_inputs().screen.target_casting_bar
            capture = psf.capture_box(detrim_rect, mode=CaptureMode.BW)
            ocr.show_image(capture)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Request builder debug')
class RequestDebug(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        requests = [
            runtime.request_factory.drain_power_now(),
            runtime.request_factory.drain_power_once(),
            runtime.request_factory.group_cure_now(),
            runtime.request_factory.raid_group_cure_now(),
            runtime.request_factory.urgent_group_cure_now(),
            runtime.request_factory.cure_default_target_now(),
            runtime.request_factory.cure_target(ALT1_NAME),
            runtime.request_factory.cure_target_by_caster(ALT1_NAME, runtime.player_mgr.get_player_by_name(ALT2_NAME)),
            runtime.request_factory.keep_drain_power(),
            runtime.request_factory.repeated_group_curing(3.0),
            runtime.request_factory.keep_dispelling(),
            runtime.request_factory.keep_stunning(),
            runtime.request_factory.keep_interrupting(),
            runtime.request_factory.dispel_now(),
            runtime.request_factory.stun_now(),
            runtime.request_factory.interrupt_now(),
        ]
        for r in requests:
            runtime.processor.run_request(r)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Screen reader test')
class ScreenReaderTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)
        self.__subscriber_id = 'ScreenReaderTest'

    def __screen_object(self, event: ScreenReaderEvents.SCREEN_OBJECT_FOUND):
        self.get_runtime().overlay.log_event(f'SRC: {event}')

    def _on_expire(self):
        EventSystem.get_main_bus().unsubscribe_all(ScreenReaderEvents.SCREEN_OBJECT_FOUND, self.__screen_object)
        reader: IScreenReader = ServiceBroker.get_broker().get_service(IScreenReader)
        reader.unsubscribe(subscriber_id=self.__subscriber_id, tag=detrim_patterns.PERSONAL_ICON_CHAOTIC_LEECH)

    def _run(self, runtime: IRuntime):
        EventSystem.get_main_bus().subscribe(ScreenReaderEvents.SCREEN_OBJECT_FOUND(), self.__screen_object)
        reader: IScreenReader = ServiceBroker.get_broker().get_service(IScreenReader)
        # 1
        local_players = runtime.playerselectors.local_online()
        local_player = local_players.resolve_players()[0]
        window_area = CaptureArea()
        detrim_area = window_area.capture_rect(local_player.get_inputs().screen.detrim_list_window, True)
        reader.subscribe(client_ids=local_players, subscriber_id=self.__subscriber_id, tag=detrim_patterns.PERSONAL_ICON_CHAOTIC_LEECH, area=detrim_area,
                         check_period=2.0, event_period=5.0)
        # 2
        remote_players = runtime.playerselectors.all_zoned_remote()
        remote_player = remote_players.resolve_players()[0]
        window_area = CaptureArea()
        detrim_area = window_area.capture_rect(remote_player.get_inputs().screen.detrim_list_window, True)
        reader.subscribe(client_ids=remote_players, subscriber_id=self.__subscriber_id, tag=detrim_patterns.PERSONAL_ICON_CHAOTIC_LEECH, area=detrim_area,
                         check_period=5.0, event_period=10.0)
        self.sleep(30.0)


@GameScriptManager.register_game_script(ScriptCategory.TEST, 'Stealth effect testing')
class StealthEffectTest(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, None, -1.0)

    def _run(self, runtime: IRuntime):
        EventSystem.get_main_bus().subscribe(ObjectStateEvents.EFFECT_STARTED(), lambda event: print(event))
        EventSystem.get_main_bus().subscribe(ObjectStateEvents.EFFECT_CANCELLED(), lambda event: print(event))
        player = runtime.player_mgr.get_player_by_name(ALT2_NAME)
        request = runtime.request_factory.custom_request(BardAbilities.shroud, player, 5.0)
        ctrl = runtime.request_ctrl_factory.create_offzone_request_controller()
        ctrl.player_switcher.borrow_player(player)
        ctrl.processor.run_request(request)
        self.sleep(10.0)
        request = runtime.request_factory.custom_request(BardAbilities.veil_of_notes, player, 5.0)
        ctrl.processor.run_request(request)
