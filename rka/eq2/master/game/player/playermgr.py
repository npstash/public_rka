from typing import List, Dict, Optional, Callable, Iterable

from rka.eq2.master import BuilderTools
from rka.eq2.master.control.client_controller import ClientConfig
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IPlayer, IPlayerManager, DEFAULT_MAX_STATUS, \
    DEFAULT_MIN_STATUS, TAbilityBuildTarget, TOptionalPlayer, TValidTarget, DEFAULT_OR_FLAGS, DEFAULT_AND_FLAGS, DEFAULT_NOR_FLAGS, \
    IEffectsManager
from rka.eq2.shared import ClientConfigData, Groups, GameServer, ClientFlags


class PlayerManager(IPlayerManager):
    def __init__(self, effects_mgr: IEffectsManager):
        from rka.eq2.master.game.player.player import Player
        self.__effects_mgr = effects_mgr
        self.__all_players = [Player(self, client_config) for client_config in ClientConfig.get_all_client_configs().values()]
        self.__player_names_to_player_list: Dict[str, List[IPlayer]] = {
            player.get_player_name(): [p for p in self.__all_players if p.get_player_name() == player.get_player_name()] for player in self.__all_players
        }
        self.__client_ids_to_players: Dict[str, IPlayer] = {player.get_client_id(): player for player in self.__all_players}
        self.__next_dummy_player_id = 0

    def initialize_players(self, builder_tools: BuilderTools):
        for player in self.__all_players:
            player.build_player_info(builder_tools)
        for player in self.__all_players:
            player.build_player_abilities(builder_tools=builder_tools)
        for player in self.__all_players:
            player.build_player_effects(builder_tools)

    def get_player_by_client_id(self, client_id) -> Optional[IPlayer]:
        if client_id not in self.__client_ids_to_players.keys():
            return None
        return self.__client_ids_to_players[client_id]

    def get_player_by_name(self, player_name: str) -> Optional[IPlayer]:
        if player_name not in self.__player_names_to_player_list.keys():
            return None
        matching_players = self.__player_names_to_player_list[player_name]
        best_match = max(matching_players, key=lambda player: player.get_status().value * 100 - player.get_client_config_data().group_id)
        return best_match

    def get_online_player_by_overlay_id(self, status_overlay_id: int) -> Optional[IPlayer]:
        for player in self.__all_players:
            if player.is_online() and player.get_client_config_data().overlay_id == status_overlay_id:
                return player
        return None

    def find_first_player(self, fn: Callable[[IPlayer], bool]) -> Optional[IPlayer]:
        for player in self.__all_players:
            if fn(player):
                return player
        return None

    def find_best_player(self, fn: Callable[[IPlayer], int]) -> Optional[IPlayer]:
        max_value = 0
        best_player = None
        for player in self.__all_players:
            value = fn(player)
            if not isinstance(value, int):
                continue
            if value > max_value:
                max_value = value
                best_player = player
        return best_player

    def find_players(self, fn: Optional[Callable[[IPlayer], bool]] = None) -> List[IPlayer]:
        result = []
        for player in self.__all_players:
            if not fn or fn(player):
                result.append(player)
        return result

    def get_players(self, and_flags=DEFAULT_AND_FLAGS, or_flags=DEFAULT_OR_FLAGS, nor_flags=DEFAULT_NOR_FLAGS,
                    min_status=DEFAULT_MIN_STATUS, max_status=DEFAULT_MAX_STATUS) -> List[IPlayer]:
        return [p for p in self.__all_players if p.get_client_flags() & and_flags == and_flags
                and p.get_client_flags() & or_flags != 0
                and p.get_client_flags() & nor_flags == 0
                and min_status <= p.get_status() <= max_status]

    def resolve_player(self, player: TOptionalPlayer, min_status=DEFAULT_MIN_STATUS, max_status=DEFAULT_MAX_STATUS) -> Optional[IPlayer]:
        if isinstance(player, str):
            resolved_player = self.get_player_by_name(player)
        elif isinstance(player, IPlayer):
            resolved_player = player
        else:
            return None
        if not resolved_player:
            return None
        if min_status <= resolved_player.get_status() <= max_status:
            return resolved_player
        return None

    def resolve_targets(self, target: TAbilityBuildTarget, player_filter: Callable[[IPlayer], bool] = None) -> List[TValidTarget]:
        if not target:
            return []
        if isinstance(target, IPlayer):
            return [target] if not player_filter or player_filter(target) else []
        elif isinstance(target, str):
            target_player = self.get_player_by_name(target)
            if target_player:
                return [target_player] if not player_filter or player_filter(target_player) else []
            # not a (managed) player
            return [target]
        elif isinstance(target, GameClass):
            return self.find_players(lambda p: p.is_class(target) and (not player_filter or player_filter(p)))
        elif isinstance(target, Iterable):
            resolved_targets = set()
            for subtarget in target:
                resolved_subtargets = self.resolve_targets(subtarget, player_filter)
                resolved_targets.update(resolved_subtargets)
            return list(resolved_targets)
        assert False, target

    def create_dummy_player(self, player_name: str) -> IPlayer:
        from rka.eq2.master.game.player.player import DummyPlayer
        client_config_data = ClientConfigData(host_id=0, client_id=f'Dummy-{self.__next_dummy_player_id}',
                                              client_flags=ClientFlags.Remote | ClientFlags.Hidden,
                                              game_server=GameServer.thurgadin, player_name=player_name,
                                              overlay_id=-1, group_id=Groups.MAIN_1, cred_key='')
        self.__next_dummy_player_id += 1
        player = DummyPlayer(self, ClientConfig(client_config_data))
        player.build_player_effects(self.__effects_mgr)
        player.effects.start_effects()
        return player
