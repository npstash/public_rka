from __future__ import annotations

from threading import RLock
from typing import Dict, List

from rka.components.events.event_system import EventSystem
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer, TOptionalPlayer
from rka.eq2.master.game.location import LocationSourceFactory, LocationOutputStream
from rka.eq2.master.game.location.location_streams import LocationStreamConnector
from rka.eq2.master.game.scripting import ScriptException
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.procedures.movement import LocationCheckerProcedure
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.shared.flags import MutableFlags


class TrackRecord:
    def __init__(self, tracker: TrackLocations, rate: float):
        self.tracker = tracker
        self.rate = rate


class TrackLocations(PlayerScriptTask, LocationSourceFactory):
    __recent_tracker_lock = RLock()
    __recent_trackers: Dict[IPlayer, TrackRecord] = dict()

    @staticmethod
    def get_running_player_tracker(runtime: IRuntime, player: IPlayer, check_rate: float) -> TrackLocations:
        with TrackLocations.__recent_tracker_lock:
            if player not in TrackLocations.__recent_trackers:
                tracker = TrackLocations(player, check_rate)
                track_record = TrackRecord(tracker, tracker.get_check_rate())
                TrackLocations.__recent_trackers[player] = track_record
                runtime.processor.run_task(tracker)
            else:
                track_record = TrackLocations.__recent_trackers[player]
                if track_record.tracker.is_expired():
                    tracker = TrackLocations(player, check_rate)
                    track_record.tracker = tracker
                    track_record.rate = check_rate
                    runtime.processor.run_task(tracker)
                elif track_record.rate > check_rate:
                    track_record.rate = check_rate
            return track_record.tracker

    @staticmethod
    def stop_player_tracker(player: IPlayer) -> TrackLocations:
        with TrackLocations.__recent_tracker_lock:
            if player in TrackLocations.__recent_trackers and not TrackLocations.__recent_trackers[player].tracker.is_expired():
                tracker = TrackLocations.__recent_trackers[player].tracker
                tracker.expire()
            return TrackLocations.__recent_trackers[player].tracker

    @staticmethod
    def __set_player_tracker(tracker: TrackLocations, player: IPlayer) -> List[LocationStreamConnector]:
        with TrackLocations.__recent_tracker_lock:
            old_sinks = list()
            if player in TrackLocations.__recent_trackers and TrackLocations.__recent_trackers[player].tracker is not tracker:
                old_tracker = TrackLocations.__recent_trackers[player].tracker
                old_sinks = old_tracker._steal_location_sinks()
                old_tracker.expire()
                old_tracker.wait_until_completed()
            TrackLocations.__recent_trackers[player] = TrackRecord(tracker, tracker.get_check_rate())
            return old_sinks

    def __init__(self, player: TOptionalPlayer, check_rate: float):
        PlayerScriptTask.__init__(self, f'Track {player} location', -1.0)
        LocationSourceFactory.__init__(self)
        self.__player = player
        self.__check_rate = check_rate
        self.__location_pipes: List[LocationOutputStream] = list()
        self.__location_pipes_lock = RLock()
        self.set_silent()

    def get_check_rate(self) -> float:
        return self.__check_rate

    def create_location_source(self) -> LocationStreamConnector:
        location_source = LocationStreamConnector(self)
        with self.__location_pipes_lock:
            self.__location_pipes.append(location_source)
        return location_source

    def add_location_sink(self, location_sink: LocationOutputStream):
        with self.__location_pipes_lock:
            self.__location_pipes.append(location_sink)

    def _steal_location_sinks(self) -> List[LocationOutputStream]:
        with self.__location_pipes_lock:
            sinks = self.__location_pipes
            self.__location_pipes = list()
        return sinks

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.__player)
        with self.__location_pipes_lock:
            self.__location_pipes += TrackLocations.__set_player_tracker(self, psf.get_player())
        location_checker = LocationCheckerProcedure(psf)
        any_sink_added = False
        # skip first sleep
        refresh_rate = 0.0
        try:
            location_checker.start_movement_tracking()
            while not self.is_expired():
                self.sleep(refresh_rate)
                refresh_rate = self.__check_rate
                if MutableFlags.AUTOMATIC_TRACKING_FOLLOW:
                    # request new location now
                    new_location = location_checker.get_location()
                else:
                    # use the location collected in meanwhile
                    new_location = location_checker.get_last_result()
                    # dont request it again in next iteration
                    location_checker.clear_last_results()
                if not new_location:
                    continue
                with self.__location_pipes_lock:
                    location_pipes_copy = self.__location_pipes[:]
                sinks_to_remove = list()
                any_sink_pushed = False
                for location_pipe in location_pipes_copy:
                    any_sink_added = True
                    if not location_pipe.push_location(new_location):
                        sinks_to_remove.append(location_pipe)
                    else:
                        any_sink_pushed = True
                with self.__location_pipes_lock:
                    for location_pipe in sinks_to_remove:
                        self.__location_pipes.remove(location_pipe)
                        location_pipe.close_sink()
                if not any_sink_pushed and any_sink_added:
                    # nobody receiving locations
                    break
        except ScriptException:
            # ignore expiration exceptions - just close gracefully
            pass
        finally:
            location_checker.stop_movement_tracking()
            # close all sinks
            with self.__location_pipes_lock:
                for location_pipe in self.__location_pipes:
                    location_pipe.close_sink()

    def _on_expire(self):
        for location_sink in self.__location_pipes:
            location_sink.close_sink()


class ReadLocation(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer, sink: LocationOutputStream):
        PlayerScriptTask.__init__(self, f'Read {player}\'s locations', -1.0)
        self.__player = player
        self.__sink = sink
        self.set_silent()

    def _run(self, runtime: IRuntime):
        psf = self.get_player_scripting_framework(self.__player)
        self.__sink.push_location(psf.get_location())


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'Track location (selected player)')
class TrackPlayer(PlayerScriptTask):
    def __init__(self, player: TOptionalPlayer = None):
        PlayerScriptTask.__init__(self, f'Track locations of {player}', duration=-1.0)
        self.__player = player

    def _run(self, runtime: IRuntime):
        self.__player = self.resolve_player(self.__player)
        TrackLocations.get_running_player_tracker(runtime, self.__player, check_rate=1.0)


@GameScriptManager.register_game_script(ScriptCategory.MOVEMENT, 'Record locations events to zone map (all players)')
class RecordLocationEventsToMap(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Record locations events to zone map', duration=-1.0)
        self.set_persistent()

    def __save_location(self, event: PlayerInfoEvents.LOCATION):
        if event.player.get_zone() == self.get_runtime().zonemaps.get_current_zone_name():
            self.get_runtime().zonemaps.push_location(event.location)

    def _run(self, runtime: IRuntime):
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.LOCATION(), self.__save_location)
        self.wait_until_completed()

    def _on_expire(self):
        EventSystem.get_main_bus().unsubscribe(PlayerInfoEvents.LOCATION(), self.__save_location)
