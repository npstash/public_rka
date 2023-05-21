import pydoc
from typing import List, Optional, Iterator

from rka.eq2.configs.shared.game_constants import CURRENT_MAX_LEVEL
from rka.eq2.master import BuilderTools
from rka.eq2.master.control import IClientConfig
from rka.eq2.master.control.action import ActionDelegate
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.ability.ability_builder import AbilityStore
from rka.eq2.master.game.ability.generated_abilities import CommonerAbilities
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.gameclass.classes_adventure import CommonerClass
from rka.eq2.master.game.gameclass.classes_virtual import PlayerClassBase, LocalClass, RemoteClass
from rka.eq2.master.game.interfaces import IPlayer, IEffectBuilder
from rka.eq2.master.game.player import PlayerInfo, logger


class PlayerConfig:
    def __init__(self):
        self.player_name: Optional[str] = None
        self.player_gameclasses: List[PlayerClassBase] = list()
        self.player_effects: List[IEffectBuilder] = list()
        self.player_info = PlayerInfo()
        self.abilities_defined = False
        self.effects_added = False
        self.has_census = True
        self.__cached_business = -1

    def _define_player_abilities(self, _player: IPlayer):
        self.abilities_defined = True

    def _define_player_effects(self):
        self.effects_added = True

    def add_class(self, player_class: PlayerClassBase):
        self.player_gameclasses.append(player_class)
        self.__cached_business = -1

    def build_all_classes_abilities(self, player: IPlayer, builder_tools: BuilderTools):
        for player_class in self.player_gameclasses:
            player_class.define_class_abilities(player)
            player_class.define_class_effects(player)
            self.player_effects += player_class.class_effects
        self._define_player_abilities(player)
        self._define_player_effects()
        assert self.abilities_defined, player
        assert self.effects_added, player
        actions = set()
        for player_class in self.player_gameclasses:
            if not self.has_census:
                player_class.fill_missing_ability_tiers(AbilityTier.UnknownHighest)
            registered_abilities = player_class.build_class_abilities(player, builder_tools=builder_tools)
            for ability in registered_abilities:
                action = ability.get_action()
                if isinstance(action, ActionDelegate):
                    action = action.unwrap_delegate()
                assert action not in actions, f'Player {player}, ability {ability}, action {action}'
                actions.add(action)

    def iter_ability_stores(self) -> Iterator[AbilityStore]:
        for player_class in self.player_gameclasses:
            for ability_store in player_class.ability_stores:
                yield ability_store

    def iter_classes(self) -> Iterator[GameClass]:
        for player_class in self.player_gameclasses:
            for ability_store in player_class.ability_stores:
                yield ability_store.game_class

    def get_class_business(self) -> int:
        if self.__cached_business < 0:
            self.__cached_business = max(self.iter_classes(), key=lambda gameclass: gameclass.business).business
        return self.__cached_business


class PlayerConfigFactory:
    @staticmethod
    def produce_player_config(client_config: IClientConfig) -> PlayerConfig:
        from rka.eq2.configs.master.players import get_playerconfig_class_name
        player_name = client_config.get_client_config_data().player_name
        player_config_class = pydoc.locate(get_playerconfig_class_name(client_config.get_client_config_data().game_server.value, player_name))
        if player_config_class:
            # noinspection PyCallingNonCallable
            player_config_instance = player_config_class()
        elif client_config.get_client_config_data().client_flags.is_local():
            logger.warn(f'No config class found for local player {player_name}')
            player_config_instance = UnknownLocalPlayer()
        else:
            logger.warn(f'No config class found for remote player {player_name}')
            player_config_instance = UnknownRemotePlayer()
        player_config_instance.player_name = player_name
        return player_config_instance


class UnknownLocalPlayer(PlayerConfig):
    def __init__(self):
        PlayerConfig.__init__(self)
        self.local = LocalClass(CURRENT_MAX_LEVEL)
        self.add_class(self.local)
        self.has_census = False


class UnknownRemotePlayer(PlayerConfig):
    def __init__(self):
        PlayerConfig.__init__(self)
        self.has_census = False
        self.remote = RemoteClass(CURRENT_MAX_LEVEL)
        self.add_class(self.remote)
        self.commoner = CommonerClass(CURRENT_MAX_LEVEL)
        self.add_class(self.commoner)

    def _define_player_abilities(self, player: IPlayer):
        super()._define_player_abilities(player)
        self.remote.standard_action_bindings(player)
        inputs = player.get_inputs()
        self.commoner.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.commoner.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)
