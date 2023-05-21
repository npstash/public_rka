from __future__ import annotations

import random
import threading
import time
from typing import Optional, Dict, List

from rka.components.io.log_service import LogService
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.location import Location, LocationInputStream, LocationRef
from rka.eq2.master.game.scripting import MovementParams, RotatePrecision, ScriptException, MovePrecision
from rka.eq2.master.game.scripting.procedures.common import TriggerReaderProcedure
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit, Procedure
from rka.log_configs import LOG_MOVEMENT

logger = LogService(LOG_MOVEMENT)


class LocationCheckerProcedure(TriggerReaderProcedure):
    class _Decorators:
        @classmethod
        def track_movements(cls, decorated):
            def wrapper(self, *args, **kwargs):
                started_here = self.start_movement_tracking()
                try:
                    result = decorated(self, *args, **kwargs)
                finally:
                    if started_here:
                        self.stop_movement_tracking()
                return result

            return wrapper

    def __init__(self, scripting: PlayerScriptingToolkit):
        TriggerReaderProcedure.__init__(self, scripting, game_command='loc')
        self._get_trigger().add_bus_event(PlayerInfoEvents.LOCATION(player=self._get_player()))
        self.__movement_tracking = False

    def _get_object(self, event: PlayerInfoEvents.LOCATION) -> Location:
        return event.location

    def _location_tracking_restarted(self):
        pass

    @_Decorators.track_movements
    def get_location(self) -> Optional[Location]:
        location = self._get_new_result()
        logger.debug(f'get_location: {location}')
        return location

    def get_last_location(self) -> Optional[Location]:
        return self.get_last_result()

    def start_movement_tracking(self) -> bool:
        logger.debug(f'start_movement_tracking: movement_tracking = {self.__movement_tracking}')
        if self.__movement_tracking:
            # this script is already tracking
            return False
        self.__movement_tracking = True
        self._location_tracking_restarted()
        self._get_trigger().start_trigger()
        return True

    def stop_movement_tracking(self) -> bool:
        logger.debug(f'stop_movement_tracking: movement_tracking = {self.__movement_tracking}')
        if not self.__movement_tracking:
            return False
        self._get_trigger().cancel_trigger()
        self.__movement_tracking = False
        return True


class GenericMovementProcedure(LocationCheckerProcedure):
    __movement_params: Dict[str, MovementParams] = dict()

    @staticmethod
    def __get_params_for_player(pname: str, force_new=False) -> MovementParams:
        if pname not in GenericMovementProcedure.__movement_params.keys() or force_new:
            GenericMovementProcedure.__movement_params[pname] = MovementParams()
        return GenericMovementProcedure.__movement_params[pname]

    def __init__(self, scripting: PlayerScriptingToolkit):
        LocationCheckerProcedure.__init__(self, scripting)
        self.__params = None
        self.__angle_for_moving_backwards = 170.0

    def _get_params(self) -> MovementParams:
        if self.__params is None:
            self.__params = GenericMovementProcedure.__get_params_for_player(self._get_player().get_player_name(), force_new=True)
        return self.__params

    def _location_tracking_restarted(self):
        # reset the minimum durations to avoid excess stacking
        self.__params = None

    def _get_rotation_duration(self, rotation_angle: float, rotation_attempts: int) -> float:
        raise NotImplementedError()

    def _update_rotation_duration(self, rotation_angle: float, actual_angle_rotated: float, rotation_duration: float):
        raise NotImplementedError()

    def set_angle_for_moving_backwards(self, angle: float):
        self.__angle_for_moving_backwards = angle

    def rotate_towards(self, current_location: Location, angle_for_move: Location, rotation_precision: float, allow_backwards: bool) -> Optional[Location]:
        logger.info(f'rotate_towards: angle_for_move={angle_for_move}, rotation_precision={rotation_precision}, allow_backwards={allow_backwards}')
        for rotation_attempt in range(MovementParams.MAX_TURN_ATTEMPTS):
            if current_location.is_angle_reached(angle_for_move, rotation_precision, allow_backwards):
                break
            rotation_angle, rotation_sign = current_location.get_angular_distance_and_rotation_sign(angle_for_move)
            if allow_backwards and rotation_angle > self.__angle_for_moving_backwards:
                rotation_angle = 180.0 - rotation_angle
                rotation_sign = -rotation_sign
                # check angle again, might be already facing backwards properly
                if current_location.is_angle_reached(angle_for_move, rotation_precision, allow_backwards):
                    break
            rotation_angle = min(rotation_angle, self._get_params().max_rotation_angle)
            rotation_duration = self._get_rotation_duration(rotation_angle, rotation_attempt)
            logger.detail(f'turning dir {rotation_sign} by {rotation_angle} duration {rotation_duration}s')
            key = self._get_player().get_inputs().keyboard.key_turn_right if rotation_sign > 0 else self._get_player().get_inputs().keyboard.key_turn_left
            ac_rotation_key = action_factory.new_action().key(key, key_type_delay=rotation_duration)
            self._get_player_toolkit().call_player_action(ac_rotation_key)
            location_before_rotation = current_location
            current_location = self.get_location()
            if not current_location:
                return None
            actual_angle_rotated = current_location.get_actual_angle_rotated(location_before_rotation, rotation_sign)
            logger.detail(f'rotation result: angle diff={rotation_angle}, actual diff={actual_angle_rotated}, t={rotation_duration}')
            self._update_rotation_duration(rotation_angle, actual_angle_rotated, rotation_duration)
        return current_location

    def _get_movement_duration(self, movement_distance: float, move_attempts: int) -> float:
        raise NotImplementedError()

    def _update_movement_duration(self, movement_distance: float, actual_movement_distance: float, movement_duration: float):
        raise NotImplementedError()

    def move_player_in_current_direction(self, current_location: Location, target_location: Location, movement_precision: float,
                                         movement_attempts: int, movement_key: str) -> Optional[Location]:
        logger.info(f'move_player_in_current_direction: target_location={target_location}, movement_precision={movement_precision}, movement_attempts={movement_attempts}')
        if current_location.is_horizontal_location_reached(target_location, movement_precision):
            return current_location
        movement_distance = current_location.get_horizontal_distance(target_location)
        movement_distance = min(movement_distance, self._get_params().max_movement_distance)
        movement_duration = self._get_movement_duration(movement_distance, movement_attempts)
        ac_movement_key = action_factory.new_action().key(movement_key, key_type_delay=movement_duration)
        logger.detail(f'moving by {movement_distance}, key {movement_key}, duration {movement_duration}s')
        self._get_player_toolkit().call_player_action(ac_movement_key)
        location_before_move = current_location
        current_location = self.get_location()
        if not current_location:
            return None
        actual_movement_distance = location_before_move.get_horizontal_distance(current_location)
        self._update_movement_duration(movement_distance, actual_movement_distance, movement_duration)
        logger.detail(f'movement result: planned move:{movement_distance}, actual:{actual_movement_distance}, t={movement_duration}')
        return current_location

    def _movement_loop(self, target_location: LocationRef, starting_location: Optional[Location] = None,
                       rotation_precision: Optional[float] = None, movement_precision: Optional[float] = None) -> bool:
        if rotation_precision is None:
            rotation_precision = self._get_params().default_rotation_precision
        if movement_precision is None:
            movement_precision = self._get_params().default_movement_precision
        current_target_location = target_location.get_location()
        current_location = starting_location if starting_location else self.get_location()
        logger.info(f'_movement_loop: target loc is {current_target_location}, current loc is {current_location}, RP:{rotation_precision}, MP:{movement_precision}')
        if not current_location:
            logger.warn(f'_movement_loop: no starting location acquired')
            return False
        if current_target_location.has_position():
            location_reached = False
            for move_attempt in range(MovementParams.MAX_MOVE_ATTEMPTS):
                location_reached = current_location.is_horizontal_location_reached(current_target_location, movement_precision)
                if location_reached:
                    break
                angle_for_move = current_location.get_angle_to_target_location(current_target_location)
                current_location = self.rotate_towards(current_location, angle_for_move, RotatePrecision.NORMAL, allow_backwards=True)
                if not current_location:
                    logger.warn(f'_movement_loop: no current location acquired')
                    return False
                front_facing = current_location.is_front_facing(current_target_location)
                if front_facing:
                    movement_key = self._get_player().get_inputs().keyboard.key_move_forward
                else:
                    logger.detail(f'_movement_loop: using backwards facing, angle is {angle_for_move.angle_xz}')
                    movement_key = self._get_player().get_inputs().keyboard.key_move_backwards
                current_location = self.move_player_in_current_direction(current_location, current_target_location, movement_precision,
                                                                         move_attempt, movement_key)
                if not current_location:
                    logger.warn(f'_movement_loop: no current location acquired after move')
                    return False
                location_reached = current_location.is_horizontal_location_reached(current_target_location, movement_precision)
                if target_location.is_changed():
                    return True
                if not self._get_player().is_alive():
                    return False
            if not location_reached:
                logger.warn(f'_movement_loop: location not reached after movement, loc is {current_location}')
                return False
        if current_target_location.has_orientation():
            current_location = self.rotate_towards(current_location, current_target_location, rotation_precision, allow_backwards=False)
            if not current_location:
                logger.warn(f'_movement_loop: location not reached after rotation, loc is {current_location}')
                return False
        logger.info(f'_movement_loop: completed, loc is {current_location}')
        return True

    def __clear_playercombatautoface(self):
        cmd_str = f'ics_playercombatautoface 0\nics_combatautoface 0\nstop_follow'
        action = self._get_player_toolkit().build_multicommand(cmd_str)
        # dont use toolkit, script might be expired
        action.call_action(self._get_player().get_client_id())

    def start_movement_tracking(self) -> bool:
        started_here = super().start_movement_tracking()
        if started_here:
            self.__clear_playercombatautoface()
        return started_here

    def stop_movement_tracking(self) -> bool:
        stopped_here = super().stop_movement_tracking()
        return stopped_here

    @LocationCheckerProcedure._Decorators.track_movements
    def move_to_location(self, target_location: LocationRef, starting_location: Optional[Location] = None,
                         rotation_precision: Optional[float] = None, movement_precision: Optional[float] = None) -> bool:
        return self._movement_loop(target_location=target_location, starting_location=starting_location,
                                   rotation_precision=rotation_precision, movement_precision=movement_precision)

    @LocationCheckerProcedure._Decorators.track_movements
    def follow_locations(self, path: LocationInputStream, pathing_precision: Optional[float] = None,
                         final_rotation_precision: Optional[float] = None, final_movement_precision: Optional[float] = None):
        location = None
        for location in path.iter_locations():
            self._movement_loop(location, movement_precision=pathing_precision, rotation_precision=RotatePrecision.COARSE)
        if location:
            self._movement_loop(location, rotation_precision=final_rotation_precision, movement_precision=final_movement_precision)


class LocationGuard:
    class SharedLocation:
        def __init__(self, location: Location, radius: float, duration: float):
            self.__radius = radius
            self.__duration = duration
            self.__location = location
            self.__locked_at: Optional[float] = None
            self.__lock = threading.RLock()
            self.__condition = threading.Condition(self.__lock)

        def overlaps(self, location: Location) -> bool:
            with self.__lock:
                return self.__location.get_horizontal_distance(location) <= self.__radius

        def is_same(self, location: Location) -> bool:
            with self.__lock:
                return self.__location == location

        def update(self, radius: float, duration: float):
            with self.__lock:
                self.__radius = max(radius, self.__radius)
                self.__duration = max(duration, self.__duration)

        def acquire(self, timeout=0.0) -> bool:
            with self.__lock:
                acquire_start = time.time()
                while self.__locked_at is not None:
                    now = time.time()
                    remaining_duration = self.__duration - (now - self.__locked_at)
                    if remaining_duration <= 0.0:
                        self.__locked_at = None
                        break
                    wait_time = remaining_duration
                    if timeout > 0.0:
                        remaining_timeout = timeout - (now - acquire_start)
                        if remaining_timeout <= 0.0:
                            return False
                        wait_time = min(remaining_duration, remaining_timeout)
                    self.__condition.wait(wait_time)
                self.__locked_at = time.time()
                return True

        def release(self):
            with self.__lock:
                if self.__locked_at:
                    self.__locked_at = None
                    self.__condition.notify_all()

    __shared_locations_lock = threading.Lock()
    __shared_locations: Dict[str, List[SharedLocation]] = dict()

    @staticmethod
    def lock_exclusive_shared_location(zone: str, location: Location, radius: float, duration: float):
        with LocationGuard.__shared_locations_lock:
            shared_locations = LocationGuard.__shared_locations.setdefault(zone, list())
            already_existed = False
            for shared_location in shared_locations:
                if shared_location.is_same(location):
                    shared_location.update(radius, duration)
                    already_existed = True
                    break
            if not already_existed:
                shared_locations.append(LocationGuard.SharedLocation(location, radius, duration))
            shared_locations_copy = list(shared_locations)
        for shared_location in shared_locations_copy:
            if not shared_location.overlaps(location):
                continue
            if not shared_location.acquire():
                logger.warn(f'failed to acquire location {zone}: {location}')
        logger.debug(f'locked location {zone}: {location}')

    @staticmethod
    def unlock_exclusive_shared_location(zone: str, location: Location):
        with LocationGuard.__shared_locations_lock:
            shared_locations_copy = list(LocationGuard.__shared_locations.setdefault(zone, list()))
        found_any = False
        for shared_location in shared_locations_copy:
            if not shared_location.overlaps(location):
                continue
            found_any = True
            shared_location.release()
        if found_any:
            logger.debug(f'released location {zone}: {location}')
        else:
            logger.warn(f'location not released - no overlapping areas found {zone}: {location}')


@DeprecationWarning
class MovementProcedureAdaptive(GenericMovementProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        GenericMovementProcedure.__init__(self, scripting)

    def _get_rotation_duration(self, rotation_angle: float, rotation_attempts: int) -> float:
        if rotation_attempts > 0 and rotation_attempts % 5 == 0:
            rotation_angle += random.random() * 70
        rotation_duration = rotation_angle / self._get_params().rotation_speed
        rotation_duration = max(rotation_duration, self._get_params().min_rotation_duration)
        return rotation_duration

    def _update_rotation_duration(self, rotation_angle: float, actual_angle_rotated: float, rotation_duration: float):
        if actual_angle_rotated == 0.0:
            self._get_params().min_rotation_duration *= 1.3
            return
        self._get_params().rotation_speed = self._get_params().rotation_speed * 0.7 + 0.3 * actual_angle_rotated / rotation_duration

    def _get_movement_duration(self, movement_distance: float, move_attempts: int) -> float:
        movement_duration = movement_distance / self._get_params().movement_speed
        movement_duration = max(movement_duration, self._get_params().min_movement_duration)
        movement_duration = min(movement_duration, self._get_params().max_movement_duration)
        return movement_duration

    def _update_movement_duration(self, movement_distance: float, actual_movement_distance: float, movement_duration: float):
        if actual_movement_distance == 0.0:
            self._get_params().min_movement_duration *= 1.1
        self._get_params().movement_speed = self._get_params().movement_speed * 0.7 + 0.3 * actual_movement_distance / movement_duration


class MovementProcedureFixed(GenericMovementProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        GenericMovementProcedure.__init__(self, scripting)

    def _get_rotation_duration(self, rotation_angle: float, rotation_attempts: int) -> float:
        d = self._get_params().rotation_duration_at_90 - self._get_params().rotation_duration_at_3
        rotation_duration = d * (rotation_angle - 3.0) / (90 - 3) + self._get_params().rotation_duration_at_3
        return rotation_duration

    def _update_rotation_duration(self, rotation_angle: float, actual_angle_rotated: float, rotation_duration: float):
        if actual_angle_rotated == 0.0:
            self._get_params().rotation_duration_at_3 += 0.03

    def _get_movement_duration(self, movement_distance: float, move_attempts: int) -> float:
        is_combat = self._get_runtime().combatstate.is_game_combat()
        speed = self._get_params().precision_movement_speed(movement_distance, is_combat)
        movement_duration = movement_distance / speed
        movement_duration = max(movement_duration, self._get_params().min_movement_duration)
        movement_duration = min(movement_duration, self._get_params().max_movement_duration)
        return movement_duration

    def _update_movement_duration(self, movement_distance: float, actual_movement_distance: float, movement_duration: float):
        pass


class NavigationProcedure(Procedure):
    DEFAULT_MOVEMENT_PRECISION = MovePrecision.COARSE
    DEFAULT_ROTATION_PRECISION = RotatePrecision.NORMAL

    def __init__(self, scripting: PlayerScriptingToolkit, final_loc_high_precision: bool, final_loc_rotation: bool):
        Procedure.__init__(self, scripting)
        self.__final_loc_high_precision = final_loc_high_precision
        self.__final_loc_rotation = final_loc_rotation
        self.__movement = MovementProcedureFactory.create_movement_procedure(scripting)

    def start_movement_tracking(self) -> bool:
        return self.__movement.start_movement_tracking()

    def stop_movement_tracking(self) -> bool:
        return self.__movement.stop_movement_tracking()

    def navigate_to_location(self, location_ref: LocationRef) -> bool:
        zone_name = self._get_player().get_zone()
        target_location = location_ref.get_location()
        pathing = self._get_runtime().zonemaps.get_pathing_to(zone_name, target_location)
        final_mp = MovePrecision.HIGH if self.__final_loc_high_precision else NavigationProcedure.DEFAULT_MOVEMENT_PRECISION
        final_rp = RotatePrecision.HIGH if self.__final_loc_high_precision else NavigationProcedure.DEFAULT_ROTATION_PRECISION
        if not pathing:
            return self.__movement.move_to_location(location_ref, movement_precision=final_mp, rotation_precision=final_rp)
        try:
            self.__movement.start_movement_tracking()
            current_location = self.__movement.get_location()
            if not current_location:
                return False
            pathing.push_location(current_location)
            next_location = None
            for next_location in pathing.iter_locations():
                reached = self.__movement.move_to_location(next_location, starting_location=current_location,
                                                           movement_precision=NavigationProcedure.DEFAULT_MOVEMENT_PRECISION,
                                                           rotation_precision=NavigationProcedure.DEFAULT_ROTATION_PRECISION)
                if not reached:
                    return False
                current_location = self.__movement.get_last_location()
                pathing.push_location(current_location)
            if next_location and self.__final_loc_high_precision:
                self.__movement.move_to_location(next_location, movement_precision=final_mp, rotation_precision=final_rp)
            if self.__final_loc_rotation:
                # make final rotation, pathing doesnt include orientations
                if next_location:
                    final_location = Location.from_position_and_orientation(position=next_location, orientation=target_location)
                else:
                    final_location = target_location.get_orientation()
                self.__movement.move_to_location(final_location, movement_precision=final_mp, rotation_precision=final_rp)
        except ScriptException:
            return False
        finally:
            self.__movement.stop_movement_tracking()
        return True


class MovementProcedureFactory:
    @staticmethod
    def create_movement_procedure(scripting: PlayerScriptingToolkit) -> GenericMovementProcedure:
        return MovementProcedureFixed(scripting)

    @staticmethod
    def create_navigation_procedure(scripting: PlayerScriptingToolkit, final_loc_high_precision: bool, final_loc_rotation: bool) -> NavigationProcedure:
        return NavigationProcedure(scripting, final_loc_high_precision, final_loc_rotation)
