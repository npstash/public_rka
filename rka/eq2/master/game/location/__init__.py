from __future__ import annotations

import math
from typing import Optional, Iterator, Callable

import regex as re

from rka.components.ai.graphs import Waypoint, Axis, WaypointExtensions


class LocationRef:
    def get_location(self) -> Optional[Location]:
        raise NotImplementedError()

    def is_changed(self) -> bool:
        raise NotImplementedError()

    def wait_for_change(self) -> bool:
        raise NotImplementedError()

    def unref(self):
        pass


class LocationTransformer(LocationRef):
    def __init__(self, source_ref: LocationRef, transform_cb: Callable[[Optional[Location]], Optional[Location]]):
        self.__transformed_source = source_ref
        self.__transform_cb = transform_cb

    def get_location(self) -> Optional[Location]:
        return self.__transform_cb(self.__transformed_source.get_location())

    def is_changed(self):
        return self.__transformed_source.is_changed()

    def wait_for_change(self) -> bool:
        return self.__transformed_source.wait_for_change()

    def unref(self):
        self.__transformed_source.unref()


class LocationPositionTransformer(LocationTransformer):
    def __init__(self, source_ref: LocationRef):
        LocationTransformer.__init__(self, source_ref, LocationPositionTransformer.transform)

    @staticmethod
    def transform(location: Optional[Location]) -> Optional[Location]:
        if not location:
            return None
        return location.get_position()


class Location(LocationRef):
    __serialized_location_parser = re.compile('\\{x:([^,]+), z:([^,]+), y:([^,]+), axz:([^,]+)(?:, info:(.*))?\\}')
    __game_location_parser = re.compile(r'(-?[\d,.]+) (-?[\d,.]+) (-?[\d,.]+) (-?[\d,.]+) (-?[\d,.]+) (-?[\d,.]+)')

    def __init__(self, x: Optional[float] = None, y: Optional[float] = None, z: Optional[float] = None,
                 axz: Optional[float] = None, info: Optional[str] = None):
        self.loc_x = x
        self.loc_y = y
        self.loc_z = z
        self.angle_xz = axz
        self.info = info

    def get_location(self) -> Optional[Location]:
        return self

    def is_changed(self) -> bool:
        return False

    def wait_for_change(self) -> bool:
        return False

    def __str__(self) -> str:
        if self.info:
            return self.info
        return f'{{x:{self.loc_x}, z:{self.loc_z}, y:{self.loc_y}, axz:{self.angle_xz}}}'

    def __eq__(self, other) -> bool:
        if not isinstance(other, Location):
            return False
        return self.loc_x == other.loc_x and self.loc_y == other.loc_y and self.loc_z == other.loc_z and self.angle_xz == other.angle_xz

    def encode_location(self, game_format=False) -> str:
        if game_format:
            if self.has_orientation():
                return f'{self.loc_x} {self.loc_y} {self.loc_z}'
            else:
                return f'{self.loc_x} {self.loc_y} {self.loc_z} {self.angle_xz} 0.0 0.0'
        if self.info:
            return f'{{x:{self.loc_x}, z:{self.loc_z}, y:{self.loc_y}, axz:{self.angle_xz}, info:{self.info}}}'
        return f'{{x:{self.loc_x}, z:{self.loc_z}, y:{self.loc_y}, axz:{self.angle_xz}}}'

    @staticmethod
    def decode_location(literal: str) -> Optional[Location]:
        match = Location.__serialized_location_parser.match(literal)
        if match:
            x_str = match.group(1)
            z_str = match.group(2)
            y_str = match.group(3)
            axz_str = match.group(4)
            info = match.group(5)
            x = float(x_str) if x_str != 'None' else None
            z = float(z_str) if z_str != 'None' else None
            y = float(y_str) if y_str != 'None' else None
            axz = float(axz_str) if axz_str != 'None' else None
            loc = Location(x=x, z=z, y=y, axz=axz)
            loc.info = info
            return loc
        match = Location.__game_location_parser.match(literal)
        if match:
            x_str = str(match.group(1)).replace(',', '')
            y_str = str(match.group(2)).replace(',', '')
            z_str = str(match.group(3)).replace(',', '')
            axz_str = str(match.group(4)).replace(',', '')
            return Location(x=float(x_str), y=float(y_str), z=float(z_str), axz=float(axz_str))
        return None

    def to_waypoint(self, default_y=0.0) -> Waypoint:
        y = self.loc_y if self.loc_y is not None else default_y
        assert self.has_position()
        waypoint = Waypoint(x=self.loc_x, y=y, z=self.loc_z)
        if self.info:
            waypoint[WaypointExtensions.INFO] = self.info
        return waypoint

    @staticmethod
    def from_waypoint(waypoint: Waypoint) -> Location:
        location = Location(x=waypoint[Axis.X], y=waypoint[Axis.Y], z=waypoint[Axis.Z], axz=None)
        if WaypointExtensions.INFO in waypoint:
            location.info = waypoint[WaypointExtensions.INFO]
        return location

    @staticmethod
    def from_position_and_orientation(position: Location, orientation: Location) -> Location:
        return Location(x=position.loc_x, y=position.loc_y, z=position.loc_z, axz=orientation.angle_xz)

    def has_position(self) -> bool:
        return self.loc_x is not None and self.loc_z is not None

    def has_orientation(self) -> bool:
        return self.angle_xz is not None

    def get_position(self) -> Location:
        return Location(x=self.loc_x, y=self.loc_y, z=self.loc_z, axz=None, info=self.info)

    def get_orientation(self) -> Location:
        return Location(x=None, y=None, z=None, axz=self.angle_xz, info=self.info)

    def get_horizontal_distance(self, target_location: Location) -> float:
        if not self.has_position() or not target_location.has_position():
            return 0.0
        dx = target_location.loc_x - self.loc_x
        dz = target_location.loc_z - self.loc_z
        d = (dx * dx + dz * dz) ** 0.5
        return d

    def get_vertical_distance(self, target_location: Location) -> float:
        if not self.has_position() or not target_location.has_position():
            return 0.0
        if self.loc_y is not None and target_location.loc_y is not None:
            dy = target_location.loc_y - self.loc_y
        else:
            dy = 0.0
        return dy

    def is_horizontal_location_reached(self, target_location: Location, movement_precision: float) -> bool:
        if not self.has_position() or not target_location.has_position():
            return True
        movement_precision = movement_precision
        dx = target_location.loc_x - self.loc_x
        dz = target_location.loc_z - self.loc_z
        return dx * dx + dz * dz <= movement_precision * movement_precision

    def is_vertical_location_reached(self, target_location: Location, movement_precision: float) -> bool:
        if not self.has_position() or not target_location.has_position():
            return True
        if self.loc_y is not None and target_location.loc_y is not None:
            dy = target_location.loc_y - self.loc_y
        else:
            dy = 0.0
        return dy <= movement_precision

    # returns 0.0 - 180.0, +/-1.0
    def get_angular_distance_and_rotation_sign(self, target_location: Location) -> (float, float):
        if not self.has_orientation() or not target_location.has_orientation():
            return 0.0, 1.0
        if target_location.angle_xz < self.angle_xz:
            da1 = self.angle_xz - target_location.angle_xz
            da2 = target_location.angle_xz + 360.0 - self.angle_xz
            if da1 < da2:
                return da1, -1.0
            return da2, 1.0
        else:
            da1 = target_location.angle_xz - self.angle_xz
            da2 = self.angle_xz + 360.0 - target_location.angle_xz
            if da1 < da2:
                return da1, 1.0
            return da2, -1.0

    def is_angle_reached(self, target_location: Location, rotation_precision: float, allow_backwards_facing=False) -> bool:
        if not self.has_orientation() or not target_location.has_orientation():
            return True
        da, _ = self.get_angular_distance_and_rotation_sign(target_location)
        if allow_backwards_facing and abs(180.0 - da) <= rotation_precision:
            return True
        return da <= rotation_precision

    def get_angle_to_target_location(self, target_location: Location) -> Location:
        if not self.has_position() or not target_location.has_position():
            return target_location
        dx = target_location.loc_x - self.loc_x
        dz = target_location.loc_z - self.loc_z
        if -0.05 < dz < 0.05:
            dz = 0.05 * (-1 if dz < 0 else 1)
        angle = math.atan(dx / dz) / math.pi * 180.0
        # noinspection PyChainedComparisons
        if dx <= 0 and dz < 0:
            # angle in range 0-90, correct
            pass
        elif dx <= 0 and dz > 0:
            # angle in range -90-0, add 180 to move into range 90-180
            angle += 180
        elif dx > 0 and dz > 0:
            # angle in range 0-90, add 180 to move into range 180-270
            angle += 180
        else:
            # angle in range -90-0, add 360 to move into range 270-360
            angle += 360
        return Location(x=None, z=None, axz=angle)

    def get_actual_angle_rotated(self, location_before_rotation: Location, rotation_sign: float) -> Optional[float]:
        if not self.has_orientation() or not location_before_rotation.has_orientation():
            return location_before_rotation.angle_xz
        if rotation_sign > 0:
            if self.angle_xz < location_before_rotation.angle_xz:
                actual_angle_rotated = self.angle_xz + 360.0 - location_before_rotation.angle_xz
            else:
                actual_angle_rotated = self.angle_xz - location_before_rotation.angle_xz
        else:
            if self.angle_xz > location_before_rotation.angle_xz:
                actual_angle_rotated = location_before_rotation.angle_xz + 360.0 - self.angle_xz
            else:
                actual_angle_rotated = location_before_rotation.angle_xz - self.angle_xz
        return actual_angle_rotated

    def is_front_facing(self, target_location: Location) -> bool:
        angle_to_target_loc = self.get_angle_to_target_location(target_location)
        rotation_angle, _ = self.get_angular_distance_and_rotation_sign(angle_to_target_loc)
        return rotation_angle <= 90.0


class LocationOutputStream:
    def push_location(self, location: Location) -> bool:
        raise NotImplementedError()

    def close_sink(self):
        raise NotImplementedError()


class LocationInputStream:
    def pop_location(self) -> Optional[Location]:
        raise NotImplementedError()

    def iter_locations(self) -> Iterator[Location]:
        while True:
            loc = self.pop_location()
            if not loc:
                return
            yield loc

    def continue_after_failed_movement(self, location: Location) -> bool:
        raise NotImplementedError()

    def close_source(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class LocationPipe(LocationInputStream, LocationOutputStream):
    def close_pipe(self):
        self.close_source()
        self.close_sink()


class LocationSourceFactory:
    def create_location_source(self) -> LocationInputStream:
        raise NotImplementedError()
