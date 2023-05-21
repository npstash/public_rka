import time
from typing import Union, Optional, List, Dict, Set, Callable

from rka.components.events.event_system import EventSystem, CloseableSubscriber
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import CURRENT_LINK_TIER
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IAction
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability import HOIcon, AbilityEffectTarget, AbilityType, AbilityPriority
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import RemoteAbilities, ConjurorAbilities, ThugAbilities, CommonerAbilities
from rka.eq2.master.game.engine.filter_tasks import AbilityGlobalFlagsFilter, StopCastingFilter, ProcessorPlayerSwitcher, GameStateFilter, \
    ControlOnlyFilter, AbilityCanceller
from rka.eq2.master.game.engine.heroic import HeroicOpportunity, HOs
from rka.eq2.master.game.engine.mode import Mode
from rka.eq2.master.game.engine.processor import Processor
from rka.eq2.master.game.engine.request import Request, DynamicRequestProxy, CastAnyWhenReady
from rka.eq2.master.game.engine.task import Task, FilterTask
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.requesting import RequestEvents
from rka.eq2.master.game.gameclass import GameClass, GameClasses
from rka.eq2.master.game.interfaces import IPlayer, TAbilityFilter, TOptionalPlayer, IAbility
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.requests import logger
from rka.eq2.master.game.requests.heroic_ops import HEROIC_OPPORTUNITIES
from rka.eq2.master.game.requests.modes import ModeFactory
from rka.eq2.master.game.requests.request_factory import RequestFactory
from rka.eq2.master.game.scripting.scripts.game_command_scripts import RemotePlayersResetZones
from rka.eq2.master.game.scripting.scripts.movement_scripts import AcceptRezOrReviveAndMoveBack, FollowLocationsScript
from rka.eq2.master.game.scripting.scripts.travel_scripts import NonZonedPlayersCovToMain
from rka.eq2.master.game.scripting.scripts.ui_interaction_scripts import RemotePlayersAcceptInvite, RemotePlayersClickAccept, RemotePlayersClickAtPointerSmall, RemotePlayersClickAtPointerLarge, \
    RemotePlayersClickAtCenter, KeepClicking
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.master.parsing import CombatantType
from rka.eq2.shared import Groups, ClientRequests
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_scheduler


class RequestController(CloseableSubscriber):
    KEEP_REPEATING_RATE = 1.0
    URGENT_REPEATING_RATE = 0.5
    DEFAULT_SUSTAIN_DURATION = 6.0

    def __init__(self, runtime: IRuntime, processor: Processor, factory: RequestFactory, main_controller: bool):
        bus = EventSystem.get_main_bus()
        CloseableSubscriber.__init__(self, bus)
        self.__runtime = runtime
        self.processor = processor
        self.factory = factory
        self.is_main_controller = main_controller
        # timestamps for repeated requests
        self.__last_stop_combat_time = 0.0
        self.__last_cure_time = 0.0
        self.__last_dispel_time = 0.0
        self.__last_stun_time = 0.0
        self.__last_interrupt_time = 0.0
        self.__last_intercept_time = 0.0
        self.__last_power_feed_time = 0.0
        self.__last_power_drain_time = 0.0
        self.__last_bulwark_time = 0.0
        self.__last_keep_clicking_request: Optional[Task] = None
        self.__last_bulwark_request: Optional[Request] = None
        # singleton requests
        self.__cure_curses_in_order: Optional[Request] = None
        # temporary prevention filters
        self.__filter_all_automatic_cures = FilterTask(AbilityFilter().no_automatic_cures(), description='no cures', duration=-1.0)
        self.__filter_all_noncombat_short = FilterTask(AbilityFilter().non_combat(), description='no combat (short)', duration=30.0)
        self.__filter_all_noncombat_perm = FilterTask(AbilityFilter().non_combat(), description='no combat (perm)', duration=-1.0)
        self.__filter_all_onlycontrol = ControlOnlyFilter(None, duration=15.0)
        self.__filter_all_no_casting: Optional[FilterTask] = None
        # modes which group requests; initialized every time a keyspec registers new keys
        self.__sustaining_mode = Mode(self.processor, 'sustaining mode', duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        self.__mode_local_player = ModeFactory.create_player_solo_mode(None, self.processor, self.factory)
        self.__mode_group_basic_combat = ModeFactory.create_basic_group_mode(self.processor, self.factory)
        self.__mode_group_aoe_combat = ModeFactory.create_aoe_group_mode(self.processor, self.factory)
        self.__mode_group_boss_combat = ModeFactory.create_boss_group_mode(self.processor, self.factory)
        self.__mode_group_hard_combat = ModeFactory.create_hard_group_mode(self.processor, self.factory)
        self.__mode_group_emergency = ModeFactory.create_emergency_group_mode(self.processor, self.factory)
        # targetting
        self.__request_set_target = DynamicRequestProxy('set targets request', duration=RequestFactory.DEFAULT_COMBAT_DURATION)
        self.__sustaining_mode.add_task_for_running(self.__request_set_target)
        # Heroic Opportunities
        self.HOs = HOs(self.__runtime)
        self.__current_HO: Optional[HeroicOpportunity] = None
        self.__request_HO: Optional[HeroicOpportunity] = None
        self.__current_HO_hint: Optional[str] = None
        self.__next_HO_starter_archetype = GameClasses.Scout
        # processor player switcher
        self.player_switcher = ProcessorPlayerSwitcher()
        self.processor.run_filter(self.player_switcher)
        # sustained tasks
        self.__maintained_tasks: Dict[IPlayer, Set[Task]] = dict()
        self.__sustaining_mode.add_callback_for_starting(lambda: bus.post(RequestEvents.COMBAT_REQUESTS_START(main_controller=main_controller, controller_instance=self)))
        self.__sustaining_mode.add_callback_for_closing(lambda: bus.post(RequestEvents.COMBAT_REQUESTS_END(main_controller=main_controller, controller_instance=self)))
        self.__sustaining_mode.add_callback_for_closing(lambda: self.__maintained_tasks.clear())
        # event-triggered requests
        self.subscribe(RequestEvents.REQUEST_PLAYER_SET_TARGET(), self.__request_set_targets)
        self.subscribe(MasterEvents.CLIENT_CONFIGURED(), self.__client_configured)
        if self.is_main_controller:
            self.subscribe(MasterEvents.CLIENT_REGISTERED(), self.__client_registered)
            self.subscribe(MasterEvents.CLIENT_UNREGISTERED(), self.__client_registered)

    def register_local_request_events(self):
        self.subscribe(CombatEvents.BARRAGE_PREPARED(your_group=True), self.__request_group_bulwark)
        self.subscribe(CombatEvents.BARRAGE_CANCELLED(), self.__cancel_request_group_bulwark)
        self.subscribe(RequestEvents.REQUEST_BALANCED_SYNERGY(), self.__request_balanced_synergy)
        self.subscribe(RequestEvents.REQUEST_CURE_CURSE(), self.request_cure_curse_target)
        self.subscribe(RequestEvents.REQUEST_CURE(), self.request_cure_target)
        self.subscribe(RequestEvents.REQUEST_DEATHSAVE(), self.request_deathsave)
        self.subscribe(RequestEvents.REQUEST_INTERCEPT(), self.__request_keep_intercepting)
        self.subscribe(RequestEvents.REQUEST_INTERRUPT(), self.request_group_interrupt)
        self.subscribe(RequestEvents.REQUEST_STUN(), self.request_group_stun)
        self.subscribe(CombatParserEvents.EFFECT_DISPELLED(from_combatant_type=CombatantType.MY_PLAYER), self.__expire_spells)
        self.subscribe(CombatParserEvents.EFFECT_DISPELLED(from_combatant_type=CombatantType.MAIN_PLAYER), self.__expire_spells)

    def setup_HOs(self):
        for ho_name, ho_handler in HEROIC_OPPORTUNITIES.items():
            self.HOs.install_HO(ho_name, ho_handler)
        self.subscribe(ObjectStateEvents.COMBAT_STATE_START(), self.__notify_combat_start)
        self.subscribe(ObjectStateEvents.COMBAT_STATE_END(), self.__notify_combat_end)
        self.subscribe(CombatEvents.HO_CHAIN_STARTED(), self.__start_chain_common_HO)
        self.subscribe(CombatEvents.HO_TRIGGERED(), self.__trigger_common_HO)
        self.subscribe(CombatEvents.HO_ADVANCED(), self.__advance_common_HO)
        self.subscribe(CombatEvents.HO_COMPLETED(), self.__complete_common_HO)

    def __notify_combat_start(self, _event: ObjectStateEvents.COMBAT_STATE_START):
        self.__cancel_HOs()
        self.__next_HO_starter_archetype = GameClasses.Scout

    def __notify_combat_end(self, _event: ObjectStateEvents.COMBAT_STATE_END):
        self.__cancel_HOs()

    def is_player_in_this_controller(self, player: IPlayer) -> bool:
        is_here = self.player_switcher.is_holder_of(player, include_disabled=True)
        return is_here

    def close(self):
        self.player_switcher.close_switcher()
        self.processor.close()
        super().close()

    # ================= rotations and modes =======================================================
    # noinspection PyMethodMayBeStatic
    def __extend_optional_mode(self, mode: Optional[Mode], duration: float):
        if mode:
            mode.extend(duration)

    def __run_optional_mode(self, mode: Optional[Mode]):
        if mode:
            self.processor.run_auto(mode)

    def change_primary_player(self, player: IPlayer):
        self.__mode_local_player = ModeFactory.create_player_solo_mode(player, self.processor, self.factory)

    def sustain_combat(self, duration: float):
        self.processor.run_auto(self.__sustaining_mode)
        self.__extend_optional_mode(self.__mode_local_player, duration)
        self.__extend_optional_mode(self.__mode_group_basic_combat, duration)
        self.__extend_optional_mode(self.__mode_group_boss_combat, duration)
        self.__extend_optional_mode(self.__mode_group_hard_combat, duration)

    def run_and_sustain(self, task: Task, restart_when_expired: bool):
        if restart_when_expired:
            self.__sustaining_mode.add_task_for_running_until_close(task)
        else:
            self.__sustaining_mode.add_task_for_extending_until_close(task)
        self.processor.run_auto(task)

    def request_group_normal_combat(self):
        self.__run_optional_mode(self.__mode_group_basic_combat)
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    def request_group_spam_dps(self):
        self.processor.run_request(self.factory.solo_dps())
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    def request_group_aoe_combat(self):
        self.__run_optional_mode(self.__mode_group_aoe_combat)
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    def request_group_boss_combat(self):
        self.__run_optional_mode(self.__mode_group_boss_combat)
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    def request_group_hard_combat(self):
        self.__run_optional_mode(self.__mode_group_hard_combat)
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    def request_solo_normal_combat(self):
        self.__run_optional_mode(self.__mode_local_player)

    # ================= healing, power, emergencies ==================================================
    def request_group_heal_now(self):
        self.processor.run_request(self.factory.group_heal_now())

    def request_consumable_buffs_debuffs(self, delay=0.0):
        self.processor.run_request(self.factory.consumable_buffs_debuffs().delay_next_start(delay))

    def request_reactive_heals(self):
        self.processor.run_request(self.factory.reactive_heals())

    def request_group_power_feed_now(self, check_repeat_rate=True):
        t = time.time()
        self.processor.run_request(self.factory.group_power_now())
        self.processor.run_request(self.factory.group_weak_power_once())
        if check_repeat_rate and t - self.__last_power_feed_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP POWER FEED', Severity.Normal)
            self.processor.run_request(self.factory.main_player_power())
            self.__sustaining_mode.add_task_for_running_until_close(self.factory.keep_feeding_power())
        self.__last_power_feed_time = t

    def request_power_drain_now(self, check_repeat_rate=True):
        t = time.time()
        self.processor.run_request(self.factory.drain_power_now())
        if check_repeat_rate and t - self.__last_power_drain_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP POWER DRAIN', Severity.Normal)
            self.__sustaining_mode.add_task_for_running_until_close(self.factory.keep_drain_power())
        self.__last_power_drain_time = t

    def request_group_emergency(self):
        self.__run_optional_mode(self.__mode_group_emergency)

    def request_deathsave(self, target_name: Union[RequestEvents.REQUEST_DEATHSAVE, str]):
        if isinstance(target_name, RequestEvents.REQUEST_DEATHSAVE):
            target_name = target_name.target_name
        request = self.factory.deathsave_target(target_name)
        self.processor.run_request(request)

    def __request_keep_intercepting(self, event: RequestEvents.REQUEST_INTERCEPT):
        t = time.time()
        if t - self.__last_intercept_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event(f'INTERCEPTING {event.target_name}', Severity.Normal)
            self.__sustaining_mode.add_task_for_running_until_close(self.factory.keep_intercepting(event.target_name))
        self.__last_intercept_time = t

    def request_emergency_rez(self):
        self.processor.run_request(self.factory.emergency_rez(), immediate=True)
        self.sustain_combat(RequestController.DEFAULT_SUSTAIN_DURATION)

    # ================= cures and curses =========================================================
    def request_group_cure_now(self, check_repeat_rate=True, prefer_raid_cure=False):
        t = time.time()
        if check_repeat_rate:
            if t - self.__last_cure_time < RequestController.URGENT_REPEATING_RATE:
                self.processor.run_request(self.factory.urgent_group_cure_now(), immediate=True)
            if t - self.__last_cure_time < RequestController.KEEP_REPEATING_RATE:
                self.__runtime.overlay.log_event('KEEP CURING', Severity.Normal)
                self.__sustaining_mode.add_task_for_starting_and_expiring_at_close(self.factory.keep_group_curing())
        if prefer_raid_cure:
            self.processor.run_request(self.factory.raid_group_cure_now(), immediate=True)
        else:
            self.processor.run_request(self.factory.group_cure_now(), immediate=True)
        self.__last_cure_time = t

    def request_specific_group_cure_now(self, group_id: Groups):
        self.processor.run_request(self.factory.specific_group_cure_now(group_id), immediate=True)

    def toggle_group_cures(self):
        if self.__filter_all_automatic_cures.is_running():
            self.enable_group_cures()
        else:
            self.disable_group_cures()

    def disable_group_cures(self):
        self.__runtime.overlay.log_event('Disable cures', event_id='filter cures', severity=Severity.Critical)
        self.processor.run_filter(self.__filter_all_automatic_cures)
        MutableFlags.ENABLE_AUTOCURE.false()

    def enable_group_cures(self):
        self.__runtime.overlay.log_event('Enable cures', event_id='filter cures', severity=Severity.Normal)
        self.__filter_all_automatic_cures.expire()
        MutableFlags.ENABLE_AUTOCURE.true()

    def request_cure_me(self):
        self.processor.run_request(self.factory.cure_default_target_now(), immediate=True)
        self.processor.run_request(self.factory.confront_fear_default_target_now())

    def request_keep_curing_me(self):
        self.__sustaining_mode.add_task_for_running_until_close(self.factory.keep_curing_me())

    def request_cure_curse_me(self):
        self.processor.run_request(self.factory.cure_curse_default_target_now())

    def request_cure_target(self, target_name: Union[RequestEvents.REQUEST_CURE, str]):
        if isinstance(target_name, RequestEvents.REQUEST_CURE):
            target_name = target_name.target_name
        request = self.factory.cure_target(target_name)
        self.processor.run_request(request, immediate=True)

    def request_cure_target_by_caster(self, target_name: str, caster: IPlayer):
        request = self.factory.cure_target_by_caster(target_name, caster)
        self.processor.run_request(request, immediate=True)

    def request_cure_curse_in_order(self, target_names: List[str]):
        if self.__cure_curses_in_order:
            self.__cure_curses_in_order.expire()
        self.__cure_curses_in_order = self.factory.cure_curse_target_list(target_names)
        self.processor.run_request(self.__cure_curses_in_order)

    def request_priest_cure_target(self, target_name: str):
        request = self.factory.priest_cure_target(target_name)
        self.processor.run_request(request, immediate=True)

    def request_mage_cure_target(self, target_name: str):
        request = self.factory.mage_cure_target(target_name)
        self.processor.run_request(request, immediate=True)

    def request_cure_curse_target(self, target_name: Union[RequestEvents.REQUEST_CURE_CURSE, str]):
        if isinstance(target_name, RequestEvents.REQUEST_CURE_CURSE):
            target_name = target_name.target_name
        request = self.factory.cure_curse_target(target_name)
        self.processor.run_request(request, immediate=True)

    # ================= stun, dispel, interrupt ==================================================
    def request_group_dispel(self, check_repeat_rate=True):
        t = time.time()
        if check_repeat_rate and t - self.__last_dispel_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP DISPELLING', Severity.Normal)
            self.__sustaining_mode.add_task_for_starting_and_expiring_at_close(self.factory.keep_dispelling())
        self.processor.run_request(self.factory.dispel_now())
        self.__last_dispel_time = t

    def request_mage_dispel(self):
        self.processor.run_request(self.factory.mage_dispel_now())

    def request_priest_dispel(self):
        self.processor.run_request(self.factory.priest_dispel_now())

    def request_group_stun(self, _event: Optional[RequestEvents.REQUEST_STUN] = None, check_repeat_rate=True):
        t = time.time()
        if check_repeat_rate and t - self.__last_stun_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP STUNNING', Severity.Normal)
            self.__sustaining_mode.add_task_for_starting_and_expiring_at_close(self.factory.keep_stunning())
        self.processor.run_request(self.factory.stun_now())
        self.__last_stun_time = t

    def request_group_interrupt(self, _event: Optional[RequestEvents.REQUEST_INTERRUPT] = None, check_repeat_rate=True, cast_all=True):
        t = time.time()
        if check_repeat_rate and t - self.__last_interrupt_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP INTERRUPTING', Severity.Normal)
            self.__sustaining_mode.add_task_for_starting_and_expiring_at_close(self.factory.keep_interrupting())
        if cast_all:
            self.processor.run_request(self.factory.interrupt_now(), immediate=True)
        else:
            self.processor.run_request(self.factory.interrupt_now_short(), immediate=True)
        self.__last_interrupt_time = t

    def request_intercept(self, target_name: str):
        self.processor.run_request(self.factory.intercept_now(target_name))

    # ================= combat econtrol ===================================================
    def request_group_attack(self, autoface: bool):
        if autoface:
            request = self.factory.combat_autoface()
        else:
            request = self.factory.combat()
        self.processor.run_request(request)
        self.__filter_all_noncombat_short.expire()
        self.__filter_all_noncombat_perm.expire()

    def request_stop_combat(self, player: IPlayer, duration=10.0):
        request_dont_dps = FilterTask(AbilityFilter().non_combat(player), description=f'no combat {player}', duration=duration)
        self.processor.run_filter(request_dont_dps)
        if player.is_remote():
            request = self.factory.zoned_cast_one(RemoteAbilities.stop_combat, player, duration=3.0)
            self.processor.run_request(request, immediate=True)
        else:
            ac = action_factory.new_action().inject_command(injector_name=player.get_ability_injector_name(),
                                                            injected_command=f'cl\ncancel_spellcast\nautoattack 0\n',
                                                            once=False, passthrough=False, duration=duration)
            ac.post_async(player.get_client_id())

    def request_group_stop_combat(self, duration=2.0, check_repeat_rate=True):
        t = time.time()
        if check_repeat_rate and t - self.__last_stop_combat_time < RequestController.KEEP_REPEATING_RATE:
            self.__runtime.overlay.log_event('KEEP NON COMBAT', Severity.Normal)
            self.__sustaining_mode.add_task_for_starting_and_expiring_at_close(self.__filter_all_noncombat_perm)
        else:
            request = self.factory.zoned_cast_one(RemoteAbilities.stop_combat, None, duration=2.0)
            self.processor.run_request(request, immediate=True)
            self.__filter_all_noncombat_short.expire()
            self.__filter_all_noncombat_short = FilterTask(AbilityFilter().non_combat(), description='no combat (short)', duration=duration)
            self.processor.run_filter(self.__filter_all_noncombat_short)
        self.__last_stop_combat_time = t

    def request_feign_death(self, player: Optional[IPlayer] = None):
        request = self.factory.zoned_cast_one(RemoteAbilities.feign_death, player, duration=5.0)
        self.processor.run_request(request)

    def __request_set_targets(self, event: RequestEvents.REQUEST_PLAYER_SET_TARGET):
        if not self.is_player_in_this_controller(event.player):
            logger.debug(f'__request_set_targets: Player {event.player} not in req_ctrl: {self}')
            return
        request = self.factory.set_targets(event.player, target_name=event.target_name, optional_targets=event.optional_targets,
                                           repeat_ratio=event.refresh_rate)
        self.__request_set_target.set_request(request)
        self.processor.run_request(self.__request_set_target, immediate=True)

    def request_group_stop_and_boss_combat(self):
        self.request_stop_follow()
        self.request_group_attack(autoface=False)
        self.request_group_boss_combat()
        self.request_consumable_buffs_debuffs(5.0)
        request = self.factory.zoned_cast_one(ConjurorAbilities.unflinching_servant, None, duration=6.0)
        self.processor.run_request(request)

    # ================= movement econtrol ===================================================
    def request_toggle_sprint(self, player: Optional[IPlayer] = None):
        request = self.factory.zoned_cast_one(RemoteAbilities.sprint, player, duration=5.0)
        self.processor.run_request(request)

    def __stop_movement_scripts(self, player: Optional[IPlayer], reason: FollowLocationsScript.CancelReason):
        if player:
            self.__runtime.automation.autopilot.stop_player_movements(player=player, reason=reason)
        else:
            self.__runtime.automation.autopilot.all_players_stop_movement(reason=reason)

    def request_follow(self, player: Optional[IPlayer] = None, target_name: Optional[str] = None):
        self.__stop_movement_scripts(player=player, reason=FollowLocationsScript.CancelReason.FOLLOW)
        players = self.__runtime.playerselectors.if_none_then_all_zoned_remote(player).resolve_players()
        if target_name:
            request = self.factory.custom_request(RemoteAbilities.follow, players, duration=2.0, target_name=target_name)
        else:
            request = self.factory.follow_default_target(players)
        self.processor.run_request(request, immediate=True)

    def request_stop_follow(self, player: Optional[IPlayer] = None):
        self.__stop_movement_scripts(player=player, reason=FollowLocationsScript.CancelReason.STOP_FOLLOW)
        request = self.factory.zoned_cast_one(RemoteAbilities.stop_follow, player, duration=2.0)
        self.processor.run_request(request, immediate=True)

    def request_player_dont_move(self, player: TOptionalPlayer, duration=10.0):
        request = self.factory.zoned_cast_one(RemoteAbilities.stop_follow, player, duration=duration)
        self.processor.run_request(request, immediate=True)
        request_dont_move = FilterTask(AbilityFilter().non_move(player), description='no moves', duration=max(1.0, duration - 2.0))
        self.processor.run_filter(request_dont_move)

    def request_toggle_crouch(self, player: Optional[IPlayer] = None):
        request = self.factory.zoned_cast_one(RemoteAbilities.crouch, player, duration=2.0)
        self.processor.run_request(request, immediate=True)

    def request_jump(self, player: Optional[IPlayer] = None):
        request = self.factory.zoned_cast_one(RemoteAbilities.jump, player, duration=2.0)
        self.processor.run_request(request, immediate=True)

    def request_group_cov_to_main(self):
        self.processor.run_task(NonZonedPlayersCovToMain())

    # ================= character control =======================================================
    def request_stop_all_non_control(self, player: IPlayer, duration: float):
        self.request_stop_follow(player)
        request_control_only = ControlOnlyFilter(player, duration=duration)
        self.processor.run_filter(request_control_only)

    def request_stop_all(self, player: IPlayer, duration: float):
        self.request_stop_combat(player)
        self.request_stop_follow(player)
        self.processor.run_filter(StopCastingFilter(player=player, duration=duration))

    def request_stop_casting(self, player: IPlayer, duration: float, delay=0.0):
        stop_casting_filter = StopCastingFilter(player, duration=duration)
        self.processor.run_filter(stop_casting_filter.delay_next_start(delay))

    def request_group_stop_all(self):
        self.request_group_stop_combat(check_repeat_rate=False)
        self.request_stop_follow()
        self.processor.run_filter(self.__filter_all_onlycontrol)

    def request_group_stop_casting(self, duration=10.0, delay=0.0):
        current_filter = self.__filter_all_no_casting
        if current_filter:
            remaining_duration = current_filter.get_remaining_duration()
            if remaining_duration and remaining_duration > duration + delay:
                return
            current_filter.expire()
        self.__filter_all_no_casting = FilterTask(AbilityFilter().op_and(lambda a: False), description='stop casting', duration=duration)
        self.processor.run_filter(self.__filter_all_no_casting.delay_next_start(delay))

    def request_group_accept_invite(self):
        self.processor.run_auto(RemotePlayersAcceptInvite())

    def request_accept_once(self, player: Optional[IPlayer] = None):
        self.processor.run_auto(RemotePlayersClickAccept(player=player, repeats=1, close_windows=False))

    def request_accept_continued(self, player: Optional[IPlayer] = None, duration=15.0):
        self.processor.run_auto(RemotePlayersClickAccept(player=player, repeats=int(duration), close_windows=False))

    def request_accept_all(self, player: Optional[IPlayer] = None):
        self.processor.run_auto(RemotePlayersClickAccept(player=player, repeats=2, close_windows=True, externals=True))

    def request_rez_or_revive(self, player: IPlayer, duration=30.0):
        accept_rez = AcceptRezOrReviveAndMoveBack(player=player, duration_sec=int(duration))
        self.processor.run_auto(accept_rez)

    def request_click_object_in_center(self, player: Optional[IPlayer] = None):
        self.processor.run_auto(RemotePlayersClickAtCenter(player))

    def request_group_reset_zones(self):
        self.processor.run_auto(RemotePlayersResetZones())

    def request_group_click_at_mouse_small(self):
        self.processor.run_task(RemotePlayersClickAtPointerSmall())

    def request_group_click_at_mouse_large(self):
        self.processor.run_task(RemotePlayersClickAtPointerLarge())

    def request_toggle_keep_clicking(self):
        if self.__last_keep_clicking_request:
            self.__last_keep_clicking_request.expire()
            self.__last_keep_clicking_request = None
        else:
            self.__last_keep_clicking_request = KeepClicking(0.6)
            self.processor.run_task(self.__last_keep_clicking_request)

    def request_cancel_spellcasting(self, player: Optional[IPlayer] = None):
        request = self.factory.zoned_cast_one(CommonerAbilities.cancel_spellcast, player=player, duration=3.0)
        self.processor.run_request(request, immediate=True)

    def request_location(self, player: IPlayer):
        request = self.factory.zoned_cast_one(CommonerAbilities.loc, player=player, duration=3.0)
        self.processor.run_request(request, immediate=True)

    def __client_configured(self, event: MasterEvents.CLIENT_CONFIGURED):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        if not self.is_player_in_this_controller(player):
            logger.debug(f'__client_configured: Player {player} not in req_ctrl: {self}')
            return
        shared_scheduler.schedule(lambda: self.request_zone_discovery(player=player), delay=8.0)

    def __client_registered(self, event: MasterEvents.CLIENT_REGISTERED):
        bus = self.__runtime.remote_client_event_system.get_bus(event.client_id)
        if bus:
            bus.subscribe(ClientEvents.CLIENT_REQUEST(request=ClientRequests.GROUP_CURE), self.__group_cure_filter_client_id)

    def __client_unregistered(self, event: MasterEvents.CLIENT_UNREGISTERED):
        bus = self.__runtime.remote_client_event_system.get_bus(event.client_id)
        if bus:
            bus.unsubscribe_all(ClientEvents.CLIENT_REQUEST, self.__group_cure_filter_client_id)

    def __group_cure_filter_client_id(self, event: ClientEvents.CLIENT_REQUEST):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        if not player.is_zoned():
            return
        if not self.is_player_in_this_controller(player):
            logger.debug(f'__group_cure_filter_client_id: Player {player} not in req_ctrl: {self}')
            return
        group_id = player.get_client_config_data().group_id
        request = self.factory.specific_group_cure_now(group_id).delay_next_start(1.0)
        self.processor.run_request(request)

    def request_zone_discovery(self, player: IPlayer, delay=0.0):
        request_check_who_in_zone = self.factory.discover_zone(player)
        request_check_who_in_zone.delay_next_start(delay=delay)
        self.processor.run_request(request_check_who_in_zone, immediate=True)

    def maintain_task_for_player(self, player: IPlayer, task: Task):
        self.__maintained_tasks.setdefault(player, set()).add(task)
        self.__sustaining_mode.add_task_for_extending_until_close(task)
        self.processor.run_auto(task)

    def cancel_tasks_maintained_for_player(self, player: IPlayer):
        tasks = self.__maintained_tasks.setdefault(player, set())
        for task in tasks:
            print(f'expiring {task}')
            task.expire()
        tasks.clear()

    # ================= combos ==============================================================
    def request_combo_implosion(self):
        self.processor.run_request(self.factory.combo_implosion())

    def request_combo_levinbolt(self):
        self.processor.run_request(self.factory.combo_levinbolt())

    def request_combo_manaschism(self):
        self.processor.run_request(self.factory.combo_manaschism())

    def request_combo_ethershadow(self):
        self.processor.run_request(self.factory.combo_ethershadow())

    def request_combo_etherflash(self):
        self.processor.run_request(self.factory.combo_etherflash())

    def request_combo_compounding_foce(self):
        self.processor.run_request(self.factory.combo_compounding_foce())

    def request_combo_cascading(self):
        self.processor.run_request(self.factory.combo_cascading())

    # ================= combat ==============================================================
    def request_spam_attacks(self, player: Optional[IPlayer] = None, duration=30.0):
        player_sel = self.__runtime.playerselectors.if_none_then_all_zoned_remote(player)
        players = player_sel.resolve_players()
        request = self.factory.spam_attacks(players)
        request.set_duration(duration)
        self.processor.run_request(request)

    def request_group_ascension_nukes(self):
        self.processor.run_request(self.factory.ascension_nukes())

    def request_group_verdicts(self):
        self.processor.run_request(self.factory.verdict_now())

    def request_aggro_to(self, player: Optional[IPlayer] = None):
        player_sel = self.__runtime.playerselectors.if_none_then_by_selection(player)
        for player in player_sel.resolve_players():
            self.__runtime.combatstate.lock_current_target(player=player)
            self.processor.run_request(self.factory.aggro_to(player=player))
            break  # use only one

    def request_tank_snap(self):
        self.processor.run_request(self.factory.tank_snap_now())

    def __request_group_bulwark(self, _event: CombatEvents.BARRAGE_PREPARED):
        delay = 3.0
        t = time.time()
        if t - self.__last_bulwark_time < 10.0:
            return
        self.__last_bulwark_request = self.factory.bulwark()
        self.processor.run_request(self.__last_bulwark_request.delay_next_start(delay))
        save_delay = max(delay - 2.0, 0.0)
        if MutableFlags.ENABLE_BARRAGE_SAVE:
            stoneskin_request = self.factory.tank_deathsave()
            self.processor.run_request(stoneskin_request.delay_next_start(save_delay))
        else:
            stoneskin_request = self.factory.tank_stoneskin()
            self.processor.run_request(stoneskin_request.delay_next_start(save_delay))
        self.__last_bulwark_time = t

    def __cancel_request_group_bulwark(self, _event: CombatEvents.BARRAGE_CANCELLED):
        if self.__last_bulwark_request is not None:
            self.__last_bulwark_request.expire()
            self.__last_bulwark_request = None

    def __request_balanced_synergy(self, event: RequestEvents.REQUEST_BALANCED_SYNERGY):
        if MutableFlags.ENABLE_AUTO_SYNERGY:
            if event.local_player_request:
                self.processor.run_request(self.factory.balanced_synergy_remote_players_now())
            else:
                self.processor.run_request(self.factory.balanced_synergy_all_players().delay_next_start(1.5))

    def request_strikes_of_consistency(self):
        self.processor.run_request(self.factory.strikes_of_consistency())

    ## =============================== Heroic Opportunities ===========================================================
    def set_HO_default_starter(self, archetype: GameClass):
        self.__next_HO_starter_archetype = archetype

    def request_HO_default_starter(self) -> Request:
        request = self.factory.heroic_opportunity_starter(self.__next_HO_starter_archetype)
        self.processor.run_request(request)
        return request

    def request_HO_starter(self, caster: Union[GameClass, IPlayer]) -> Request:
        request = self.factory.heroic_opportunity_starter(caster)
        self.processor.run_request(request)
        return request

    def request_HO_solo_trigger(self, gameclass: GameClass) -> Request:
        request = self.factory.heroic_opportunity_solo_trigger(gameclass)
        self.processor.run_request(request)
        return request

    def request_HO_advance(self, ho_icons: Union[HOIcon, List[HOIcon]], max_hits: int, ability_filter: Optional[TAbilityFilter] = None, delay: Optional[float] = None) -> Request:
        request = self.factory.heroic_opportunity_advance(ho_icons=ho_icons, max_hits=max_hits, ability_filter=ability_filter)
        if delay:
            request = request.delay_next_start(delay)
        self.processor.run_request(request)
        return request

    def __cancel_HOs(self):
        if self.__current_HO:
            self.__current_HO.cancel()
            self.__current_HO = None
        if self.__request_HO:
            self.__request_HO.cancel()
            self.__request_HO = None

    def __check_HO(self, HO_name: str) -> Optional[HeroicOpportunity]:
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return None
        ho = self.__current_HO
        if not ho:
            return None
        if HO_name != ho.get_name():
            ho.cancel()
            self.__current_HO = None
            return None
        return ho

    def set_HO_hint(self, hint: str):
        self.__current_HO_hint = hint

    def request_HO_chain(self, HO_name: str):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__request_HO = self.HOs.get_HO(HO_name)
        self.__request_HO.request_chain()

    def __start_chain_common_HO(self, event: CombatEvents.HO_CHAIN_STARTED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        if self.__current_HO:
            self.__current_HO.cancel()
            self.__current_HO = None
        if self.__request_HO:
            self.__current_HO = self.__request_HO
            self.__request_HO = None
        else:
            self.__current_HO = self.HOs.get_blank_HO()
        self.__current_HO.chain_started(event.caster_name, self.__current_HO_hint)
        self.__current_HO.request_trigger()

    def __break_chain_common_HO(self, _event: CombatEvents.HO_CHAIN_BROKEN):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        self.__cancel_HOs()

    def __trigger_common_HO(self, event: CombatEvents.HO_TRIGGERED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        old_HO = self.__current_HO
        self.__current_HO = self.HOs.get_HO(event.ho_name)
        if old_HO:
            self.__current_HO.continue_from_chain(old_HO)
        else:
            self.__current_HO.chain_started(event.caster_name, self.__current_HO_hint)
        self.__current_HO.triggered(event.caster_name, self.__current_HO_hint)

    def __advance_common_HO(self, event: CombatEvents.HO_ADVANCED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        ho = self.__check_HO(event.ho_name)
        if not ho:
            return
        self.__current_HO.advanced(event.caster_name, self.__current_HO_hint)

    def __complete_common_HO(self, event: CombatEvents.HO_COMPLETED):
        if not MutableFlags.AUTO_HEROIC_OPPORTUNITY:
            return
        ho = self.__check_HO(event.ho_name)
        if not ho:
            return
        self.__current_HO.completed(event.caster_name, self.__current_HO_hint)

    # ================= special  =================================================================
    def request_group_summon_pets(self):
        self.processor.run_request(self.factory.summon_pets())

    def request_group_permanent_buffs(self):
        if self.__runtime.combatstate.is_combat():
            self.processor.run_request(self.factory.rebuff_other_player_essentials())
            self.processor.run_request(self.factory.rebuff_self_essentials())
        else:
            self.processor.run_request(self.factory.rebuff_other_player())
            self.processor.run_request(self.factory.rebuff_self())
        self.processor.run_request(self.factory.rebuff_persistent_passive_buffs())

    def get_dispelled_abilities(self, ability_name: str, from_combatant: str) -> List[IAbility]:
        abilities_to_recast = list()
        locator = self.__runtime.ability_reg.get_ability_locator_by_name(ability_name)
        if not locator:
            logger.info(f'Dispel effect not in registry: {ability_name}')
            return abilities_to_recast
        from_player = self.__runtime.player_mgr.get_player_by_name(from_combatant)
        if not from_player:
            logger.warn(f'Dispel target not my player: {from_player}')
            return abilities_to_recast
        abilities = locator.resolve(AbilityFilter().zoned_casters())
        if not abilities:
            logger.warn(f'Ability not cast by a zoned caster: {locator}')
            return abilities_to_recast
        for ability in abilities:
            if ability.ext.effect_target not in [AbilityEffectTarget.Self, AbilityEffectTarget.Group, AbilityEffectTarget.Raid,
                                                 AbilityEffectTarget.GroupMember, AbilityEffectTarget.Ally]:
                continue
            if ability.ext.effect_target == AbilityEffectTarget.Self:
                if from_combatant != ability.player.get_player_name():
                    continue
            if ability.ext.effect_target in [AbilityEffectTarget.GroupMember, AbilityEffectTarget.Ally]:
                if not ability.get_target() or not ability.get_target().match_target(from_combatant):
                    continue
            abilities_to_recast.append(ability)
        return abilities_to_recast

    def __expire_spells(self, event: CombatParserEvents.EFFECT_DISPELLED):
        for ability in self.get_dispelled_abilities(event.effect_name, event.from_combatant):
            ability.expire_duration()
            # try to recast if a passive buff
            if ability.ext.is_maintained_buff():
                request = self.factory.zoned_cast_one(ability.locator, ability.player, duration=30.0)
                self.processor.run_request(request, immediate=False)

    def request_group_prepull_buffs(self):
        self.processor.run_request(self.factory.prepull_buffs())

    def request_group_timelord(self):
        request = self.factory.timelord_now()
        self.processor.run_request(request)

    def request_detect_weakness(self):
        players = self.player_switcher.get_holding_players(False)
        request = self.factory.cached_request(ability_locator=ThugAbilities.detect_weakness,
                                              players=players,
                                              request_type=CastAnyWhenReady, duration=10.0)
        self.__sustaining_mode.add_task_for_running_until_close(request)

    def request_powerpainforce_links(self, link_type: str):
        players = self.player_switcher.get_holding_players(False)
        request = self.factory.powerpainforce_links(CURRENT_LINK_TIER, link_type, players)
        if request:
            self.processor.run_request(request)

    def request_custom_ability(self, player: IPlayer, casting: float, reuse: float, recovery=1.0, duration=0.0,
                               ability_name: Optional[str] = None, ability_type: Optional[AbilityType] = None, priority=AbilityPriority.MANUAL_REQUEST,
                               action: Optional[IAction] = None, ability_crc: Optional[int] = None, item_id: Optional[int] = None,
                               min_state=PlayerStatus.Zoned, cannot_modify=False) -> IAbility:
        ability = self.factory.custom_ability(player=player, casting=casting, reuse=reuse, recovery=recovery, duration=duration,
                                              ability_name=ability_name, ability_type=ability_type, priority=priority,
                                              action=action, ability_crc=ability_crc, item_id=item_id, min_state=min_state, cannot_modify=cannot_modify)
        request = self.factory.custom_ability_request(ability)
        self.processor.run_request(request)


class RequestControllerFactory:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__main_request_ctrl: Optional[RequestController] = None
        self.__standard_filters: List[Callable[[], FilterTask]] = list()
        self.__add_standard_processor_filters()

    def add_common_processor_filter(self, filter_factory: Callable[[], FilterTask]):
        self.__standard_filters.append(filter_factory)
        if self.__main_request_ctrl:
            filter_task = filter_factory()
            self.__main_request_ctrl.processor.run_filter(filter_task)

    def __add_standard_processor_filters(self):
        self.add_common_processor_filter(lambda: FilterTask(AbilityFilter().permitted_caster_state(), description='permitted casters', duration=-1.0))
        self.add_common_processor_filter(lambda: FilterTask(AbilityFilter().permitted_target_state(), description='permitted targets', duration=-1.0))
        self.add_common_processor_filter(lambda: GameStateFilter(self.__runtime))
        self.add_common_processor_filter(lambda: AbilityGlobalFlagsFilter())
        self.add_common_processor_filter(lambda: AbilityCanceller(self.__runtime))

    def __apply_common_processor_filter(self, controller: RequestController):
        for filter_factory in self.__standard_filters:
            filter_task = filter_factory()
            controller.processor.run_filter(filter_task)

    def create_main_request_controller(self, processor: Processor, factory: RequestFactory) -> RequestController:
        assert not self.__main_request_ctrl
        self.__main_request_ctrl = RequestController(self.__runtime, processor, factory, True)
        self.__main_request_ctrl.register_local_request_events()
        self.__main_request_ctrl.setup_HOs()
        # main zone filters
        filter_in_zone = FilterTask(AbilityFilter().permitted_caster_zone(), description='zoned casters', duration=-1.0)
        self.__main_request_ctrl.processor.run_filter(filter_in_zone)
        self.__apply_common_processor_filter(self.__main_request_ctrl)
        return self.__main_request_ctrl

    def create_offzone_request_controller(self) -> RequestController:
        processor = self.__runtime.processor_factory.create_processor()
        factory = RequestFactory(self.__runtime)
        request_ctrl = RequestController(self.__runtime, processor, factory, False)
        self.__apply_common_processor_filter(request_ctrl)
        return request_ctrl
