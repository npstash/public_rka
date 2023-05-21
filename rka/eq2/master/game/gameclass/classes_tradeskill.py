from rka.eq2.master.game.ability.generated_abilities import SageAbilities, AlchemistAbilities, JewelerAbilities, ProvisionerAbilities, \
    CarpenterAbilities, ArmorerAbilities, TailorAbilities, WoodworkerAbilities, ArtisanAbilities, WeaponsmithAbilities
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.gameclass.classes_virtual import PlayerClassBase
from rka.eq2.master.game.interfaces import IPlayer


class ArtisanClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.artisan = self.add_subclass(GameClasses.Artisan)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.artisan.builder(ArtisanAbilities.salvage).build()
        if player.is_local():
            self.artisan.builder(ArtisanAbilities.salvage).command()


class ScholarClass(ArtisanClass):
    def __init__(self, class_level: int):
        ArtisanClass.__init__(self, class_level)
        self.scholar = self.add_subclass(GameClasses.Scholar)


class CraftsmanClass(ArtisanClass):
    def __init__(self, class_level: int):
        ArtisanClass.__init__(self, class_level)
        self.craftsman = self.add_subclass(GameClasses.Craftsman)


class OutfitterClass(ArtisanClass):
    def __init__(self, class_level: int):
        ArtisanClass.__init__(self, class_level)
        self.outfitter = self.add_subclass(GameClasses.Outfitter)


class SageClass(ScholarClass):
    def __init__(self, class_level: int):
        ScholarClass.__init__(self, class_level)
        self.sage = self.add_subclass(GameClasses.Sage)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.sage.builder(SageAbilities.spellbinding).action(inputs.crafting_hotbar.hotkey1).build()
        self.sage.builder(SageAbilities.notation).action(inputs.crafting_hotbar.hotkey2).build()
        self.sage.builder(SageAbilities.lettering).action(inputs.crafting_hotbar.hotkey3).build()
        self.sage.builder(SageAbilities.incantation).action(inputs.crafting_hotbar.hotkey4).build()
        self.sage.builder(SageAbilities.scripting).action(inputs.crafting_hotbar.hotkey5).build()
        self.sage.builder(SageAbilities.calligraphy).action(inputs.crafting_hotbar.hotkey6).build()


class AlchemistClass(ScholarClass):
    def __init__(self, class_level: int):
        ScholarClass.__init__(self, class_level)
        self.alchemist = self.add_subclass(GameClasses.Alchemist)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.alchemist.builder(AlchemistAbilities.endothermic).action(inputs.crafting_hotbar.hotkey1).build()
        self.alchemist.builder(AlchemistAbilities.reactions).action(inputs.crafting_hotbar.hotkey2).build()
        self.alchemist.builder(AlchemistAbilities.experiment).action(inputs.crafting_hotbar.hotkey3).build()
        self.alchemist.builder(AlchemistAbilities.exothermic).action(inputs.crafting_hotbar.hotkey4).build()
        self.alchemist.builder(AlchemistAbilities.synthesis).action(inputs.crafting_hotbar.hotkey5).build()
        self.alchemist.builder(AlchemistAbilities.analyze).action(inputs.crafting_hotbar.hotkey6).build()


class JewelerClass(ScholarClass):
    def __init__(self, class_level: int):
        ScholarClass.__init__(self, class_level)
        self.jeweler = self.add_subclass(GameClasses.Jeweler)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.jeweler.builder(JewelerAbilities.mind_over_matter).action(inputs.crafting_hotbar.hotkey1).build()
        self.jeweler.builder(JewelerAbilities.focus_of_spirit).action(inputs.crafting_hotbar.hotkey2).build()
        self.jeweler.builder(JewelerAbilities.faceting).action(inputs.crafting_hotbar.hotkey3).build()
        self.jeweler.builder(JewelerAbilities.sixth_sense).action(inputs.crafting_hotbar.hotkey4).build()
        self.jeweler.builder(JewelerAbilities.center_of_spirit).action(inputs.crafting_hotbar.hotkey5).build()
        self.jeweler.builder(JewelerAbilities.round_cut).action(inputs.crafting_hotbar.hotkey6).build()


class ProvisionerClass(CraftsmanClass):
    def __init__(self, class_level: int):
        CraftsmanClass.__init__(self, class_level)
        self.provisioner = self.add_subclass(GameClasses.Provisioner)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.provisioner.builder(ProvisionerAbilities.constant_heat).action(inputs.crafting_hotbar.hotkey1).build()
        self.provisioner.builder(ProvisionerAbilities.seasoning).action(inputs.crafting_hotbar.hotkey2).build()
        self.provisioner.builder(ProvisionerAbilities.awareness).action(inputs.crafting_hotbar.hotkey3).build()
        self.provisioner.builder(ProvisionerAbilities.slow_simmer).action(inputs.crafting_hotbar.hotkey4).build()
        self.provisioner.builder(ProvisionerAbilities.pinch_of_salt).action(inputs.crafting_hotbar.hotkey5).build()
        self.provisioner.builder(ProvisionerAbilities.realization).action(inputs.crafting_hotbar.hotkey6).build()


class CarpenterClass(CraftsmanClass):
    def __init__(self, class_level: int):
        CraftsmanClass.__init__(self, class_level)
        self.carpenter = self.add_subclass(GameClasses.Carpenter)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.carpenter.builder(CarpenterAbilities.tee_joint).action(inputs.crafting_hotbar.hotkey1).build()
        self.carpenter.builder(CarpenterAbilities.concentrate).action(inputs.crafting_hotbar.hotkey2).build()
        self.carpenter.builder(CarpenterAbilities.metallurgy).action(inputs.crafting_hotbar.hotkey3).build()
        self.carpenter.builder(CarpenterAbilities.wedge_joint).action(inputs.crafting_hotbar.hotkey4).build()
        self.carpenter.builder(CarpenterAbilities.ponder).action(inputs.crafting_hotbar.hotkey5).build()
        self.carpenter.builder(CarpenterAbilities.smelting).action(inputs.crafting_hotbar.hotkey6).build()


class WoodworkerClass(CraftsmanClass):
    def __init__(self, class_level: int):
        CraftsmanClass.__init__(self, class_level)
        self.tailor = self.add_subclass(GameClasses.Woodworker)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.tailor.builder(WoodworkerAbilities.carving).action(inputs.crafting_hotbar.hotkey1).build()
        self.tailor.builder(WoodworkerAbilities.measure).action(inputs.crafting_hotbar.hotkey2).build()
        self.tailor.builder(WoodworkerAbilities.handwork).action(inputs.crafting_hotbar.hotkey3).build()
        self.tailor.builder(WoodworkerAbilities.calibrate).action(inputs.crafting_hotbar.hotkey4).build()
        self.tailor.builder(WoodworkerAbilities.chiselling).action(inputs.crafting_hotbar.hotkey5).build()
        self.tailor.builder(WoodworkerAbilities.whittling).action(inputs.crafting_hotbar.hotkey6).build()


class ArmorerClass(OutfitterClass):
    def __init__(self, class_level: int):
        OutfitterClass.__init__(self, class_level)
        self.armorer = self.add_subclass(GameClasses.Armorer)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.armorer.builder(ArmorerAbilities.strikes).action(inputs.crafting_hotbar.hotkey1).build()
        self.armorer.builder(ArmorerAbilities.steady_heat).action(inputs.crafting_hotbar.hotkey2).build()
        self.armorer.builder(ArmorerAbilities.angle_joint).action(inputs.crafting_hotbar.hotkey3).build()
        self.armorer.builder(ArmorerAbilities.hammering).action(inputs.crafting_hotbar.hotkey4).build()
        self.armorer.builder(ArmorerAbilities.stoke_coals).action(inputs.crafting_hotbar.hotkey5).build()
        self.armorer.builder(ArmorerAbilities.bridle_joint).action(inputs.crafting_hotbar.hotkey6).build()


class WeaponsmithClass(OutfitterClass):
    def __init__(self, class_level: int):
        OutfitterClass.__init__(self, class_level)
        self.weaponsmith = self.add_subclass(GameClasses.Weaponsmith)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.weaponsmith.builder(WeaponsmithAbilities.hardening).action(inputs.crafting_hotbar.hotkey1).build()
        self.weaponsmith.builder(WeaponsmithAbilities.tempering).action(inputs.crafting_hotbar.hotkey2).build()
        self.weaponsmith.builder(WeaponsmithAbilities.anneal).action(inputs.crafting_hotbar.hotkey3).build()
        self.weaponsmith.builder(WeaponsmithAbilities.set).action(inputs.crafting_hotbar.hotkey4).build()
        self.weaponsmith.builder(WeaponsmithAbilities.strengthening).action(inputs.crafting_hotbar.hotkey5).build()
        self.weaponsmith.builder(WeaponsmithAbilities.compress).action(inputs.crafting_hotbar.hotkey6).build()


class TailorClass(OutfitterClass):
    def __init__(self, class_level: int):
        OutfitterClass.__init__(self, class_level)
        self.tailor = self.add_subclass(GameClasses.Tailor)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        self.tailor.builder(TailorAbilities.stitching).action(inputs.crafting_hotbar.hotkey1).build()
        self.tailor.builder(TailorAbilities.nimble).action(inputs.crafting_hotbar.hotkey2).build()
        self.tailor.builder(TailorAbilities.knots).action(inputs.crafting_hotbar.hotkey3).build()
        self.tailor.builder(TailorAbilities.hem).action(inputs.crafting_hotbar.hotkey4).build()
        self.tailor.builder(TailorAbilities.dexterous).action(inputs.crafting_hotbar.hotkey5).build()
        self.tailor.builder(TailorAbilities.binding).action(inputs.crafting_hotbar.hotkey6).build()
