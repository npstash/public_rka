from rka.eq2.configs.master.guildhalls import GuildHallName, guild_hall_configs
from rka.eq2.master.game.ability.generated_abilities import *
from rka.eq2.master.game.effect.effects import ItemEffects
from rka.eq2.master.game.gameclass.classes_adventure import MysticClass
from rka.eq2.master.game.gameclass.classes_ascension import ElementalistClass
from rka.eq2.master.game.gameclass.classes_tradeskill import SageClass
from rka.eq2.master.game.gameclass.classes_virtual import ItemsClass, LocalClass
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import HomeCityNames
from rka.eq2.master.game.player.player_config import PlayerConfig


def get_playerconfig_class_name(server_name: str, player_name: str) -> str:
    return f'{__name__}.{server_name}_{player_name}'


class Servername_Playername(PlayerConfig):
    def __init__(self):
        PlayerConfig.__init__(self)
        self.mystic = MysticClass(125)
        self.remote = LocalClass(125)
        self.elementalist = ElementalistClass(120)
        self.items = ItemsClass()
        self.sage = SageClass(125)
        self.add_class(self.mystic)
        self.add_class(self.elementalist)
        self.add_class(self.remote)
        self.add_class(self.items)
        self.add_class(self.sage)
        self.player_info.home_city = HomeCityNames.qeynos
        self.player_info.guildhall_config = guild_hall_configs[GuildHallName.ExampleGuild]

    def _define_player_abilities(self, player: IPlayer):
        super()._define_player_abilities(player)
        self.mystic.standard_action_bindings(player)
        self.elementalist.standard_action_bindings(player)
        self.remote.standard_action_bindings(player)
        ### items
        self.items.items.builder(ItemsAbilities.quelule_cocktail).build()
        self.items.items.builder(ItemsAbilities.critical_thinking).charm_1().build()
        self.items.items.builder(ItemsAbilities.poison_fingers).build()
        self.items.items.builder(ItemsAbilities.noxious_effusion).build()
        self.items.items.builder(ItemsAbilities.divine_embrace).build()
        self.items.items.builder(ItemsAbilities.mindworms).build()
        self.items.items.builder(ItemsAbilities.voidlink).build()
        self.items.items.builder(ItemsAbilities.embrace_of_frost).build()
        self.items.items.builder(ItemsAbilities.flames_of_yore).build()
        self.items.items.builder(ItemsAbilities.essence_of_smash).build()
        self.items.items.builder(ItemsAbilities.prepaded_cutdown).build()
        self.items.items.builder(ItemsAbilities.piercing_gaze).build()

    def _define_player_effects(self):
        super()._define_player_effects()
        self.player_effects.append(ItemEffects.SYMPHONY_OF_THE_VOID())
