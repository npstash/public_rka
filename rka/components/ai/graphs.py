from __future__ import annotations

import enum
from enum import auto
from typing import Optional, Iterable, Iterator, Dict, List, Any, Collection, Tuple, Generator


class Axis(enum.IntEnum):
    X = auto()
    Y = auto()
    Z = auto()


class Waypoint:
    def __init__(self, x: float, y: float, z: float, properties: Optional[Dict] = None):
        if properties:
            self.__properties: Dict[Any, Any] = properties
        else:
            self.__properties: Dict[Any, Any] = {Axis.X: x, Axis.Y: y, Axis.Z: z}
        self.__x = x
        self.__y = y
        self.__z = z
        self.comparator = self.default_comparator

    def __contains__(self, item):
        return self.__properties.__contains__(item)

    def __getitem__(self, item):
        return self.__properties[item]

    def __setitem__(self, key, value):
        if key is Axis.X:
            self.__x = value
        elif key is Axis.Y:
            self.__y = value
        elif key is Axis.Z:
            self.__z = value
        self.__properties[key] = value

    def __str__(self) -> str:
        info_s = f', info:{self[WaypointExtensions.INFO]}' if WaypointExtensions.INFO in self.__properties else ''
        id_s = f', id:{self[WaypointExtensions.ID]}' if WaypointExtensions.ID in self.__properties else ''
        v_s = f', v:{self[WaypointExtensions.VISITED]}' if WaypointExtensions.VISITED in self.__properties else ''
        c_s = f', c:{self[WaypointExtensions.COLOR]}' if WaypointExtensions.COLOR in self.__properties else ''
        return str({a.name: self[a] for a in Axis}) + info_s + id_s + v_s + c_s

    def default_comparator(self, other: Waypoint) -> bool:
        return self.__x == other.__x and self.__y == other.__y and self.__z == other.__z

    def __eq__(self, other: Waypoint) -> bool:
        return self.comparator(other)

    def __hash__(self) -> int:
        return int(self.__x + 101.0 * self.__y + 1009.0 * self.__z)

    def copy_waypoint(self) -> Waypoint:
        return Waypoint(x=self.__x, y=self.__y, z=self.__z, properties=self.__properties.copy())

    def shift(self, x: Optional[float] = None, y: Optional[float] = None, z: Optional[float] = None) -> Waypoint:
        x = self.__x + x if x else self.__x
        y = self.__y + y if y else self.__y
        z = self.__z + z if z else self.__z
        return Waypoint(x=x, y=y, z=z)

    def distance(self, other: Waypoint) -> float:
        diff_x = (self.__x - other.__x) ** 2
        diff_y = (self.__y - other.__y) ** 2
        diff_z = (self.__z - other.__z) ** 2
        return (diff_x + diff_y + diff_z) ** 0.5

    def distance_on_axes(self, other: Waypoint, axes: Iterable[Axis]) -> float:
        diff_x = 0.0
        diff_y = 0.0
        diff_z = 0.0
        if not axes:
            axes = Axis
        for axis in axes:
            if axis is Axis.X:
                diff_x = (self.__x - other.__x) ** 2
            elif axis is Axis.Y:
                diff_y = (self.__y - other.__y) ** 2
            elif axis is Axis.Z:
                diff_z = (self.__z - other.__z) ** 2
        return (diff_x + diff_y + diff_z) ** 0.5

    def distance_on_axis(self, other: Waypoint, axis: Axis) -> float:
        if axis is Axis.X:
            return abs(self.__x - other.__x)
        if axis is Axis.Y:
            return abs(self.__y - other.__y)
        if axis is Axis.Z:
            return abs(self.__z - other.__z)
        assert False


class IWaypointFilter:
    def accept(self, w: Waypoint) -> bool:
        raise NotImplementedError()

    @staticmethod
    def always() -> IWaypointFilter:
        class Inner(IWaypointFilter):
            def accept(self, w: Waypoint) -> bool:
                return True

        return Inner()

    @staticmethod
    def outside(from_waypoint: Waypoint, rule: SpatialRule) -> IWaypointFilter:
        class Inner(IWaypointFilter):
            def accept(self, w: Waypoint) -> bool:
                return not rule.is_near(from_waypoint, w)

        return Inner()

    @staticmethod
    def inside(from_waypoint: Waypoint, rule: SpatialRule) -> IWaypointFilter:
        class Inner(IWaypointFilter):
            def accept(self, w: Waypoint) -> bool:
                return rule.is_near(from_waypoint, w)

        return Inner()

    @staticmethod
    def in_colors(colors: Iterable[int]) -> IWaypointFilter:
        class Inner(IWaypointFilter):
            def accept(self, w: Waypoint) -> bool:
                return w[WaypointExtensions.COLOR] in colors

        return Inner()

    @staticmethod
    def other_with_same_color(waypoint: Waypoint, color: int) -> IWaypointFilter:
        class Inner(IWaypointFilter):
            def accept(self, w: Waypoint) -> bool:
                return w is not waypoint and w[WaypointExtensions.COLOR] == color

        return Inner()


class IWaypointComparator:
    def compare(self, w1: Waypoint, w2: Waypoint) -> float:
        raise NotImplementedError()

    @staticmethod
    def always(value: bool) -> IWaypointComparator:
        comparator = IWaypointComparator()

        def f(_w1: Waypoint, _w2: Waypoint) -> float:
            return value

        comparator.compare = f
        return comparator

    @staticmethod
    def no_further_than(max_distance: float) -> IWaypointComparator:
        comparator = IWaypointComparator()

        def f(w1: Waypoint, w2: Waypoint) -> float:
            d = w1.distance(w2)
            return -1.0 if d > max_distance else max_distance - d

        comparator.compare = f
        return comparator

    @staticmethod
    def no_further_than_xz(max_distance: float) -> IWaypointComparator:
        comparator = IWaypointComparator()

        def f(w1: Waypoint, w2: Waypoint) -> float:
            d = w1.distance_on_axes(w2, [Axis.X, Axis.Z])
            return -1.0 if d > max_distance else max_distance - d

        comparator.compare = f
        return comparator


class SpatialRule(IWaypointComparator):
    def __init__(self, max_distance_by_axis: Dict[Axis, float], constraints: List[IWaypointComparator]):
        self.__max_distance_by_axis = max_distance_by_axis
        self.__constraints = constraints

    def __get_first_in_range(self, sorted_waypoints: List[Waypoint], sort_axis: Axis, threshold: float,
                             start_from: int, end_at: int) -> Optional[int]:
        if start_from == end_at:
            return None
        if end_at - start_from == 1:
            if sorted_waypoints[start_from][sort_axis] >= threshold:
                return start_from
            return None
        mid = (end_at + start_from) // 2
        idx1 = self.__get_first_in_range(sorted_waypoints, sort_axis, threshold, start_from, mid)
        idx2 = self.__get_first_in_range(sorted_waypoints, sort_axis, threshold, mid, end_at)
        if idx1 is None:
            return idx2
        if idx2 is None:
            return idx1
        return idx1 if idx1 < idx2 else idx2

    def get_first_in_range(self, sorted_waypoints: List[Waypoint], sort_axis: Axis,
                           lookup_waypoint: Waypoint, distance: Optional[float] = None) -> Optional[int]:
        if distance is None:
            distance = self.__max_distance_by_axis[sort_axis]
        threshold = lookup_waypoint[sort_axis] - distance
        return self.__get_first_in_range(sorted_waypoints, sort_axis, threshold, 0, len(sorted_waypoints))

    def is_near(self, w1: Waypoint, w2: Waypoint) -> bool:
        for axis in Axis:
            if not self.is_near_by_axis(w1, w2, axis):
                return False
        for constraint in self.__constraints:
            if constraint.compare(w1, w2) < 0.0:
                return False
        return True

    def is_near_by_axis(self, w1: Waypoint, w2: Waypoint, axis: Axis) -> bool:
        return w1.distance_on_axis(w2, axis) <= self.__max_distance_by_axis[axis]

    def is_near_by_axes(self, w1: Waypoint, w2: Waypoint, axes: Iterable[Axis]) -> bool:
        if not axes:
            return False
        for axis in axes:
            if w1.distance_on_axis(w2, axis) > self.__max_distance_by_axis[axis]:
                return False
        return True

    def create_sorting(self) -> SpatialSorting:
        return SpatialSorting(self, self.__max_distance_by_axis)

    def compare(self, w1: Waypoint, w2: Waypoint):
        return self.is_near(w1, w2)


class SpatialSorting:
    def __init__(self, spatial_rule: SpatialRule, max_distance_by_axis: Dict[Axis, float]):
        self.__spatial_rule = spatial_rule
        self.__max_distance_by_axis = max_distance_by_axis
        self.__max_by_axis: Dict[Axis, Waypoint] = dict()
        self.__min_by_axis: Dict[Axis, Waypoint] = dict()
        self.__span_by_axis: Dict[Axis, float] = dict()
        self.__sorted_waypoints: List[Waypoint] = list()
        self.__sort_axis = Axis.X

    def __get_best_sort_axis(self) -> Axis:
        return max(self.__span_by_axis.items(), key=lambda item: item[1] / self.__max_distance_by_axis[item[0]])[0]

    def from_waypoints(self, waypoints: Collection[Waypoint]) -> SpatialSorting:
        if not waypoints:
            return self
        for axis in Axis:
            w1 = self.__max_by_axis[axis] = max(waypoints, key=lambda w: w[axis])
            w2 = self.__min_by_axis[axis] = min(waypoints, key=lambda w: w[axis])
            self.__span_by_axis[axis] = w1.distance_on_axis(w2, axis)
        self.__sort_axis = self.__get_best_sort_axis()
        self.__sorted_waypoints = sorted(waypoints, key=lambda w: w[self.__sort_axis])
        return self

    def insert(self, waypoint: Waypoint):
        if not self.__sorted_waypoints:
            self.from_waypoints([waypoint])
            return
        any_new_span = False
        for axis in Axis:
            new_span = False
            if self.__max_by_axis[axis][axis] < waypoint[axis]:
                self.__max_by_axis[axis] = waypoint
                new_span = True
            if self.__min_by_axis[axis][axis] > waypoint[axis]:
                self.__min_by_axis[axis] = waypoint
                new_span = True
            if new_span:
                w1 = self.__max_by_axis[axis]
                w2 = self.__min_by_axis[axis]
                self.__span_by_axis[axis] = w1.distance_on_axis(w2, axis)
                any_new_span = True
        if any_new_span:
            new_sort_axis = self.__get_best_sort_axis()
            if new_sort_axis != self.__sort_axis:
                self.__sort_axis = new_sort_axis
                self.__sorted_waypoints = sorted(self.__sorted_waypoints, key=lambda w: w[self.__sort_axis])
        idx = self.__spatial_rule.get_first_in_range(self.__sorted_waypoints, self.__sort_axis, waypoint, 0.0)
        if idx is None:
            self.__sorted_waypoints.append(waypoint)
        else:
            self.__sorted_waypoints.insert(idx, waypoint)

    def delete(self, waypoint: Waypoint) -> bool:
        if not self.__sorted_waypoints:
            return False
        start_index = self.__spatial_rule.get_first_in_range(self.__sorted_waypoints, self.__sort_axis, waypoint)
        if start_index is None:
            return False
        for i in range(start_index, len(self.__sorted_waypoints)):
            w = self.__sorted_waypoints[i]
            if waypoint == w:
                self.__sorted_waypoints.pop(i)
                return True
            if not self.__spatial_rule.is_near_by_axis(waypoint, self.__sorted_waypoints[i], self.__sort_axis):
                break
        return False

    def iterate_waypoints_around(self, around_waypoint: Waypoint, waypoint_filter: Optional[IWaypointFilter] = None) -> Iterator[Waypoint]:
        waypoints = self.__sorted_waypoints[:]
        axis = self.__sort_axis
        start_index = self.__spatial_rule.get_first_in_range(waypoints, axis, around_waypoint)
        if start_index is None:
            return
        for i in range(start_index, len(waypoints)):
            w = waypoints[i]
            if waypoint_filter and not waypoint_filter.accept(w):
                continue
            if not self.__spatial_rule.is_near_by_axis(around_waypoint, w, axis):
                break
            if self.__spatial_rule.is_near(around_waypoint, w):
                yield w

    def get_nearest_waypoint(self, around_waypoint: Waypoint, waypoint_filter: Optional[IWaypointFilter] = None) -> Optional[Waypoint]:
        nearest_dist = -1.0
        nearest_wp: Optional[Waypoint] = None
        for w in self.iterate_waypoints_around(around_waypoint):
            if waypoint_filter and not waypoint_filter.accept(w):
                continue
            distance = w.distance(around_waypoint)
            if distance >= 0.0 and (nearest_dist < 0.0 or distance < nearest_dist):
                nearest_dist = distance
                nearest_wp = w
        return nearest_wp if nearest_dist >= 0.0 else None

    def get_span(self, axis: Axis) -> Optional[float]:
        if axis not in self.__span_by_axis:
            return None
        return self.__span_by_axis[axis]


class WaypointExtensions(enum.IntEnum):
    # noinspection PyTypeChecker
    ID = max(Axis) + 1
    NEIGHBOURS = auto()
    VISITED = auto()
    DISTANCE = auto()
    COLOR = auto()
    INFO = auto()


class Path:
    def __init__(self, graph: Graph, ending_waypoint: Waypoint, proximity_rule: SpatialRule, reach_sorting: SpatialSorting):
        self.__graph = graph
        self.__ending_waypoint = ending_waypoint
        self.__proximity_rule = proximity_rule
        self.__reach_sorting = reach_sorting
        self.__end_is_reached = False

    def __get_closest_to_final(self, current_waypoint: Waypoint) -> Optional[Waypoint]:
        closest_to_current = self.__reach_sorting.get_nearest_waypoint(current_waypoint)
        if not closest_to_current:
            return None
        best_next_waypoint = None
        best_next_waypoint_distance = None
        for waypoint in closest_to_current[WaypointExtensions.NEIGHBOURS]:
            if best_next_waypoint is None or waypoint[WaypointExtensions.DISTANCE] < best_next_waypoint_distance:
                best_next_waypoint = waypoint
                best_next_waypoint_distance = waypoint[WaypointExtensions.DISTANCE]
        return best_next_waypoint

    def get_graph_copy(self) -> Graph:
        return self.__graph.copy_graph()

    def is_end_reached(self) -> bool:
        return self.__end_is_reached

    def get_next_nearest_waypoint(self, current_waypoint: Waypoint) -> Optional[Waypoint]:
        assert current_waypoint
        if self.__end_is_reached:
            return None
        if self.__proximity_rule.is_near(current_waypoint, self.__ending_waypoint):
            self.__end_is_reached = True
            return None
        # find nearest waypoint outside of proximity reach
        outside_proximity = IWaypointFilter.outside(current_waypoint, self.__proximity_rule)
        best_next_waypoint = self.__get_closest_to_final(current_waypoint)
        while best_next_waypoint and not outside_proximity.accept(best_next_waypoint):
            best_next_waypoint = self.__get_closest_to_final(best_next_waypoint)
        return best_next_waypoint

    # noinspection PyPep8Naming
    @staticmethod
    def _is_line(rule: SpatialRule, waypoints: List[Waypoint]) -> bool:
        assert len(waypoints) >= 2
        if len(waypoints) == 2:
            return True
        # vector from start to end
        A = waypoints[0]
        B = waypoints[-1]
        dAB = (B[Axis.X] - A[Axis.X], B[Axis.Y] - A[Axis.Y], B[Axis.Z] - A[Axis.Z])
        # check waypoint on the way
        for C in waypoints[1:-1]:
            # vector from start to this
            dAC = (C[Axis.X] - A[Axis.X], C[Axis.Y] - A[Axis.Y], C[Axis.Z] - A[Axis.Z])
            a = (dAB[0] * dAC[0] + dAB[1] * dAC[1] + dAB[2] * dAC[2]) / (dAB[0] ** 2 + dAB[1] ** 2 + dAB[2] ** 2)
            dAD = (dAB[0] * a, dAB[1] * a, dAB[2] * a)
            D = A.shift(x=dAD[0], y=dAD[1], z=dAD[2])
            if not rule.is_near(C, D):
                return False
        return True

    def get_next_furthest_waypoint_on_line(self, current_waypoint: Waypoint) -> Optional[Waypoint]:
        assert current_waypoint
        waypoints_on_the_line: List[Waypoint] = [current_waypoint]
        while True:
            next_waypoint = self.get_next_nearest_waypoint(current_waypoint)
            if next_waypoint:
                waypoints_on_the_line.append(next_waypoint)
                if Path._is_line(rule=self.__proximity_rule, waypoints=waypoints_on_the_line):
                    current_waypoint = next_waypoint
                    continue
            if len(waypoints_on_the_line) > 1:
                return current_waypoint
            return None


class Graph:
    def __init__(self):
        self.__next_id = 0
        self.__waypoints: List[Waypoint] = list()

    def copy_graph(self, waypoint_filter: Optional[IWaypointFilter] = None) -> Graph:
        new_waypoints = dict()
        for old_w in self.__waypoints:
            if waypoint_filter and not waypoint_filter.accept(old_w):
                continue
            new_w = old_w.copy_waypoint()
            new_waypoints[new_w[WaypointExtensions.ID]] = new_w
        for new_w in new_waypoints.values():
            old_neighbours = new_w[WaypointExtensions.NEIGHBOURS]
            new_w[WaypointExtensions.NEIGHBOURS] = []
            for old_neighbour in old_neighbours:
                w_id = old_neighbour[WaypointExtensions.ID]
                if w_id not in new_waypoints:
                    continue
                new_w[WaypointExtensions.NEIGHBOURS].append(new_waypoints[w_id])
        new_graph = Graph()
        new_graph.__waypoints = list(new_waypoints.values())
        new_graph.__next_id = self.__next_id
        return new_graph

    def add_waypoint(self, waypoint: Waypoint):
        waypoint[WaypointExtensions.ID] = self.__next_id
        waypoint[WaypointExtensions.NEIGHBOURS] = list()
        self.__waypoints.append(waypoint)
        self.__next_id += 1

    def remove_waypoint(self, waypoint: Waypoint) -> bool:
        if waypoint not in self.__waypoints:
            return False
        neighbours = waypoint[WaypointExtensions.NEIGHBOURS]
        for neighbour in neighbours:
            neighbour[WaypointExtensions.NEIGHBOURS].remove(waypoint)
        neighbours.clear()
        self.__waypoints.remove(waypoint)
        return True

    def get_closest_waypoint(self, waypoint: Waypoint, axes: Optional[Iterable[Axis]] = None) -> Optional[Waypoint]:
        best_w = None
        best_distance = -1.0
        for w in self.__waypoints:
            if axes:
                distance = w.distance_on_axes(waypoint, axes)
            else:
                distance = w.distance(waypoint)
            if best_w is None or distance < best_distance:
                best_w = w
                best_distance = distance
        if not best_w:
            return None
        return best_w.copy_waypoint()

    # noinspection PyMethodMayBeStatic
    def unidirectional_edge(self, w1: Waypoint, w2: Waypoint):
        assert w1 is not w2, (str(w1), str(w2))
        assert w2 not in w1[WaypointExtensions.NEIGHBOURS], (str(w1), str(w2))
        w1[WaypointExtensions.NEIGHBOURS].append(w2)

    # noinspection PyMethodMayBeStatic
    def bidirectional_edge(self, w1: Waypoint, w2: Waypoint):
        assert w1 is not w2, (str(w1), str(w2))
        if w1 in w2[WaypointExtensions.NEIGHBOURS]:
            return
        if w2 in w1[WaypointExtensions.NEIGHBOURS]:
            return
        assert w1 not in w2[WaypointExtensions.NEIGHBOURS], (str(w1), str(w2))
        assert w2 not in w1[WaypointExtensions.NEIGHBOURS], (str(w1), str(w2))
        w1[WaypointExtensions.NEIGHBOURS].append(w2)
        w2[WaypointExtensions.NEIGHBOURS].append(w1)

    def create_sorting(self, sorting_rule: SpatialRule) -> SpatialSorting:
        return sorting_rule.create_sorting().from_waypoints(self.__waypoints)

    def iterate_waypoints(self) -> Iterator[Waypoint]:
        for w in self.__waypoints:
            yield w

    def iterate_edges(self) -> Iterator[Tuple[Waypoint, Waypoint]]:
        for w1 in self.__waypoints:
            for w2 in w1[WaypointExtensions.NEIGHBOURS]:
                yield w1, w2

    def traverse_graph(self, starting_waypoint: Waypoint, bfs: bool) -> Generator[Tuple[Waypoint, Waypoint], bool, None]:
        assert starting_waypoint in self.__waypoints
        edges = [(starting_waypoint, w) for w in starting_waypoint[WaypointExtensions.NEIGHBOURS]]
        while edges:
            w1, w2 = edges.pop()
            descend = None
            while descend is None:
                descend = yield w1, w2
            if descend:
                new_edges = [(w2, w) for w in w2[WaypointExtensions.NEIGHBOURS]]
                if bfs:
                    edges = new_edges + edges
                else:
                    edges += new_edges
        if starting_waypoint[WaypointExtensions.NEIGHBOURS]:
            yield

    def draw_graph(self, x_axis=Axis.X, y_axis=Axis.Y, axes: Optional = None):
        if not self.__waypoints:
            return
        if axes:
            from matplotlib.axes import Axes
            assert isinstance(axes, Axes)
            plt = axes
        else:
            import matplotlib.pyplot as plt
        max_Y_wp = max(self.__waypoints, key=lambda w: w[Axis.Y])[Axis.Y]
        min_Y_wp = min(self.__waypoints, key=lambda w: w[Axis.Y])[Axis.Y]

        info_waypoints = [w for w in self.__waypoints if WaypointExtensions.INFO in w]
        noinfo_waypoints = [w for w in self.__waypoints if WaypointExtensions.INFO not in w]
        for w1, w2 in self.iterate_edges():
            w1_Y = w1[Axis.Y]
            if max_Y_wp - w1_Y < w1_Y - min_Y_wp:
                e_color = '#00AA00'
            else:
                e_color = '#004400'
            plt.plot([w1[x_axis], w2[x_axis]], [w1[y_axis], w2[y_axis]], c=e_color, zorder=1)

        wni_colors = ['#00AA44'] * len(noinfo_waypoints)
        for i, w in enumerate(noinfo_waypoints):
            w_Y = w[Axis.Y]
            if max_Y_wp - w_Y > w_Y - min_Y_wp:
                wni_colors[i] = '#004422'
        plt.scatter(x=[w[x_axis] for w in noinfo_waypoints],
                    y=[w[y_axis] for w in noinfo_waypoints],
                    c=wni_colors, marker='.', zorder=2)

        wi_colors = ['#AA0000'] * len(info_waypoints)
        for i, w in enumerate(info_waypoints):
            w_Y = w[Axis.Y]
            if max_Y_wp - w_Y > w_Y - min_Y_wp:
                wi_colors[i] = '#440000'
        plt.scatter(x=[w[x_axis] for w in info_waypoints],
                    y=[w[y_axis] for w in info_waypoints],
                    c=wi_colors, marker='o', zorder=3)

        for waypoint in info_waypoints:
            x = waypoint[x_axis]
            y = waypoint[y_axis]
            info = str(waypoint[WaypointExtensions.INFO])
            plt.text(x=x, y=y, s=info, zorder=4)

    # noinspection PyMethodMayBeStatic
    def tag_graph(self, tag_locs: Dict[Any, Waypoint], x_axis=Axis.X, y_axis=Axis.Y, axes: Optional = None):
        import matplotlib.pyplot as plt
        if axes:
            from matplotlib.axes import Axes
            assert isinstance(axes, Axes)
            plt = axes
        for obj, waypoint in tag_locs.items():
            x = waypoint[x_axis]
            y = waypoint[y_axis]
            plt.scatter(x=[x], y=[y], c=['blue'], marker='o', zorder=3)
            plt.text(x=x, y=y, s=str(obj), zorder=4)

    # noinspection PyMethodMayBeStatic
    def show_graph(self, axes: Optional = None):
        import matplotlib.pyplot as plt
        if axes:
            from matplotlib.axes import Axes
            assert isinstance(axes, Axes)
            plt = axes
        plt.autoscale(True)
        if not axes:
            plt.show()


class MapGraph:
    def __init__(self, proximity_rule: SpatialRule, merge_rule: SpatialRule, connect_rule: SpatialRule, reach_rule: SpatialRule):
        self.__proximity_rule = proximity_rule
        self.__merge_rule = merge_rule
        self.__connect_rule = connect_rule
        self.__reach_rule = reach_rule
        self.__merge_sorting = merge_rule.create_sorting()
        self.__connect_sorting = connect_rule.create_sorting()
        self.__reach_sorting = reach_rule.create_sorting()
        self.__graph = Graph()

    def __connect_waypoint(self, waypoint: Waypoint, bidirectional: bool):
        connected = False
        for w in self.__connect_sorting.iterate_waypoints_around(waypoint):
            if w is waypoint:
                continue
            if bidirectional:
                self.__graph.bidirectional_edge(waypoint, w)
            else:
                self.__graph.unidirectional_edge(waypoint, w)
            connected = True
        if not connected:
            # find nearest one, which is not yet connected
            w = self.__reach_sorting.get_nearest_waypoint(waypoint)
            if w:
                if bidirectional:
                    self.__graph.bidirectional_edge(waypoint, w)
                else:
                    self.__graph.unidirectional_edge(waypoint, w)

    def __merge_waypoints(self, waypoint: Waypoint) -> Optional[Waypoint]:
        # this merge strat simply ignores the new waypoint
        for merged_with in self.__merge_sorting.iterate_waypoints_around(waypoint):
            return merged_with
        return None

    def get_graph(self) -> Graph:
        return self.__graph

    def show_graph(self, x_axis=Axis.X, y_axis=Axis.Y):
        self.__graph.draw_graph(x_axis=x_axis, y_axis=y_axis)
        self.__graph.show_graph()

    def copy_map(self) -> MapGraph:
        new_map = MapGraph(proximity_rule=self.__proximity_rule,
                           merge_rule=self.__merge_rule,
                           connect_rule=self.__connect_rule,
                           reach_rule=self.__reach_rule)
        new_map.from_graph(self.__graph)
        return new_map

    def from_waypoints(self, waypoints: List[Waypoint]):
        self.__merge_sorting.from_waypoints(waypoints)
        self.__connect_sorting.from_waypoints(waypoints)
        self.__reach_sorting.from_waypoints(waypoints)
        self.__graph = Graph()
        for w in waypoints:
            self.__graph.add_waypoint(w)
        for w in waypoints:
            self.__connect_waypoint(w, bidirectional=False)

    def from_graph(self, graph: Graph):
        graph = graph.copy_graph()
        waypoints = list(graph.iterate_waypoints())
        self.__merge_sorting.from_waypoints(waypoints)
        self.__connect_sorting.from_waypoints(waypoints)
        self.__reach_sorting.from_waypoints(waypoints)
        self.__graph = graph

    def from_map(self, mapgraph: MapGraph):
        self.from_graph(mapgraph.__graph)

    # return True if new point added, otherwise it was merged
    def add_waypoint(self, waypoint: Waypoint) -> bool:
        waypoint = waypoint.copy_waypoint()
        merged_with = self.__merge_waypoints(waypoint)
        if merged_with:
            if WaypointExtensions.INFO in waypoint:
                merged_with[WaypointExtensions.INFO] = waypoint[WaypointExtensions.INFO]
                return True
            return False
        self.__graph.add_waypoint(waypoint)
        self.__connect_waypoint(waypoint, bidirectional=True)
        self.__merge_sorting.insert(waypoint)
        self.__connect_sorting.insert(waypoint)
        self.__reach_sorting.insert(waypoint)
        return True

    # return True if a waypoint was found and removed
    def remove_closest_waypoint(self, waypoint: Waypoint, axes: Optional[Iterable[Axis]] = None) -> bool:
        existing_waypoint = self.__graph.get_closest_waypoint(waypoint, axes)
        if not existing_waypoint:
            return False
        if not self.__graph.remove_waypoint(existing_waypoint):
            return False
        assert self.__merge_sorting.delete(existing_waypoint)
        assert self.__connect_sorting.delete(existing_waypoint)
        assert self.__reach_sorting.delete(existing_waypoint)
        return True

    @staticmethod
    def __graph_coloring(graph: Graph):
        for w in graph.iterate_waypoints():
            w[WaypointExtensions.VISITED] = False
        next_color = 1
        for w in graph.iterate_waypoints():
            if w[WaypointExtensions.VISITED]:
                continue
            current_color = next_color
            next_color += 1
            w[WaypointExtensions.VISITED] = True
            w[WaypointExtensions.COLOR] = current_color
            gen = graph.traverse_graph(w, bfs=False)
            for w1, w2 in gen:
                descend = False
                assert w1[WaypointExtensions.VISITED], w1
                if not w2[WaypointExtensions.VISITED] or w2[WaypointExtensions.COLOR] != current_color:
                    w2[WaypointExtensions.VISITED] = True
                    w2[WaypointExtensions.COLOR] = current_color
                    descend = True
                gen.send(descend)

    @staticmethod
    def __mark_shortest_path(graph: Graph, ending_waypoint: Waypoint):
        for w in graph.iterate_waypoints():
            w[WaypointExtensions.VISITED] = False
        ending_waypoint[WaypointExtensions.VISITED] = True
        ending_waypoint[WaypointExtensions.DISTANCE] = 0.0
        # traverse the graph from the destination
        gen = graph.traverse_graph(starting_waypoint=ending_waypoint, bfs=True)
        for w1, w2 in gen:
            descend = False
            assert w1[WaypointExtensions.VISITED], w1
            starting_distance = w1[WaypointExtensions.DISTANCE]
            new_distance_at_next = w1.distance(w2) + starting_distance
            if not w2[WaypointExtensions.VISITED] or new_distance_at_next < w2[WaypointExtensions.DISTANCE]:
                w2[WaypointExtensions.DISTANCE] = new_distance_at_next
                w2[WaypointExtensions.VISITED] = True
                descend = True
            gen.send(descend)

    # None if no path exists
    def get_paths_to(self, ending_waypoint: Waypoint) -> Optional[Path]:
        # reach_sorting = self.__graph.create_sorting(self.__reach_rule)
        self.__graph_coloring(self.__graph)
        ending_colors = {w[WaypointExtensions.COLOR] for w in self.__reach_sorting.iterate_waypoints_around(ending_waypoint)}
        if not ending_colors:
            return None
        # remove colors which dont participate in any of paths, create new graph
        new_graph = self.__graph.copy_graph(IWaypointFilter.in_colors(ending_colors))
        new_graph.add_waypoint(ending_waypoint)
        reach_sorting = new_graph.create_sorting(self.__reach_rule)
        # find points to connect the end to and connect them
        nearby_waypoints = set()
        for color in ending_colors:
            # find only one of each color
            waypoint_filter = IWaypointFilter.other_with_same_color(ending_waypoint, color)
            # unfortunately it means that some color regions will be connected with reach distance
            closest_waypoint = reach_sorting.get_nearest_waypoint(ending_waypoint, waypoint_filter)
            if closest_waypoint:
                nearby_waypoints.add(closest_waypoint)
        for w in nearby_waypoints:
            new_graph.bidirectional_edge(ending_waypoint, w)
        MapGraph.__mark_shortest_path(graph=new_graph, ending_waypoint=ending_waypoint)
        return Path(graph=new_graph, ending_waypoint=ending_waypoint, proximity_rule=self.__proximity_rule, reach_sorting=reach_sorting)


def main_test():
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    import matplotlib.pyplot as plt

    waypoints = [Waypoint(10.0, 10.0, 2.0),
                 Waypoint(7.0, 7.0, 1.0),
                 Waypoint(3.0, 8.0, 1.5),
                 Waypoint(2.0, 11.0, -1.0),
                 Waypoint(1.0, 12.0, 0.0),
                 Waypoint(11.0, 9.0, 5.0),
                 Waypoint(5.0, 4.0, 2.0),
                 Waypoint(5.0, 1.0, 0.0),
                 Waypoint(6.0, -3.0, 1.0),
                 Waypoint(4.0, 5.0, 1.5),
                 Waypoint(6.0, 5.0, 1.0),
                 Waypoint(2.0, -2.0, 1.0),
                 Waypoint(-1.0, -3.0, 0.0),
                 ]

    distances_merge = {Axis.X: 1.0, Axis.Y: 1.0, Axis.Z: 0.5}
    distances_connect = {Axis.X: 3.0, Axis.Y: 3.0, Axis.Z: 3.0}
    distances_reach = {Axis.X: 6.0, Axis.Y: 6.0, Axis.Z: 5.0}
    merge_rule = SpatialRule(distances_merge, [IWaypointComparator.no_further_than(2.0)])
    connect_rule = SpatialRule(distances_connect, [IWaypointComparator.no_further_than(7.0)])
    reach_rule = SpatialRule(distances_reach, [IWaypointComparator.no_further_than(10.0)])

    mapgraph = MapGraph(proximity_rule=merge_rule, merge_rule=merge_rule, connect_rule=connect_rule, reach_rule=reach_rule)
    mapgraph.from_waypoints(waypoints)

    start_at = Waypoint(11.0, 11.0, 3.0)
    end_at = Waypoint(-4.0, 5.0, -1.0)

    path = mapgraph.get_paths_to(end_at)
    draw_graph = path.get_graph_copy()
    plt.ion()
    for w1, w2 in draw_graph.iterate_edges():
        plt.plot([w1[Axis.X], w2[Axis.X]], [w1[Axis.Y], w2[Axis.Y]], c='b')
    plt.scatter(x=[w[Axis.X] for w in waypoints + [start_at, end_at]],
                y=[w[Axis.Y] for w in waypoints + [start_at, end_at]],
                c=['g'] * len(waypoints) + ['b'] * 2)
    for next_w in draw_graph.iterate_waypoints():
        plt.text(next_w[Axis.X], next_w[Axis.Y], f'{next_w[WaypointExtensions.ID]}')
    plt.draw()
    plt.pause(1.0)

    next_w = start_at
    while True:
        print(next_w)
        plt.scatter(x=[next_w[Axis.X]], y=[next_w[Axis.Y]], c='r')
        plt.draw()
        plt.pause(1.0)
        next_w = path.get_next_nearest_waypoint(next_w)
        if not next_w or next_w == end_at:
            break
    print(next_w)
    plt.scatter(x=[next_w[Axis.X]], y=[next_w[Axis.Y]], c='r')
    plt.draw()
    plt.pause(2.0)


if __name__ == '__main__':
    main_test()
