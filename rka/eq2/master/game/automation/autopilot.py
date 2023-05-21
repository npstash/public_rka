from __future__ import annotations

import time
from threading import RLock
from typing import Optional, Dict

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability.generated_abilities import CommonerAbilities
from rka.eq2.master.game.automation import logger
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer, IPlayerSelector
from rka.eq2.master.game.location import Location, LocationPositionTransformer
from rka.eq2.master.game.location.location_streams import FixedLocationInputStream, SingleLocationInputStream
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.scripts.location_scripts import TrackLocations
from rka.eq2.master.game.scripting.scripts.movement_scripts import FollowLocationsScript, FollowLocationStream, FollowLocationRef, IFollowLocationsObserver
from rka.eq2.shared import ClientFlags


class Autopilot:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__movement_scripts_lock = RLock()
        self.__movement_scripts: Dict[IPlayer, FollowLocationsScript] = dict()

    def __stop_movement(self, player: IPlayer, wait_to_complete_previous: bool, reason: FollowLocationsScript.CancelReason) -> bool:
        if player not in self.__movement_scripts:
            return True
        if self.__movement_scripts[player].is_expired():
            return True
        script = self.__movement_scripts[player]
        if not script.is_cancel_possible(reason):
            return False
        script.expire()
        if wait_to_complete_previous:
            script.wait_until_completed()
        return True

    def __player_move(self, player: IPlayer, movement_script: FollowLocationsScript, allow_cancel: bool):
        class _Observer(IFollowLocationsObserver):
            def __init__(self, runtime_: IRuntime):
                self.__runtime = runtime_

            def movement_completed(self, moved_player: IPlayer, last_location: Optional[Location], reached: bool):
                self.__runtime.overlay.log_event(f'{moved_player} movement OFF', Severity.Low)

        with self.__movement_scripts_lock:
            if not self.__stop_movement(player=player, wait_to_complete_previous=True, reason=FollowLocationsScript.CancelReason.NEW_MOVEMENT_SCRIPT):
                self.__runtime.overlay.log_event(f'failed to start {player} movement', Severity.Low)
                return
            movement_script.add_movement_observer(_Observer(self.__runtime))
            if not allow_cancel:
                movement_script.disable_cancel_reason(FollowLocationsScript.CancelReason.FOLLOW)
                movement_script.disable_cancel_reason(FollowLocationsScript.CancelReason.STOP_MOVEMENT)
            self.__movement_scripts[player] = movement_script
            self.__runtime.processor.run_task(movement_script)
            self.__runtime.overlay.log_event(f'{player} movement ON', Severity.Low)

    def register_custom_movement_script(self, player: IPlayer, movement_script: FollowLocationsScript):
        with self.__movement_scripts_lock:
            self.__stop_movement(player=player, wait_to_complete_previous=False, reason=FollowLocationsScript.CancelReason.NEW_MOVEMENT_SCRIPT)
            self.__movement_scripts[player] = movement_script

    def player_move_to_location(self, player: IPlayer, location: Location, only_position=False, high_precision=False, allow_cancel=True):
        self.__runtime.overlay.log_event(f'{player} moves to {location}', Severity.Normal)
        if only_position:
            location = location.get_position()
        location_input = SingleLocationInputStream(location)
        movement_script = FollowLocationStream(player, location_input, high_precision=high_precision)
        self.__player_move(player=player, movement_script=movement_script, allow_cancel=allow_cancel)

    def player_anchor_at_location(self, player: IPlayer, location: Location, only_position=True, high_precision=False, allow_cancel=True):
        self.__runtime.overlay.log_event(f'{player} anchors at {location}', Severity.Normal)
        if only_position:
            location = location.get_position()
        location_input = FixedLocationInputStream(location, delay=4.0)
        movement_script = FollowLocationStream(player, location_input, high_precision=high_precision)
        self.__player_move(player=player, movement_script=movement_script, allow_cancel=allow_cancel)

    def player_move_to_player(self, player: IPlayer, move_to_this_player: IPlayer):
        requested_at = time.time()

        def location_received(event: PlayerInfoEvents.LOCATION):
            EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.LOCATION, location_received)
            # request valid only for a short time
            if time.time() > requested_at + 5.0:
                return
            self.player_move_to_location(player=player, location=event.location, only_position=True)

        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.LOCATION(player=move_to_this_player), location_received)
        self.__runtime.request_ctrl.request_location(move_to_this_player)

    def player_follow_player(self, player: IPlayer, follow_this_player: IPlayer, allow_cancel=True):
        if player is follow_this_player:
            logger.warn(f'Follow yourself, huh?')
            return
        if player.is_local():
            logger.warn(f'{player} not allowed to follow, because its local')
            return
        self.__runtime.overlay.log_event(f'{player} follows {follow_this_player}', Severity.Normal)
        player_tracker = TrackLocations.get_running_player_tracker(self.__runtime, follow_this_player, check_rate=2.0)
        location_ref_to_track = player_tracker.create_location_source()
        position_to_track = LocationPositionTransformer(location_ref_to_track)
        movement_script = FollowLocationRef(player, position_to_track)
        self.__player_move(player=player, movement_script=movement_script, allow_cancel=allow_cancel)

    def stop_player_movements(self, player: IPlayer, reason: FollowLocationsScript.CancelReason):
        with self.__movement_scripts_lock:
            self.__stop_movement(player=player, wait_to_complete_previous=False, reason=reason)

    def all_players_stop_movement(self, reason: FollowLocationsScript.CancelReason):
        with self.__movement_scripts_lock:
            for player in self.__movement_scripts.keys():
                self.__stop_movement(player=player, wait_to_complete_previous=False, reason=reason)

    def all_players_move_to_main_player(self):
        requested_at = time.time()

        def location_received(event: PlayerInfoEvents.LOCATION):
            EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.LOCATION, location_received)
            # request valid only for a short time
            if time.time() > requested_at + 5.0:
                return
            for player in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned):
                self.player_move_to_location(player, event.location, only_position=True)

        main_player = self.__runtime.playerstate.get_main_player()
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.LOCATION(player=main_player), location_received)
        self.__runtime.request_ctrl.request_location(main_player)

    def all_players_follow_main_player(self):
        main_player = self.__runtime.playerstate.get_main_player()
        for player in self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned):
            self.player_follow_player(player, main_player)

    def apply_formation(self, formation_id: str, anchor=False, player_sel: Optional[IPlayerSelector] = None, allow_cancel=True) -> bool:
        formations = self.__runtime.zonemaps.load_formations()
        if formation_id not in formations:
            logger.warn(f'No formation found for id {formation_id}')
            return False
        formation = formations[formation_id]
        if player_sel:
            allowed_players = player_sel.resolve_players()
        else:
            allowed_players = self.__runtime.playerselectors.all_zoned_remote().resolve_players()
        for player, location in formation.items():
            if not player.is_online() or player not in allowed_players:
                continue
            if anchor:
                self.player_anchor_at_location(player=player, location=location, only_position=True, high_precision=True, allow_cancel=allow_cancel)
            else:
                self.player_move_to_location(player=player, location=location, only_position=True, high_precision=True, allow_cancel=allow_cancel)

    def store_formation(self, formation_id: str):
        requested_at = time.time()
        zoned_players = self.__runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        requested_formation: Dict[IPlayer, Optional[Location]] = {player: None for player in zoned_players}

        def location_received(event: PlayerInfoEvents.LOCATION):
            if time.time() > requested_at + 5.0:
                EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.LOCATION, location_received)
                return
            if event.player not in requested_formation or requested_formation[event.player] is not None:
                return
            requested_formation[event.player] = event.location
            if None in requested_formation.values():
                return
            # all requeted player locations set
            self.__runtime.overlay.log_event(f'Formation {formation_id} captured', Severity.Normal)
            self.__runtime.zonemaps.store_formation(formation_id=formation_id, formation=requested_formation)
            EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.LOCATION, location_received)

        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.LOCATION(), location_received)
        request = self.__runtime.request_factory.custom_request(ability_locator=CommonerAbilities.loc, players=zoned_players, duration=5.0)
        self.__runtime.processor.run_request(request, immediate=True)
