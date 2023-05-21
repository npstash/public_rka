from typing import List, Optional, Iterable, Callable, Union

from rka.eq2.master import IRuntime
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IPlayer, IPlayerSelector, TOptionalPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.shared import Groups, ClientFlags


class PlayerSelectorFactory:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime

    # noinspection PyMethodMayBeStatic
    def union(self, selector_1: Union[IPlayerSelector, List[IPlayer]], selector_2: Union[IPlayerSelector, List[IPlayer]]) -> IPlayerSelector:
        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                players1 = selector_1.resolve_players() if isinstance(selector_1, IPlayerSelector) else selector_1
                players2 = selector_2.resolve_players() if isinstance(selector_2, IPlayerSelector) else selector_2
                return players1 + players2

        return _Inner()

    # noinspection PyMethodMayBeStatic
    def intersection(self, selector_1: Union[IPlayerSelector, List[IPlayer]], selector_2: Union[IPlayerSelector, List[IPlayer]]) -> IPlayerSelector:
        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                players1 = set(selector_1.resolve_players() if isinstance(selector_1, IPlayerSelector) else selector_1)
                players2 = set(selector_2.resolve_players() if isinstance(selector_2, IPlayerSelector) else selector_2)
                return list(players1.intersection(players2))

        return _Inner()

    # noinspection PyMethodMayBeStatic
    def difference(self, keep: Union[IPlayerSelector, List[IPlayer]], exclude: Union[IPlayerSelector, List[IPlayer]]) -> IPlayerSelector:
        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                players1 = set(keep.resolve_players() if isinstance(keep, IPlayerSelector) else keep)
                players2 = set(exclude.resolve_players() if isinstance(exclude, IPlayerSelector) else exclude)
                return list(players1.difference(players2))

        return _Inner()

    def zoned_remote_by_selection_or_all(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                selection_id = runtime.overlay.get_selection_id()
                player_by_id = runtime.player_mgr.get_online_player_by_overlay_id(selection_id)
                if not player_by_id or not player_by_id.is_zoned():
                    return []
                if player_by_id.is_local():
                    return runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
                return [player_by_id]

        return _Inner()

    def if_none_then_by_selection(self, player: TOptionalPlayer) -> IPlayerSelector:
        runtime = self.__runtime
        player = self.__runtime.player_mgr.resolve_player(player)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                if isinstance(player, IPlayer):
                    return [player]
                selection_id = runtime.overlay.get_selection_id()
                player_by_id = runtime.player_mgr.get_online_player_by_overlay_id(selection_id)
                if player_by_id:
                    return [player_by_id]
                return []

        return _Inner()

    def if_none_then_all_zoned_remote(self, player: TOptionalPlayer) -> IPlayerSelector:
        runtime = self.__runtime
        player = self.__runtime.player_mgr.resolve_player(player)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                if isinstance(player, IPlayer):
                    return [player]
                return runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)

        return _Inner()

    def local_online(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                player = runtime.player_mgr.find_first_player(lambda player_: player_.is_local() and player_.is_online())
                if not player:
                    return None
                return [player]

        return _Inner()

    def remote_online(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(lambda player: player.is_remote() and player.is_online())

        return _Inner()

    def remote_online_non_member(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(lambda player: player.is_remote() and player.is_online() and not player.get_player_info().membership)

        return _Inner()

    def remote_non_hidden(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(lambda player: player.is_remote() and not player.is_hidden())

        return _Inner()

    def hidden(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(lambda player: player.is_hidden())

        return _Inner()

    def all_online(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.get_players(min_status=PlayerStatus.Online)

        return _Inner()

    def all_logged(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.get_players(min_status=PlayerStatus.Logged)

        return _Inner()

    def all_zoned(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.get_players(min_status=PlayerStatus.Zoned)

        return _Inner()

    def all_zoned_remote(self) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)

        return _Inner()

    def all_zoned_remote_except(self, except_sel: IPlayerSelector) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                except_players = except_sel.resolve_players()
                zoned = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
                for except_player in except_players:
                    if except_player in zoned:
                        zoned.remove(except_player)
                return zoned

        return _Inner()

    def filtered_remote_by_class(self, game_class: GameClass, from_players_sel: IPlayerSelector):
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                from_players = from_players_sel.resolve_players()
                players_by_class = runtime.player_mgr.find_players(lambda player: player.is_remote() and player.is_class(game_class))
                return [player for player in players_by_class if player in from_players]

        return _Inner()

    def filtered_by_class(self, game_class: GameClass, from_players_sel: IPlayerSelector):
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                from_players = from_players_sel.resolve_players()
                players_by_class = runtime.player_mgr.find_players(lambda player: player.is_class(game_class))
                return [player for player in players_by_class if player in from_players]

        return _Inner()

    def one_zoned_by_class(self, game_class: GameClass, zone_name: Optional[str] = None):
        runtime = self.__runtime

        def condition(player: IPlayer) -> bool:
            if not player.is_remote() or not player.is_class(game_class):
                return False
            if not zone_name:
                return player.get_status() >= PlayerStatus.Zoned
            return zone_name == player.get_zone()

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                player_by_class = runtime.player_mgr.find_first_player(condition)
                if player_by_class:
                    return [player_by_class]
                return []

        return _Inner()

    def all_remote_zoned_by_class(self, game_class: GameClass, zone_name: Optional[str] = None):
        runtime = self.__runtime

        def condition(player: IPlayer) -> bool:
            if not player.is_remote() or not player.is_class(game_class):
                return False
            if not zone_name:
                return player.get_status() >= PlayerStatus.Zoned
            return zone_name == player.get_zone()

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(condition)

        return _Inner()

    def all_remote_in_zone(self, zone_name: str):
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                zoned_players = runtime.player_mgr.find_players(lambda player: player.is_remote() and player.get_zone() == zone_name)
                if zoned_players:
                    return zoned_players
                return []

        return _Inner()

    # noinspection PyMethodMayBeStatic
    def by_copy(self, players: Iterable[IPlayer]) -> IPlayerSelector:
        players = list(players)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return players

        return _Inner()

    # noinspection PyMethodMayBeStatic
    def by_ref(self, players: Iterable[IPlayer]) -> IPlayerSelector:
        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return list(players)

        return _Inner()

    # noinspection PyMethodMayBeStatic
    def by_result(self, cb: Callable[[], Iterable[IPlayer]]) -> IPlayerSelector:
        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                result = cb()
                if isinstance(result, list):
                    return result
                return list(result)

        return _Inner()

    def by_group(self, group_id: Groups) -> IPlayerSelector:
        runtime = self.__runtime

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(lambda player: player.is_remote() and player.get_client_config_data().group_id == group_id)

        return _Inner()

    def can_login(self, player_filter: Callable[[IPlayer], bool]) -> IPlayerSelector:
        runtime = self.__runtime

        def condition(player: IPlayer) -> bool:
            if not player.is_remote():
                return False
            return player.get_status() > PlayerStatus.Offline and player_filter(player)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(condition)

        return _Inner()

    def cant_login(self, player_filter: Callable[[IPlayer], bool]) -> IPlayerSelector:
        runtime = self.__runtime

        def condition(player: IPlayer) -> bool:
            if not player.is_remote():
                return False
            return player.get_status() <= PlayerStatus.Offline and player_filter(player)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(condition)

        return _Inner()

    def can_relog_into(self, into_player: IPlayer) -> IPlayerSelector:
        runtime = self.__runtime

        def _can_relog_into(p_from: IPlayer, p_to: IPlayer) -> bool:
            from_host = p_from.get_host_id()
            if from_host is None:
                return False
            to_host_1 = p_to.get_client_config_data().host_id
            if to_host_1 == from_host:
                return True
            to_host_2 = p_to.get_client_config_data().alternative_host_id
            if to_host_2 is not None and to_host_2 == from_host:
                return True
            return False

        def condition(player: IPlayer) -> bool:
            if not player.is_remote():
                return False
            return player.get_status() > PlayerStatus.Offline and _can_relog_into(player, into_player)

        class _Inner(IPlayerSelector):
            def resolve_players(self) -> List[IPlayer]:
                return runtime.player_mgr.find_players(condition)

        return _Inner()
