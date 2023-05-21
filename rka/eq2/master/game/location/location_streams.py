import time
from threading import Condition
from typing import Callable, Optional

from rka.components.ai.graphs import Path, Waypoint
from rka.eq2.master.game.location import Location, LocationOutputStream, LocationInputStream, LocationPipe, LocationRef
from rka.eq2.master.game.scripting.toolkit import ScriptingToolkit


class CallbackLocationOutputStream(LocationOutputStream):
    def __init__(self, callback: Callable[[Location], bool]):
        self.__callback = callback
        self.__closed = False

    def push_location(self, location: Location) -> bool:
        if self.__closed:
            return False
        self.__closed = self.__callback(location)
        return not self.__closed

    def close_sink(self):
        self.__closed = True


class FileLocationOutputStream(LocationOutputStream):
    def __init__(self, filename: str):
        self.__recording_filename = filename
        self.__recording_file = None
        self.__closed = False

    def push_location(self, location: Location) -> bool:
        if self.__closed:
            return False
        if not self.__recording_file:
            try:
                self.__recording_file = open(self.__recording_filename, 'w')
            except IOError:
                self.__closed = True
                return False
        self.__recording_file.write(f'{location.encode_location()}\n')
        return True

    def close_sink(self):
        if self.__closed or not self.__recording_file:
            return
        self.__recording_file.close()
        self.__closed = True


class LocationInputStreamTransformer(LocationInputStream):
    def __init__(self, input_stream: LocationInputStream, transform_cb: Callable[[Location], Optional[Location]]):
        self.__transformed_source = input_stream
        self.__transform_cb = transform_cb

    def pop_location(self) -> Optional[Location]:
        loc = self.__transformed_source.pop_location()
        if not loc:
            return None
        return self.__transform_cb(loc)

    def continue_after_failed_movement(self, location: Location) -> bool:
        return self.__transformed_source.continue_after_failed_movement(location)

    def close_source(self):
        self.__transformed_source.close_source()


class FixedLocationInputStream(LocationInputStream):
    def __init__(self, fixed_location: Location, delay: float):
        self.__fixed_location = fixed_location
        self.__delay = delay
        self.__closed = False
        self.__first_given = False

    def pop_location(self) -> Optional[Location]:
        if self.__closed:
            return None
        if self.__first_given:
            time.sleep(self.__delay)
        self.__first_given = True
        return self.__fixed_location

    def continue_after_failed_movement(self, location: Location) -> bool:
        return not self.__closed

    def close_source(self):
        self.__closed = True


class SingleLocationInputStream(LocationInputStream):
    def __init__(self, location: Location):
        self.__location = location
        self.__closed = False

    def pop_location(self) -> Optional[Location]:
        if self.__closed:
            return None
        self.__closed = True
        return self.__location

    def continue_after_failed_movement(self, location: Location) -> bool:
        return not self.__closed

    def close_source(self):
        self.__closed = True


class FileLocationInputStream(LocationInputStream):
    def __init__(self, filename: str):
        self.__filename = filename
        self.__record_file = None
        self.__closed = False

    def pop_location(self) -> Optional[Location]:
        if self.__closed:
            return None
        if not self.__record_file:
            try:
                self.__record_file = open(self.__filename, 'r')
            except IOError:
                self.__closed = True
                return
        line = self.__record_file.readline().strip()
        if not line:
            self.close_source()
            return None
        loc_str = line.strip()
        return Location.decode_location(loc_str)

    def continue_after_failed_movement(self, location: Location) -> bool:
        return not self.__closed

    def close_source(self):
        if self.__closed:
            return
        self.__record_file.close()
        self.__closed = True


class LocationStreamConnector(LocationPipe, LocationRef):
    def __init__(self, scripting: Optional[ScriptingToolkit] = None):
        self.__scripting = scripting
        self.__location: Optional[Location] = None
        self.__location_condition = Condition()
        self.__update_count = 0
        self.__closed = False
        self.__max_pop_wait = 60.0
        self.__already_waited = 0.0

    def __reset_change(self):
        self.__update_count = 0

    def __wait(self):
        if self.__scripting:
            self.__scripting.wait(self.__location_condition, 2.0)
        else:
            self.__location_condition.wait(2.0)
        self.__already_waited += 2.0

    def __acquire_location(self):
        with self.__location_condition:
            self.__already_waited = 0.0
            while self.__location is None and not self.__closed:
                if self.__already_waited >= self.__max_pop_wait:
                    return
                self.__wait()
            if self.__closed:
                self.__location = None

    def set_max_pop_wait(self, timeout: float):
        self.__max_pop_wait = timeout

    def get_location(self) -> Optional[Location]:
        with self.__location_condition:
            self.__acquire_location()
            self.__reset_change()
            return self.__location

    def is_changed(self) -> bool:
        return self.__update_count > 0

    def wait_for_change(self) -> bool:
        with self.__location_condition:
            self.__already_waited = 0.0
            while not self.__closed and not self.is_changed():
                if self.__already_waited >= self.__max_pop_wait:
                    return False
                self.__wait()
            if self.__closed:
                return False
            return self.is_changed()

    def unref(self):
        self.close_source()

    def pop_location(self) -> Optional[Location]:
        with self.__location_condition:
            self.__acquire_location()
            location = self.__location
            self.__location = None
            self.__reset_change()
            return location

    def continue_after_failed_movement(self, _location: Location) -> bool:
        return not self.__closed

    def close_sink(self):
        with self.__location_condition:
            self.__closed = True
            self.__location_condition.notify()

    def close_source(self):
        with self.__location_condition:
            self.__closed = True
            self.__location_condition.notify()

    def push_location(self, location: Location) -> bool:
        assert location
        if self.__closed:
            return False
        with self.__location_condition:
            if not self.__location or self.__location != location:
                self.__update_count += 1
            self.__location = location
            self.__location_condition.notify()
        return True


class PathingLocationInputStream(LocationPipe):
    def __init__(self, path: Path, final_loc: Location, default_y=0.0, use_lines=False):
        self.__path = path
        self.__final_location = final_loc
        self.__current_waypoint: Optional[Waypoint] = None
        self.__default_y = default_y
        self.__closed = False
        self.__use_lines = use_lines

    def pop_location(self) -> Optional[Location]:
        if self.__closed or self.__path.is_end_reached():
            self.__closed = True
            return None
        if not self.__current_waypoint:
            return None
        if self.__use_lines:
            waypoint = self.__path.get_next_furthest_waypoint_on_line(self.__current_waypoint)
        else:
            waypoint = self.__path.get_next_nearest_waypoint(self.__current_waypoint)
        if waypoint is None and self.__path.is_end_reached():
            return self.__final_location
        if waypoint is None:
            self.__closed = True
            return None
        return Location.from_waypoint(waypoint)

    def push_location(self, location: Location) -> bool:
        self.__current_waypoint = location.to_waypoint(self.__default_y)
        return not self.__path.is_end_reached()

    def continue_after_failed_movement(self, location: Location) -> bool:
        return False

    def close_source(self):
        self.__closed = True

    def close_sink(self):
        self.__closed = True
