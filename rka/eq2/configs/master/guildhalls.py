from enum import auto
from typing import Dict

from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import GuildHallInfo
from rka.util.util import NameEnum


class GuildHallName(NameEnum):
    ExampleGuild = auto()


guild_hall_configs: Dict[GuildHallName, GuildHallInfo] = {
    GuildHallName.ExampleGuild: GuildHallInfo(
        guildhall_name='ExampleGuild',
        taskboard_location=Location.decode_location('PUT COORDINATES HERE'),
        recipe_merchant_location=Location.decode_location('PUT COORDINATES HERE'),
        recipe_merchant_name='Merchant',
        writ_agent_location=Location.decode_location('PUT COORDINATES HERE'),
        writ_agent_name='Writ agent',
        private_guild=False,
        workstation_locations={
            GameClasses.Jeweler: Location.decode_location('PUT COORDINATES HERE'),
        },
        housing=False,
    ),
}
