from typing import Dict, Optional, List, Callable

from rka.components.concurrency.workthread import RKAFuture, RKAFutureMuxer
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import IPlayerSelector, IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting.framework import PlayerScriptTask
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.shared import ClientFlags


class ProcessingScriptFactory:
    def create_script(self, player: IPlayer):
        raise NotImplementedError()


class ProcessPlayers(PlayerScriptTask):
    def __init__(self, description: str, player_selector: IPlayerSelector, script_factory: ProcessingScriptFactory,
                 auto_logout=True, max_running_players=10, allow_mixed_hidden_players=True):
        PlayerScriptTask.__init__(self, f'Process {description} for all players', -1.0)
        self.player_selector = player_selector
        self.script_factory = script_factory
        self.auto_logout = auto_logout
        self.max_running_players = max_running_players
        self.allow_mixed_hidden_players = allow_mixed_hidden_players
        self.login_was_required: Dict[IPlayer, bool] = dict()

    def _resolve_best_player_by_overlay_id(self, mandatory_condition: Optional[Callable[[IPlayer], bool]] = None) -> Optional[IPlayer]:
        def player_score(player: IPlayer) -> Optional[int]:
            if player.get_client_config_data().overlay_id != current_overlay_id:
                return None
            player_status_score = 10 if player.get_status() >= PlayerStatus.Online else 1
            condition_score = 1 if mandatory_condition and mandatory_condition(player) else 0
            return player.get_client_config_data().group_id.get_overlay_resolve_priority() * player_status_score * condition_score

        current_overlay_id = self.get_runtime().overlay.get_selection_id()
        return self.get_runtime().player_mgr.find_best_player(player_score)

    @staticmethod
    def __find_online_player_for_host_id(runtime: IRuntime, host_id: int) -> Optional[IPlayer]:
        online_players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote)
        for online_player in online_players:
            current_online_hid = online_player.get_host_id()
            if current_online_hid is None:
                logger.warn(f'Could not read current Host ID for {online_player}')
                continue
            if host_id == current_online_hid:
                return online_player
        return None

    @staticmethod
    def __find_online_player_for(runtime: IRuntime, target_player: IPlayer) -> Optional[IPlayer]:
        if target_player.get_status() >= PlayerStatus.Online:
            return target_player
        # 1st find matching Host_ID (i.e. matching primary host for this player)
        online_player = ProcessPlayers.__find_online_player_for_host_id(runtime, target_player.get_client_config_data().host_id)
        if online_player:
            return online_player
        # 2nd find matching alternative Host_ID (i.e. matching secondary host for this player)
        return ProcessPlayers.__find_online_player_for_host_id(runtime, target_player.get_client_config_data().alternative_host_id)

    def __login_player(self, from_player: IPlayer, to_player: IPlayer):
        self.get_player_scripting_framework(from_player).player_processing_start_random_wait()
        target_psf = self.get_player_scripting_framework(to_player, allow_offline=True)
        _, login_was_required, _ = self.get_player_scripting_framework(from_player).login_sync(target_psf)
        self.login_was_required[to_player] = login_was_required

    def __start_processing_for_player(self, player: IPlayer):
        if player.get_status() < PlayerStatus.Logged:
            logger.warn(f'Player {player} should be logged, but is {player.get_status().name}')
            return
        script = self.script_factory.create_script(player)
        psf = self.get_player_scripting_framework(player)
        psf.run_script(script)
        script.wait_until_completed()

    def __logout_player(self, player: IPlayer):
        logout_required = self.auto_logout and self.login_was_required.setdefault(player, False)
        psf = self.get_player_scripting_framework(player)
        if logout_required:
            psf.logout()

    def __process_one_player_sync(self, from_player: IPlayer, to_player: IPlayer):
        self.get_runtime().overlay.log_event(f'Starting processing of {to_player} from {from_player}\'s account', Severity.Normal)
        self.__login_player(from_player=from_player, to_player=to_player)
        self.__start_processing_for_player(to_player)
        self.__logout_player(to_player)
        self.get_runtime().overlay.log_event(f'Completed processing of {to_player}', Severity.Normal)

    def _run(self, runtime: IRuntime):
        process_players = self.player_selector.resolve_players()
        player_futures: Dict[IPlayer, RKAFuture] = dict()
        future_muxer = RKAFutureMuxer()
        while process_players and not self.is_expired():
            unreachable_players: List[IPlayer] = []
            map_online_to_process: Dict[IPlayer, IPlayer] = dict()
            # select execution hosts
            for process_player in process_players:
                online_player = ProcessPlayers.__find_online_player_for(runtime, process_player)
                if not online_player:
                    unreachable_players.append(process_player)
                    continue
                # dont overwrite mappings where requested player is already online
                if online_player in map_online_to_process and map_online_to_process[online_player] == online_player:
                    continue
                map_online_to_process[online_player] = process_player
            # remove players for which there are no online clients with shared host, i.e. no host available
            for process_player in unreachable_players:
                process_players.remove(process_player)
            # exclude players that already run a script
            online_players = list(map_online_to_process.keys())
            for online_player in online_players:
                if online_player in player_futures and not player_futures[online_player].is_completed():
                    del map_online_to_process[online_player]
            # all hosts are busy, wait
            if not map_online_to_process:
                future_muxer.wait_and_pop()
                continue
            if not self.allow_mixed_hidden_players:
                # dont process hidden and non-hidden players at the same time
                is_any_non_hidden_running = False
                for player, player_future in player_futures.items():
                    if player.is_remote() and not player.is_hidden() and not player_future.is_completed():
                        is_any_non_hidden_running = True
                is_any_non_hidden_on_list = False
                for process_player in map_online_to_process.values():
                    if process_player.is_remote() and not process_player.is_hidden():
                        is_any_non_hidden_on_list = True
                # process non-hidden players first - i.e. remove hidden from list, if any non-hidden are on list
                online_players = list(map_online_to_process.keys())
                if is_any_non_hidden_running or is_any_non_hidden_on_list:
                    for online_player in online_players:
                        if map_online_to_process[online_player].is_hidden():
                            del map_online_to_process[online_player]
            # prevent running too many players at a time
            running_players_by_hometown = dict()
            for player, player_future in player_futures.items():
                if not player_future.is_completed():
                    hometown = player.get_player_info().home_city
                    running_players_by_hometown[hometown] = running_players_by_hometown.setdefault(hometown, 0) + 1
            if running_players_by_hometown and max(running_players_by_hometown.values()) >= self.max_running_players:
                future_muxer.wait_and_pop()
                continue
            for online_player, process_player in map_online_to_process.items():
                process_action = lambda f_p=online_player, t_p=process_player: self.__process_one_player_sync(from_player=f_p, to_player=t_p)
                process_future = self.run_concurrent_task(process_action)
                player_futures[process_player] = process_future
                player_futures[online_player] = process_future
                future_muxer.add_future(process_future)
                # dont start processing again for this player
                process_players.remove(process_player)
                hometown = online_player.get_player_info().home_city
                running_players_by_hometown[hometown] = running_players_by_hometown.setdefault(hometown, 0) + 1
                if running_players_by_hometown and max(running_players_by_hometown.values()) >= self.max_running_players:
                    break
        future_muxer.wait_for_all()
