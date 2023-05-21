from __future__ import annotations

import enum
from typing import Optional, Callable, List, Union

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.ability.generated_abilities import PriestAbilities, RemoteAbilities
from rka.eq2.master.game.engine.filter_tasks import ConfirmAbilityCasting
from rka.eq2.master.game.engine.task import FilterTask
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer, IAbility
from rka.eq2.master.game.location import Location, LocationInputStream, LocationRef
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import ScriptException, MovePrecision, RotatePrecision, RepeatMode
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask, PlayerScriptingFramework
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.procedures.movement import MovementProcedureFactory
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared import ClientFlags
from rka.eq2.shared.flags import MutableFlags
from rka.eq2.shared.shared_workers import shared_worker


class IFollowLocationsObserver:
    def waypoint_reached(self, player: IPlayer, location: Location):
        pass

    def movement_completed(self, player: IPlayer, last_location: Optional[Location], reached: bool):
        pass


class FollowLocationsScript(PlayerScriptTask):
    class CancelReason(enum.Enum):
        FOLLOW = enum.auto()
        STOP_FOLLOW = enum.auto()
        NEW_MOVEMENT_SCRIPT = enum.auto()
        OTHER = enum.auto()
        UNCONDITIONAL = enum.auto()

    def __init__(self, player: IPlayer):
        PlayerScriptTask.__init__(self, f'{player} follow locations', -1.0)
        self.__movement_observers: List[IFollowLocationsObserver] = list()
        self.__cancel_reasons = {reason: True for reason in FollowLocationsScript.CancelReason}
        self.player = player
        self.set_silent()

    def _notify_waypoint_reached(self, location: Location):
        for observer in self.__movement_observers.copy():
            shared_worker.push_task(lambda: observer.waypoint_reached(self.player, location))

    def _notify_movement_completed(self, last_location: Optional[Location], reached: bool):
        for observer in self.__movement_observers.copy():
            shared_worker.push_task(lambda: observer.movement_completed(self.player, last_location, reached))

    def add_movement_observer(self, movement_observer: IFollowLocationsObserver):
        self.__movement_observers.append(movement_observer)

    def disable_cancel_reason(self, reason: FollowLocationsScript.CancelReason):
        self.__cancel_reasons[reason] = False

    def is_cancel_possible(self, reason: FollowLocationsScript.CancelReason) -> bool:
        if reason == FollowLocationsScript.CancelReason.UNCONDITIONAL:
            return True
        return self.__cancel_reasons[reason]

    def _run(self, runtime: IRuntime):
        raise NotImplementedError()


class FollowLocationStream(FollowLocationsScript):
    def __init__(self, player: IPlayer, location_source: LocationInputStream, high_precision=False):
        FollowLocationsScript.__init__(self, player)
        self.__location_source = location_source
        self.__high_precision = high_precision

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        hp = self.__high_precision
        navigate = MovementProcedureFactory.create_navigation_procedure(psf, final_loc_high_precision=hp, final_loc_rotation=hp)
        next_location = None
        location_reached = False
        no_follow = FilterTask(AbilityFilter().op_and(lambda ability_: ability_.locator != RemoteAbilities.follow or ability_.player != self.player), 'no following', 15.0)
        runtime.processor.run_filter(no_follow)
        try:
            navigate.start_movement_tracking()
            for next_location in self.__location_source.iter_locations():
                location_reached = navigate.navigate_to_location(next_location)
                if not location_reached:
                    break
                self._notify_waypoint_reached(next_location)
                no_follow.extend(15.0)
        except ScriptException:
            pass
        finally:
            navigate.stop_movement_tracking()
            no_follow.expire()
            self._notify_movement_completed(next_location, location_reached)

    def _on_expire(self):
        self.__location_source.close_source()
        super()._on_expire()


class FollowLocationRef(FollowLocationsScript):
    def __init__(self, player: IPlayer, location_ref_to_track: LocationRef):
        FollowLocationsScript.__init__(self, player)
        self.__location_ref_to_track = location_ref_to_track

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        movement = MovementProcedureFactory.create_movement_procedure(psf)
        next_location = None
        location_reached = False
        try:
            movement.start_movement_tracking()
            while not self.is_expired():
                current_target_location = self.__location_ref_to_track.get_location()
                if not current_target_location:
                    break
                location_reached = movement.move_to_location(target_location=self.__location_ref_to_track,
                                                             movement_precision=MovePrecision.COARSE, rotation_precision=RotatePrecision.NORMAL)
                if not location_reached and not self.__location_ref_to_track.is_changed():
                    break
                self._notify_waypoint_reached(next_location)
                if not self.__location_ref_to_track.wait_for_change():
                    break
        except ScriptException:
            pass
        finally:
            movement.stop_movement_tracking()
            self._notify_movement_completed(next_location, location_reached)

    def _on_expire(self):
        self.__location_ref_to_track.unref()
        super()._on_expire()


@GameScriptManager.register_game_script([ScriptCategory.MOVEMENT, ScriptCategory.QUICKSTART], 'Use mender in front of local player (zoned remote players)')
class RemotePlayersUseMenderBot(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, 'Use mender bot', -1.0)

    # noinspection PyMethodMayBeStatic
    def move_to_mender(self, psf: PlayerScriptingFramework, location: Location):
        psf.try_close_all_windows()
        psf.move_to_location(location)
        psf.recenter_camera()
        psf.use_repair_bot()
        psf.try_close_all_windows()

    def _run(self, runtime: IRuntime):
        main_player = runtime.playerstate.get_main_player()
        psf = self.get_player_scripting_framework(main_player)
        location = psf.get_location()
        if not location:
            self.fail_script('could not receive location')
            return
        players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        for player in players:
            psf = self.get_player_scripting_framework(player)
            self.run_concurrent_task(self.move_to_mender, psf, location)


class AcceptRezOrReviveAndMoveBack(PlayerScriptTask):
    def __init__(self, player: IPlayer, duration_sec: int):
        PlayerScriptTask.__init__(self, f'Revive {player}', duration=-1.0)
        self.__player = player
        self.__duration_sec = duration_sec
        self.__revived = False
        self.set_silent()
        EventSystem.get_main_bus().subscribe(CombatEvents.PLAYER_REVIVED(player=player), self.__player_revived)

    def __player_revived(self, _event: CombatEvents.PLAYER_REVIVED):
        if self.__revived:
            return
        self.expire()

    def _on_expire(self):
        EventSystem.get_main_bus().unsubscribe_all(CombatEvents.PLAYER_REVIVED, self.__player_revived)
        super()._on_expire()

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.__player)
        ticks = self.__duration_sec if not MutableFlags.AUTO_REVIVE_IF_NO_REZ else 3
        try:
            for tick in range(ticks):
                if tick < 10:
                    self.sleep(1.0)
                else:
                    self.sleep(2.0)
                if psf.try_click_accepts():
                    return
        except ScriptException:
            return
        if not MutableFlags.AUTO_REVIVE_IF_NO_REZ:
            return
        if not psf.find_match_by_tag(ui_patterns.PATTERN_BUTTON_REVIVE, repeat=RepeatMode.DONT_REPEAT):
            runtime.overlay.log_event('Count not find revive button', Severity.Normal)
            return
        current_loc = psf.get_location()
        self.__revived = True
        if not psf.click_match(ui_patterns.PATTERN_BUTTON_REVIVE, repeat=RepeatMode.DONT_REPEAT):
            runtime.overlay.log_event('Count not find revive button', Severity.Normal)
            return
        self.sleep(5.0)
        psf.navigate_to_location(current_loc)


class PlayerActionTrip(FollowLocationsScript):
    def __init__(self, player: IPlayer,
                 move_to: Optional[Union[Location, List[Location]]] = None, wait_after_moving: Optional[float] = None,
                 action: Optional[Callable[[PlayerScriptingFramework], None]] = None, wait_after_action: Optional[float] = None,
                 return_movement=True, return_to: Optional[Location] = None, high_precision=False):
        FollowLocationsScript.__init__(self, player)
        self.move_to = move_to if isinstance(move_to, (list, set)) else [move_to]
        self.wait_after_moving = wait_after_moving
        self.action = action
        self.wait_after_action = wait_after_action
        self.return_movement = return_movement
        self.return_to = return_to
        self.high_precision = high_precision

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.player)
        current_location = psf.get_location()
        move_to = min(self.move_to, key=lambda loc: current_location.get_horizontal_distance(loc))
        if self.return_movement and not self.return_to:
            self.return_to = current_location
        no_follow = FilterTask(AbilityFilter().op_and(lambda ability_: ability_.locator != RemoteAbilities.follow or ability_.player != self.player), 'no following', 15.0)
        runtime.processor.run_filter(no_follow)
        try:
            psf.move_to_location(move_to, high_precision=self.high_precision, allow_moving_backwards=True)
            if self.wait_after_moving:
                self.sleep(self.wait_after_moving)
            if self.action:
                self.action(psf)
                if self.wait_after_action:
                    self.sleep(self.wait_after_action)
            if self.return_to:
                psf.move_to_location(self.return_to, high_precision=self.high_precision)
        finally:
            no_follow.expire()


class MoveCureReturn(PlayerActionTrip):
    def __init__(self, player: IPlayer, curse: bool, move_to: Optional[Union[Location, List[Location]]] = None,
                 return_to: Optional[Location] = None, high_precision=False):
        PlayerActionTrip.__init__(self, player=player,
                                  move_to=move_to, wait_after_moving=1.0,
                                  action=self.__cure, wait_after_action=1.0,
                                  return_movement=True, return_to=return_to, high_precision=high_precision)
        self.curse = curse

    def __condition(self, ab: IAbility) -> bool:
        if not self.curse and not ab.ext.cure:
            return False
        if self.curse and ab.locator != PriestAbilities.cure_curse:
            return False
        target = ab.get_target()
        if not target:
            return False
        return target.match_target(self.player)

    def __cure(self, psf: PlayerScriptingFramework):
        confirmation = ConfirmAbilityCasting(ability=self.__condition, duration=-1.0)
        try:
            self.get_runtime().processor.run_filter(confirmation)
            if self.curse:
                psf.get_runtime().request_ctrl.request_cure_curse_target(self.player.get_player_name())
            else:
                if self.player.is_class(GameClasses.Priest) or self.player.is_class(GameClasses.Mage):
                    psf.get_runtime().request_ctrl.request_cure_target_by_caster(self.player.get_player_name(), self.player)
                else:
                    psf.get_runtime().request_ctrl.request_cure_target(self.player.get_player_name())
            confirmation.wait_for_ability(4.0)
        finally:
            confirmation.expire()
