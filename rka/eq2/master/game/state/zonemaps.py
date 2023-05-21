import json
import time
from json.encoder import JSONEncoder
from threading import RLock
from typing import Dict, Optional, Any

from rka.components.ai.graphs import MapGraph, SpatialRule, Axis, IWaypointComparator
from rka.components.cleanup import Closeable
from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.datafiles import zone_map_filename, saved_formations_filename
from rka.eq2.master import IRuntime
from rka.eq2.master.game import is_unknown_zone, get_canonical_zone_name
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location, LocationOutputStream, LocationPipe
from rka.eq2.master.game.location.location_streams import FileLocationOutputStream, FileLocationInputStream, PathingLocationInputStream
from rka.eq2.master.game.scripting.procedures.movement import NavigationProcedure
from rka.eq2.master.game.state import logger
from rka.eq2.master.serialize import EventParamSerializer


class ZoneMaps(LocationOutputStream, Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=False)
        self.__runtime = runtime
        self.__lock = RLock()
        proximity_dist = NavigationProcedure.DEFAULT_MOVEMENT_PRECISION
        self.proximity_rule = SpatialRule(max_distance_by_axis={Axis.X: proximity_dist, Axis.Z: proximity_dist, Axis.Y: 2.0},
                                          constraints=[IWaypointComparator.no_further_than_xz(proximity_dist)])
        self.merge_rule = SpatialRule(max_distance_by_axis={Axis.X: 1.5, Axis.Z: 1.5, Axis.Y: 1.5},
                                      constraints=[IWaypointComparator.no_further_than_xz(2.0)])
        self.connect_rule = SpatialRule(max_distance_by_axis={Axis.X: 6.0, Axis.Z: 6.0, Axis.Y: 2.5},
                                        constraints=[IWaypointComparator.no_further_than_xz(6.0)])
        self.reach_rule = SpatialRule(max_distance_by_axis={Axis.X: 20.0, Axis.Z: 20.0, Axis.Y: 10.0},
                                      constraints=[IWaypointComparator.no_further_than_xz(20.0)])
        self.__cached_maps: Dict[str, MapGraph] = dict()
        self.__current_zone_name = None
        self.__current_formations: Optional[Dict[str, Dict[IPlayer, Location]]] = None
        self.__formations_aliases: Dict[str, str] = dict()
        self.__temporary_locations: Dict[str, Location] = dict()
        self.__serializers = EventParamSerializer(runtime)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__zone_changed)

    def __create_zone_map(self) -> MapGraph:
        return MapGraph(proximity_rule=self.proximity_rule, merge_rule=self.merge_rule,
                        connect_rule=self.connect_rule, reach_rule=self.reach_rule)

    @staticmethod
    def __get_average_y(zonemap: MapGraph) -> float:
        total_y = 0.0
        count = 0
        for wp in zonemap.get_graph().iterate_waypoints():
            total_y += wp[Axis.Y]
            count += 1
        return total_y / count if count else 0.0

    def __load_zone_map(self, zone_name: str) -> Optional[MapGraph]:
        if is_unknown_zone(zone_name):
            return None
        canonical_zone_name = get_canonical_zone_name(zone_name)
        filename = zone_map_filename(canonical_zone_name)
        reader = FileLocationInputStream(filename)
        locations = list(reader.iter_locations())
        reader.close_source()
        total_y = 0.0
        count = 0
        for location in locations:
            if location.loc_y is not None:
                total_y += location.loc_y
                count += 1
        default_y = total_y / count if count else 0.0
        loaded_map = None
        for location in locations:
            if not loaded_map:
                loaded_map = self.__create_zone_map()
            waypoint = location.to_waypoint(default_y=default_y)
            loaded_map.add_waypoint(waypoint)
        if loaded_map:
            self.__runtime.overlay.log_event(f'Loaded waypoints for {zone_name}', Severity.Normal)
        return loaded_map

    def __save_zone_map(self, map_to_save: MapGraph, zone_name: str) -> bool:
        assert map_to_save, zone_name
        if is_unknown_zone(zone_name):
            return False
        waypoints = list(map_to_save.get_graph().iterate_waypoints())
        if not waypoints:
            return True
        canonical_zone_name = get_canonical_zone_name(zone_name)
        filename = zone_map_filename(canonical_zone_name)
        writer = FileLocationOutputStream(filename)
        for waypoint in waypoints:
            location = Location.from_waypoint(waypoint)
            writer.push_location(location)
        writer.close_sink()
        self.__runtime.overlay.log_event(f'Saved waypoints for {zone_name}', Severity.Normal)
        return True

    def __get_cached_zone_map(self, zone_name: str, create_if_absent: bool) -> Optional[MapGraph]:
        with self.__lock:
            if is_unknown_zone(zone_name):
                return None
            canonical_zone_name = get_canonical_zone_name(zone_name)
            if canonical_zone_name not in self.__cached_maps:
                if not create_if_absent:
                    return None
                new_zone_map = self.__create_zone_map()
                self.__cached_maps[canonical_zone_name] = new_zone_map
            return self.__cached_maps[canonical_zone_name]

    def __set_cached_zone_map(self, zone_name: str, zone_map: MapGraph) -> bool:
        with self.__lock:
            if is_unknown_zone(zone_name):
                return False
            canonical_zone_name = get_canonical_zone_name(zone_name)
            self.__cached_maps[canonical_zone_name] = zone_map.copy_map()
            return True

    def __get_zone_map(self, zone_name: str, create_if_absent: bool) -> Optional[MapGraph]:
        with self.__lock:
            zone_map = self.__get_cached_zone_map(zone_name, False)
            if not zone_map:
                zone_map = self.__load_zone_map(zone_name)
                if zone_map:
                    self.__set_cached_zone_map(zone_name, zone_map)
            if not zone_map and create_if_absent:
                zone_map = self.__get_cached_zone_map(zone_name, True)
            return zone_map

    def __save_current_zone_map(self) -> bool:
        with self.__lock:
            zone_map = self.__get_cached_zone_map(self.__current_zone_name, False)
            if not zone_map:
                return False
            return self.__save_zone_map(zone_map, self.__current_zone_name)

    def get_current_zone_map(self) -> Optional[MapGraph]:
        with self.__lock:
            zone_map = self.__get_zone_map(self.__current_zone_name, False)
            if not zone_map:
                return None
            return zone_map.copy_map()

    def update_current_map(self, mapgraph: MapGraph) -> bool:
        with self.__lock:
            if not self.__set_cached_zone_map(self.__current_zone_name, mapgraph):
                logger.warn(f'Cannot update zone map, zone name not set')
                return False
            return self.__save_current_zone_map()

    def get_current_zone_name(self) -> Optional[str]:
        return self.__current_zone_name

    def get_location_by_name(self, info: str) -> Optional[Location]:
        with self.__lock:
            if not info:
                logger.warn(f'Expected non-null info for location')
                return None
            if info.lower() in self.__temporary_locations:
                return self.__temporary_locations[info.lower()]
            zone_map = self.__get_zone_map(self.__current_zone_name, False)
            if not zone_map:
                return None
            graph = zone_map.get_graph()
            for waypoint in graph.iterate_waypoints():
                location = Location.from_waypoint(waypoint)
                if location.info and location.info.lower() == info.lower():
                    return location
        return None

    def push_location(self, location: Location) -> bool:
        with self.__lock:
            zone_map = self.__get_zone_map(self.__current_zone_name, True)
            waypoint = location.to_waypoint(default_y=ZoneMaps.__get_average_y(zone_map))
            zone_map.add_waypoint(waypoint)
        return True

    def add_temporary_location(self, location: Location):
        with self.__lock:
            if not location.info:
                logger.warn(f'No info for temporary location {location}')
                return
            self.__temporary_locations[location.info.lower()] = location

    def remove_temporary_location(self, location: Location):
        with self.__lock:
            if not location.info or location.info.lower() not in self.__temporary_locations:
                return
            del self.__temporary_locations[location.info.lower()]

    def save_location(self):
        main_player = self.__runtime.playerstate.get_main_player()
        if not main_player:
            return
        requested_zone = self.get_current_zone_name()
        if not requested_zone:
            return
        requested_at = time.time()

        def location_received(event: PlayerInfoEvents.LOCATION):
            def save_location(location_name: Optional[str]):
                if not location_name:
                    return
                if self.get_current_zone_name() != requested_zone:
                    return
                location = event.location
                location.info = location_name
                self.push_location(location)

            if time.time() > requested_at + 5.0:
                return
            self.__runtime.overlay.get_text(f'Location name for {event.location}', save_location)
            EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.LOCATION, location_received)

        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.LOCATION(player=main_player), location_received)
        self.__runtime.request_ctrl.request_location(main_player)

    def close_sink(self):
        self.__save_current_zone_map()

    def close(self):
        self.close_sink()
        Closeable.close(self)

    def __zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        if not event.player.is_main_player():
            return
        new_zone = event.player.get_zone()
        if new_zone == self.__current_zone_name:
            return
        logger.info(f'change_to_zone: {self.__current_zone_name} -> {event.player.get_zone()}')
        with self.__lock:
            if self.__current_zone_name:
                self.__save_current_zone_map()
            self.__get_zone_map(new_zone, False)
            self.__current_zone_name = new_zone
            self.__current_formations = None
            self.__formations_aliases.clear()
            self.__temporary_locations.clear()

    def get_pathing_to(self, zone_name: str, target_loc: Location) -> Optional[LocationPipe]:
        if is_unknown_zone(zone_name):
            return None
        with self.__lock:
            loaded_map = self.__get_zone_map(zone_name, False)
            if not loaded_map:
                return None
            average_y = ZoneMaps.__get_average_y(loaded_map)
            waypoint = target_loc.to_waypoint(default_y=average_y)
            path = loaded_map.get_paths_to(waypoint)
            if not path:
                return None
            return PathingLocationInputStream(path=path, final_loc=target_loc, default_y=average_y, use_lines=True)

    def __json_to_object(self, obj) -> Any:
        if isinstance(obj, dict):
            for k, v in obj.items():
                obj[k] = self.__json_to_object(v)
        return self.__serializers.json_to_object(obj)

    def __object_to_json(self, **kwargs) -> JSONEncoder:
        return EventParamSerializer(self.__runtime, **kwargs)

    def load_formations(self) -> Dict[str, Dict[IPlayer, Location]]:
        if is_unknown_zone(self.__current_zone_name):
            logger.warn(f'cannot load formations, no zone set')
            return dict()
        if self.__current_formations is None:
            self.__load_formations()
        result = dict(self.__current_formations)
        for alias, formation_id in self.__formations_aliases.items():
            result[alias] = result[formation_id]
        return result

    def __load_formations(self):
        canonical_zone_name = get_canonical_zone_name(self.__current_zone_name)
        filename = saved_formations_filename(canonical_zone_name)
        try:
            with open(filename, 'r') as file:
                data = json.load(file, object_hook=self.__json_to_object)
            self.__current_formations = {f_id: {p_loc['player']: p_loc['location'] for p_loc in p_locs} for f_id, p_locs in data.items()}
        except FileNotFoundError:
            self.__current_formations = dict()
        except IOError:
            logger.warn(f'Could not load formations for {self.__current_zone_name}')
            self.__current_formations = dict()

    def store_formation(self, formation_id: str, formation: Dict[IPlayer, Location]) -> bool:
        if is_unknown_zone(self.__current_zone_name):
            logger.warn(f'cannot save formation {formation_id}, no zone set')
            return False
        if self.__current_formations is None:
            self.__load_formations()
        self.__current_formations[formation_id] = formation
        for player, location in formation.items():
            location.info = f'location for {player.get_player_name()}'
        data = {f_id: [{'player': player, 'location': location} for player, location in fms.items()] for f_id, fms in self.__current_formations.items()}
        canonical_zone_name = get_canonical_zone_name(self.__current_zone_name)
        filename = saved_formations_filename(canonical_zone_name)
        try:
            with open(filename, 'w') as file:
                # noinspection PyTypeChecker
                json.dump(data, file, indent=2, cls=self.__object_to_json)
        except IOError:
            logger.warn(f'Could not save formations for {self.__current_zone_name}')
            return False
        return True

    def add_formation_alias(self, existing_formation_id: str, alias: str):
        if is_unknown_zone(self.__current_zone_name):
            logger.warn(f'cannot load formations, no zone set')
            return
        if self.__current_formations is None:
            self.__load_formations()
        self.__formations_aliases[alias] = existing_formation_id
