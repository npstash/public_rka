from rka.components.ui.capture import MatchPattern
from rka.eq2.configs.shared.game_constants import EQ2_WINDOW_NAME
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability import injection_useability_template, AbilityTier, AbilityPriority
from rka.eq2.master.game.ability.ability_monitors import BulwarkCastingCompletedMonitor
from rka.eq2.master.game.ability.generated_abilities import *
from rka.eq2.master.game.effect.effects import PriestEffects, ShamanEffects, MysticEffects, DefilerEffects, ClericEffects, InquisitorEffects, DruidEffects, \
    WardenEffects, FuryEffects, GeneralEffects, DirgeEffects, TroubadorEffects, BrigandEffects, EnchanterEffects, \
    IllusionistEffects, CoercerEffects, ConjurorEffects, FighterEffects, BrawlerEffects, MonkEffects
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.requesting import RequestEvents
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.gameclass.classes_virtual import PlayerClassBase
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import TellType
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns


class CommonerClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.common = self.add_subclass(GameClasses.Commoner)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        # abstract ability - dummy prototype
        abstract_ability = self.common.builder(CommonerAbilities.abstract_ability)
        abstract_ability.census_data(casting=0.0, reuse=0.0, recovery=0.0).action(action_factory.new_action())
        abstract_ability.build()
        # transmute
        transmute = self.common.builder(CommonerAbilities.transmute)
        if player.is_local():
            transmute.command()
        transmute.build()
        # extract_planar_essence - its not listed in character census (list of abilities)
        extract_planar_essence = self.common.builder(CommonerAbilities.extract_planar_essence)
        extract_planar_essence.tier(AbilityTier.Apprentice)
        if player.is_local():
            extract_planar_essence.command()
        extract_planar_essence.build()
        # call to guild hall. this ability cannot be found in CENSUS
        call_to_guild = self.common.builder(CommonerAbilities.call_to_guild_hall)
        call_to_guild.census_data(casting=10.0, reuse=15 * 60.0, recovery=0.5)
        if player.is_local():
            call_to_guild.non_census_injection_use_ability_str(injection_str=injection_useability_template.format(3266969222))
            call_to_guild.command()
        call_to_guild.build()
        # call to home. CENSUS data for this ability is wrong
        call_to_home = self.common.builder(CommonerAbilities.call_to_home)
        call_to_home.census_data(casting=10.0, reuse=30 * 60.0, recovery=0.5)
        if player.is_local():
            call_to_home_ability_crc = player.get_player_info().home_city.get_call_to_home_ability_crc()
            call_to_home.non_census_injection_use_ability_str(injection_str=injection_useability_template.format(call_to_home_ability_crc))
            call_to_home.command()
        call_to_home.build()
        # get location
        get_loc = self.common.builder(CommonerAbilities.loc)
        get_loc.census_data(casting=0.0, reuse=0.0, recovery=0.0)
        get_loc.non_census_injection_use_ability_str('loc')
        if player.is_local():
            self.common.builder(CommonerAbilities.loc).command()
        get_loc.build()
        # who - zone discovery ability; add window checking to prevent this ability to be clicked when eq2 is not active; must use emote in this case
        who = self.common.builder(CommonerAbilities.who)
        who.census_data(casting=0.0, reuse=20.0, recovery=0.0, duration=0.0)
        who.command()
        if player.is_local():
            who.non_census_injection_use_ability_str('who')
        else:
            who.non_census_injection_use_ability_str('who\ncombat_filter 1')
        tag_match = MatchPattern.by_tag(ui_patterns.PATTERN_BUTTON_EQ2_MENU)
        who.pre_action(action_factory.new_action().window_check(EQ2_WINDOW_NAME).find_capture_match(tag_match))
        who.build()
        # set target
        set_target = self.common.builder(CommonerAbilities.set_target)
        set_target.census_data(casting=0.0, reuse=1.0, recovery=0.0)
        set_target.non_census_injection_use_ability_on_target_builder_fn(lambda target: '\n'.join(['target {}'.format(t) for t in target.split(';')]))
        set_target.target(player)
        set_target.command()
        set_target.build()
        # cancel spellcast
        cancel_spellcast = self.common.builder(CommonerAbilities.cancel_spellcast)
        cancel_spellcast.census_data(casting=0.0, reuse=0.0, recovery=0.5)
        cancel_spellcast.non_census_injection_use_ability_str('cancel_spellcast')
        cancel_spellcast.modify_set('cancel_spellcast', True)
        cancel_spellcast.command()
        cancel_spellcast.build()
        # salve - castable only with Pact of Nature
        salve = self.common.builder(CommonerAbilities.salve)
        salve.tier(AbilityTier.Adept).direct_heal_delay().disabled()
        salve.build()
        # other
        self.common.builder(CommonerAbilities.visions_of_vetrovia_flawless_execution).build()


class PriestClass(CommonerClass):
    def __init__(self, class_level: int):
        CommonerClass.__init__(self, class_level)
        self.priest = self.add_subclass(GameClasses.Priest)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.priest.builder(PriestAbilities.balanced_synergy).build()
        self.priest.builder(PriestAbilities.cloak_of_divinity).build()
        self.priest.builder(PriestAbilities.cure).build()
        self.priest.builder(PriestAbilities.cure_curse).build()
        self.priest.builder(PriestAbilities.divine_providence).build()
        self.priest.builder(PriestAbilities.reprieve).build()
        self.priest.builder(PriestAbilities.smite_of_consistency).build()
        self.priest.builder(PriestAbilities.undaunted).build()
        self.priest.builder(PriestAbilities.wrath).build()
        # modifications
        self.priest.builder(PriestAbilities.cure).cancel_spellcast()
        self.priest.builder(PriestAbilities.cure_curse).cancel_spellcast()
        self.priest.builder(PriestAbilities.balanced_synergy).casting_end_confirm_event(CombatEvents.PLAYER_SYNERGIZED(caster_name=player.get_player_name()))
        self.priest.builder(PriestAbilities.balanced_synergy).expiration_event(CombatEvents.PLAYER_SYNERGY_FADES(caster_name=player.get_player_name()))
        confirm_event = CombatParserEvents.DETRIMENT_RELIEVED(by_combatant=player.get_player_name(), is_curse=True,
                                                              ability_name=PriestAbilities.cure_curse.get_canonical_name())
        self.priest.builder(PriestAbilities.cure_curse).casting_end_confirm_event(confirm_event)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(PriestEffects.MAJESTIC_CASTING(10))


class ShamanClass(PriestClass):
    def __init__(self, class_level: int):
        PriestClass.__init__(self, class_level)
        self.shaman = self.add_subclass(GameClasses.Shaman)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.shaman.builder(ShamanAbilities.ancestral_channeling).build()
        self.shaman.builder(ShamanAbilities.ancestral_palisade).build()
        self.shaman.builder(ShamanAbilities.eidolic_ward).build()
        # self.shaman.builder(ShamanAbilities.malady).build()
        self.shaman.builder(ShamanAbilities.scourge).build()
        self.shaman.builder(ShamanAbilities.soul_shackle).build()
        self.shaman.builder(ShamanAbilities.spirit_aegis).build()
        self.shaman.builder(ShamanAbilities.summon_spirit_companion).build()
        self.shaman.builder(ShamanAbilities.totemic_protection).build()
        self.shaman.builder(ShamanAbilities.umbral_trap).build()
        self.shaman.builder(ShamanAbilities.immunities).build()
        # modifications
        self.shaman.builder(ShamanAbilities.summon_spirit_companion).recast_maintained()
        self.shaman.builder(ShamanAbilities.malady).effect_duration(4.5)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(ShamanEffects.WITCHDOCTORS_HERBAL_RECIPE(8))
        self.class_effects.append(ShamanEffects.ENHANCE_ANCESTRAL_CHANNELING(10))


class MysticClass(ShamanClass):
    def __init__(self, class_level: int):
        ShamanClass.__init__(self, class_level)
        self.mystic = self.add_subclass(GameClasses.Mystic)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.mystic.builder(MysticAbilities.ancestral_avatar).build()
        self.mystic.builder(MysticAbilities.ancestral_balm).build()
        # self.mystic.builder(MysticAbilities.ancestral_bolster).build()
        self.mystic.builder(MysticAbilities.ancestral_savior).build()
        self.mystic.builder(MysticAbilities.ancestral_support).build()
        self.mystic.builder(MysticAbilities.ancestral_ward).build()
        self.mystic.builder(MysticAbilities.ancestry).build()
        self.mystic.builder(MysticAbilities.bolster).build()
        self.mystic.builder(MysticAbilities.chilling_strike).build()
        self.mystic.builder(MysticAbilities.circle_of_the_ancients).build()
        self.mystic.builder(MysticAbilities.ebbing_spirit).build()
        self.mystic.builder(MysticAbilities.echoes_of_the_ancients).build()
        self.mystic.builder(MysticAbilities.haze).build()
        self.mystic.builder(MysticAbilities.immunization).build()
        self.mystic.builder(MysticAbilities.lamenting_soul).build()
        self.mystic.builder(MysticAbilities.lunar_attendant).build()
        self.mystic.builder(MysticAbilities.oberon).build()
        self.mystic.builder(MysticAbilities.plague).build()
        self.mystic.builder(MysticAbilities.polar_fire).build()
        self.mystic.builder(MysticAbilities.premonition).build()
        self.mystic.builder(MysticAbilities.prophetic_ward).build()
        self.mystic.builder(MysticAbilities.rejuvenation).build()
        self.mystic.builder(MysticAbilities.ritual_healing).build()
        self.mystic.builder(MysticAbilities.ritual_of_alacrity).build()
        self.mystic.builder(MysticAbilities.spirit_tap).build()
        self.mystic.builder(MysticAbilities.stampede_of_the_herd).build()
        self.mystic.builder(MysticAbilities.torpor).build()
        self.mystic.builder(MysticAbilities.transcendence).build()
        self.mystic.builder(MysticAbilities.umbral_barrier).build()
        self.mystic.builder(MysticAbilities.wards_of_the_eidolon).build()
        self.mystic.builder(MysticAbilities.runic_armor).build()
        self.mystic.builder(MysticAbilities.strength_of_the_ancestors).build()
        # modifications
        self.mystic.builder(MysticAbilities.ancestral_balm).cancel_spellcast()
        self.mystic.builder(MysticAbilities.transcendence).direct_heal_delay()
        self.mystic.builder(MysticAbilities.wards_of_the_eidolon).census_error('duration', 29.0)
        self.mystic.builder(MysticAbilities.ritual_of_alacrity).effect_builder(MysticEffects.RITUAL_OF_ALACRITY())
        self.mystic.builder(MysticAbilities.strength_of_the_ancestors).effect_builder(MysticEffects.STRENGTH_OF_THE_ANCESTORS())

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(MysticEffects.ENHANCE_BOLSTER(5))
        self.class_effects.append(MysticEffects.FOCUS_BOLSTER())
        self.class_effects.append(MysticEffects.ENHANCE_CURE_CURSE(5))
        self.class_effects.append(MysticEffects.SPIRITUAL_STABILITY())

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.mystic.builder(MysticAbilities.umbral_barrier).action(inputs.hotbar1.hotkey2)
        self.mystic.builder(MysticAbilities.prophetic_ward).action(inputs.hotbar1.hotkey3)
        self.shaman.builder(ShamanAbilities.spirit_aegis).action(inputs.hotbar1.hotkey4)
        self.shaman.builder(ShamanAbilities.ancestral_palisade).action(inputs.hotbar1.hotkey5)
        self.shaman.builder(ShamanAbilities.soul_shackle).action(inputs.hotbar1.hotkey6)
        self.mystic.builder(MysticAbilities.ancestral_support).action(inputs.hotbar1.hotkey7)
        self.shaman.builder(ShamanAbilities.totemic_protection).action(inputs.hotbar1.hotkey8).target(GameClasses.Local)
        self.shaman.builder(ShamanAbilities.ancestral_channeling).action(inputs.hotbar1.hotkey9)
        self.mystic.builder(MysticAbilities.transcendence).action(inputs.hotbar1.hotkey10)
        self.mystic.builder(MysticAbilities.torpor).action(inputs.hotbar1.hotkey11).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cloak_of_divinity).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.mystic.builder(MysticAbilities.ancestral_ward).action(inputs.hotbar2.hotkey1).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.oberon).action(inputs.hotbar2.hotkey2).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.immunization).action(inputs.hotbar2.hotkey3).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ritual_of_alacrity).action(inputs.hotbar2.hotkey4).target(GameClasses.Druid)
        self.shaman.builder(ShamanAbilities.scourge).action(inputs.hotbar2.hotkey5)
        self.mystic.builder(MysticAbilities.echoes_of_the_ancients).action(inputs.hotbar2.hotkey6)
        self.shaman.builder(ShamanAbilities.umbral_trap).action(inputs.hotbar2.hotkey7)
        self.mystic.builder(MysticAbilities.ancestral_savior).action(inputs.hotbar2.hotkey8).target(GameClasses.Local)
        self.shaman.builder(ShamanAbilities.eidolic_ward).action(inputs.hotbar2.hotkey9).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.wards_of_the_eidolon).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.priest.builder(PriestAbilities.cure_curse).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ancestral_balm).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ebbing_spirit).action(inputs.hotbar3.hotkey3)
        self.mystic.builder(MysticAbilities.spirit_tap).action(inputs.hotbar3.hotkey4)
        self.mystic.builder(MysticAbilities.stampede_of_the_herd).action(inputs.hotbar3.hotkey5)
        self.mystic.builder(MysticAbilities.bolster).action(inputs.hotbar3.hotkey6).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ancestral_bolster).action(inputs.hotbar3.hotkey7)
        self.mystic.builder(MysticAbilities.polar_fire).action(inputs.hotbar3.hotkey8)
        self.mystic.builder(MysticAbilities.circle_of_the_ancients).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.shaman.builder(ShamanAbilities.summon_spirit_companion).action(inputs.hotbar5.hotkey7)
        self.mystic.builder(MysticAbilities.ancestry).action(inputs.hotbar5.hotkey8).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.premonition).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ancestral_avatar).action(inputs.hotbar5.hotkey10)
        self.priest.builder(PriestAbilities.reprieve).action(inputs.hotbar5.hotkey11)
        self.priest.builder(PriestAbilities.undaunted).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)
        # not on hotbars
        self.priest.builder(PriestAbilities.cure).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.rejuvenation).target(GameClasses.Local)
        self.mystic.builder(MysticAbilities.ritual_healing).target(GameClasses.Local)


class DefilerClass(ShamanClass):
    def __init__(self, class_level: int):
        ShamanClass.__init__(self, class_level)
        self.defiler = self.add_subclass(GameClasses.Defiler)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.defiler.builder(DefilerAbilities.abhorrent_seal).build()
        self.defiler.builder(DefilerAbilities.abomination).build()
        self.defiler.builder(DefilerAbilities.ancestral_avenger).build()
        self.defiler.builder(DefilerAbilities.ancient_shroud).build()
        self.defiler.builder(DefilerAbilities.bane_of_warding).build()
        self.defiler.builder(DefilerAbilities.cannibalize).build()
        self.defiler.builder(DefilerAbilities.carrion_warding).build()
        self.defiler.builder(DefilerAbilities.death_cries).build()
        self.defiler.builder(DefilerAbilities.harbinger).build()
        self.defiler.builder(DefilerAbilities.hexation).build()
        self.defiler.builder(DefilerAbilities.invective).build()
        self.defiler.builder(DefilerAbilities.maelstrom).build()
        self.defiler.builder(DefilerAbilities.mail_of_souls).build()
        self.defiler.builder(DefilerAbilities.malicious_spirits).build()
        self.defiler.builder(DefilerAbilities.nightmares).build()
        self.defiler.builder(DefilerAbilities.phantasmal_barrier).build()
        self.defiler.builder(DefilerAbilities.purulence).build()
        self.defiler.builder(DefilerAbilities.soul_cannibalize).build()
        self.defiler.builder(DefilerAbilities.spiritual_circle).build()
        self.defiler.builder(DefilerAbilities.tendrils_of_horror).build()
        self.defiler.builder(DefilerAbilities.voice_of_the_ancestors).build()
        self.defiler.builder(DefilerAbilities.wild_accretion).build()
        self.defiler.builder(DefilerAbilities.wraithwall).build()
        # modifications
        self.defiler.builder(DefilerAbilities.phantasmal_barrier).effect_duration(10.0)
        self.defiler.builder(DefilerAbilities.wild_accretion).direct_heal_delay()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(DefilerEffects.ENHANCE_MAELSTROM(5))
        self.class_effects.append(DefilerEffects.ENHANCE_SPIRITIAL_CIRCLE(5))
        self.class_effects.append(DefilerEffects.CURSEWEAVING())
        self.class_effects.append(DefilerEffects.WRAITHWALL(3))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.defiler.builder(DefilerAbilities.carrion_warding).action(inputs.hotbar1.hotkey2)
        self.defiler.builder(DefilerAbilities.phantasmal_barrier).action(inputs.hotbar1.hotkey3)
        self.shaman.builder(ShamanAbilities.spirit_aegis).action(inputs.hotbar1.hotkey4)
        self.shaman.builder(ShamanAbilities.soul_shackle).action(inputs.hotbar1.hotkey5)
        self.shaman.builder(ShamanAbilities.totemic_protection).action(inputs.hotbar1.hotkey6).target(GameClasses.Local)
        self.shaman.builder(ShamanAbilities.ancestral_channeling).action(inputs.hotbar1.hotkey7)
        self.defiler.builder(DefilerAbilities.wild_accretion).action(inputs.hotbar1.hotkey8)
        self.defiler.builder(DefilerAbilities.ancient_shroud).action(inputs.hotbar1.hotkey9).target(player)
        self.defiler.builder(DefilerAbilities.death_cries).action(inputs.hotbar1.hotkey10).target(GameClasses.Local)
        self.defiler.builder(DefilerAbilities.wraithwall).action(inputs.hotbar1.hotkey11).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cloak_of_divinity).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.defiler.builder(DefilerAbilities.malicious_spirits).action(inputs.hotbar2.hotkey1)
        self.defiler.builder(DefilerAbilities.maelstrom).action(inputs.hotbar2.hotkey2)
        self.defiler.builder(DefilerAbilities.nightmares).action(inputs.hotbar2.hotkey3)
        self.defiler.builder(DefilerAbilities.bane_of_warding).action(inputs.hotbar2.hotkey4)
        self.defiler.builder(DefilerAbilities.abhorrent_seal).action(inputs.hotbar2.hotkey5)
        self.defiler.builder(DefilerAbilities.abomination).action(inputs.hotbar2.hotkey6)
        self.defiler.builder(DefilerAbilities.hexation).action(inputs.hotbar2.hotkey7)
        self.defiler.builder(DefilerAbilities.ancestral_avenger).action(inputs.hotbar2.hotkey8).target(player)
        self.shaman.builder(ShamanAbilities.eidolic_ward).action(inputs.hotbar2.hotkey9).target(GameClasses.Local)
        self.defiler.builder(DefilerAbilities.purulence).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.priest.builder(PriestAbilities.cure_curse).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cure).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.defiler.builder(DefilerAbilities.voice_of_the_ancestors).action(inputs.hotbar3.hotkey3)
        self.defiler.builder(DefilerAbilities.mail_of_souls).action(inputs.hotbar3.hotkey4)
        self.defiler.builder(DefilerAbilities.spiritual_circle).action(inputs.hotbar3.hotkey5)
        self.defiler.builder(DefilerAbilities.cannibalize).action(inputs.hotbar3.hotkey6)
        self.defiler.builder(DefilerAbilities.soul_cannibalize).action(inputs.hotbar3.hotkey7)
        ### hotbar 5
        self.shaman.builder(ShamanAbilities.summon_spirit_companion).action(inputs.hotbar5.hotkey7)
        self.defiler.builder(DefilerAbilities.harbinger).action(inputs.hotbar5.hotkey8).target(player)
        self.defiler.builder(DefilerAbilities.invective).action(inputs.hotbar5.hotkey9).target(player)
        self.defiler.builder(DefilerAbilities.tendrils_of_horror).action(inputs.hotbar5.hotkey10).target(player)
        self.priest.builder(PriestAbilities.reprieve).action(inputs.hotbar5.hotkey11)
        self.priest.builder(PriestAbilities.undaunted).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class ClericClass(PriestClass):
    def __init__(self, class_level: int):
        PriestClass.__init__(self, class_level)
        self.cleric = self.add_subclass(GameClasses.Cleric)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.cleric.builder(ClericAbilities.bulwark_of_faith).build()
        self.cleric.builder(ClericAbilities.divine_guidance).build()
        self.cleric.builder(ClericAbilities.divine_waters).build()
        self.cleric.builder(ClericAbilities.equilibrium).build()
        self.cleric.builder(ClericAbilities.immaculate_revival).build()
        self.cleric.builder(ClericAbilities.light_of_devotion).build()
        self.cleric.builder(ClericAbilities.perseverance_of_the_divine).build(optional=True)
        # modifications
        self.cleric.builder(ClericAbilities.light_of_devotion).effect_duration(4.5)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(ClericEffects.ENHANCE_DIVINE_GUIDANCE(10))


class InquisitorClass(ClericClass):
    def __init__(self, class_level):
        ClericClass.__init__(self, class_level)
        self.inquisitor = self.add_subclass(GameClasses.Inquisitor)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.inquisitor.builder(InquisitorAbilities.alleviation).build()
        self.inquisitor.builder(InquisitorAbilities.chilling_invigoration).build()
        self.inquisitor.builder(InquisitorAbilities.cleansing_of_the_soul).build()
        self.inquisitor.builder(InquisitorAbilities.condemn).build()
        self.inquisitor.builder(InquisitorAbilities.deny).build()
        self.inquisitor.builder(InquisitorAbilities.divine_armor).build()
        self.inquisitor.builder(InquisitorAbilities.divine_aura).build()
        # self.inquisitor.builder(InquisitorAbilities.divine_provenance).build()
        # self.inquisitor.builder(InquisitorAbilities.divine_recovery).build()
        self.inquisitor.builder(InquisitorAbilities.divine_righteousness).build()
        self.inquisitor.builder(InquisitorAbilities.evidence_of_faith).build()
        self.inquisitor.builder(InquisitorAbilities.fanatics_inspiration).build()
        self.inquisitor.builder(InquisitorAbilities.fanatics_protection).build()
        self.inquisitor.builder(InquisitorAbilities.fanaticism).build()
        self.inquisitor.builder(InquisitorAbilities.forced_obedience).build()
        self.inquisitor.builder(InquisitorAbilities.heresy).build()
        self.inquisitor.builder(InquisitorAbilities.inquest).build()
        self.inquisitor.builder(InquisitorAbilities.inquisition).build()
        self.inquisitor.builder(InquisitorAbilities.invocation_strike).build()
        self.inquisitor.builder(InquisitorAbilities.litany_circle).build()
        self.inquisitor.builder(InquisitorAbilities.malevolent_diatribe).build()
        self.inquisitor.builder(InquisitorAbilities.penance).build()
        self.inquisitor.builder(InquisitorAbilities.redemption).build()
        self.inquisitor.builder(InquisitorAbilities.repentance).build()
        self.inquisitor.builder(InquisitorAbilities.resolute_flagellant).build()
        self.inquisitor.builder(InquisitorAbilities.strike_of_flames).build()
        self.inquisitor.builder(InquisitorAbilities.tenacity).build()
        self.inquisitor.builder(InquisitorAbilities.vengeance).build()
        self.inquisitor.builder(InquisitorAbilities.verdict).build()
        # modifications
        self.inquisitor.builder(InquisitorAbilities.malevolent_diatribe).untracked_triggers(6.0)
        self.inquisitor.builder(InquisitorAbilities.alleviation).direct_heal_delay()
        self.inquisitor.builder(InquisitorAbilities.evidence_of_faith).untracked_triggers(6.0)
        self.inquisitor.builder(InquisitorAbilities.fanatics_protection).untracked_triggers(15.0)
        self.inquisitor.builder(InquisitorAbilities.chilling_invigoration).untracked_triggers(10.0)
        self.inquisitor.builder(InquisitorAbilities.penance).untracked_triggers(6.0)
        self.inquisitor.builder(InquisitorAbilities.fanatics_inspiration).untracked_triggers(3.0)
        self.inquisitor.builder(InquisitorAbilities.verdict).tier(AbilityTier.Grandmaster)  # Ancient not in census
        self.inquisitor.builder(InquisitorAbilities.fanaticism).recast_maintained()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(InquisitorEffects.FANATICS_PROTECTION(3))
        self.class_effects.append(InquisitorEffects.ENHANCE_REDEMPTION(5))
        self.class_effects.append(InquisitorEffects.FANATICS_FOCUS())

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.cleric.builder(ClericAbilities.divine_guidance).action(inputs.hotbar1.hotkey2)
        self.cleric.builder(ClericAbilities.divine_waters).action(inputs.hotbar1.hotkey3)
        self.inquisitor.builder(InquisitorAbilities.inquisition).action(inputs.hotbar1.hotkey4)
        self.inquisitor.builder(InquisitorAbilities.malevolent_diatribe).action(inputs.hotbar1.hotkey5)
        self.inquisitor.builder(InquisitorAbilities.alleviation).action(inputs.hotbar1.hotkey6)
        self.cleric.builder(ClericAbilities.bulwark_of_faith).action(inputs.hotbar1.hotkey7)
        self.inquisitor.builder(InquisitorAbilities.fanatics_protection).action(inputs.hotbar1.hotkey8).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.fanatics_inspiration).action(inputs.hotbar1.hotkey9).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.penance).action(inputs.hotbar1.hotkey10).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.chilling_invigoration).action(inputs.hotbar1.hotkey11).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cloak_of_divinity).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.inquisitor.builder(InquisitorAbilities.heresy).action(inputs.hotbar2.hotkey1)
        self.inquisitor.builder(InquisitorAbilities.forced_obedience).action(inputs.hotbar2.hotkey2)
        self.inquisitor.builder(InquisitorAbilities.verdict).action(inputs.hotbar2.hotkey3)
        self.inquisitor.builder(InquisitorAbilities.divine_provenance).action(inputs.hotbar2.hotkey4)
        self.inquisitor.builder(InquisitorAbilities.evidence_of_faith).action(inputs.hotbar2.hotkey5)
        self.cleric.builder(ClericAbilities.perseverance_of_the_divine).action(inputs.hotbar2.hotkey6).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.redemption).action(inputs.hotbar2.hotkey7).target(GameClasses.Local)
        self.cleric.builder(ClericAbilities.immaculate_revival).action(inputs.hotbar2.hotkey8)
        self.cleric.builder(ClericAbilities.equilibrium).action(inputs.hotbar2.hotkey9)
        self.inquisitor.builder(InquisitorAbilities.divine_aura).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.priest.builder(PriestAbilities.cure_curse).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cure).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.cleansing_of_the_soul).action(inputs.hotbar3.hotkey3)
        self.inquisitor.builder(InquisitorAbilities.resolute_flagellant).action(inputs.hotbar3.hotkey4)
        self.inquisitor.builder(InquisitorAbilities.divine_righteousness).action(inputs.hotbar3.hotkey5)
        self.inquisitor.builder(InquisitorAbilities.condemn).action(inputs.hotbar3.hotkey6)
        self.inquisitor.builder(InquisitorAbilities.deny).action(inputs.hotbar3.hotkey7)
        self.inquisitor.builder(InquisitorAbilities.strike_of_flames).action(inputs.hotbar3.hotkey8)
        self.inquisitor.builder(InquisitorAbilities.invocation_strike).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.inquisitor.builder(InquisitorAbilities.divine_armor).action(inputs.hotbar5.hotkey7).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.inquest).action(inputs.hotbar5.hotkey8).target(GameClasses.Local)
        self.inquisitor.builder(InquisitorAbilities.tenacity).action(inputs.hotbar5.hotkey9)
        self.inquisitor.builder(InquisitorAbilities.fanaticism).action(inputs.hotbar5.hotkey10)
        self.priest.builder(PriestAbilities.reprieve).action(inputs.hotbar5.hotkey11)
        self.priest.builder(PriestAbilities.undaunted).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class DruidClass(PriestClass):
    def __init__(self, class_level: int):
        PriestClass.__init__(self, class_level)
        self.druid = self.add_subclass(GameClasses.Druid)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.druid.builder(DruidAbilities.howling_with_the_pack).build()
        self.druid.builder(DruidAbilities.rage_of_the_wild).build()
        self.druid.builder(DruidAbilities.rebirth).build()
        self.druid.builder(DruidAbilities.serene_symbol).build()
        self.druid.builder(DruidAbilities.serenity).build()
        self.druid.builder(DruidAbilities.spirit_of_the_bat).build()
        self.druid.builder(DruidAbilities.sylvan_touch).build()
        # self.druid.builder(DruidAbilities.thunderspike).build()
        # self.druid.builder(DruidAbilities.tortoise_shell).build()
        self.druid.builder(DruidAbilities.tunares_grace).build()
        self.druid.builder(DruidAbilities.woodward).build()
        self.druid.builder(DruidAbilities.wrath_of_nature).build()
        # modifications
        self.druid.builder(DruidAbilities.rage_of_the_wild).direct_heal_delay()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class WardenClass(DruidClass):
    def __init__(self, class_level):
        DruidClass.__init__(self, class_level)
        self.warden = self.add_subclass(GameClasses.Warden)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.warden.builder(WardenAbilities.aspect_of_the_forest).build()
        self.warden.builder(WardenAbilities.clearwater_current).build()
        self.warden.builder(WardenAbilities.cyclone).build()
        self.warden.builder(WardenAbilities.frostbite).build()
        self.warden.builder(WardenAbilities.frostbite_slice).build()
        self.warden.builder(WardenAbilities.healing_grove).build()
        self.warden.builder(WardenAbilities.healstorm).build()
        self.warden.builder(WardenAbilities.hierophantic_genesis).build()
        self.warden.builder(WardenAbilities.icefall).build()
        self.warden.builder(WardenAbilities.infuriating_thorns).build()
        self.warden.builder(WardenAbilities.instinct).build()
        self.warden.builder(WardenAbilities.natures_embrace).build()
        self.warden.builder(WardenAbilities.natures_renewal).build()
        self.warden.builder(WardenAbilities.photosynthesis).build()
        self.warden.builder(WardenAbilities.regenerating_spores).build()
        self.warden.builder(WardenAbilities.sandstorm).build()
        self.warden.builder(WardenAbilities.shatter_infections).build()
        self.warden.builder(WardenAbilities.spirit_of_the_wolf).build()
        # self.warden.builder(WardenAbilities.storm_of_shale).build()
        self.warden.builder(WardenAbilities.sylvan_bloom).build()
        self.warden.builder(WardenAbilities.sylvan_embrace).build()
        self.warden.builder(WardenAbilities.thorncoat).build()
        self.warden.builder(WardenAbilities.tunares_chosen).build()
        self.warden.builder(WardenAbilities.tunares_watch).build()
        self.warden.builder(WardenAbilities.verdant_whisper).build()
        self.warden.builder(WardenAbilities.ward_of_the_untamed).build()
        self.warden.builder(WardenAbilities.whirl_of_permafrost).build()
        self.warden.builder(WardenAbilities.winds_of_growth).build()
        self.warden.builder(WardenAbilities.winds_of_healing).build()
        self.warden.builder(WardenAbilities.winds_of_permafrost).build()
        # modifications
        self.warden.builder(WardenAbilities.winds_of_growth).effect_duration(8.0)
        self.warden.builder(WardenAbilities.clearwater_current).effect_duration(24.0)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(DruidEffects.WILD_REGENERATION(10))
        self.class_effects.append(WardenEffects.ENHANCE_CURE_CURSE(5))
        self.class_effects.append(WardenEffects.ENHANCE_HEALING_GROVE(5))
        self.class_effects.append(WardenEffects.ENHANCE_DEATH_INTERVENTIONS(5))
        self.class_effects.append(WardenEffects.CLEARWATER_CURRENT(3))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.warden.builder(WardenAbilities.winds_of_healing).action(inputs.hotbar1.hotkey2)
        self.warden.builder(WardenAbilities.healstorm).action(inputs.hotbar1.hotkey3)
        self.warden.builder(WardenAbilities.winds_of_growth).action(inputs.hotbar1.hotkey4)
        self.warden.builder(WardenAbilities.photosynthesis).action(inputs.hotbar1.hotkey5).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.clearwater_current).action(inputs.hotbar1.hotkey6).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.ward_of_the_untamed).action(inputs.hotbar1.hotkey7)
        self.druid.builder(DruidAbilities.tortoise_shell).action(inputs.hotbar1.hotkey8)
        self.warden.builder(WardenAbilities.sandstorm).action(inputs.hotbar1.hotkey9)
        self.druid.builder(DruidAbilities.howling_with_the_pack).action(inputs.hotbar1.hotkey10)
        self.druid.builder(DruidAbilities.serenity).action(inputs.hotbar1.hotkey11)
        self.priest.builder(PriestAbilities.cloak_of_divinity).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.warden.builder(WardenAbilities.infuriating_thorns).action(inputs.hotbar2.hotkey1).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.hierophantic_genesis).action(inputs.hotbar2.hotkey2).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.healing_grove).action(inputs.hotbar2.hotkey3)
        self.warden.builder(WardenAbilities.storm_of_shale).action(inputs.hotbar2.hotkey4)
        self.druid.builder(DruidAbilities.serene_symbol).action(inputs.hotbar2.hotkey5)
        self.warden.builder(WardenAbilities.natures_renewal).action(inputs.hotbar2.hotkey6).target(player)
        self.warden.builder(WardenAbilities.tunares_watch).action(inputs.hotbar2.hotkey7)
        self.druid.builder(DruidAbilities.sylvan_touch).action(inputs.hotbar2.hotkey8).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.sylvan_embrace).action(inputs.hotbar2.hotkey9)
        self.warden.builder(WardenAbilities.cyclone).action(inputs.hotbar2.hotkey10).target(GameClasses.Local)
        ### hotbar 3
        self.priest.builder(PriestAbilities.cure_curse).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cure).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.druid.builder(DruidAbilities.tunares_grace).action(inputs.hotbar3.hotkey3)
        self.warden.builder(WardenAbilities.verdant_whisper).action(inputs.hotbar3.hotkey4)
        self.warden.builder(WardenAbilities.shatter_infections).action(inputs.hotbar3.hotkey5)
        self.druid.builder(DruidAbilities.rebirth).action(inputs.hotbar3.hotkey6)
        ### hotbar 5
        self.warden.builder(WardenAbilities.tunares_chosen).action(inputs.hotbar5.hotkey5)
        self.warden.builder(WardenAbilities.thorncoat).action(inputs.hotbar5.hotkey6).target(GameClasses.Local)
        self.druid.builder(DruidAbilities.spirit_of_the_bat).action(inputs.hotbar5.hotkey7).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.aspect_of_the_forest).action(inputs.hotbar5.hotkey8).target(GameClasses.Local)
        self.warden.builder(WardenAbilities.regenerating_spores).action(inputs.hotbar5.hotkey9).target(player)
        self.warden.builder(WardenAbilities.instinct).action(inputs.hotbar5.hotkey10)
        self.priest.builder(PriestAbilities.reprieve).action(inputs.hotbar5.hotkey11)
        self.priest.builder(PriestAbilities.undaunted).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class FuryClass(DruidClass):
    def __init__(self, class_level):
        DruidClass.__init__(self, class_level)
        self.fury = self.add_subclass(GameClasses.Fury)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.fury.builder(FuryAbilities.abolishment).build()
        self.fury.builder(FuryAbilities.animal_form).build()
        self.fury.builder(FuryAbilities.autumns_kiss).build()
        self.fury.builder(FuryAbilities.death_swarm).build()
        self.fury.builder(FuryAbilities.devour).build()
        self.fury.builder(FuryAbilities.embodiment_of_nature).build()
        self.fury.builder(FuryAbilities.energy_vortex).build()
        self.fury.builder(FuryAbilities.fae_fire).build()
        self.fury.builder(FuryAbilities.feral_pulse).build()
        self.fury.builder(FuryAbilities.feral_tenacity).build()
        self.fury.builder(FuryAbilities.force_of_nature).build()
        self.fury.builder(FuryAbilities.heart_of_the_storm).build()
        self.fury.builder(FuryAbilities.hibernation).build()
        self.fury.builder(FuryAbilities.intimidation).build()
        self.fury.builder(FuryAbilities.lucidity).build()
        self.fury.builder(FuryAbilities.maddening_swarm).build()
        self.fury.builder(FuryAbilities.natural_cleanse).build()
        self.fury.builder(FuryAbilities.natural_regeneration).build()
        self.fury.builder(FuryAbilities.natures_elixir).build()
        self.fury.builder(FuryAbilities.natures_salve).build()
        self.fury.builder(FuryAbilities.pact_of_nature).build()
        self.fury.builder(FuryAbilities.pact_of_the_cheetah).build()
        self.fury.builder(FuryAbilities.porcupine).build()
        self.fury.builder(FuryAbilities.primal_fury).build()
        self.fury.builder(FuryAbilities.raging_whirlwind).build()
        self.fury.builder(FuryAbilities.regrowth).build()
        self.fury.builder(FuryAbilities.ring_of_fire).build()
        self.fury.builder(FuryAbilities.starnova).build()
        self.fury.builder(FuryAbilities.stormbearers_fury).build()
        self.fury.builder(FuryAbilities.thornskin).build()
        self.fury.builder(FuryAbilities.thunderbolt).build()
        self.fury.builder(FuryAbilities.untamed_regeneration).build()
        self.fury.builder(FuryAbilities.wraths_blessing).build()
        self.fury.builder(FuryAbilities.vortex_of_nature).build()
        # modifications
        self.fury.builder(FuryAbilities.porcupine).untracked_triggers(10.0)
        self.druid.builder(DruidAbilities.sylvan_touch).effect_builder(FuryEffects.OVERGROWING_SPINES_2())
        self.fury.builder(FuryAbilities.pact_of_nature).effect_builder(FuryEffects.PACT_OF_NATURE())

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(DruidEffects.PURE_SERENITY(8))
        self.class_effects.append(FuryEffects.ENHANCE_DEATH_SWARM(5))
        self.class_effects.append(FuryEffects.ENHANCE_FERAL_TENACITY(5))
        self.class_effects.append(FuryEffects.ENHANCE_PACT_OF_THE_CHEETAH(5))
        self.class_effects.append(FuryEffects.ENHANCE_TEMPEST(5))
        self.class_effects.append(FuryEffects.STORMBEARERS_FURY(3))
        self.class_effects.append(FuryEffects.FOCUS_HIBERNATION())

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.druid.builder(DruidAbilities.woodward).action(inputs.hotbar1.hotkey2)
        self.fury.builder(FuryAbilities.autumns_kiss).action(inputs.hotbar1.hotkey3)
        self.fury.builder(FuryAbilities.untamed_regeneration).action(inputs.hotbar1.hotkey4)
        self.fury.builder(FuryAbilities.hibernation).action(inputs.hotbar1.hotkey5)
        self.fury.builder(FuryAbilities.regrowth).action(inputs.hotbar1.hotkey6).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.porcupine).action(inputs.hotbar1.hotkey7)
        self.fury.builder(FuryAbilities.fae_fire).action(inputs.hotbar1.hotkey8)
        self.fury.builder(FuryAbilities.energy_vortex).action(inputs.hotbar1.hotkey9)
        self.druid.builder(DruidAbilities.serenity).action(inputs.hotbar1.hotkey10)
        self.druid.builder(DruidAbilities.howling_with_the_pack).action(inputs.hotbar1.hotkey11)
        self.priest.builder(PriestAbilities.cloak_of_divinity).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.druid.builder(DruidAbilities.serene_symbol).action(inputs.hotbar2.hotkey1)
        self.fury.builder(FuryAbilities.maddening_swarm).action(inputs.hotbar2.hotkey2)
        self.fury.builder(FuryAbilities.death_swarm).action(inputs.hotbar2.hotkey3)
        self.fury.builder(FuryAbilities.intimidation).action(inputs.hotbar2.hotkey4)
        self.fury.builder(FuryAbilities.devour).action(inputs.hotbar2.hotkey5)
        self.fury.builder(FuryAbilities.natural_regeneration).action(inputs.hotbar2.hotkey6).target(GameClasses.Local)
        self.druid.builder(DruidAbilities.sylvan_touch).action(inputs.hotbar2.hotkey7).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.feral_tenacity).action(inputs.hotbar2.hotkey8).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.feral_pulse).action(inputs.hotbar2.hotkey9)
        self.fury.builder(FuryAbilities.pact_of_the_cheetah).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.priest.builder(PriestAbilities.cure_curse).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.priest.builder(PriestAbilities.cure).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.abolishment).action(inputs.hotbar3.hotkey3)
        self.druid.builder(DruidAbilities.tunares_grace).action(inputs.hotbar3.hotkey4)
        self.fury.builder(FuryAbilities.natural_cleanse).action(inputs.hotbar3.hotkey5)
        self.fury.builder(FuryAbilities.stormbearers_fury).action(inputs.hotbar3.hotkey6)
        self.fury.builder(FuryAbilities.raging_whirlwind).action(inputs.hotbar3.hotkey7)
        self.druid.builder(DruidAbilities.wrath_of_nature).action(inputs.hotbar3.hotkey8)
        self.druid.builder(DruidAbilities.rebirth).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.fury.builder(FuryAbilities.thornskin).action(inputs.hotbar5.hotkey4).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.wraths_blessing).action(inputs.hotbar5.hotkey5).target(GameClasses.Shaman)
        self.fury.builder(FuryAbilities.pact_of_nature).action(inputs.hotbar5.hotkey6).target(GameClasses.Dirge)
        self.druid.builder(DruidAbilities.spirit_of_the_bat).action(inputs.hotbar5.hotkey7).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.force_of_nature).action(inputs.hotbar5.hotkey8).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.lucidity).action(inputs.hotbar5.hotkey9).target([GameClasses.Local, player])
        self.fury.builder(FuryAbilities.primal_fury).action(inputs.hotbar5.hotkey10)
        self.priest.builder(PriestAbilities.reprieve).action(inputs.hotbar5.hotkey11)
        self.priest.builder(PriestAbilities.undaunted).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)
        ### not on hotbars
        self.fury.builder(FuryAbilities.animal_form).target(GameClasses.Mage)
        self.fury.builder(FuryAbilities.natures_elixir).target(GameClasses.Local)
        self.fury.builder(FuryAbilities.natures_salve).target(GameClasses.Local)


class ScoutClass(CommonerClass):
    def __init__(self, class_level: int):
        CommonerClass.__init__(self, class_level)
        self.scout = self.add_subclass(GameClasses.Scout)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.scout.builder(ScoutAbilities.balanced_synergy).build()
        self.scout.builder(ScoutAbilities.cheap_shot).build()
        self.scout.builder(ScoutAbilities.dagger_storm).build()
        self.scout.builder(ScoutAbilities.dozekars_resilience).build()
        self.scout.builder(ScoutAbilities.evade).build()
        self.scout.builder(ScoutAbilities.lucky_break).build()
        self.scout.builder(ScoutAbilities.persistence).build()
        self.scout.builder(ScoutAbilities.strike_of_consistency).build()
        # self.scout.builder(ScoutAbilities.trick_of_the_hunter).build()
        # modifications
        self.scout.builder(ScoutAbilities.balanced_synergy).casting_end_confirm_event(CombatEvents.PLAYER_SYNERGIZED(caster_name=player.get_player_name()))
        self.scout.builder(ScoutAbilities.balanced_synergy).expiration_event(CombatEvents.PLAYER_SYNERGY_FADES(caster_name=player.get_player_name()))

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class PredatorClass(ScoutClass):
    def __init__(self, class_level: int):
        ScoutClass.__init__(self, class_level)
        self.predator = self.add_subclass(GameClasses.Predator)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class BardClass(ScoutClass):
    def __init__(self, class_level: int):
        ScoutClass.__init__(self, class_level)
        self.bard = self.add_subclass(GameClasses.Bard)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.bard.builder(BardAbilities.bladedance).build()
        self.bard.builder(BardAbilities.deadly_dance).build()
        self.bard.builder(BardAbilities.disheartening_descant).build()
        self.bard.builder(BardAbilities.dodge_and_cover).build(optional=True)
        # self.bard.builder(BardAbilities.hungering_lyric).build()
        self.bard.builder(BardAbilities.melody_of_affliction).build()
        self.bard.builder(BardAbilities.quick_tempo).build()
        self.bard.builder(BardAbilities.requiem).build()
        self.bard.builder(BardAbilities.shroud).build()
        self.bard.builder(BardAbilities.song_of_shielding).build(optional=True)
        self.bard.builder(BardAbilities.songspinners_note).build(optional=True)
        self.bard.builder(BardAbilities.veil_of_notes).build()
        self.bard.builder(BardAbilities.zanders_choral_rebuff).build()
        self.bard.builder(BardAbilities.brias_inspiring_ballad).build()
        # modifications
        self.bard.builder(BardAbilities.songspinners_note).effect_duration(60.0)
        self.bard.builder(BardAbilities.shroud).effect_builder(GeneralEffects.STEALTH())
        self.bard.builder(BardAbilities.dodge_and_cover).effect_duration(15.0)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class DirgeClass(BardClass):
    def __init__(self, class_level: int):
        BardClass.__init__(self, class_level)
        self.dirge = self.add_subclass(GameClasses.Dirge)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.dirge.builder(DirgeAbilities.anthem_of_war).build()
        self.dirge.builder(DirgeAbilities.battle_cry).build()
        self.dirge.builder(DirgeAbilities.cacophony_of_blades).build()
        self.dirge.builder(DirgeAbilities.claras_chaotic_cacophony).build()
        self.dirge.builder(DirgeAbilities.confront_fear).build()
        self.dirge.builder(DirgeAbilities.darksong_spin).build()
        self.dirge.builder(DirgeAbilities.daros_sorrowful_dirge).build()
        self.dirge.builder(DirgeAbilities.dirges_refrain).build()
        self.dirge.builder(DirgeAbilities.echoing_howl).build()
        self.dirge.builder(DirgeAbilities.exuberant_encore).build()
        # self.dirge.builder(DirgeAbilities.gravitas).build()
        self.dirge.builder(DirgeAbilities.howl_of_death).build()
        self.dirge.builder(DirgeAbilities.hymn_of_horror).build()
        self.dirge.builder(DirgeAbilities.hyrans_seething_sonata).build()
        self.dirge.builder(DirgeAbilities.jarols_sorrowful_requiem).build()
        self.dirge.builder(DirgeAbilities.lanets_excruciating_scream).build()
        self.dirge.builder(DirgeAbilities.ludas_nefarious_wail).build()
        self.dirge.builder(DirgeAbilities.magnetic_note).build()
        self.dirge.builder(DirgeAbilities.oration_of_sacrifice).build()
        self.dirge.builder(DirgeAbilities.peal_of_battle).build()
        self.dirge.builder(DirgeAbilities.sonic_barrier).build()
        self.dirge.builder(DirgeAbilities.support).build()
        self.dirge.builder(DirgeAbilities.tarvens_crippling_crescendo).build()
        self.dirge.builder(DirgeAbilities.thuris_doleful_thrust).build()
        self.dirge.builder(DirgeAbilities.verliens_keen_of_despair).build()
        self.dirge.builder(DirgeAbilities.percussion_of_stone).build()
        self.dirge.builder(DirgeAbilities.rianas_relentless_tune).build()
        self.dirge.builder(DirgeAbilities.luck_of_the_dirge).build()
        self.dirge.builder(DirgeAbilities.harls_rousing_tune).build()
        self.dirge.builder(DirgeAbilities.anthem_of_battle).build()
        self.dirge.builder(DirgeAbilities.jaels_mysterious_mettle).build()
        # modifications
        self.dirge.builder(DirgeAbilities.support).census_data(casting=2.0, reuse=3.0, recovery=1.0, beneficial=False)
        self.dirge.builder(DirgeAbilities.magnetic_note).effect_duration(6.0)
        self.dirge.builder(DirgeAbilities.battle_cry).recast_maintained()
        self.bard.builder(BardAbilities.zanders_choral_rebuff).modify_set('priority', AbilityPriority.MAJOR_DEBUFF)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(DirgeEffects.UNSTOPPING_ENCORE(3))
        self.class_effects.append(DirgeEffects.ECHOING_HOWL(3))
        self.class_effects.append(DirgeEffects.ENHANCE_CACOPHONY_OF_BLADES(5))
        self.class_effects.append(DirgeEffects.ENHANCE_ORATION_OF_SACRIFICE(5))
        self.class_effects.append(DirgeEffects.ENHANCE_SHROUD(5))
        self.class_effects.append(DirgeEffects.CONTROLLING_CONFRONTATIONS(5))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.dirge.builder(DirgeAbilities.support).action(inputs.hotbar1.hotkey2)
        self.scout.builder(ScoutAbilities.dagger_storm).action(inputs.hotbar1.hotkey3)
        self.dirge.builder(DirgeAbilities.darksong_spin).action(inputs.hotbar1.hotkey4)
        self.dirge.builder(DirgeAbilities.hymn_of_horror).action(inputs.hotbar1.hotkey5)
        self.dirge.builder(DirgeAbilities.echoing_howl).action(inputs.hotbar1.hotkey6)
        self.bard.builder(BardAbilities.melody_of_affliction).action(inputs.hotbar1.hotkey7)
        self.bard.builder(BardAbilities.requiem).action(inputs.hotbar1.hotkey8)
        self.dirge.builder(DirgeAbilities.anthem_of_war).action(inputs.hotbar1.hotkey9)
        self.dirge.builder(DirgeAbilities.lanets_excruciating_scream).action(inputs.hotbar1.hotkey10)
        self.dirge.builder(DirgeAbilities.verliens_keen_of_despair).action(inputs.hotbar1.hotkey11)
        self.dirge.builder(DirgeAbilities.tarvens_crippling_crescendo).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.dirge.builder(DirgeAbilities.daros_sorrowful_dirge).action(inputs.hotbar2.hotkey1)
        self.dirge.builder(DirgeAbilities.claras_chaotic_cacophony).action(inputs.hotbar2.hotkey2)
        self.bard.builder(BardAbilities.zanders_choral_rebuff).action(inputs.hotbar2.hotkey3)
        self.bard.builder(BardAbilities.disheartening_descant).action(inputs.hotbar2.hotkey4)
        self.dirge.builder(DirgeAbilities.peal_of_battle).action(inputs.hotbar2.hotkey5)
        self.dirge.builder(DirgeAbilities.magnetic_note).action(inputs.hotbar2.hotkey6).target(GameClasses.Local)
        self.dirge.builder(DirgeAbilities.sonic_barrier).action(inputs.hotbar2.hotkey7).target(GameClasses.Local)
        self.dirge.builder(DirgeAbilities.oration_of_sacrifice).action(inputs.hotbar2.hotkey8).target(GameClasses.Local)
        self.bard.builder(BardAbilities.bladedance).action(inputs.hotbar2.hotkey9)
        self.bard.builder(BardAbilities.veil_of_notes).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.dirge.builder(DirgeAbilities.exuberant_encore).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.bard.builder(BardAbilities.quick_tempo).action(inputs.hotbar3.hotkey2)
        self.bard.builder(BardAbilities.deadly_dance).action(inputs.hotbar3.hotkey3)
        self.bard.builder(BardAbilities.songspinners_note).action(inputs.hotbar3.hotkey4)
        self.dirge.builder(DirgeAbilities.confront_fear).action(inputs.hotbar3.hotkey5).target([GameClasses.Local, GameClasses.Druid])
        self.dirge.builder(DirgeAbilities.thuris_doleful_thrust).action(inputs.hotbar3.hotkey6)
        self.dirge.builder(DirgeAbilities.howl_of_death).action(inputs.hotbar3.hotkey7)
        ### hotbar 5
        self.dirge.builder(DirgeAbilities.dirges_refrain).action(inputs.hotbar5.hotkey8)
        self.dirge.builder(DirgeAbilities.hyrans_seething_sonata).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.dirge.builder(DirgeAbilities.battle_cry).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.scout.builder(ScoutAbilities.dozekars_resilience).action(inputs.hotbar5.hotkey11)
        self.scout.builder(ScoutAbilities.persistence).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class TroubadorClass(BardClass):
    def __init__(self, class_level: int):
        BardClass.__init__(self, class_level)
        self.troubador = self.add_subclass(GameClasses.Troubador)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.troubador.builder(TroubadorAbilities.abhorrent_verse).build()
        self.troubador.builder(TroubadorAbilities.bagpipe_solo).build()
        self.troubador.builder(TroubadorAbilities.breathtaking_bellow).build()
        self.troubador.builder(TroubadorAbilities.ceremonial_blade).build()
        self.troubador.builder(TroubadorAbilities.chaos_anthem).build()
        self.troubador.builder(TroubadorAbilities.countersong).build()
        self.troubador.builder(TroubadorAbilities.dancing_blade).build()
        self.troubador.builder(TroubadorAbilities.demoralizing_processional).build()
        self.troubador.builder(TroubadorAbilities.depressing_chant).build()
        self.troubador.builder(TroubadorAbilities.discordant_verse).build()
        self.troubador.builder(TroubadorAbilities.energizing_ballad).build()
        self.troubador.builder(TroubadorAbilities.jesters_cap).build()
        self.troubador.builder(TroubadorAbilities.lullaby).build()
        # self.troubador.builder(TroubadorAbilities.maelstrom_of_sound).build()
        # self.troubador.builder(TroubadorAbilities.maestros_harmony).build()
        self.troubador.builder(TroubadorAbilities.painful_lamentations).build()
        self.troubador.builder(TroubadorAbilities.perfect_shrill).build()
        self.troubador.builder(TroubadorAbilities.perfection_of_the_maestro).build()
        self.troubador.builder(TroubadorAbilities.reverberation).build()
        self.troubador.builder(TroubadorAbilities.sandras_deafening_strike).build()
        self.troubador.builder(TroubadorAbilities.singing_shot).build()
        self.troubador.builder(TroubadorAbilities.sonic_interference).build()
        self.troubador.builder(TroubadorAbilities.support).build()
        self.troubador.builder(TroubadorAbilities.tap_essence).build()
        self.troubador.builder(TroubadorAbilities.thunderous_overture).build()
        self.troubador.builder(TroubadorAbilities.upbeat_tempo).build()
        self.troubador.builder(TroubadorAbilities.vexing_verses).build()
        self.troubador.builder(TroubadorAbilities.resonance).build()
        self.troubador.builder(TroubadorAbilities.impassioned_rousing).build()
        self.troubador.builder(TroubadorAbilities.raxxyls_rousing_tune).build()
        self.troubador.builder(TroubadorAbilities.aria_of_magic).build()
        self.troubador.builder(TroubadorAbilities.allegretto).build()
        # modifications
        self.troubador.builder(TroubadorAbilities.support).census_data(casting=2.5, reuse=4.0, recovery=1.0, beneficial=False)
        self.troubador.builder(TroubadorAbilities.lullaby).census_error('duration', 36.0)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        # self.class_effects.append(BardEffects.IMPROVED_REFLEXES(8))
        self.class_effects.append(TroubadorEffects.CONTINUED_PERFORMANCE(3))
        self.class_effects.append(TroubadorEffects.REVERBERATION(3))
        self.class_effects.append(TroubadorEffects.ENHANCE_CHEAP_SHOT(5))
        self.class_effects.append(TroubadorEffects.ENHANCE_SINGING_SHOT(5))
        self.class_effects.append(TroubadorEffects.ENHANCE_PERFECTION_OF_THE_MAESTRO(5))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.troubador.builder(TroubadorAbilities.support).action(inputs.hotbar1.hotkey2)
        self.scout.builder(ScoutAbilities.dagger_storm).action(inputs.hotbar1.hotkey3)
        self.troubador.builder(TroubadorAbilities.reverberation).action(inputs.hotbar1.hotkey4)
        self.troubador.builder(TroubadorAbilities.thunderous_overture).action(inputs.hotbar1.hotkey5)
        self.bard.builder(BardAbilities.melody_of_affliction).action(inputs.hotbar1.hotkey6)
        self.bard.builder(BardAbilities.requiem).action(inputs.hotbar1.hotkey7)
        self.troubador.builder(TroubadorAbilities.abhorrent_verse).action(inputs.hotbar1.hotkey8).target(GameClasses.Local)
        self.troubador.builder(TroubadorAbilities.perfection_of_the_maestro).action(inputs.hotbar1.hotkey9)
        self.troubador.builder(TroubadorAbilities.breathtaking_bellow).action(inputs.hotbar1.hotkey10)
        self.troubador.builder(TroubadorAbilities.tap_essence).action(inputs.hotbar1.hotkey11)
        self.troubador.builder(TroubadorAbilities.dancing_blade).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.troubador.builder(TroubadorAbilities.chaos_anthem).action(inputs.hotbar2.hotkey1)
        self.troubador.builder(TroubadorAbilities.demoralizing_processional).action(inputs.hotbar2.hotkey2)
        self.troubador.builder(TroubadorAbilities.sonic_interference).action(inputs.hotbar2.hotkey3)
        self.bard.builder(BardAbilities.zanders_choral_rebuff).action(inputs.hotbar2.hotkey4)
        self.bard.builder(BardAbilities.disheartening_descant).action(inputs.hotbar2.hotkey5)
        self.troubador.builder(TroubadorAbilities.jesters_cap).action(inputs.hotbar2.hotkey6).target([GameClasses.Local, GameClasses.Druid])
        self.bard.builder(BardAbilities.dodge_and_cover).action(inputs.hotbar2.hotkey7)
        self.troubador.builder(TroubadorAbilities.countersong).action(inputs.hotbar2.hotkey8)
        self.bard.builder(BardAbilities.bladedance).action(inputs.hotbar2.hotkey9)
        self.bard.builder(BardAbilities.veil_of_notes).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.troubador.builder(TroubadorAbilities.bagpipe_solo).action(inputs.hotbar3.hotkey1)
        self.troubador.builder(TroubadorAbilities.energizing_ballad).action(inputs.hotbar3.hotkey2).target(GameClasses.Local)
        self.bard.builder(BardAbilities.quick_tempo).action(inputs.hotbar3.hotkey3)
        self.bard.builder(BardAbilities.deadly_dance).action(inputs.hotbar3.hotkey4)
        self.bard.builder(BardAbilities.songspinners_note).action(inputs.hotbar3.hotkey5)
        self.troubador.builder(TroubadorAbilities.maelstrom_of_sound).action(inputs.hotbar3.hotkey6)
        self.troubador.builder(TroubadorAbilities.depressing_chant).action(inputs.hotbar3.hotkey7)
        self.troubador.builder(TroubadorAbilities.vexing_verses).action(inputs.hotbar3.hotkey8)
        self.troubador.builder(TroubadorAbilities.discordant_verse).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.bard.builder(BardAbilities.song_of_shielding).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.troubador.builder(TroubadorAbilities.upbeat_tempo).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.scout.builder(ScoutAbilities.dozekars_resilience).action(inputs.hotbar5.hotkey11)
        self.scout.builder(ScoutAbilities.persistence).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class ThugClass(ScoutClass):
    def __init__(self, class_level: int):
        ScoutClass.__init__(self, class_level)
        self.thug = self.add_subclass(GameClasses.Thug)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.thug.builder(ThugAbilities.change_of_engagement).build()
        self.thug.builder(ThugAbilities.danse_macabre).build()
        self.thug.builder(ThugAbilities.detect_weakness).build()
        self.thug.builder(ThugAbilities.pris_de_fer).build()
        self.thug.builder(ThugAbilities.shadow).build()
        # self.thug.builder(ThugAbilities.thieving_essence).build()
        self.thug.builder(ThugAbilities.torporous_strike).build()
        self.thug.builder(ThugAbilities.traumatic_swipe).build()
        # self.thug.builder(ThugAbilities.walk_the_plank).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class BrigandClass(ThugClass):
    def __init__(self, class_level: int):
        ThugClass.__init__(self, class_level)
        self.brigand = self.add_subclass(GameClasses.Brigand)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        # self.brigand.builder(BrigandAbilities.barroom_negotiation).build()
        self.brigand.builder(BrigandAbilities.battery_and_assault).build()
        self.brigand.builder(BrigandAbilities.beg_for_mercy).build()
        self.brigand.builder(BrigandAbilities.black_jack).build()
        self.brigand.builder(BrigandAbilities.blinding_dust).build()
        self.brigand.builder(BrigandAbilities.bum_rush).build()
        self.brigand.builder(BrigandAbilities.cornered).build()
        self.brigand.builder(BrigandAbilities.crimson_swath).build()
        self.brigand.builder(BrigandAbilities.cuss).build()
        self.brigand.builder(BrigandAbilities.debilitate).build()
        self.brigand.builder(BrigandAbilities.deceit).build()
        self.brigand.builder(BrigandAbilities.deft_disarm).build()
        self.brigand.builder(BrigandAbilities.desperate_thrust).build()
        self.brigand.builder(BrigandAbilities.dispatch).build()
        self.brigand.builder(BrigandAbilities.double_up).build()
        self.brigand.builder(BrigandAbilities.entangle).build()
        self.brigand.builder(BrigandAbilities.forced_arbitration).build()
        self.brigand.builder(BrigandAbilities.gut_rip).build()
        self.brigand.builder(BrigandAbilities.holdup).build()
        self.brigand.builder(BrigandAbilities.mug).build()
        self.brigand.builder(BrigandAbilities.murderous_rake).build()
        self.brigand.builder(BrigandAbilities.perforate).build()
        self.brigand.builder(BrigandAbilities.puncture).build()
        self.brigand.builder(BrigandAbilities.riot).build()
        self.brigand.builder(BrigandAbilities.safehouse).build()
        self.brigand.builder(BrigandAbilities.stunning_blow).build()
        self.brigand.builder(BrigandAbilities.thieves_guild).build()
        self.brigand.builder(BrigandAbilities.vital_strike).build()
        self.brigand.builder(BrigandAbilities.will_to_survive).build()
        # modifications
        self.brigand.builder(BrigandAbilities.battery_and_assault).effect_duration(30.0)
        self.brigand.builder(BrigandAbilities.crimson_swath).effect_builder(BrigandEffects.CRIMSON_SWATH())
        self.brigand.builder(BrigandAbilities.riot).effect_builder(BrigandEffects.RIOT())

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(BrigandEffects.TENURE())
        self.class_effects.append(BrigandEffects.FOCUS_DISPATCH())
        self.class_effects.append(BrigandEffects.BLINDING_DUST(3))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.scout.builder(ScoutAbilities.dagger_storm).action(inputs.hotbar1.hotkey2)
        self.brigand.builder(BrigandAbilities.blinding_dust).action(inputs.hotbar1.hotkey3)
        self.brigand.builder(BrigandAbilities.forced_arbitration).action(inputs.hotbar1.hotkey4)
        self.brigand.builder(BrigandAbilities.cornered).action(inputs.hotbar1.hotkey5)
        self.brigand.builder(BrigandAbilities.crimson_swath).action(inputs.hotbar1.hotkey6)
        self.thug.builder(ThugAbilities.danse_macabre).action(inputs.hotbar1.hotkey7)
        self.brigand.builder(BrigandAbilities.dispatch).action(inputs.hotbar1.hotkey8)
        self.thug.builder(ThugAbilities.shadow).action(inputs.hotbar1.hotkey9)
        self.thug.builder(ThugAbilities.change_of_engagement).action(inputs.hotbar1.hotkey10)
        self.brigand.builder(BrigandAbilities.mug).action(inputs.hotbar1.hotkey11)
        self.brigand.builder(BrigandAbilities.holdup).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.thug.builder(ThugAbilities.traumatic_swipe).action(inputs.hotbar2.hotkey1)
        self.thug.builder(ThugAbilities.torporous_strike).action(inputs.hotbar2.hotkey2)
        self.brigand.builder(BrigandAbilities.battery_and_assault).action(inputs.hotbar2.hotkey3)
        self.brigand.builder(BrigandAbilities.deft_disarm).action(inputs.hotbar2.hotkey4)
        self.brigand.builder(BrigandAbilities.puncture).action(inputs.hotbar2.hotkey5)
        self.brigand.builder(BrigandAbilities.entangle).action(inputs.hotbar2.hotkey6)
        self.brigand.builder(BrigandAbilities.debilitate).action(inputs.hotbar2.hotkey7)
        self.brigand.builder(BrigandAbilities.murderous_rake).action(inputs.hotbar2.hotkey8)
        self.brigand.builder(BrigandAbilities.will_to_survive).action(inputs.hotbar2.hotkey9)
        self.brigand.builder(BrigandAbilities.bum_rush).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.scout.builder(ScoutAbilities.cheap_shot).action(inputs.hotbar3.hotkey1)
        self.brigand.builder(BrigandAbilities.stunning_blow).action(inputs.hotbar3.hotkey2)
        self.brigand.builder(BrigandAbilities.black_jack).action(inputs.hotbar3.hotkey3)
        self.thug.builder(ThugAbilities.pris_de_fer).action(inputs.hotbar3.hotkey4)
        self.brigand.builder(BrigandAbilities.cuss).action(inputs.hotbar3.hotkey5)
        self.brigand.builder(BrigandAbilities.double_up).action(inputs.hotbar3.hotkey6)
        self.brigand.builder(BrigandAbilities.deceit).action(inputs.hotbar3.hotkey7)
        self.brigand.builder(BrigandAbilities.gut_rip).action(inputs.hotbar3.hotkey8)
        self.brigand.builder(BrigandAbilities.vital_strike).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.thug.builder(ThugAbilities.detect_weakness).action(inputs.hotbar5.hotkey8)
        self.brigand.builder(BrigandAbilities.thieves_guild).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.brigand.builder(BrigandAbilities.safehouse).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.scout.builder(ScoutAbilities.dozekars_resilience).action(inputs.hotbar5.hotkey11)
        self.scout.builder(ScoutAbilities.persistence).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)
        # not on hotbars
        self.brigand.builder(BrigandAbilities.beg_for_mercy).target(player)


class MageClass(CommonerClass):
    def __init__(self, class_level: int):
        CommonerClass.__init__(self, class_level)
        self.mage = self.add_subclass(GameClasses.Mage)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.mage.builder(MageAbilities.absorb_magic).build()
        self.mage.builder(MageAbilities.arcane_augur).build()
        self.mage.builder(MageAbilities.balanced_synergy).build()
        self.mage.builder(MageAbilities.cure_magic).build()
        self.mage.builder(MageAbilities.scaled_protection).build()
        self.mage.builder(MageAbilities.smite_of_consistency).build()
        self.mage.builder(MageAbilities.unda_arcanus_spiritus).build()
        self.mage.builder(MageAbilities.undeath).build()
        self.mage.builder(MageAbilities.magis_shielding).build()
        # modifications
        self.mage.builder(MageAbilities.cure_magic).cancel_spellcast()
        self.mage.builder(MageAbilities.balanced_synergy).casting_end_confirm_event(CombatEvents.PLAYER_SYNERGIZED(caster_name=player.get_player_name()))
        self.mage.builder(MageAbilities.balanced_synergy).expiration_event(CombatEvents.PLAYER_SYNERGY_FADES(caster_name=player.get_player_name()))


class SorcererClass(MageClass):
    def __init__(self, class_level: int):
        MageClass.__init__(self, class_level)
        self.sorcerer = self.add_subclass(GameClasses.Sorcerer)


class EnchanterClass(MageClass):
    def __init__(self, class_level: int):
        MageClass.__init__(self, class_level)
        self.enchanter = self.add_subclass(GameClasses.Enchanter)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.enchanter.builder(EnchanterAbilities.aura_of_power).build()
        self.enchanter.builder(EnchanterAbilities.blinding_shock).build()
        self.enchanter.builder(EnchanterAbilities.channeled_focus).build()
        self.enchanter.builder(EnchanterAbilities.chronosiphoning).build()
        # self.enchanter.builder(EnchanterAbilities.ego_whip).build()
        self.enchanter.builder(EnchanterAbilities.enchanted_vigor).build()
        self.enchanter.builder(EnchanterAbilities.id_explosion).build()
        # self.enchanter.builder(EnchanterAbilities.mana_cloak).build()
        self.enchanter.builder(EnchanterAbilities.mana_flow).build()
        self.enchanter.builder(EnchanterAbilities.manasoul).build()
        self.enchanter.builder(EnchanterAbilities.nullifying_staff).build(optional=True)
        self.enchanter.builder(EnchanterAbilities.peace_of_mind).build()
        self.enchanter.builder(EnchanterAbilities.spellblades_counter).build()
        self.enchanter.builder(EnchanterAbilities.temporal_mimicry).build()
        self.enchanter.builder(EnchanterAbilities.touch_of_empathy).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(EnchanterEffects.FOCUS_PEACE_OF_MIND())
        self.class_effects.append(EnchanterEffects.CHANNELED_FOCUS(10))


class IllusionistClass(EnchanterClass):
    def __init__(self, class_level: int):
        EnchanterClass.__init__(self, class_level)
        self.illusionist = self.add_subclass(GameClasses.Illusionist)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.illusionist.builder(IllusionistAbilities.arms_of_imagination).build()
        self.illusionist.builder(IllusionistAbilities.bewilderment).build()
        self.illusionist.builder(IllusionistAbilities.brainburst).build()
        self.illusionist.builder(IllusionistAbilities.chromatic_illusion).build()
        self.illusionist.builder(IllusionistAbilities.chromatic_shower).build()
        self.illusionist.builder(IllusionistAbilities.chromatic_storm).build()
        self.illusionist.builder(IllusionistAbilities.entrance).build()
        self.illusionist.builder(IllusionistAbilities.extract_mana).build()
        self.illusionist.builder(IllusionistAbilities.flash_of_brilliance).build()
        self.illusionist.builder(IllusionistAbilities.illusionary_instigation).build()
        self.illusionist.builder(IllusionistAbilities.illusory_barrier).build()
        self.illusionist.builder(IllusionistAbilities.manatap).build()
        self.illusionist.builder(IllusionistAbilities.nightmare).build()
        self.illusionist.builder(IllusionistAbilities.paranoia).build()
        self.illusionist.builder(IllusionistAbilities.personae_reflection).build()
        self.illusionist.builder(IllusionistAbilities.phantom_troupe).build()
        self.illusionist.builder(IllusionistAbilities.phase).build()
        self.illusionist.builder(IllusionistAbilities.prismatic_chaos).build()
        self.illusionist.builder(IllusionistAbilities.rapidity).build()
        self.illusionist.builder(IllusionistAbilities.savante).build()
        self.illusionist.builder(IllusionistAbilities.speechless).build()
        self.illusionist.builder(IllusionistAbilities.support).build()
        self.illusionist.builder(IllusionistAbilities.synergism).build()
        self.illusionist.builder(IllusionistAbilities.time_compression).build()
        self.illusionist.builder(IllusionistAbilities.time_warp).build()
        self.illusionist.builder(IllusionistAbilities.timelord).build()
        self.illusionist.builder(IllusionistAbilities.ultraviolet_beam).build()
        self.illusionist.builder(IllusionistAbilities.rune_of_thought).build()
        self.illusionist.builder(IllusionistAbilities.chronal_mastery).build()
        # modifications
        self.illusionist.builder(IllusionistAbilities.support).census_data(casting=1.5, reuse=4.0, recovery=1.0, beneficial=False)
        self.illusionist.builder(IllusionistAbilities.illusory_barrier).untracked_triggers(30.0)
        self.illusionist.builder(IllusionistAbilities.timelord).modify_set('reuse', 3600.0)  # reuse on a player is 30 min (ancient) or 37 min (master)
        self.illusionist.builder(IllusionistAbilities.personae_reflection).recast_maintained()
        self.illusionist.builder(IllusionistAbilities.time_warp).effect_duration(10.0)
        self.illusionist.builder(IllusionistAbilities.brainburst).census_error('duration', 13.5)
        self.illusionist.builder(IllusionistAbilities.speechless).census_error('duration', 18.0)
        self.illusionist.builder(IllusionistAbilities.paranoia).census_error('duration', 8.5)
        self.illusionist.builder(IllusionistAbilities.entrance).census_error('duration', 45.0)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(IllusionistEffects.HASTENED_MANA_FLOW(5))
        self.class_effects.append(IllusionistEffects.CHROMATIC_ILLUSION(3))
        self.class_effects.append(IllusionistEffects.ENHANCE_FLASH_OF_BRILLIANCE(5))
        self.class_effects.append(IllusionistEffects.ENHANCE_SAVANTE(5))
        self.class_effects.append(IllusionistEffects.ENHANCE_CURE_MAGIC_ILLUSIONIST())
        self.class_effects.append(IllusionistEffects.ENHANCE_ILLUSORY_ALLIES(5))
        self.class_effects.append(IllusionistEffects.ENHANCE_SPEECHLESS(5))
        self.class_effects.append(IllusionistEffects.ENHANCE_ENTRANCE(5))

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.illusionist.builder(IllusionistAbilities.support).action(inputs.hotbar1.hotkey2)
        self.illusionist.builder(IllusionistAbilities.flash_of_brilliance).action(inputs.hotbar1.hotkey3)
        self.enchanter.builder(EnchanterAbilities.peace_of_mind).action(inputs.hotbar1.hotkey4)
        self.illusionist.builder(IllusionistAbilities.chromatic_illusion).action(inputs.hotbar1.hotkey5)
        self.enchanter.builder(EnchanterAbilities.chronosiphoning).action(inputs.hotbar1.hotkey6)
        self.illusionist.builder(IllusionistAbilities.phase).action(inputs.hotbar1.hotkey7)
        self.enchanter.builder(EnchanterAbilities.spellblades_counter).action(inputs.hotbar1.hotkey8)
        self.illusionist.builder(IllusionistAbilities.speechless).action(inputs.hotbar1.hotkey9)
        self.illusionist.builder(IllusionistAbilities.paranoia).action(inputs.hotbar1.hotkey10)
        self.mage.builder(MageAbilities.absorb_magic).action(inputs.hotbar1.hotkey11)
        self.illusionist.builder(IllusionistAbilities.nightmare).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.illusionist.builder(IllusionistAbilities.phantom_troupe).action(inputs.hotbar2.hotkey1)
        self.illusionist.builder(IllusionistAbilities.illusionary_instigation).action(inputs.hotbar2.hotkey2).target(GameClasses.Local)
        self.illusionist.builder(IllusionistAbilities.time_warp).action(inputs.hotbar2.hotkey3)
        self.illusionist.builder(IllusionistAbilities.illusory_barrier).action(inputs.hotbar2.hotkey4).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.touch_of_empathy).action(inputs.hotbar2.hotkey5).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.temporal_mimicry).action(inputs.hotbar2.hotkey6).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.blinding_shock).action(inputs.hotbar2.hotkey7)
        self.mage.builder(MageAbilities.unda_arcanus_spiritus).action(inputs.hotbar2.hotkey8)
        self.enchanter.builder(EnchanterAbilities.id_explosion).action(inputs.hotbar2.hotkey9)
        self.enchanter.builder(EnchanterAbilities.channeled_focus).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.mage.builder(MageAbilities.cure_magic).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.illusionist.builder(IllusionistAbilities.savante).action(inputs.hotbar3.hotkey2)
        self.enchanter.builder(EnchanterAbilities.manasoul).action(inputs.hotbar3.hotkey3)
        self.illusionist.builder(IllusionistAbilities.manatap).action(inputs.hotbar3.hotkey4)
        self.enchanter.builder(EnchanterAbilities.mana_flow).action(inputs.hotbar3.hotkey5).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.aura_of_power).action(inputs.hotbar3.hotkey6)
        self.illusionist.builder(IllusionistAbilities.timelord).action(inputs.hotbar3.hotkey7).target(GameClasses.Local)
        self.illusionist.builder(IllusionistAbilities.prismatic_chaos).action(inputs.hotbar3.hotkey8).target(GameClasses.Local)
        self.illusionist.builder(IllusionistAbilities.entrance).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.illusionist.builder(IllusionistAbilities.personae_reflection).action(inputs.hotbar5.hotkey5)
        self.illusionist.builder(IllusionistAbilities.time_compression).action(inputs.hotbar5.hotkey6).target(GameClasses.Shaman)
        self.illusionist.builder(IllusionistAbilities.arms_of_imagination).action(inputs.hotbar5.hotkey7).target(GameClasses.Local)
        self.illusionist.builder(IllusionistAbilities.rapidity).action(inputs.hotbar5.hotkey8)
        self.illusionist.builder(IllusionistAbilities.synergism).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.enchanted_vigor).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.mage.builder(MageAbilities.scaled_protection).action(inputs.hotbar5.hotkey11)
        self.mage.builder(MageAbilities.undeath).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class CoercerClass(EnchanterClass):
    def __init__(self, class_level: int):
        EnchanterClass.__init__(self, class_level)
        self.coercer = self.add_subclass(GameClasses.Coercer)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.coercer.builder(CoercerAbilities.asylum).build()
        self.coercer.builder(CoercerAbilities.brainshock).build()
        self.coercer.builder(CoercerAbilities.cannibalize_thoughts).build()
        self.coercer.builder(CoercerAbilities.channel).build()
        self.coercer.builder(CoercerAbilities.coercive_healing).build()
        self.coercer.builder(CoercerAbilities.enraging_demeanor).build()
        self.coercer.builder(CoercerAbilities.ether_balance).build()
        self.coercer.builder(CoercerAbilities.hemorrhage).build()
        self.coercer.builder(CoercerAbilities.intellectual_remedy).build()
        self.coercer.builder(CoercerAbilities.lethal_focus).build()
        self.coercer.builder(CoercerAbilities.manaward).build()
        self.coercer.builder(CoercerAbilities.medusa_gaze).build()
        self.coercer.builder(CoercerAbilities.mesmerize).build()
        self.coercer.builder(CoercerAbilities.mind_control).build()
        self.coercer.builder(CoercerAbilities.mindbend).build()
        self.coercer.builder(CoercerAbilities.obliterated_psyche).build()
        self.coercer.builder(CoercerAbilities.peaceful_link).build()
        self.coercer.builder(CoercerAbilities.possess_essence).build()
        self.coercer.builder(CoercerAbilities.shift_mana).build()
        self.coercer.builder(CoercerAbilities.shock_wave).build()
        self.coercer.builder(CoercerAbilities.silence).build()
        self.coercer.builder(CoercerAbilities.simple_minds).build()
        self.coercer.builder(CoercerAbilities.sirens_stare).build()
        self.coercer.builder(CoercerAbilities.stupefy).build()
        self.coercer.builder(CoercerAbilities.support).build()
        self.coercer.builder(CoercerAbilities.tashiana).build()
        self.coercer.builder(CoercerAbilities.velocity).build()
        # modifications
        self.coercer.builder(CoercerAbilities.support).census_data(casting=2.0, reuse=3.0, recovery=1.0, beneficial=False)
        self.coercer.builder(CoercerAbilities.possess_essence).recast_maintained()
        self.coercer.builder(CoercerAbilities.coercive_healing).recast_maintained()
        self.enchanter.builder(EnchanterAbilities.aura_of_power).modify_set('reuse', 180.0)  # uses recast timer from mana_cloak

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(EnchanterEffects.ACADEM(10))
        self.class_effects.append(CoercerEffects.ENHANCE_MANA_FLOW(5))
        self.class_effects.append(CoercerEffects.ENHANCE_ABSORB_MAGIC(5))
        self.class_effects.append(CoercerEffects.ETHER_BALANCE(3))
        self.class_effects.append(CoercerEffects.MIND_CONTROL(3))
        self.class_effects.append(CoercerEffects.ENHANCE_CHANNEL(5))
        self.class_effects.append(CoercerEffects.ENHANCE_STUPEFY(5))
        self.class_effects.append(CoercerEffects.HASTENED_MANA(5))
        self.class_effects.append(CoercerEffects.SIRENS_STARE())
        self.class_effects.append(CoercerEffects.MIND_MASTERY())

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.coercer.builder(CoercerAbilities.support).action(inputs.hotbar1.hotkey2)
        self.coercer.builder(CoercerAbilities.intellectual_remedy).action(inputs.hotbar1.hotkey3)
        self.enchanter.builder(EnchanterAbilities.peace_of_mind).action(inputs.hotbar1.hotkey4)
        self.coercer.builder(CoercerAbilities.ether_balance).action(inputs.hotbar1.hotkey5)
        self.enchanter.builder(EnchanterAbilities.chronosiphoning).action(inputs.hotbar1.hotkey6)
        self.coercer.builder(CoercerAbilities.obliterated_psyche).action(inputs.hotbar1.hotkey7)
        self.enchanter.builder(EnchanterAbilities.spellblades_counter).action(inputs.hotbar1.hotkey8)
        self.coercer.builder(CoercerAbilities.tashiana).action(inputs.hotbar1.hotkey9)
        self.coercer.builder(CoercerAbilities.medusa_gaze).action(inputs.hotbar1.hotkey10)
        self.mage.builder(MageAbilities.absorb_magic).action(inputs.hotbar1.hotkey11)
        self.coercer.builder(CoercerAbilities.asylum).action(inputs.hotbar1.hotkey12)
        ### hotbar 2
        self.enchanter.builder(EnchanterAbilities.touch_of_empathy).action(inputs.hotbar2.hotkey1).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.temporal_mimicry).action(inputs.hotbar2.hotkey2).target(GameClasses.Local)
        self.coercer.builder(CoercerAbilities.manaward).action(inputs.hotbar2.hotkey3).target(GameClasses.Local)
        self.coercer.builder(CoercerAbilities.lethal_focus).action(inputs.hotbar2.hotkey4).target(GameClasses.Local)
        self.coercer.builder(CoercerAbilities.mind_control).action(inputs.hotbar2.hotkey5).target(GameClasses.Local)
        self.coercer.builder(CoercerAbilities.shock_wave).action(inputs.hotbar2.hotkey6)
        self.enchanter.builder(EnchanterAbilities.blinding_shock).action(inputs.hotbar2.hotkey7)
        self.mage.builder(MageAbilities.unda_arcanus_spiritus).action(inputs.hotbar2.hotkey8)
        self.enchanter.builder(EnchanterAbilities.id_explosion).action(inputs.hotbar2.hotkey9)
        self.enchanter.builder(EnchanterAbilities.channeled_focus).action(inputs.hotbar2.hotkey10)
        ### hotbar 3
        self.mage.builder(MageAbilities.cure_magic).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.coercer.builder(CoercerAbilities.channel).action(inputs.hotbar3.hotkey2)
        self.enchanter.builder(EnchanterAbilities.manasoul).action(inputs.hotbar3.hotkey3)
        self.coercer.builder(CoercerAbilities.cannibalize_thoughts).action(inputs.hotbar3.hotkey4)
        self.enchanter.builder(EnchanterAbilities.mana_flow).action(inputs.hotbar3.hotkey5).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.aura_of_power).action(inputs.hotbar3.hotkey6)
        self.coercer.builder(CoercerAbilities.stupefy).action(inputs.hotbar3.hotkey7)
        self.coercer.builder(CoercerAbilities.mindbend).action(inputs.hotbar3.hotkey8)
        self.coercer.builder(CoercerAbilities.mesmerize).action(inputs.hotbar3.hotkey9)
        ### hotbar 5
        self.coercer.builder(CoercerAbilities.possess_essence).action(inputs.hotbar5.hotkey4)
        self.coercer.builder(CoercerAbilities.sirens_stare).action(inputs.hotbar5.hotkey5).target(GameClasses.Fighter)
        self.coercer.builder(CoercerAbilities.coercive_healing).action(inputs.hotbar5.hotkey6)
        self.coercer.builder(CoercerAbilities.peaceful_link).action(inputs.hotbar5.hotkey7)
        self.coercer.builder(CoercerAbilities.velocity).action(inputs.hotbar5.hotkey8)
        self.coercer.builder(CoercerAbilities.enraging_demeanor).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.enchanter.builder(EnchanterAbilities.enchanted_vigor).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.mage.builder(MageAbilities.scaled_protection).action(inputs.hotbar5.hotkey11)
        self.mage.builder(MageAbilities.undeath).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)


class SummonerClass(MageClass):
    def __init__(self, class_level: int):
        MageClass.__init__(self, class_level)
        self.summoner = self.add_subclass(GameClasses.Summoner)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.summoner.builder(SummonerAbilities.blightfire).build()
        self.summoner.builder(SummonerAbilities.elemental_toxicity).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class ConjurorClass(SummonerClass):
    def __init__(self, class_level: int):
        SummonerClass.__init__(self, class_level)
        self.conjuror = self.add_subclass(GameClasses.Conjuror)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.conjuror.builder(ConjurorAbilities.aqueous_swarm).build()
        self.conjuror.builder(ConjurorAbilities.call_of_the_hero).build()
        self.conjuror.builder(ConjurorAbilities.crystal_blast).build()
        self.conjuror.builder(ConjurorAbilities.earthen_avatar).build()
        self.conjuror.builder(ConjurorAbilities.earthquake).build()
        self.conjuror.builder(ConjurorAbilities.elemental_barrier).build()
        self.conjuror.builder(ConjurorAbilities.elemental_blast).build()
        self.conjuror.builder(ConjurorAbilities.essence_shift).build()
        self.conjuror.builder(ConjurorAbilities.fire_seed).build()
        self.conjuror.builder(ConjurorAbilities.flameshield).build()
        self.conjuror.builder(ConjurorAbilities.petrify).build()
        self.conjuror.builder(ConjurorAbilities.plane_shift).build()
        self.conjuror.builder(ConjurorAbilities.sacrifice).build()
        self.conjuror.builder(ConjurorAbilities.servants_intervention).build()
        self.conjuror.builder(ConjurorAbilities.stoneskin).build()
        self.conjuror.builder(ConjurorAbilities.stoneskins).build()
        self.conjuror.builder(ConjurorAbilities.summoners_siphon).build()
        self.conjuror.builder(ConjurorAbilities.unflinching_servant).build()
        self.conjuror.builder(ConjurorAbilities.winds_of_velious).build()
        self.conjuror.builder(ConjurorAbilities.world_ablaze).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(ConjurorEffects.FOCUS_ELEMENTAL_TOXICITY())
        self.class_effects.append(ConjurorEffects.FOCUS_SACRIFICE())
        self.class_effects.append(ConjurorEffects.SACRIFICIAL_LAMB(5))
        self.class_effects.append(ConjurorEffects.ENHANCE_CURE_MAGIC_CONJUROR())

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.conjuror.builder(ConjurorAbilities.crystal_blast).action(inputs.hotbar1.hotkey2)
        self.conjuror.builder(ConjurorAbilities.aqueous_swarm).action(inputs.hotbar1.hotkey3)
        self.conjuror.builder(ConjurorAbilities.winds_of_velious).action(inputs.hotbar1.hotkey4)
        self.conjuror.builder(ConjurorAbilities.petrify).action(inputs.hotbar1.hotkey5)
        self.mage.builder(MageAbilities.absorb_magic).action(inputs.hotbar1.hotkey6)
        self.conjuror.builder(ConjurorAbilities.stoneskin).action(inputs.hotbar1.hotkey7)
        self.conjuror.builder(ConjurorAbilities.stoneskins).action(inputs.hotbar1.hotkey8)
        self.conjuror.builder(ConjurorAbilities.elemental_barrier).action(inputs.hotbar1.hotkey9)
        self.conjuror.builder(ConjurorAbilities.essence_shift).action(inputs.hotbar1.hotkey10)
        self.conjuror.builder(ConjurorAbilities.sacrifice).action(inputs.hotbar1.hotkey11)
        ### hotbar 2
        self.summoner.builder(SummonerAbilities.elemental_toxicity).action(inputs.hotbar2.hotkey1)
        self.conjuror.builder(ConjurorAbilities.elemental_blast).action(inputs.hotbar2.hotkey2)
        self.conjuror.builder(ConjurorAbilities.earthquake).action(inputs.hotbar2.hotkey3)
        self.mage.builder(MageAbilities.unda_arcanus_spiritus).action(inputs.hotbar2.hotkey4)
        self.summoner.builder(SummonerAbilities.blightfire).action(inputs.hotbar2.hotkey5)
        self.conjuror.builder(ConjurorAbilities.unflinching_servant).action(inputs.hotbar2.hotkey6)
        ### hotbar 3
        self.mage.builder(MageAbilities.cure_magic).action(inputs.hotbar3.hotkey1).target(GameClasses.Local)
        self.conjuror.builder(ConjurorAbilities.world_ablaze).action(inputs.hotbar3.hotkey2)
        self.conjuror.builder(ConjurorAbilities.plane_shift).action(inputs.hotbar3.hotkey3)
        self.conjuror.builder(ConjurorAbilities.summoners_siphon).action(inputs.hotbar3.hotkey4)
        ### hotbar 5
        self.conjuror.builder(ConjurorAbilities.servants_intervention).action(inputs.hotbar5.hotkey7)
        self.conjuror.builder(ConjurorAbilities.earthen_avatar).action(inputs.hotbar5.hotkey8)
        self.conjuror.builder(ConjurorAbilities.flameshield).action(inputs.hotbar5.hotkey9).target(GameClasses.Local)
        self.conjuror.builder(ConjurorAbilities.fire_seed).action(inputs.hotbar5.hotkey10).target(GameClasses.Local)
        self.mage.builder(MageAbilities.scaled_protection).action(inputs.hotbar5.hotkey11)
        self.mage.builder(MageAbilities.undeath).action(inputs.hotbar5.hotkey12)
        ### hotbar 12
        self.common.builder(CommonerAbilities.call_to_guild_hall).action(inputs.hotbarUp12.hotkey11)
        self.common.builder(CommonerAbilities.call_to_home).action(inputs.hotbarUp12.hotkey12)
        ### not on hotbars
        self.conjuror.builder(ConjurorAbilities.call_of_the_hero).target(GameClasses.Local)


class FighterClass(CommonerClass):
    def __init__(self, class_level: int):
        CommonerClass.__init__(self, class_level)
        self.fighter = self.add_subclass(GameClasses.Fighter)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.fighter.builder(FighterAbilities.balanced_synergy).build()
        self.fighter.builder(FighterAbilities.bulwark_of_order).build()
        self.fighter.builder(FighterAbilities.fighting_chance).build()
        self.fighter.builder(FighterAbilities.intercept).build()
        # self.fighter.builder(FighterAbilities.provocation).build()
        self.fighter.builder(FighterAbilities.rescue).build()
        self.fighter.builder(FighterAbilities.strike_of_consistency).build()
        # self.fighter.builder(FighterAbilities.goading_gesture).build()
        # modifications
        self.fighter.builder(FighterAbilities.balanced_synergy).casting_end_confirm_event(CombatEvents.PLAYER_SYNERGIZED(caster_name=player.get_player_name()))
        self.fighter.builder(FighterAbilities.balanced_synergy).expiration_event(CombatEvents.PLAYER_SYNERGY_FADES(caster_name=player.get_player_name()))
        if player.is_local():
            synergy_event = RequestEvents.REQUEST_BALANCED_SYNERGY(player_name=player.get_player_name())
            self.fighter.builder(FighterAbilities.balanced_synergy).add_head_injection('gsay FBalanced Synergy')
            self.fighter.builder(FighterAbilities.balanced_synergy).casting_start_confirm_event(synergy_event)
        bulwark = self.fighter.builder(FighterAbilities.bulwark_of_order)
        bulwark.casting_monitor(BulwarkCastingCompletedMonitor())
        bulwark.casting_end_confirm_event(CombatParserEvents.COMBAT_HIT(attacker_name=player.get_player_name(), ability_name='overpower', is_multi=False, is_autoattack=False, is_dot=False))

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(FighterEffects.ANCIENT_FOCUS(10))


class CrusaderClass(FighterClass):
    def __init__(self, class_level: int):
        FighterClass.__init__(self, class_level)
        self.crusader = self.add_subclass(GameClasses.Crusader)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.crusader.builder(CrusaderAbilities.vital_trigger).build()
        self.crusader.builder(CrusaderAbilities.zealots_challenge).build()
        self.crusader.builder(CrusaderAbilities.hammer_ground).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class WarriorClass(FighterClass):
    def __init__(self, class_level: int):
        FighterClass.__init__(self, class_level)
        self.warrior = self.add_subclass(GameClasses.Warrior)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)


class BrawlerClass(FighterClass):
    def __init__(self, class_level: int):
        FighterClass.__init__(self, class_level)
        self.brawler = self.add_subclass(GameClasses.Brawler)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.brawler.builder(BrawlerAbilities.baton_flurry).build()  # TODO optional
        self.brawler.builder(BrawlerAbilities.boneshattering_combination).build()
        self.brawler.builder(BrawlerAbilities.brawlers_tenacity).build()
        # self.brawler.builder(BrawlerAbilities.chi).build()
        self.brawler.builder(BrawlerAbilities.combat_mastery).build()
        # self.brawler.builder(BrawlerAbilities.crane_flock).build()
        self.brawler.builder(BrawlerAbilities.crane_sweep).build()
        self.brawler.builder(BrawlerAbilities.devastation_fist).build()
        self.brawler.builder(BrawlerAbilities.eagle_spin).build()  # TODO optional
        self.brawler.builder(BrawlerAbilities.eagles_patience).build()
        self.brawler.builder(BrawlerAbilities.inner_focus).build()
        self.brawler.builder(BrawlerAbilities.mantis_leap).build()
        self.brawler.builder(BrawlerAbilities.mantis_star).build()
        self.brawler.builder(BrawlerAbilities.pressure_point).build()
        # self.brawler.builder(BrawlerAbilities.sneering_assault).build()
        self.brawler.builder(BrawlerAbilities.stone_cold).build()
        self.brawler.builder(BrawlerAbilities.tag_team).build()
        # modifications
        self.brawler.builder(BrawlerAbilities.mantis_star).override_passthrough(passthrough=True)  # due to min-range
        self.brawler.builder(BrawlerAbilities.boneshattering_combination).override_passthrough(passthrough=True)  # unidentified request bug
        tag_team = self.brawler.builder(BrawlerAbilities.tag_team)
        tag_team.effect_duration(8.0)
        tag_team.casting_start_confirm_event(ChatEvents.PLAYER_TELL(from_player_name=player.get_player_name(), tell_type=TellType.say, tell='Look! I\'m elsewhere!', to_local=True))

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(BrawlerEffects.ENHANCE_BRAWLERS_TENACITY(10))
        self.class_effects.append(BrawlerEffects.ENHANCE_INNER_FOCUS(10))


class MonkClass(BrawlerClass):
    def __init__(self, class_level: int):
        BrawlerClass.__init__(self, class_level)
        self.monk = self.add_subclass(GameClasses.Monk)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.monk.builder(MonkAbilities.arctic_talon).build()
        self.monk.builder(MonkAbilities.bob_and_weave).build()
        self.monk.builder(MonkAbilities.body_like_mountain).build()
        self.monk.builder(MonkAbilities.challenge).build()
        self.monk.builder(MonkAbilities.charging_tiger).build()
        # self.monk.builder(MonkAbilities.crescent_strike).build()
        self.monk.builder(MonkAbilities.dragonfire).build()
        # self.monk.builder(MonkAbilities.evasion).build()
        # self.monk.builder(MonkAbilities.fall_of_the_phoenix).build()
        # self.monk.builder(MonkAbilities.feign_death).build()
        self.monk.builder(MonkAbilities.five_rings).build()
        # self.monk.builder(MonkAbilities.fluid_combination).build()
        self.monk.builder(MonkAbilities.flying_scissors).build()
        self.monk.builder(MonkAbilities.frozen_palm).build()
        self.monk.builder(MonkAbilities.hidden_openings).build()
        self.monk.builder(MonkAbilities.lightning_palm).build()
        self.monk.builder(MonkAbilities.mend).build()
        self.monk.builder(MonkAbilities.mountain_stance).build()
        self.monk.builder(MonkAbilities.outward_calm).build()
        self.monk.builder(MonkAbilities.peel).build()
        self.monk.builder(MonkAbilities.perfect_form).build()
        self.monk.builder(MonkAbilities.provoking_stance).build()
        # self.monk.builder(MonkAbilities.reprimand).build()
        self.monk.builder(MonkAbilities.rising_dragon).build()
        self.monk.builder(MonkAbilities.rising_phoenix).build()
        self.monk.builder(MonkAbilities.roundhouse_kick).build()
        self.monk.builder(MonkAbilities.silent_palm).build()
        self.monk.builder(MonkAbilities.silent_threat).build()
        self.monk.builder(MonkAbilities.striking_cobra).build()
        self.monk.builder(MonkAbilities.superior_guard).build()
        self.monk.builder(MonkAbilities.tsunami).build()
        self.monk.builder(MonkAbilities.waking_dragon).build()
        self.monk.builder(MonkAbilities.will_of_the_heavens).build()
        self.monk.builder(MonkAbilities.winds_of_salvation).build()
        # modifications
        self.monk.builder(MonkAbilities.dragonfire).effect_duration(8.0)
        self.monk.builder(MonkAbilities.rising_dragon).census_error('duration', 13.5)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(MonkEffects.ENHANCE_TAUNTS(5))


class PaladinClass(CrusaderClass):
    def __init__(self, class_level: int):
        CrusaderClass.__init__(self, class_level)
        self.paladin = self.add_subclass(GameClasses.Paladin)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        self.paladin.builder(PaladinAbilities.divine_will).build()
        self.paladin.builder(PaladinAbilities.clarion).build()
        self.paladin.builder(PaladinAbilities.power_cleave).build()
        self.paladin.builder(PaladinAbilities.divine_vengeance).build()
        self.paladin.builder(PaladinAbilities.faith_strike).build()
        self.paladin.builder(PaladinAbilities.faithful_cry).build()
        self.paladin.builder(PaladinAbilities.holy_strike).build()
        self.paladin.builder(PaladinAbilities.judgment).build()
        self.paladin.builder(PaladinAbilities.penitent_kick).build()
        self.paladin.builder(PaladinAbilities.heroic_dash).build()
        self.paladin.builder(PaladinAbilities.demonstration_of_faith).build()
        self.paladin.builder(PaladinAbilities.holy_aid).build()
        self.paladin.builder(PaladinAbilities.prayer_of_healing).build()
        self.paladin.builder(PaladinAbilities.righteousness).build()
        self.paladin.builder(PaladinAbilities.decree).build()
        self.paladin.builder(PaladinAbilities.crusaders_judgement).build()
        self.paladin.builder(PaladinAbilities.ancient_wrath).build()
        self.paladin.builder(PaladinAbilities.holy_circle).build()

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
