import time
from typing import Optional

from rka.components.concurrency.workthread import RKAFuture
from rka.components.events.event_system import EventSystem, CloseableSubscriber
from rka.components.ui.overlay import Severity, OvWarning, OvTimerStage
from rka.eq2.master import IRuntime, RequiresRuntime
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import FighterAbilities, PriestAbilities
from rka.eq2.master.game.engine.task import FilterTask, IAbilityCastingObserver
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.events.requesting import RequestEvents
from rka.eq2.master.game.interfaces import IAbility
from rka.eq2.master.game.player import TellType
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.master.parsing import get_dps_str, DpsMeasure, CombatantType
from rka.eq2.master.ui import PermanentUIEvents
from rka.eq2.parsing.parsing_util import ParsingHelpers
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.services.api.ps_connector_events import PSEvents


class OverlayInfoAbilitiesFilter(FilterTask, RequiresRuntime, IAbilityCastingObserver):
    def __init__(self):
        FilterTask.__init__(self, filter_cb=AbilityFilter(), description='filter: log ability cast', duration=-1.0)
        RequiresRuntime.__init__(self)

    @staticmethod
    def get_timer_name(ability: IAbility):
        pname = ability.player.get_player_name()[:3]
        return f'{pname}: {ability.ext.ability_name}'

    def __timer_for_ability(self, ability: IAbility):
        casting = ability.get_casting_secs()
        duration = ability.get_duration_secs()
        reuse = ability.get_reuse_secs()
        if not ability.ext.maintained:
            reuse -= duration
            reuse = max(reuse, 0)
        overlay = self.get_runtime().overlay
        if overlay is not None:
            name = OverlayInfoAbilitiesFilter.get_timer_name(ability)
            if ability.ext.timer_severity <= Severity.Low:
                reuse = 0.0
            overlay.start_timer(name=name, severity=ability.ext.timer_severity, casting=casting, duration=duration, reuse=reuse, expire=0.0)
        return True

    def notify_casting(self, ability: IAbility):
        if ability.ext.timer_severity is not None:
            self.__timer_for_ability(ability)
        log_casting = ability.ext.log_severity is not None or ability.ext.is_combo() or MutableFlags.SHOW_ALL_SPELLCASTING
        local_player_log = ability.player.is_local()  # and ability.ext.priority >= AbilityPriority.CONTROL_EFFECT
        if log_casting or local_player_log:
            default_severity = Severity.Normal if ability.ext.is_combo() else Severity.Low
            severity = ability.ext.log_severity if ability.ext.log_severity is not None else default_severity
            ability_str = ability.ability_variant_display_name()
            ability_str = f'{ability_str} COMBO' if ability.ext.is_combo() else ability_str
            self.get_runtime().overlay.log_event(ability_str, severity)


class OverlayController(CloseableSubscriber):
    def __init__(self, runtime: IRuntime):
        CloseableSubscriber.__init__(self, EventSystem.get_main_bus())
        self.__runtime = runtime
        self.__last_start_time = 0.0
        self.__last_bulwark_time = 0.0
        self.__last_barrage_caster: Optional[str] = None
        self.__barrage_warning: Optional[RKAFuture] = None

    def setup_overlay_updates(self):
        # client info
        self.subscribe(MasterEvents.CLIENT_REGISTERED(), self.__client_found)
        self.subscribe(MasterEvents.CLIENT_UNREGISTERED(), self.__client_lost)
        # tells and messages
        self.subscribe(ChatEvents.PLAYER_TELL(tell_type=TellType.tell, to_local=False), self.__tell_to_remote_player)
        self.subscribe(ChatEvents.PLAYER_TELL(to_local=True), self.__inc_countdown)
        self.subscribe(ChatEvents.POINT_AT_PLAYER(), self.__point_at_player)
        # player info
        self.subscribe(PlayerInfoEvents.FRIEND_LOGGED(), self.__friend_logged)
        self.subscribe(PlayerInfoEvents.PLAYER_LINKDEAD(), self.__player_linkdead)
        self.subscribe(PlayerInfoEvents.AUTOFOLLOW_BROKEN(), self.__autofollow_broken)
        self.subscribe(PlayerInfoEvents.AUTOFOLLOW_IMPOSSIBLE(), self.__cannot_autofollow)
        self.subscribe(PlayerInfoEvents.QUEST_OFFERED(failed=True), self.__cannot_accept_quest)
        self.subscribe(PlayerInfoEvents.ITEM_RECEIVED(), self.__item_received)
        # group state
        self.subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__player_zone_changed)
        self.subscribe(PlayerInfoEvents.PLAYER_JOINED_GROUP(), self.__player_joined_group)
        self.subscribe(PlayerInfoEvents.PLAYER_LEFT_GROUP(), self.__player_left_group)
        self.subscribe(PlayerInfoEvents.PLAYER_GROUP_DISBANDED(), self.__player_group_disbanded)
        # game object state
        self.subscribe(ObjectStateEvents.ABILITY_EXPIRED(), self.__ability_expired)
        self.subscribe(ObjectStateEvents.ABILITY_CASTING_CONFIRMED(ability_name=FighterAbilities.bulwark_of_order.get_canonical_name()), self.__bulwark_confirmed)
        self.subscribe(ObjectStateEvents.PLAYER_STATUS_CHANGED(), self.__player_status_changed)
        self.__runtime.request_ctrl_factory.add_common_processor_filter(OverlayInfoAbilitiesFilter)
        # combat events from main parser
        self.subscribe(CombatParserEvents.DPS_PARSE_START(), self.__dps_start)
        self.subscribe(CombatParserEvents.DPS_PARSE_TICK(combat_flag=True), self.__dps_tick)
        self.subscribe(CombatParserEvents.CRITICAL_STONESKIN(), self.__critical_stoneskin)
        self.subscribe(CombatParserEvents.COMBATANT_CONFIRMED(combatant_type=CombatantType.NPC), self.__combatant_joined)
        self.subscribe(CombatParserEvents.DETRIMENT_RELIEVED(ability_name=PriestAbilities.cure_curse.get_canonical_name()), self.__cure_curse_confirmed)
        self.subscribe(CombatParserEvents.EFFECT_DISPELLED(), self.__effect_dispelled)
        # combat trigger-based events
        self.subscribe(CombatEvents.PLAYER_DIED(), self.__player_died)
        self.subscribe(CombatEvents.PLAYER_REVIVED(), self.__player_revived)
        self.subscribe(CombatEvents.PLAYER_DEATHSAVED(), self.__player_deathsaved)
        self.subscribe(CombatEvents.PLAYER_SYNERGY_FADES(), self.__synergy_fades)
        self.subscribe(CombatEvents.GROUP_SYNERGY_COMPLETED(), self.__synergy_completed)
        self.subscribe(CombatEvents.ENEMY_KILL(), self.__enemy_died)
        # manual requests, also from others
        self.subscribe(RequestEvents.REQUEST_BALANCED_SYNERGY(local_player_request=False), self.__synergy_request)
        # barrage
        self.subscribe(CombatEvents.BARRAGE_PREPARED(), self.__barrage_prepared)
        self.subscribe(CombatEvents.BARRAGE_RELEASED(), self.__barrage_released)
        self.subscribe(CombatEvents.BARRAGE_CANCELLED(), self.__barrage_cancelled)
        self.subscribe(CombatEvents.READYUP(), self.__readyup)
        # HO
        self.subscribe(CombatEvents.HO_CHAIN_STARTED(), self.__start_chain_common_HO)
        self.subscribe(CombatEvents.HO_CHAIN_BROKEN(), self.__break_chain_common_HO)
        self.subscribe(CombatEvents.HO_TRIGGERED(), self.__trigger_common_HO)
        self.subscribe(CombatEvents.HO_ADVANCED(), self.__advance_common_HO)
        self.subscribe(CombatEvents.HO_COMPLETED(), self.__complete_common_HO)
        # PS-TTS connector
        self.subscribe(PSEvents.TRIGGER_RECEIVED(), self.__ps_event_received)
        self.subscribe(PSEvents.MESSAGE_RECEIVED(), self.__ps_message_received)
        self.subscribe(PSEvents.CLIENTS_RECEIVED(), self.__ps_clients_received)

    def start_timer(self):
        self.__runtime.overlay.start_timer('TIMER', duration=300.0, expire=0.0, direction=1)
        current_time = time.time()
        diff = current_time - self.__last_start_time
        if diff < 10000.0:
            self.__runtime.overlay.log_event(f'Time lapsed: {diff:.5f}', Severity.Normal)
        self.__last_start_time = current_time

    def __client_found(self, event: MasterEvents.CLIENT_REGISTERED):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        self.__runtime.overlay.log_event(f'{player.get_player_name()} connected', severity=Severity.Normal)

    def __client_lost(self, event: MasterEvents.CLIENT_UNREGISTERED):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        self.__runtime.overlay.log_event(f'{player.get_player_name()} disconnected', severity=Severity.Normal)
        if self.__runtime.combatstate.is_combat():
            self.__runtime.tts.say(f'{player.get_player_name()} lost', interrupts=False)

    def __readyup(self, event: CombatEvents.READYUP):
        if not event.player.is_local():
            return
        self.__runtime.overlay.start_timer('ReadyUp!', duration=1.0, casting=0.0, reuse=80.0, expire=60.0, severity=Severity.Normal)

    def __start_chain_common_HO(self, event: CombatEvents.HO_CHAIN_STARTED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__runtime.overlay.log_event(f'HO start: {event.caster_name}', Severity.Low)

    def __break_chain_common_HO(self, event: CombatEvents.HO_CHAIN_BROKEN):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__runtime.overlay.log_event(f'HO break: {event.caster_name}', Severity.Low)

    def __trigger_common_HO(self, event: CombatEvents.HO_TRIGGERED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__runtime.overlay.log_event(f'HO trigger: {event.caster_name}, {event.ho_name}', Severity.Low)

    def __advance_common_HO(self, event: CombatEvents.HO_ADVANCED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__runtime.overlay.log_event(f'HO advanced: {event.caster_name}, {event.ho_name}', Severity.Low)

    def __complete_common_HO(self, event: CombatEvents.HO_COMPLETED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__runtime.overlay.log_event(f'HO completed: {event.caster_name}, {event.ho_name}', Severity.Low)

    def __bulwark_confirmed(self, _event: ObjectStateEvents.ABILITY_CASTING_CONFIRMED):
        self.__runtime.overlay.log_event(f'Bulwark OK', Severity.Low)
        if self.__barrage_warning:
            self.__barrage_warning.cancel_future()
        self.__runtime.overlay.display_warning(warning_text='OK', duration=1.5)
        self.__last_bulwark_time = time.time()

    def __barrage_timer(self, casting: float):
        warnings = [OvWarning(stage=OvTimerStage.Expire, offset=-2.0, action=lambda: self.__runtime.alerts.micro_trigger())]
        self.__runtime.overlay.start_timer(f'Barrage', duration=5.0, casting=casting, reuse=40.0, expire=10.0, severity=Severity.Low, warnings=warnings)

    def __barrage_prepared(self, event: CombatEvents.BARRAGE_PREPARED):
        self.__runtime.overlay.log_event(f'Barrage PREPARE at {event.target_name}', Severity.Low)
        self.__barrage_timer(casting=5.0)
        shared_scheduler.schedule(lambda: self.__runtime.alerts.major_trigger(), delay=2.0)
        if event.your_group:
            if time.time() - self.__last_bulwark_time >= 10.0:
                self.__last_barrage_caster = event.caster_name
                self.__barrage_warning = shared_scheduler.schedule(lambda: self.__runtime.overlay.display_warning('BARRAGE', duration=4.0), delay=3.0)

    def __barrage_released(self, event: CombatEvents.BARRAGE_RELEASED):
        self.__runtime.overlay.log_event(f'Barrage RELEASE at {event.target_name}', Severity.Low)
        # update the timer, preparation period may be more than its casting time actually
        self.__barrage_timer(casting=0.0)
        self.__last_barrage_caster = None

    def __barrage_cancelled(self, _event: CombatEvents.BARRAGE_CANCELLED):
        self.__runtime.overlay.log_event('Barrage CANCEL', Severity.Low)
        self.__runtime.overlay.del_timer(f'Barrage')
        if self.__barrage_warning:
            self.__barrage_warning.cancel_future()
        self.__runtime.overlay.display_warning('cancel', conditional_text='BARRAGE', duration=1.5)
        self.__last_barrage_caster = None

    def __enemy_died(self, event: CombatEvents.ENEMY_KILL):
        if self.__barrage_warning and self.__last_barrage_caster == event.enemy_name:
            self.__barrage_warning.cancel_future()
        self.__last_barrage_caster = None

    def __combatant_joined(self, event: CombatParserEvents.COMBATANT_CONFIRMED):
        if not ParsingHelpers.is_boss(event.combatant_name):
            return
        self.__runtime.overlay.start_timer(name=f'BURN', duration=27.0, expire=0.0, severity=Severity.High, replace_stage=OvTimerStage.Expire)

    def __cure_curse_confirmed(self, event: CombatParserEvents.DETRIMENT_RELIEVED):
        player = self.__runtime.player_mgr.resolve_player(event.by_combatant)
        if player:
            ability = PriestAbilities.cure_curse.resolve_for_player(player)
            if not ability:
                return
        else:
            abilities = PriestAbilities.cure_curse.resolve()
            if not abilities:
                return
            ability = abilities[0]
        reuse = ability.get_reuse_secs()
        self.__runtime.overlay.start_timer(name=f'CC|{event.by_combatant}', casting=0.0, duration=0.0, reuse=reuse, expire=5.0, severity=Severity.Normal)

    def __player_deathsaved(self, event: CombatEvents.PLAYER_DEATHSAVED):
        self.__runtime.tts.say('death')
        self.__runtime.overlay.log_event(f'{event.player} deathsaved', Severity.Normal)

    def __player_linkdead(self, event: PlayerInfoEvents.PLAYER_LINKDEAD):
        self.__runtime.overlay.log_event(f'{event.player} linkdead', Severity.High)

    def __autofollow_broken(self, event: PlayerInfoEvents.AUTOFOLLOW_BROKEN):
        self.__runtime.overlay.log_event(f'{event.player} no longer following {event.followed_player_name}', Severity.Normal)
        self.__runtime.alerts.minor_trigger()

    def __cannot_autofollow(self, event: PlayerInfoEvents.AUTOFOLLOW_IMPOSSIBLE):
        self.__runtime.overlay.log_event(f'{event.player} cant follow', Severity.Normal)
        self.__runtime.alerts.micro_trigger()

    def __cannot_accept_quest(self, event: PlayerInfoEvents.QUEST_OFFERED):
        self.__runtime.overlay.log_event(f'{event.player} cant accept quest', Severity.Normal)
        self.__runtime.alerts.micro_trigger()

    def __item_received(self, event: PlayerInfoEvents.ITEM_RECEIVED):
        self.__runtime.overlay.log_event(f'{event.player} got {event.item_name}', Severity.Low)

    def __point_at_player(self, event: ChatEvents.POINT_AT_PLAYER):
        self.__runtime.overlay.log_event(f'{event.pointing_player} points at {event.pointed_player_name}', Severity.Normal)

    def __friend_logged(self, event: PlayerInfoEvents.FRIEND_LOGGED):
        inout = 'in' if event.login else 'out'
        self.__runtime.overlay.log_event(f'Friend: {event.friend_name} log {inout}', Severity.Normal)

    def __synergy_request(self, _event: RequestEvents.REQUEST_BALANCED_SYNERGY):
        self.__runtime.tts.say(f'synergy')

    def __synergy_fades(self, _event: CombatEvents.PLAYER_SYNERGY_FADES):
        self.__runtime.overlay.del_timer('SYNERGY')

    def __synergy_completed(self, _event: CombatEvents.GROUP_SYNERGY_COMPLETED):
        self.__runtime.overlay.start_timer(name='SYNERGY', casting=0.0, duration=30.0, severity=Severity.Low)

    def __inc_countdown(self, event: ChatEvents.PLAYER_TELL):
        if 'Inc in 10' in event.tell:
            time_name = 'INC 10'
            self.__runtime.overlay.start_timer(name=time_name, duration=10.0, expire=0.0, severity=Severity.Critical)
            self.__runtime.tts.say('Incoming in 10')
        elif 'Inc in 15' in event.tell:
            time_name = 'INC 15'
            self.__runtime.overlay.start_timer(name=time_name, duration=15.0, expire=0.0, severity=Severity.Critical)
            self.__runtime.tts.say('Incoming in 15')
        elif 'PAUSE 15' in event.tell:
            time_name = 'PAUSE'
            self.__runtime.overlay.start_timer(name=time_name, duration=15.0 * 60.0, expire=0.0, severity=Severity.Critical)

    def __tell_to_remote_player(self, event: ChatEvents.PLAYER_TELL):
        from_player = self.__runtime.player_mgr.get_player_by_name(event.from_player_name)
        if from_player:
            # only show other player's tells
            return
        text = f'{event.from_player_name} to {event.to_player}: {event.tell}'
        self.__runtime.overlay.log_event(text, Severity.Normal)

    def __dps_start(self, event: CombatParserEvents.DPS_PARSE_START):
        self.__runtime.overlay.log_event(f'{event.attacker_name[:10]} pulled {event.target_name}', Severity.Normal)

    def __dps_tick(self, _event: CombatParserEvents.DPS_PARSE_TICK):
        current_dps = self.__runtime.current_dps
        if not current_dps:
            parse_str = '(wait init)'
        else:
            parse_str = current_dps.get_parse_info_str(combatant_limit=7, add_inc_dps=True, add_combat_duration=True, add_inc_spike=True)
            self.__tint_screen()
        self.__runtime.overlay.update_parse_window(parse_str)

    def __tint_screen(self):
        if not MutableFlags.SHOW_INCOMING_DAMAGE_TINT:
            return
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            return
        current_dps = self.__runtime.current_dps
        if not current_dps:
            return
        combatant_record = current_dps.get_combatant_record(main_player.get_player_name())
        if not combatant_record:
            return
        hitpoints = main_player.get_player_info().health
        instant_received = combatant_record.get_hitpoints_damage(DpsMeasure.INSTANT)
        instant_warded = combatant_record.get_consumed_wards(DpsMeasure.INSTANT)
        if instant_received > 1.0 * hitpoints:
            # gray, critical
            self.__runtime.overlay.set_screen_tint(127, 127, 127, 60, duration=1.2)
        elif instant_received > 0.8 * hitpoints:
            # red, urgent
            self.__runtime.overlay.set_screen_tint(200, 0, 0, 45, duration=1.2)
        elif instant_warded > 1.0 * hitpoints:
            if instant_received > 0.6 * hitpoints:
                # orange, safe but bleeding
                self.__runtime.overlay.set_screen_tint(200, 150, 0, 45, duration=1.2)
            else:
                # green, safe but hardly
                self.__runtime.overlay.set_screen_tint(0, 200, 200, 35, duration=1.2)

    def __player_status_changed(self, event: ObjectStateEvents.PLAYER_STATUS_CHANGED):
        self.__runtime.overlay.set_status(event.player.get_client_config_data().overlay_id,
                                          event.player.get_player_name(),
                                          event.player.get_status().get_display_severity())
        self.__runtime.overlay.log_event(f'{event.player.get_player_name()} status {event.player.get_status().name}', Severity.Low)

    def __player_zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        if event.player.is_main_player():
            self.__runtime.overlay.log_event(f'Zone: {event.player.get_zone()}', Severity.Critical, event_id=PermanentUIEvents.ZONE.str())
        else:
            self.__runtime.overlay.log_event(f'{event.player.get_player_name()} zoned to {event.player.get_zone()}', Severity.Low)

    def __player_joined_group(self, event: PlayerInfoEvents.PLAYER_JOINED_GROUP):
        self.__runtime.overlay.log_event(f'{event.player_name} joined group', Severity.Low)

    def __player_left_group(self, event: PlayerInfoEvents.PLAYER_LEFT_GROUP):
        self.__runtime.overlay.log_event(f'{event.player_name} left group', Severity.Low)

    def __player_group_disbanded(self, _event: PlayerInfoEvents.PLAYER_GROUP_DISBANDED):
        self.__runtime.overlay.log_event(f'group is disbanded', Severity.Low)

    def __player_died(self, event: CombatEvents.PLAYER_DIED):
        self.__runtime.overlay.log_event(f'{event.player.get_player_name()} died', Severity.Normal)
        if event.player.is_local():
            current_dps = self.__runtime.current_dps
            if not current_dps:
                return
            cr = current_dps.get_combatant_record(event.player.get_player_name())
            if not cr:
                return
            inc_instant = cr.get_incoming_damage(DpsMeasure.INSTANT)
            inc_recent = cr.get_incoming_damage(DpsMeasure.RECENT)
            self.__runtime.overlay.log_event(f'instant damage: {get_dps_str(inc_instant)}', Severity.High)
            self.__runtime.overlay.log_event(f'recent inc dps: {get_dps_str(inc_recent)}', Severity.High)

    def __player_revived(self, event: CombatEvents.PLAYER_REVIVED):
        self.__runtime.overlay.log_event(f'{event.player.get_player_name()} revived', Severity.Normal)

    def __critical_stoneskin(self, event: CombatParserEvents.CRITICAL_STONESKIN):
        self.__runtime.overlay.log_event(f'**stoneskin** {event.amount_readable}', Severity.Normal)
        self.__runtime.alerts.micro_trigger()

    def __ability_expired(self, event: ObjectStateEvents.ABILITY_EXPIRED):
        ability = event.ability
        if not ability.ext.timer_severity:
            return
        name = OverlayInfoAbilitiesFilter.get_timer_name(ability)
        self.__runtime.overlay.del_timer(name)
        if ability.ext.timer_severity <= Severity.Low:
            return
        overlay = self.__runtime.overlay
        reuse = ability.get_reuse_secs()
        if not ability.ext.maintained:
            reuse -= ability.get_duration_secs()
            reuse = max(reuse, 0)
        overlay.start_timer(name=name, severity=ability.ext.timer_severity, casting=0.0, duration=0.0, reuse=reuse, expire=0.0)

    def __effect_dispelled(self, event: CombatParserEvents.EFFECT_DISPELLED):
        for ability in self.__runtime.request_ctrl.get_dispelled_abilities(event.effect_name, event.from_combatant):
            if ability.ext.is_maintained_buff():
                self.__runtime.overlay.log_event(f'Lost buff: {ability}', Severity.Low)

    def __ps_event_received(self, event: PSEvents.TRIGGER_RECEIVED):
        self.__runtime.overlay.log_event(f'PS: {event.trigger_event_data.message}', Severity.Normal)
        if event.trigger_event_data.voice_message:
            self.__runtime.tts.say(event.trigger_event_data.voice_message)

    def __ps_message_received(self, event: PSEvents.MESSAGE_RECEIVED):
        self.__runtime.overlay.log_event(f'PS: {event.message}', Severity.Normal)

    def __ps_clients_received(self, event: PSEvents.CLIENTS_RECEIVED):
        self.__runtime.overlay.log_event(f'PS: {len(event.clients)} clients connected', Severity.Low)
