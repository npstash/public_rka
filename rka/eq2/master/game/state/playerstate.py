from typing import Optional

from rka.components.events.event_system import EventSystem
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer, TValidPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.state import logger
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.shared import GameServer, ClientFlags


class PlayerState:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__player_mgr = runtime.player_mgr
        EventSystem.get_main_bus().subscribe(MasterEvents.CLIENT_REGISTERED(), self.__notify_client_registered)
        EventSystem.get_main_bus().subscribe(MasterEvents.CLIENT_UNREGISTERED(), self.__notify_client_unregistered)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.FRIEND_LOGGED(), self.__notify_friend_logged)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_LINKDEAD(), self.__notify_player_linkdead)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__zone_changed)
        EventSystem.get_main_bus().subscribe(ObjectStateEvents.PLAYER_STATUS_CHANGED(from_status=PlayerStatus.Zoned), self.__zone_out_remote_players)

    # noinspection PyMethodMayBeStatic
    def __transition_player_up_to_status(self, player: IPlayer, target_status: PlayerStatus, min_status=PlayerStatus.Offline):
        while min_status <= player.get_status() < target_status:
            current_status = player.get_status()
            player.set_status(current_status.next())

    # noinspection PyMethodMayBeStatic
    def __transition_player_down_to_status(self, player: IPlayer, target_status: PlayerStatus):
        while player.get_status() > target_status:
            current_status = player.get_status()
            player.set_status(current_status.previous())

    def get_main_player(self) -> Optional[IPlayer]:
        main_players = self.__player_mgr.find_players(lambda player: player.is_main_player())
        if main_players:
            if len(main_players) > 1:
                logger.error('Multiple main players online: ' + ', '.join(map(str, main_players)))
            return main_players[0]
        return None

    def get_main_player_name(self) -> Optional[str]:
        main_player = self.get_main_player()
        if not main_player:
            return None
        return main_player.get_player_name()

    def get_main_player_zone(self) -> Optional[str]:
        main_player = self.get_main_player()
        if main_player is None:
            return None
        return main_player.get_zone()

    def get_main_server(self) -> Optional[GameServer]:
        main_player = self.get_main_player()
        if main_player is None:
            return None
        return main_player.get_server()

    def notify_player_zoned_to_main(self, player: TValidPlayer) -> bool:
        logger.info(f'player {player} changes zone to main zone')
        main_zone = self.get_main_player_zone()
        if main_zone is not None:
            return self.notify_player_zoned(player, main_zone)
        return False

    def notify_main_player_zoned(self, zone: str) -> bool:
        main_player = self.get_main_player()
        if main_player is not None:
            return self.notify_player_zoned(main_player, zone)
        logger.error(f'main player zoned {zone} but not registered online yet')
        return True

    def notify_player_zoned(self, player: TValidPlayer, zone: str) -> bool:
        logger.info(f'player {player} changes zone to {zone}')
        assert zone is not None
        player = self.__runtime.player_mgr.resolve_player(player, min_status=PlayerStatus.Offline)
        if player is None:
            return False
        if not player.is_main_player():
            main_zone = self.get_main_player_zone()
            if not main_zone:
                return False
            main_server = self.get_main_server()
        else:
            self.__transition_player_up_to_status(player, PlayerStatus.Zoned, min_status=PlayerStatus.Online)
            main_zone = zone
            main_server = player.get_server()
        old_zone = player.get_zone()
        player.set_zone(zone)
        if zone == main_zone and player.get_server() == main_server:
            self.__transition_player_up_to_status(player, PlayerStatus.Zoned, min_status=PlayerStatus.Online)
            if not player.is_alive():
                player.set_alive(True)
        else:
            self.__transition_player_up_to_status(player, PlayerStatus.Logged, min_status=PlayerStatus.Online)
            self.__transition_player_down_to_status(player, PlayerStatus.Logged)
        if player.is_main_player():
            # other players are in old zone
            for other_player in self.__player_mgr.find_players(lambda p: p.is_remote() and p.get_status() >= PlayerStatus.Logged):
                self.notify_player_zoned(other_player, other_player.get_zone())
        return zone != old_zone

    def __zone_out_remote_players(self, event: ObjectStateEvents.PLAYER_STATUS_CHANGED):
        if event.player.is_local() and event.to_status < PlayerStatus.Zoned:
            remote_players = self.__player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
            for player in remote_players:
                player.set_status(PlayerStatus.Logged)

    def __notify_client_registered(self, event: MasterEvents.CLIENT_REGISTERED):
        player = self.__player_mgr.get_player_by_client_id(event.client_id)
        if not player:
            logger.error(f'unknown client registered: {event}')
            return
        logger.info(f'player {player} is online')
        self.__transition_player_up_to_status(player, PlayerStatus.Online)

    def __notify_client_unregistered(self, event: MasterEvents.CLIENT_UNREGISTERED):
        player = self.__player_mgr.get_player_by_client_id(event.client_id)
        if not player:
            logger.error(f'unknown client un registered: {event}')
            return
        logger.info(f'player {player} is offline')
        self.__transition_player_down_to_status(player, PlayerStatus.Offline)

    def __notify_friend_logged(self, event: PlayerInfoEvents.FRIEND_LOGGED):
        player = self.__runtime.player_mgr.get_player_by_name(event.friend_name)
        if not player:
            return
        if event.login:
            self.__transition_player_up_to_status(player, PlayerStatus.Logged, min_status=PlayerStatus.Online)
        else:
            self.__transition_player_down_to_status(player, PlayerStatus.Online)

    def __notify_player_linkdead(self, event: PlayerInfoEvents.PLAYER_LINKDEAD):
        self.__transition_player_down_to_status(event.player, PlayerStatus.Online)

    def __zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        self.set_default_target(event.player, None)
        self.set_follow_target(event.player, None)

    def get_default_target(self, for_player: IPlayer) -> Optional[str]:
        if for_player.is_local():
            return None
        default_target_name = for_player.aspects.default_target_name
        if not default_target_name:
            default_target_name = self.get_main_player_name()
        return default_target_name

    # noinspection PyMethodMayBeStatic
    def set_default_target(self, for_player: IPlayer, target_name: Optional[str]):
        for_player.aspects.default_target_name = target_name

    # noinspection PyMethodMayBeStatic
    def get_follow_target(self, for_player: IPlayer) -> Optional[str]:
        if for_player.is_local():
            return None
        default_follow_target = for_player.aspects.default_follow_target
        if not default_follow_target:
            default_follow_target = self.get_main_player_name()
        return default_follow_target

    # noinspection PyMethodMayBeStatic
    def set_follow_target(self, for_player: IPlayer, follow_target: Optional[str]):
        for_player.aspects.default_follow_target = follow_target
