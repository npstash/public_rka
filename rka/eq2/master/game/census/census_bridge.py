from typing import Optional

from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.gameclass import GameClass
from rka.eq2.master.game.interfaces import IPlayer
from rka.services.api.census import TCensusStruct


class ICensusBridge:
    def get_max_known_player_hitpoints(self) -> Optional[int]:
        raise NotImplementedError()

    def get_item_id(self, item_name: str) -> Optional[int]:
        raise NotImplementedError()

    def get_player_census_data(self, server_name: str, player_name: str) -> Optional[TCensusStruct]:
        raise NotImplementedError()

    def get_ability_census_data_for_player(self, player: IPlayer, gameclass: GameClass, abilityname_lower: str) -> Optional[TCensusStruct]:
        raise NotImplementedError()

    def get_ability_census_data_by_tier(self, gameclass: GameClass, player_level: int,
                                        abilityname_lower: str, ability_tier: AbilityTier) -> Optional[TCensusStruct]:
        raise NotImplementedError()
