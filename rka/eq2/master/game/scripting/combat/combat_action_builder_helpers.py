from __future__ import annotations

import enum
import time
from threading import RLock
from typing import Optional, Dict, Tuple, List, Callable, Union

from rka.components.common_events import CommonEvents
from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.workthread import RKAFuture
from rka.components.events import Event
from rka.components.events.event_system import IEventBus, EventSystem
from rka.components.resources import Resource
from rka.components.ui.capture import Rect
from rka.components.ui.overlay import Severity
from rka.components.ui.tts import ITTSSession
from rka.eq2.configs.master.friends import Friends
from rka.eq2.configs.shared.rka_constants import STAY_IN_VOICE
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability.generated_abilities import FighterAbilities, PriestAbilities, ScoutAbilities, MageAbilities
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.gameclass import GameClass, GameClasses
from rka.eq2.master.game.interfaces import IPlayer, IAbility, IPlayerSelector
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.scripting import RaidSlotInfo
from rka.eq2.master.game.scripting.combat import logger, ICombatPhase
from rka.eq2.master.game.scripting.combat.combat_action_builder import CombatPhaseActionBuilder, CombatScriptBuilderCustomAction
from rka.eq2.master.game.scripting.combat.combat_actions import GroupRaidPlayersCheckerAction
from rka.eq2.master.game.scripting.framework import PlayerScriptingFramework
from rka.eq2.master.game.scripting.scripts.movement_scripts import PlayerActionTrip, FollowLocationsScript, MoveCureReturn
from rka.eq2.master.parsing import CombatantType
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_scheduler
from rka.services.api.ps_connector import IPSConnector
from rka.services.broker import ServiceBroker


class HeroicOpportunityHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase, fixed_archetype: Optional[GameClass] = None):
        CombatScriptBuilderCustomAction.__init__(self, 'Heroic Opportunity Helper', phase)
        self.__fixed_archetype = fixed_archetype
        self.__requested_player: Optional[IPlayer] = None

    def build_phase(self, builder: CombatPhaseActionBuilder):
        with builder.add_new_trigger('HO started') as trigger:
            trigger.add_bus_event(CombatEvents.HO_CHAIN_STARTED())
            trigger.add_action(self.__HO_started)
        with builder.add_new_trigger('request HO') as trigger:
            trigger.add_bus_event(ChatEvents.POINT_AT_PLAYER())
            trigger.add_action(self.__request_HO)
        builder.add_single_task(self.__set_default_HO, delay=0.0)
        builder.add_disable_ascensions()

    def set_fixed_archetype(self, fixed_archetype: GameClass):
        self.__fixed_archetype = fixed_archetype
        self.__requested_player = None
        self.__set_default_HO()

    def set_fixed_player(self, fixed_player: IPlayer):
        self.__fixed_archetype = None
        self.__requested_player = fixed_player
        self.__set_default_HO()

    def __get_effective_archetype(self) -> Optional[GameClass]:
        if self.__requested_player:
            return self.__requested_player.get_adventure_class().get_archetype()
        elif self.__fixed_archetype:
            return self.__fixed_archetype
        return None

    def request_HO(self):
        archetype = self.__get_effective_archetype()
        if archetype:
            self.get_runtime().request_ctrl.request_HO_starter(self.__requested_player if self.__requested_player else archetype)
            self.get_runtime().request_ctrl.request_HO_solo_trigger(archetype)

    def trigger_HO(self):
        archetype = self.__get_effective_archetype()
        if archetype:
            self.get_runtime().request_ctrl.request_HO_solo_trigger(archetype)

    def __set_default_HO(self):
        if self.__fixed_archetype:
            self.get_runtime().request_ctrl.set_HO_default_starter(self.__fixed_archetype)

    def __HO_started(self, _event: CombatEvents.HO_CHAIN_STARTED):
        self.trigger_HO()

    def __request_HO(self, event: ChatEvents.POINT_AT_PLAYER):
        if not event.pointed_player:
            return
        self.__requested_player = event.pointed_player
        self.request_HO()


class BalancedSynergyHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase):
        CombatScriptBuilderCustomAction.__init__(self, 'Balanced Synergy Helper', phase)
        self.__synergies: Dict[str, Tuple[float, str, RKAFuture]] = dict()
        synergy = FighterAbilities.balanced_synergy.resolve_for_player_default_all(None)[0]
        self.__synergy_duration = synergy.census.duration

    def build_phase(self, builder: CombatPhaseActionBuilder):
        with builder.add_new_trigger('synergizes') as trigger:
            trigger.add_bus_event(CombatEvents.PLAYER_SYNERGIZED())
            trigger.add_action(self.__synergizes)
        with builder.add_new_trigger('fades') as trigger:
            trigger.add_bus_event(CombatEvents.PLAYER_SYNERGY_FADES())
            trigger.add_action(self.__synergy_fades)

    def update_synergy_monitor(self):
        self.get_runtime().overlay.del_timer('SYNERGY-OK')
        for i in range(6):
            self.get_runtime().overlay.del_timer(f'SYNERGY-{i + 1}')
        if not self.__synergies:
            return
        check_classes = {
            GameClasses.Priest: False,
            GameClasses.Scout: False,
            GameClasses.Fighter: False,
            GameClasses.Mage: False,
        }
        start_times = []
        for player_name, (start_time, reported_by, future) in self.__synergies.items():
            start_times.append(start_time)
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            if player:
                adv_class = player.get_adventure_class()
                if not adv_class:
                    logger.warn(f'Missing advnture class for {player}')
                    continue
                archetype = adv_class.get_archetype()
                check_classes[archetype] = True
            elif player_name in Friends.__dict__:
                gameclass = Friends[player_name]
                logger.info(f'Synergized by a friend {player_name}: {gameclass}')
                check_classes[gameclass.value.get_archetype()] = True
        earlierst_start = min(start_times)
        now = time.time()
        remaining_duration = self.__synergy_duration - (now - earlierst_start)
        if remaining_duration <= 0.0:
            return
        all_classes = all(check_classes.values())
        synergy_log = ','.join([player_name[:4] for player_name in self.__synergies.keys()])
        sign = '+' if all_classes else '-'
        self.get_runtime().overlay.log_event(f'SYN{sign} [{synergy_log}]')
        if all_classes:
            self.get_runtime().overlay.start_timer('SYNERGY-OK', duration=remaining_duration, severity=Severity.High)
            self.__synergy_ready()
            return
        player_count = min(6, len(self.__synergies))
        self.get_runtime().overlay.start_timer(f'SYNERGY-{player_count}', duration=remaining_duration, severity=Severity.High)

    def cancel_synergy(self, player_name: str):
        if player_name not in self.__synergies:
            return
        start_time, reported_by, future = self.__synergies[player_name]
        future.cancel_future()
        del self.__synergies[player_name]
        self.update_synergy_monitor()

    # noinspection PyMethodMayBeStatic
    def __match_synergy(self, ability: IAbility) -> bool:
        if ability.locator in [MageAbilities.balanced_synergy, PriestAbilities.balanced_synergy, ScoutAbilities.balanced_synergy, FighterAbilities.balanced_synergy]:
            return True
        return False

    def __synergizes(self, event: CombatEvents.PLAYER_SYNERGIZED):
        player_name = event.caster_name
        logger.info(f'{player_name} synergized with the group')
        if player_name in self.__synergies:
            start_time, reported_by, future = self.__synergies[player_name]
            if event.reported_by_player != reported_by:
                return
            logger.warn(f'Player {player_name} already synergized')
            future.cancel_future()
        future = shared_scheduler.schedule(lambda: self.cancel_synergy(player_name), delay=self.__synergy_duration)
        self.__synergies[player_name] = (time.time(), event.reported_by_player, future)
        self.update_synergy_monitor()

    def __synergy_fades(self, event: CombatEvents.PLAYER_SYNERGY_FADES):
        logger.info(f'{event.caster_name}\'s synergy faded')
        self.cancel_synergy(event.caster_name)

    def __synergy_ready(self):
        self.get_runtime().overlay.log_event(f'SYNERGY READY (COUNTER)', Severity.Normal)


class TargetSelfAndCurefHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase,
                 detriment_tag: Resource, is_curse=True, detriment_name: Optional[str] = None,
                 mage_cure=False, check_period=1.0, check_pause=10.0):
        CombatScriptBuilderCustomAction.__init__(self, 'Target self and cure helper', phase)
        self.__detriment_tag = detriment_tag
        self.__is_curse = is_curse
        self.__detriment_name = detriment_name
        self.__mage_cure = mage_cure
        self.__check_period = check_period
        self.__check_pause = check_pause

    def build_phase(self, builder: CombatPhaseActionBuilder):
        phase = self.get_phase()
        builder.add_detect_personal_detrim(players=phase.get_phase_participants(include_local=True),
                                           task=lambda player_, location_: self.__check_your_curse(phase, player_, location_),
                                           detrim_tag=self.__detriment_tag,
                                           check_period=self.__check_period,
                                           check_pause=self.__check_pause)
        combatant_name = phase.get_combat_script().get_combatant_name()
        if self.__detriment_name:
            with builder.add_new_trigger('cured') as trigger:
                trigger.add_bus_event(CombatParserEvents.DETRIMENT_RELIEVED(detriment_name=self.__detriment_name.lower()))
                trigger.add_action(lambda event_: self.__restore_target_event(event_, combatant_name))
        elif self.__is_curse:
            with builder.add_new_trigger('cured') as trigger:
                trigger.add_bus_event(CombatParserEvents.DETRIMENT_RELIEVED(is_curse=True))
                trigger.add_action(lambda event_: self.__restore_target_event(event_, combatant_name))

    def __check_your_curse(self, phase: ICombatPhase, player: IPlayer, _location: Rect):
        self.get_runtime().combatstate.set_players_target(players=player, target_name=player.get_player_name())
        if self.__is_curse:
            self.get_runtime().request_ctrl.request_cure_curse_target(player.get_player_name())
        elif self.__mage_cure:
            self.get_runtime().request_ctrl.request_mage_cure_target(player.get_player_name())
        else:
            self.get_runtime().request_ctrl.request_cure_target(player.get_player_name())
        self.get_runtime().tts.say(f'target yourself {player.get_player_name()}')
        self.get_runtime().overlay.display_warning('CURSE', 1.0)
        combatant_name = phase.get_combat_script().get_combatant_name()
        phase.get_combat_script().get_scheduler().schedule(lambda: self.__restore_target(player, combatant_name), delay=10.0)

    def __restore_target(self, player: IPlayer, combatant_name: str):
        self.get_runtime().overlay.log_event(f'Restoring target {combatant_name} for {player}', Severity.Normal)
        self.get_runtime().combatstate.set_players_target(players=player, target_name=combatant_name)

    def __restore_target_event(self, event: CombatParserEvents.DETRIMENT_RELIEVED, combatant_name: str):
        if not CombatantType.is_my_player(event.from_combatant_type):
            return
        player = self.get_runtime().player_mgr.get_player_by_name(event.from_combatant)
        if player:
            self.__restore_target(player, combatant_name)


class RaidDetrimMonitorfHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase,
                 detriment_tag: Resource,
                 use_tts: bool, use_warning: bool, tts: Optional[ITTSSession] = None,
                 check_period=1.0, repeat_delay=10.0,
                 player_name_cb: Optional[Callable[[str], bool]] = None,
                 check_local_player=True):
        CombatScriptBuilderCustomAction.__init__(self, 'Monitor raid detrims', phase)
        self.__detriment_tag = detriment_tag
        self.__use_tts = use_tts
        self.__use_warning = use_warning
        self.__tts = tts
        self.__check_period = check_period
        self.__repeat_delay = repeat_delay
        self.__player_name_cb = player_name_cb
        self.__check_local_player = check_local_player

    def build_phase(self, builder: CombatPhaseActionBuilder):
        phase = self.get_phase()
        builder.add_detect_raid_detrims(task=self.__check_detriments,
                                        detrim_tag=self.__detriment_tag,
                                        check_period=self.__check_period,
                                        check_pause=self.__repeat_delay)
        builder.add_custom_action(GroupRaidPlayersCheckerAction(phase, check_raid=True))

    def __accept_raid_member(self, raid_slot: RaidSlotInfo, raid_member: Optional[str], local_player_name: str) -> bool:
        if not raid_member:
            logger.warn(f'no raid member name for {raid_slot}')
            return False
        if not self.__check_local_player and raid_member == local_player_name:
            return False
        return True

    def __check_detriments(self, raid_slots: List[RaidSlotInfo]):
        psf = self.get_combat_script().get_local_player_scripting_framework()
        if not psf:
            logger.error('Cannot check raider names, no local PSF')
            return
        local_player_name = psf.get_player().get_player_name()
        for raid_slot in raid_slots:
            raid_member = raid_slot.get_raid_member_name(self.get_runtime())
            logger.debug(f'Detrim {self.__detriment_tag} found at {raid_slot}, raider {raid_member}. tts={self.__use_tts}, warn={self.__use_warning}, cb={self.__player_name_cb}')
        if self.__use_tts:
            for raid_slot in raid_slots:
                raid_member = raid_slot.get_raid_member_name(self.get_runtime())
                if not self.__accept_raid_member(raid_slot, raid_member, local_player_name):
                    continue
                tts = self.__tts if self.__tts else self.get_runtime().tts
                tts.say(f'check {raid_member}')
                break
        if self.__use_warning:
            for raid_slot in raid_slots:
                raid_member = raid_slot.get_raid_member_name(self.get_runtime())
                if not self.__accept_raid_member(raid_slot, raid_member, local_player_name):
                    continue
                if self.get_runtime().player_mgr.get_player_by_name(raid_member):
                    self.get_runtime().overlay.display_warning(raid_member, 1.0)
                    break
        if self.__player_name_cb:
            for raid_slot in raid_slots:
                raid_member = raid_slot.get_raid_member_name(self.get_runtime())
                if not self.__accept_raid_member(raid_slot, raid_member, local_player_name):
                    continue
                if not self.__player_name_cb(raid_member):
                    break


class TTSHelper(CombatScriptBuilderCustomAction, ITTSSession):
    class TTSType(enum.Enum):
        DISCORD = enum.auto()
        PS = enum.auto()
        TTS = enum.auto()

        def create_session(self, runtime: IRuntime) -> ITTSSession:
            logger.debug(f'Create TTS session for TTS type {self}')
            if self == TTSHelper.TTSType.DISCORD:
                session = runtime.group_tts.open_session(STAY_IN_VOICE)
                return session
            if self == TTSHelper.TTSType.PS:
                session: IPSConnector = ServiceBroker.get_broker().get_service(IPSConnector)
                return session
            return runtime.tts

    def __init__(self, phase: ICombatPhase, close_session_when_stopped=False):
        CombatScriptBuilderCustomAction.__init__(self, 'TTSHelper', phase)
        self.__close_session_when_stopped = close_session_when_stopped
        self.__tts: Optional[ITTSSession] = None
        self.__tts_lock = RLock()
        self.__group_checker = GroupRaidPlayersCheckerAction(phase, check_raid=False)

    def build_phase(self, builder: CombatPhaseActionBuilder):
        builder.add_custom_action(self.__group_checker)
        builder.add_single_task(self.__get_tts_session, delay=3.0)

    def __voice_flag_changed(self, _event: CommonEvents.FLAG_CHANGED):
        self.close_session()

    def _phase_prepared(self):
        EventSystem.get_main_bus().subscribe(CommonEvents.FLAG_CHANGED(flag_name=MutableFlags.DISCORD_GROUP_VOICE.name), self.__voice_flag_changed)
        EventSystem.get_main_bus().subscribe(CommonEvents.FLAG_CHANGED(flag_name=MutableFlags.PS_GROUP_VOICE.name), self.__voice_flag_changed)

    def _phase_stopped(self):
        if self.__close_session_when_stopped:
            self.close_session()
        EventSystem.get_main_bus().unsubscribe_all(CommonEvents.FLAG_CHANGED, self.__voice_flag_changed)

    def __get_tts_session(self) -> ITTSSession:
        with self.__tts_lock:
            if self.__tts and self.__tts.is_session_open():
                return self.__tts
            has_other_players = self.__group_checker.has_other_players()
            if has_other_players:
                if MutableFlags.DISCORD_GROUP_VOICE:
                    tts_type = TTSHelper.TTSType.DISCORD
                elif MutableFlags.PS_GROUP_VOICE:
                    tts_type = TTSHelper.TTSType.PS
                else:
                    tts_type = TTSHelper.TTSType.TTS
            else:
                tts_type = TTSHelper.TTSType.TTS
            logger.info(f'TTSHelper type decided is {tts_type}, other players = {has_other_players}')
            self.__tts = tts_type.create_session(self.get_runtime())
            self.__tts.get_ready()
            return self.__tts

    def get_ready(self) -> bool:
        # TTS will be ready as soon as group setup is checked
        return True

    def say(self, text: str, interrupts=False) -> bool:
        logger.info(f'TTSHelper.say: {text} with {self.__tts.__class__}')
        tts = self.__get_tts_session()
        retry_with_default = tts != self.get_runtime().tts
        self.get_runtime().overlay.log_event(text, Severity.Normal)
        result = tts.say(text)
        if not result and retry_with_default:
            logger.info(f'TTSHelper.say: failed to say {text}, using default')
            return self.get_runtime().tts.say(text, interrupts)
        return result

    def is_session_open(self) -> bool:
        with self.__tts_lock:
            return self.__tts and self.__tts.is_session_open()

    def close_session(self):
        with self.__tts_lock:
            if self.__tts and self.__tts != self.get_runtime().tts:
                self.__tts.close_session()
            self.__tts = None


class ScheduledActionCanceller(CombatScriptBuilderCustomAction):
    class _Subscription:
        def __init__(self, scheduler: RKAScheduler, action: Callable, delay: float, event: Event, bus: IEventBus, action_id: Optional[str]):
            self.__action = action
            self.__event = event
            self.__bus = bus
            self.__future = scheduler.schedule(self.__call_action, delay)
            self.__lock = RLock()
            self.__is_done = False
            self.action_id = action_id
            bus.subscribe(event, self.__event_received)

        def __call_action(self):
            with self.__lock:
                if self.__is_done:
                    return
                self.__is_done = True
            logger.debug(f'ScheduledActionCanceller: call action: {self.__action}, cancel event {self.__event}')
            self.__action()
            self.__bus.unsubscribe(self.__event, self.__event_received)

        def __event_received(self, _event: Event):
            logger.debug(f'ScheduledActionCanceller: event received: {self.__event}')
            self.cancel()

        def is_done(self) -> bool:
            with self.__lock:
                return self.__is_done

        def cancel(self):
            with self.__lock:
                if self.__is_done:
                    return
                self.__is_done = True
            logger.debug(f'ScheduledActionCanceller: cancel calling {self.__action}, with event {self.__event}')
            self.__future.cancel_future()
            self.__bus.unsubscribe(self.__event, self.__event_received)

    def __init__(self, phase: ICombatPhase):
        CombatScriptBuilderCustomAction.__init__(self, 'Scheduled action canceller', phase)
        self.__subscribed_events: List[ScheduledActionCanceller._Subscription] = list()
        self.__lock = RLock()

    def build_phase(self, builder: CombatPhaseActionBuilder):
        pass

    def do_this_unless_event(self, action: Callable, delay: float, event: Event, bus: Optional[IEventBus] = None, action_id: Optional[str] = None):
        logger.info(f'do_this_unless_event: {action} in {delay}, cancel event {event}')
        scheduler = self.get_combat_script().get_scheduler()
        if not bus:
            bus = EventSystem.get_main_bus()
        with self.__lock:
            # cancel previous action of same ID, but also purge the list from time to time
            remove_subs = list()
            for sub in self.__subscribed_events:
                if (action_id and action_id == sub.action_id) or sub.is_done():
                    remove_subs.append(sub)
            for sub in remove_subs:
                self.__subscribed_events.remove(sub)
            new_sub = ScheduledActionCanceller._Subscription(scheduler, action, delay, event, bus, action_id)
            self.__subscribed_events.append(new_sub)
        for sub in remove_subs:
            sub.cancel()

    def _phase_prepared(self):
        with self.__lock:
            if self.__subscribed_events:
                logger.warn(f'Subscriptions not cleared in {self}')
                self.__subscribed_events.clear()

    def _phase_stopped(self):
        with self.__lock:
            subs = list(self.__subscribed_events)
            self.__subscribed_events.clear()
        for sub in subs:
            sub.cancel()


class MovementHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase):
        CombatScriptBuilderCustomAction.__init__(self, 'Movement helper', phase)
        self.__builder: Optional[CombatPhaseActionBuilder] = None

    def build_phase(self, builder: CombatPhaseActionBuilder):
        self.__builder = builder

    def _phase_prepared(self):
        pass

    def _phase_stopped(self):
        pass

    def __resolve_location(self, loc: Union[None, str, Location]) -> Optional[Location]:
        if loc is None:
            return None
        if isinstance(loc, Location):
            return loc
        assert isinstance(loc, str)
        script_loc = self.get_combat_script().get_location(loc)
        if script_loc:
            return script_loc
        return Location.decode_location(loc)

    def __resolve_locations(self, move_to: Union[str, Location, List[Union[str, Location]]]):
        if isinstance(move_to, (Location, str)):
            return self.__resolve_location(move_to)
        return [self.__resolve_location(loc) for loc in move_to]

    def __run_movement_script(self, script: FollowLocationsScript, allow_cancel: bool):
        player = script.player
        if not allow_cancel:
            script.disable_cancel_reason(reason=FollowLocationsScript.CancelReason.FOLLOW)
            script.disable_cancel_reason(reason=FollowLocationsScript.CancelReason.STOP_FOLLOW)
        self.get_runtime().automation.autopilot.register_custom_movement_script(player=player, movement_script=script)
        script_queue_name = f'{player.get_player_name()}-movement'
        self.__builder.add_preemptive_script(script_queue_name, script, restart_delay=1.0)

    def player_move_and_cure(self, player: Union[IPlayer, str], curse: bool, move_to: Union[str, Location, List[Union[str, Location]]],
                             return_to: Optional[Union[str, Location]] = None, allow_cancel=True):
        return_to = self.__resolve_location(return_to)
        move_to = self.__resolve_locations(move_to)
        logger.info(f'{player} cure at {move_to}')
        if not self.get_phase().is_phase_participant(player):
            logger.warn(f'MovementHelper.player_cure_at_and_return: {player} is not phase participant!')
            return
        script = MoveCureReturn(player, move_to=move_to, curse=curse, return_to=return_to)
        self.__run_movement_script(script=script, allow_cancel=allow_cancel)

    def player_joust_to(self, player: Union[IPlayer, str], move_to: Union[str, Location, List[Union[str, Location]]],
                        stay_time=0.0, return_to: Optional[Union[str, Location]] = None, do_return=True, allow_cancel=True,
                        action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        return_to = self.__resolve_location(return_to)
        move_to = self.__resolve_locations(move_to)
        logger.info(f'{player} joust to {move_to}, wait {stay_time}, return to {return_to}')
        if not self.get_phase().is_phase_participant(player):
            logger.warn(f'MovementHelper.player_joust_to: {player} is not phase participant!')
            return
        script = PlayerActionTrip(player, move_to=move_to, wait_after_moving=stay_time,
                                  return_movement=do_return, return_to=return_to, action=action)
        self.__run_movement_script(script=script, allow_cancel=allow_cancel)

    def players_joust_to(self, player_sel: IPlayerSelector, move_to: Union[str, Location, List[Union[str, Location]]],
                         stay_time=0.0, return_to: Optional[Union[str, Location]] = None, do_return=True, allow_cancel=True,
                         action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        for player in player_sel:
            self.player_joust_to(player=player, move_to=move_to, stay_time=stay_time, return_to=return_to, do_return=do_return,
                                 allow_cancel=allow_cancel, action=action)

    def all_players_joust_to(self, move_to: Union[str, Location, List[Union[str, Location]]], stay_time=0.0,
                             return_to: Optional[Union[str, Location]] = None, do_return=True, allow_cancel=True,
                             action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        players = self.get_phase().get_phase_participants(include_local=False)
        self.players_joust_to(player_sel=players, move_to=move_to, stay_time=stay_time, return_to=return_to, do_return=do_return,
                              allow_cancel=allow_cancel, action=action)

    def player_move_to(self, player: IPlayer, move_to: Union[str, Location, List[Union[str, Location]]], allow_cancel=True,
                       action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        self.player_joust_to(player=player, move_to=move_to, do_return=False, stay_time=0.0, allow_cancel=allow_cancel,
                             action=action)

    def players_move_to(self, player_sel: IPlayerSelector, move_to: Union[str, Location, List[Union[str, Location]]], allow_cancel=True,
                        action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        self.players_joust_to(player_sel=player_sel, move_to=move_to, do_return=False, stay_time=0.0, allow_cancel=allow_cancel,
                              action=action)

    def all_players_move_to(self, move_to: Union[str, Location, List[Union[str, Location]]], allow_cancel=True,
                            action: Optional[Callable[[PlayerScriptingFramework], None]] = None):
        self.all_players_joust_to(move_to=move_to, do_return=False, stay_time=0.0, allow_cancel=allow_cancel, action=action)


class PlayerFinderHelper(CombatScriptBuilderCustomAction):
    def __init__(self, phase: ICombatPhase):
        CombatScriptBuilderCustomAction.__init__(self, 'Player finder helper', phase)

    def build_phase(self, builder: CombatPhaseActionBuilder):
        pass

    def _phase_prepared(self):
        pass

    def _phase_stopped(self):
        pass

    def sort_participants_by_busy(self, game_class=GameClasses.Commoner, include_local=False, least_busy=True) -> List[IPlayer]:
        players = self.get_runtime().playerselectors.filtered_by_class(game_class, from_players_sel=self.get_phase().get_phase_participants(include_local=include_local))
        sorted_players = list(sorted(players.resolve_players(), key=lambda player_: player_.get_adventure_class().business, reverse=not least_busy))
        return sorted_players

    def find_busy_player_by_class(self, game_class: GameClass, include_local=False, least_busy=True) -> Optional[IPlayer]:
        players = self.sort_participants_by_busy(game_class=game_class, include_local=include_local, least_busy=least_busy)
        if not players:
            return None
        return players[0]
