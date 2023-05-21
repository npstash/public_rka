from rka.eq2.master.game.ability.generated_abilities import ElementalistAbilities, ThaumaturgistAbilities, GeomancerAbilities, EtherealistAbilities
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.gameclass.classes_virtual import PlayerClassBase
from rka.eq2.master.game.interfaces import IPlayer


class ElementalistClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.elementalist = self.add_subclass(GameClasses.Elementalist)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.elementalist.builder(ElementalistAbilities.blistering_waste).build()
        self.elementalist.builder(ElementalistAbilities.brittle_armor).build()
        self.elementalist.builder(ElementalistAbilities.dominion_of_fire).build()
        self.elementalist.builder(ElementalistAbilities.elemental_amalgamation).build()
        self.elementalist.builder(ElementalistAbilities.elemental_overlord).build()
        self.elementalist.builder(ElementalistAbilities.fiery_incineration).build()
        self.elementalist.builder(ElementalistAbilities.frost_pyre).build()
        self.elementalist.builder(ElementalistAbilities.frozen_heavens).build()
        self.elementalist.builder(ElementalistAbilities.glacial_freeze).build()
        self.elementalist.builder(ElementalistAbilities.phoenix_rising).build()
        self.elementalist.builder(ElementalistAbilities.scorched_earth).build()
        self.elementalist.builder(ElementalistAbilities.thermal_depletion).build()
        self.elementalist.builder(ElementalistAbilities.wildfire).build()
        # modifications
        self.elementalist.builder(ElementalistAbilities.brittle_armor).effect_duration(45.0)

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 3
        self.elementalist.builder(ElementalistAbilities.frost_pyre).action(inputs.hotbar4.hotkey1)
        self.elementalist.builder(ElementalistAbilities.thermal_depletion).action(inputs.hotbar4.hotkey2)
        self.elementalist.builder(ElementalistAbilities.brittle_armor).action(inputs.hotbar4.hotkey3)
        self.elementalist.builder(ElementalistAbilities.glacial_freeze).action(inputs.hotbar4.hotkey4)
        self.elementalist.builder(ElementalistAbilities.scorched_earth).action(inputs.hotbar4.hotkey5)
        self.elementalist.builder(ElementalistAbilities.dominion_of_fire).action(inputs.hotbar4.hotkey6)
        self.elementalist.builder(ElementalistAbilities.elemental_overlord).action(inputs.hotbar4.hotkey7)
        self.elementalist.builder(ElementalistAbilities.frozen_heavens).action(inputs.hotbar4.hotkey8)
        # not on hotbars
        self.elementalist.builder(ElementalistAbilities.phoenix_rising).target(GameClasses.Local)


class ThaumaturgistClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.thaumaturgist = self.add_subclass(GameClasses.Thaumaturgist)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.thaumaturgist.builder(ThaumaturgistAbilities.anti_life).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.bloatfly).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.blood_contract).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.blood_parasite).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.bonds_of_blood).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.desiccation).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.exsanguination).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.necrotic_consumption).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.oblivion_link).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.revocation_of_life).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.septic_strike).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.tainted_mutation).build()
        self.thaumaturgist.builder(ThaumaturgistAbilities.virulent_outbreak).build()

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 3
        self.thaumaturgist.builder(ThaumaturgistAbilities.revocation_of_life).action(inputs.hotbar4.hotkey1)
        self.thaumaturgist.builder(ThaumaturgistAbilities.virulent_outbreak).action(inputs.hotbar4.hotkey2)
        self.thaumaturgist.builder(ThaumaturgistAbilities.desiccation).action(inputs.hotbar4.hotkey3)
        self.thaumaturgist.builder(ThaumaturgistAbilities.necrotic_consumption).action(inputs.hotbar4.hotkey4)
        self.thaumaturgist.builder(ThaumaturgistAbilities.exsanguination).action(inputs.hotbar4.hotkey5)
        self.thaumaturgist.builder(ThaumaturgistAbilities.tainted_mutation).action(inputs.hotbar4.hotkey6)
        self.thaumaturgist.builder(ThaumaturgistAbilities.anti_life).action(inputs.hotbar4.hotkey7)
        self.thaumaturgist.builder(ThaumaturgistAbilities.bloatfly).action(inputs.hotbar4.hotkey8)
        # not on hotbars
        self.thaumaturgist.builder(ThaumaturgistAbilities.oblivion_link).target(GameClasses.Local)


class GeomancerClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.geomancer = self.add_subclass(GameClasses.Geomancer)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.geomancer.builder(GeomancerAbilities.bastion_of_iron).build()
        self.geomancer.builder(GeomancerAbilities.domain_of_earth).build()
        self.geomancer.builder(GeomancerAbilities.earthen_phalanx).build()
        self.geomancer.builder(GeomancerAbilities.erosion).build()
        self.geomancer.builder(GeomancerAbilities.geotic_rampage).build()
        self.geomancer.builder(GeomancerAbilities.granite_protector).build()
        self.geomancer.builder(GeomancerAbilities.mudslide).build()
        self.geomancer.builder(GeomancerAbilities.obsidian_mind).build()
        self.geomancer.builder(GeomancerAbilities.stone_hammer).build()
        self.geomancer.builder(GeomancerAbilities.telluric_rending).build()
        self.geomancer.builder(GeomancerAbilities.terrene_destruction).build()
        self.geomancer.builder(GeomancerAbilities.terrestrial_coffin).build()
        self.geomancer.builder(GeomancerAbilities.xenolith).build()

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 3
        self.geomancer.builder(GeomancerAbilities.granite_protector).action(inputs.hotbar4.hotkey1)
        self.geomancer.builder(GeomancerAbilities.terrestrial_coffin).action(inputs.hotbar4.hotkey2)
        self.geomancer.builder(GeomancerAbilities.earthen_phalanx).action(inputs.hotbar4.hotkey3)
        self.geomancer.builder(GeomancerAbilities.bastion_of_iron).action(inputs.hotbar4.hotkey4)
        self.geomancer.builder(GeomancerAbilities.obsidian_mind).action(inputs.hotbar4.hotkey5)
        self.geomancer.builder(GeomancerAbilities.xenolith).action(inputs.hotbar4.hotkey6)
        self.geomancer.builder(GeomancerAbilities.domain_of_earth).action(inputs.hotbar4.hotkey7)
        self.geomancer.builder(GeomancerAbilities.erosion).action(inputs.hotbar4.hotkey8)


class EtherealistClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.etherealist = self.add_subclass(GameClasses.Etherealist)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.etherealist.builder(EtherealistAbilities.cascading_force).build()
        self.etherealist.builder(EtherealistAbilities.compounding_force).build()
        self.etherealist.builder(EtherealistAbilities.essence_of_magic).build()
        self.etherealist.builder(EtherealistAbilities.ethereal_conduit).build()
        self.etherealist.builder(EtherealistAbilities.ethereal_gift).build()
        self.etherealist.builder(EtherealistAbilities.etherflash).build()
        self.etherealist.builder(EtherealistAbilities.ethershadow_assassin).build()
        self.etherealist.builder(EtherealistAbilities.feedback_loop).build()
        self.etherealist.builder(EtherealistAbilities.focused_blast).build()
        self.etherealist.builder(EtherealistAbilities.implosion).build()
        self.etherealist.builder(EtherealistAbilities.levinbolt).build()
        self.etherealist.builder(EtherealistAbilities.mana_schism).build()
        self.etherealist.builder(EtherealistAbilities.recapture).build()
        self.etherealist.builder(EtherealistAbilities.touch_of_magic).build()

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 3
        self.etherealist.builder(EtherealistAbilities.ethereal_gift).action(inputs.hotbar4.hotkey1)
        self.etherealist.builder(EtherealistAbilities.essence_of_magic).action(inputs.hotbar4.hotkey2)
        self.etherealist.builder(EtherealistAbilities.ethereal_conduit).action(inputs.hotbar4.hotkey3).target(GameClasses.Local)
        self.etherealist.builder(EtherealistAbilities.touch_of_magic).action(inputs.hotbar4.hotkey4)
        self.etherealist.builder(EtherealistAbilities.feedback_loop).action(inputs.hotbar4.hotkey5)
        self.etherealist.builder(EtherealistAbilities.implosion).action(inputs.hotbar4.hotkey6)
        self.etherealist.builder(EtherealistAbilities.etherflash).action(inputs.hotbar4.hotkey7)
        self.etherealist.builder(EtherealistAbilities.compounding_force).action(inputs.hotbar4.hotkey8)
        # not on hotbar
        self.etherealist.builder(EtherealistAbilities.recapture).target(GameClasses.Local)
