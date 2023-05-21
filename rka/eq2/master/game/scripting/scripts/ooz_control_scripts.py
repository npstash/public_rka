from __future__ import annotations

from typing import List, Optional, Iterable

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer, IPlayerSelector
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import ScriptException
from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.script_mgr import GameScriptManager
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.ui import PermanentUIEvents
from rka.eq2.shared import ClientRequests
from rka.eq2.shared.client_events import ClientEvents


@GameScriptManager.register_game_script(ScriptCategory.COMBAT, 'Enable OOZ combat (first remote player to request it)')
class EnableOOZCombat(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, f'Start OOZ combats', duration=-1.0)
        from rka.eq2.master.game.requests.request_controller import RequestController
        self.__request_ctrl: Optional[RequestController] = None
        self.__combat_player_sel: Optional[IPlayerSelector] = None
        self.__requesting_player: Optional[IPlayer] = None
        self.__subscribed_for_combat_request: List[IPlayer] = list()
        self.set_singleton(override_previous=True)

    def _on_run_completed(self):
        self.get_runtime().overlay.log_event(None, Severity.Critical, PermanentUIEvents.OOZ)
        super()._on_run_completed()

    def _run(self, runtime: IRuntime):
        runtime.overlay.log_event('OOZ script is running!', Severity.Critical, PermanentUIEvents.OOZ)
        self.__subscribed_for_combat_request = runtime.player_mgr.get_players(max_status=PlayerStatus.Logged)
        self.__subscribe_for_combat_request(self.__subscribed_for_combat_request)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__player_zone_changed)
        self.wait_until_completed()

    def __subscribe_for_combat_request(self, players: Iterable[IPlayer]):
        for player in players:
            bus = self.get_runtime().remote_client_event_system.get_bus(player.get_client_id())
            bus.subscribe(ClientEvents.CLIENT_REQUEST(), self.__combat_requested)

    def __unsubscribe_for_combat_request(self, players: Iterable[IPlayer]):
        for player in players:
            bus = self.get_runtime().remote_client_event_system.get_bus(player.get_client_id())
            if bus:
                bus.unsubscribe_all(ClientEvents.CLIENT_REQUEST, self.__combat_requested)

    def __accept_player_into_script(self, player: IPlayer) -> bool:
        return player.is_remote() \
               and player.is_logged() \
               and self.__requesting_player.get_zone() == player.get_zone()

    def __include_players_from_same_zone(self):
        # will include requesting player, unless its suddenly not logged
        same_zone_players = self.get_runtime().player_mgr.find_players(self.__accept_player_into_script)
        for player in same_zone_players:
            self.__request_ctrl.player_switcher.borrow_player(player)
        self.__request_ctrl.player_switcher.disable_player(self.__requesting_player)
        # dont keep requesting player in the list of automated players
        if self.__requesting_player in same_zone_players:
            same_zone_players.remove(self.__requesting_player)
        self.__combat_player_sel = self.get_runtime().playerselectors.by_ref(same_zone_players)

    def __player_zone_changed(self, _event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        if not self.__request_ctrl:
            return
        self.__request_ctrl.player_switcher.return_all_players()
        self.__include_players_from_same_zone()

    def __combat_requested(self, event: ClientEvents.CLIENT_REQUEST):
        if event.request in [ClientRequests.START_OOZC, ClientRequests.STOP_OOZC]:
            return
        requesting_player = self.get_runtime().player_mgr.get_player_by_client_id(event.client_id)
        if requesting_player not in self.__subscribed_for_combat_request:
            logger.warn(f'unexpeceted subscribed player {requesting_player} for {event}')
            self.__subscribed_for_combat_request.append(requesting_player)
        if self.is_expired() or (self.__requesting_player and self.__requesting_player != requesting_player):
            logger.warn(f'unexpeceted {event} in {self}')
            self.__unsubscribe_for_combat_request(self.__subscribed_for_combat_request)
            self.__subscribed_for_combat_request.clear()
            return
        if not self.__request_ctrl:
            # the leading player is now selected
            self.__unsubscribe_for_combat_request(self.__subscribed_for_combat_request)
            self.__subscribed_for_combat_request = [requesting_player]
            self.__subscribe_for_combat_request(self.__subscribed_for_combat_request)
            self.__requesting_player = requesting_player
            self.__request_ctrl = self.get_runtime().request_ctrl_factory.create_offzone_request_controller()
            self.__request_ctrl.change_primary_player(requesting_player)
            self.__include_players_from_same_zone()
            self.get_runtime().overlay.log_event(f'OOZ leader: {self.__requesting_player}', Severity.Critical, PermanentUIEvents.OOZ)
        self.__update_combat(event.request)

    def __update_combat(self, request_type: str):
        self.get_runtime().combatstate.set_players_target(players=self.__combat_player_sel.resolve_players(),
                                                          target_name=self.__requesting_player.get_player_name())
        if request_type == ClientRequests.COMBAT:
            self.__request_ctrl.request_group_normal_combat()
            self.__request_ctrl.request_group_spam_dps()
        elif request_type == ClientRequests.FOLLOW:
            for player in self.__combat_player_sel.resolve_players():
                self.__request_ctrl.request_follow(player=player, target_name=self.__requesting_player.get_player_name())
        elif request_type == ClientRequests.STOP_FOLLOW:
            for player in self.__combat_player_sel.resolve_players():
                self.__request_ctrl.request_stop_follow(player=player)
        elif request_type == ClientRequests.GROUP_CURE:
            self.__request_ctrl.request_group_cure_now(False)
        elif request_type == ClientRequests.ACCEPT:
            for player in self.__combat_player_sel.resolve_players():
                self.__request_ctrl.request_accept_all(player=player)
        elif request_type == ClientRequests.CLICK:
            for player in self.__combat_player_sel.resolve_players():
                self.__request_ctrl.request_click_object_in_center(player=player)

    def _on_expire(self):
        EventSystem.get_main_bus().unsubscribe_all(PlayerInfoEvents.PLAYER_ZONE_CHANGED, self.__player_zone_changed)
        self.__unsubscribe_for_combat_request(self.__subscribed_for_combat_request)
        if self.__request_ctrl:
            self.__request_ctrl.close()
        super()._on_expire()


class OOZAutoCombat(PlayerScriptTask):
    def __init__(self, participants: IPlayerSelector):
        PlayerScriptTask.__init__(self, f'OOZ combat', duration=-1.0)
        self.__participants = participants
        from rka.eq2.master.game.requests.request_controller import RequestController
        self.__request_ctrl: Optional[RequestController] = None

    def _run(self, runtime: IRuntime):
        self.__request_ctrl = self.get_runtime().request_ctrl_factory.create_offzone_request_controller()
        current_participants = set(self.__participants.resolve_players())
        for player in current_participants:
            self.__request_ctrl.player_switcher.borrow_player(player)
        while not self.is_expired():
            self.__request_ctrl.request_group_spam_dps()
            self.__request_ctrl.request_group_normal_combat()
            self.__request_ctrl.request_group_boss_combat()
            try:
                self.sleep(4.0)
            except ScriptException:
                break
            updated_participants = set(self.__participants.resolve_players())
            for player in updated_participants:
                if player not in current_participants:
                    self.__request_ctrl.player_switcher.borrow_player(player)
            for player in current_participants:
                if player not in updated_participants:
                    self.__request_ctrl.player_switcher.return_player(player)
            current_participants = updated_participants

    def _on_expire(self):
        if self.__request_ctrl:
            self.__request_ctrl.close()
        super()._on_expire()
