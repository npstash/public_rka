from typing import Optional, Callable, Any

from rka.eq2.configs.shared.rka_constants import AUTOCOMBAT_TICK
from rka.eq2.master.game.ability import AbilityTier, AbilityType, AbilityPriority
from rka.eq2.master.game.ability.generated_abilities import *
from rka.eq2.master.game.effect import EffectType, EffectScopeType
from rka.eq2.master.game.effect.effect_builder import EffectBuilder
from rka.eq2.master.game.interfaces import IEffectBuilder, TEffectValue, EffectTarget


def named_effect(fn: Callable[[Any], EffectBuilder]):
    def inner(*args, **kwargs):
        builder = fn(*args, **kwargs)
        effect_name = f'{fn.__name__}({", ".join(map(str, (*args, *kwargs.values())))})'
        builder.set_effect_name(effect_name)
        return builder

    return inner


class GeneralEffects:
    @staticmethod
    @named_effect
    def STEALTH() -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).set(EffectType.STEALTH, True)

    @staticmethod
    @named_effect
    def CASTING_SPEED(casting_add: float) -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.CASTING_SPEED, casting_add)

    @staticmethod
    @named_effect
    def REUSE_SPEED(reuse_add: float) -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.REUSE_SPEED, reuse_add)

    @staticmethod
    @named_effect
    def RECOVERY_SPEED(recovery_add: float) -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.RECOVERY_SPEED, recovery_add)

    @staticmethod
    @named_effect
    def LOCAL_PLAYER_CASTING_DELAY() -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_CASTING, AUTOCOMBAT_TICK / 2)


class ItemEffects:
    @staticmethod
    @named_effect
    def SYMPHONY_OF_THE_VOID() -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            return base_value * 0.05 if target_ability.census.type == AbilityType.spells else None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def CHORUS_OF_THE_NIGHT() -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            return base_value * 0.05 if target_ability.census.type == AbilityType.arts else None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def ASCENDED_ASCENSION(max_ascension_level: int) -> IEffectBuilder:
        def casting_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.census.type != AbilityType.ascension:
                return None
            if target_ability.census.level > 100 + max_ascension_level:
                return None
            return -base_value * 0.1

        assert max_ascension_level < 100
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_CASTING, casting_modifier)

    @staticmethod
    @named_effect
    def ENLIGHTENED_ASCENSION(max_ascension_level: int) -> IEffectBuilder:
        def reuse_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.census.type != AbilityType.ascension:
                return None
            if target_ability.census.level <= 100 + max_ascension_level:
                return -base_value * 0.175
            return base_value * 0.035

        assert max_ascension_level < 100
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_REUSE, reuse_modifier)

    @staticmethod
    @named_effect
    def ICE_PYRE() -> IEffectBuilder:
        # should be 20%, but its broken in game
        return EffectBuilder(ElementalistAbilities.frost_pyre).mul(EffectType.DURATION, 0.18)


class ScriptEffects:
    @staticmethod
    @named_effect
    def ABSORB_MAGIC_ZERO_RECAST() -> IEffectBuilder:
        return EffectBuilder(MageAbilities.absorb_magic).set(EffectType.BASE_REUSE, 0.0)

    @staticmethod
    @named_effect
    def CURE_CURSE_ZERO_RECAST() -> IEffectBuilder:
        return EffectBuilder(PriestAbilities.cure_curse).set(EffectType.BASE_REUSE, 0.0)

    @staticmethod
    @named_effect
    def BALANCED_SYNERGY_ZERO_RECAST() -> IEffectBuilder:
        def reuse_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            if target.ability().locator in [FighterAbilities.balanced_synergy,
                                            ScoutAbilities.balanced_synergy,
                                            MageAbilities.balanced_synergy,
                                            PriestAbilities.balanced_synergy]:
                return 0.0
            return base_value

        return EffectBuilder(EffectScopeType.PLAYER).set(EffectType.BASE_REUSE, reuse_modifier)


class FighterEffects:
    @staticmethod
    @named_effect
    def ANCIENT_FOCUS(aa_points: int) -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            return base_value * 0.01 * aa_points if target_ability.census.beneficial else None

        assert 1 <= aa_points <= 10
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)


class BrawlerEffects:
    @staticmethod
    @named_effect
    def ENHANCE_BRAWLERS_TENACITY(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(BrawlerAbilities.brawlers_tenacity).add(EffectType.DURATION, aa_points * 1.5)

    @staticmethod
    @named_effect
    def ENHANCE_INNER_FOCUS(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(BrawlerAbilities.inner_focus).add(EffectType.DURATION, aa_points * 0.5)


class MonkEffects:
    @staticmethod
    @named_effect
    def ENHANCE_TAUNTS(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        if aa_points >= 4:
            aa_points += 1

        def reuse_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MonkAbilities.silent_threat or target_ability.locator == FighterAbilities.goading_gesture:
                return -aa_points * 1.0
            return None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_REUSE, reuse_modifier)


class PriestEffects:
    @staticmethod
    @named_effect
    def MAJESTIC_CASTING(aa_points: int) -> IEffectBuilder:
        def casting_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MysticAbilities.umbral_barrier \
                    or target_ability.locator == InquisitorAbilities.malevolent_diatribe \
                    or target_ability.locator == WardenAbilities.healstorm:
                return -base_value * 0.015 * aa_points
            return None

        assert 1 <= aa_points <= 10
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_CASTING, casting_modifier)

    @staticmethod
    @named_effect
    def ANCIENT_ALACRITY(aa_points: int) -> IEffectBuilder:
        def casting_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MysticAbilities.ritual_healing \
                    or target_ability.locator == WardenAbilities.natures_embrace:
                return -base_value * 0.033 * aa_points
            return None

        assert 1 <= aa_points <= 10
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_CASTING, casting_modifier)


class DruidEffects:
    @staticmethod
    @named_effect
    def WILD_REGENERATION(aa_points: int) -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == WardenAbilities.healstorm \
                    or target_ability.locator == WardenAbilities.photosynthesis \
                    or target_ability.locator == FuryAbilities.autumns_kiss \
                    or target_ability.locator == FuryAbilities.regrowth:
                return -0.25 * aa_points
            return None

        assert 1 <= aa_points <= 10
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def ENHANCE_WRATH_OF_NATURE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(DruidAbilities.wrath_of_nature).add(EffectType.DURATION, -1.0 * aa_points)

    @staticmethod
    @named_effect
    def PURE_SERENITY(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 8
        return EffectBuilder(DruidAbilities.serenity).add(EffectType.BASE_REUSE, -5.0 * aa_points)


class WardenEffects:
    @staticmethod
    @named_effect
    def ENHANCE_CURE_CURSE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(PriestAbilities.cure_curse).add(EffectType.BASE_CASTING, -0.2 * aa_points)

    @staticmethod
    @named_effect
    def CLEARWATER_CURRENT(aa_points: int) -> IEffectBuilder:
        reuse = [30.0, 20.0, 10.0][aa_points - 1]
        return EffectBuilder(WardenAbilities.clearwater_current).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def ENHANCE_HEALING_GROVE(aa_points: int) -> EffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(WardenAbilities.healing_grove).add(EffectType.BASE_REUSE, -2.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_DEATH_INTERVENTIONS(aa_points: int) -> IEffectBuilder:
        def reuse_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == WardenAbilities.tunares_watch \
                    or target_ability.locator == WardenAbilities.natures_renewal:
                return -2.0 * aa_points
            return None

        assert 1 <= aa_points <= 5
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_REUSE, reuse_modifier)


class FuryEffects:
    @staticmethod
    @named_effect
    def FOCUS_HIBERNATION() -> IEffectBuilder:
        return EffectBuilder(FuryAbilities.hibernation).add(EffectType.DURATION, -2.0)

    @staticmethod
    @named_effect
    def ENHANCE_DEATH_SWARM(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(FuryAbilities.death_swarm).add(EffectType.DURATION, -1.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_FERAL_TENACITY(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(FuryAbilities.feral_tenacity).add(EffectType.BASE_REUSE, -18.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_PACT_OF_THE_CHEETAH(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(FuryAbilities.pact_of_the_cheetah).add(EffectType.DURATION, 3.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_TEMPEST(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(FuryAbilities.raging_whirlwind).add(EffectType.DURATION, -0.8 * aa_points)

    @staticmethod
    @named_effect
    def STORMBEARERS_FURY(aa_points: int) -> IEffectBuilder:
        reuse = [75.0, 45.0, 25.0][aa_points - 1]
        return EffectBuilder(FuryAbilities.stormbearers_fury).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def OVERGROWING_SPINES_2() -> IEffectBuilder:
        return EffectBuilder(DruidAbilities.sylvan_touch).set(EffectType.RESET_ABILITY, FuryAbilities.porcupine)

    @staticmethod
    @named_effect
    def PACT_OF_NATURE() -> IEffectBuilder:
        return EffectBuilder(FuryAbilities.pact_of_nature).set(EffectType.GRANT_ABILITY, CommonerAbilities.salve)


class ClericEffects:
    @staticmethod
    @named_effect
    def ENHANCE_DIVINE_GUIDANCE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(ClericAbilities.divine_guidance).add(EffectType.DURATION, 0.4 * aa_points)


class InquisitorEffects:
    @staticmethod
    @named_effect
    def FANATICS_PROTECTION(aa_points: int) -> IEffectBuilder:
        reuse = [18.0, 12.0, 6.0][aa_points - 1]
        return EffectBuilder(InquisitorAbilities.fanatics_protection).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def FANATICS_FOCUS() -> IEffectBuilder:
        return EffectBuilder(InquisitorAbilities.fanaticism).add(EffectType.BASE_CASTING, 3.0)

    @staticmethod
    @named_effect
    def ENHANCE_REDEMPTION(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(InquisitorAbilities.redemption).add(EffectType.BASE_REUSE, -18.0 * aa_points)


class ShamanEffects:
    @staticmethod
    @named_effect
    def WITCHDOCTORS_HERBAL_RECIPE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 8
        return EffectBuilder(MysticAbilities.ebbing_spirit).add(EffectType.BASE_REUSE, aa_points * -1.25)

    @staticmethod
    @named_effect
    def ENHANCE_ANCESTRAL_CHANNELING(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(ShamanAbilities.ancestral_channeling).add(EffectType.DURATION, 0.1 * aa_points)


class MysticEffects:
    @staticmethod
    @named_effect
    def ENHANCE_CURE_CURSE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        casting_mod = [-0.21, -0.39, -0.53, -0.65, -0.75][aa_points - 1]
        return EffectBuilder(PriestAbilities.cure_curse).add(EffectType.BASE_CASTING, casting_mod)

    @staticmethod
    @named_effect
    def FOCUS_BOLSTER() -> IEffectBuilder:
        return EffectBuilder(MysticAbilities.bolster).add(EffectType.DURATION, 12.0)

    @staticmethod
    @named_effect
    def ENHANCE_BOLSTER(aa_points: int) -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MysticAbilities.bolster or target_ability.locator == MysticAbilities.ancestral_bolster:
                return 2.0 * aa_points
            return None

        assert 1 <= aa_points <= 5
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def STRENGTH_OF_THE_ANCESTORS() -> IEffectBuilder:
        durations = {
            AbilityTier.Ancient.value: 32.0,
            AbilityTier.Grandmaster.value: 26.0,
            AbilityTier.Master.value: 20.0,
            AbilityTier.Expert.value: 16.0,
            AbilityTier.Adept.value: 12.0,
            AbilityTier.Journeyman.value: 9.0,
            AbilityTier.Apprentice.value: 6.0,
        }

        def duration_modifier(source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MysticAbilities.bolster or target_ability.locator == MysticAbilities.ancestral_bolster:
                source_ability = source.ability()
                tier = source_ability.census.tier_int
                return durations[tier]
            return None

        def casting_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == MysticAbilities.bolster or target_ability.locator == MysticAbilities.ancestral_bolster:
                return 4.0
            return None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier).set(EffectType.BASE_CASTING, casting_modifier)

    @staticmethod
    @named_effect
    def SPIRITUAL_STABILITY() -> IEffectBuilder:
        return EffectBuilder(MysticAbilities.immunization).set(EffectType.BASE_CASTING, 0.5).set(EffectType.BASE_REUSE, 90.0)

    @staticmethod
    @named_effect
    def RITUAL_OF_ALACRITY() -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.CASTING_SPEED, 33.0).add(EffectType.REUSE_SPEED, 33.0)


class DefilerEffects:
    @staticmethod
    @named_effect
    def ENHANCE_MAELSTROM(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(DefilerAbilities.maelstrom).add(EffectType.DURATION, -3.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_SPIRITIAL_CIRCLE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(DefilerAbilities.spiritual_circle).add(EffectType.DURATION, 1.0 * aa_points)

    @staticmethod
    @named_effect
    def CURSEWEAVING() -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == DefilerAbilities.abomination \
                    or target_ability.locator == DefilerAbilities.bane_of_warding \
                    or target_ability.locator == DefilerAbilities.abhorrent_seal:
                return base_value * 0.2
            return None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def WRAITHWALL(aa_points: int) -> IEffectBuilder:
        reuse = [30.0, 20.0, 10.0][aa_points - 1]
        return EffectBuilder(DefilerAbilities.wraithwall).set(EffectType.BASE_REUSE, reuse)


class BardEffects:
    @staticmethod
    @named_effect
    def IMPROVED_REFLEXES(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 8
        return EffectBuilder(BardAbilities.bladedance).add(EffectType.BASE_REUSE, -25.0 * aa_points)


class DirgeEffects:
    @staticmethod
    @named_effect
    def ENHANCE_CACOPHONY_OF_BLADES(aa_points: int) -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == DirgeAbilities.cacophony_of_blades or target_ability.locator == DirgeAbilities.peal_of_battle:
                return 1.0 * aa_points
            return None

        assert 1 <= aa_points <= 5
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def UNSTOPPING_ENCORE(aa_points: int) -> IEffectBuilder:
        duration_mult = [0.33, 0.66, 1.0][aa_points - 1]
        return EffectBuilder(DirgeAbilities.exuberant_encore).mul(EffectType.DURATION, duration_mult)

    @staticmethod
    @named_effect
    def ENHANCE_SHROUD(aa_points: int) -> IEffectBuilder:
        return EffectBuilder(BardAbilities.shroud).add(EffectType.BASE_CASTING, -0.3 * aa_points)

    @staticmethod
    @named_effect
    def ECHOING_HOWL(aa_points: int) -> IEffectBuilder:
        reuse = [60.0, 40.0, 20.0][aa_points - 1]
        return EffectBuilder(DirgeAbilities.echoing_howl).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def ENHANCE_ORATION_OF_SACRIFICE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(DirgeAbilities.oration_of_sacrifice).add(EffectType.BASE_REUSE, -1.0 * aa_points)

    @staticmethod
    @named_effect
    def CONTROLLING_CONFRONTATIONS(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(DirgeAbilities.confront_fear).add(EffectType.BASE_REUSE, -1.0 * aa_points)


class TroubadorEffects:
    @staticmethod
    @named_effect
    def ENHANCE_CHEAP_SHOT(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(ScoutAbilities.cheap_shot).add(EffectType.DURATION, aa_points * 0.2)

    @staticmethod
    @named_effect
    def HARMONIZATION() -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            return base_value * 0.10 * (target_ability.ext.harmonize if target_ability.ext.harmonize else 0.0)

        return EffectBuilder(EffectScopeType.GROUP).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def CONTINUED_PERFORMANCE(aa_points: int) -> IEffectBuilder:
        duration_mult = [0.33, 0.66, 1.0][aa_points - 1]
        return EffectBuilder(TroubadorAbilities.bagpipe_solo).mul(EffectType.DURATION, duration_mult)

    @staticmethod
    @named_effect
    def REVERBERATION(aa_points: int) -> IEffectBuilder:
        reuse = [60.0, 40.0, 20.0][aa_points - 1]
        return EffectBuilder(TroubadorAbilities.reverberation).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def ENHANCE_SINGING_SHOT(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(TroubadorAbilities.singing_shot).add(EffectType.DURATION, 0.5 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_PERFECTION_OF_THE_MAESTRO(aa_points: int) -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == TroubadorAbilities.perfection_of_the_maestro or target_ability.locator == TroubadorAbilities.maestros_harmony:
                return 2.0 * aa_points
            return None

        assert 1 <= aa_points <= 5
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)


class ThugEffects:
    @staticmethod
    @named_effect
    def TRAUMATIC_SWIPE() -> IEffectBuilder:
        return EffectBuilder(EffectScopeType.NON_PLAYER).mul(EffectType.REUSE_SPEED, -50.0)


class BrigandEffects:
    @staticmethod
    @named_effect
    def TENURE() -> IEffectBuilder:
        def duration_modifier(_source: EffectTarget, target: EffectTarget, base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.census.type == AbilityType.arts:
                return base_value * 0.1
            return None

        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def BLINDING_DUST(aa_points: int) -> IEffectBuilder:
        reuse = [180.0, 120.0, 60.0][aa_points - 1]
        return EffectBuilder(BrigandAbilities.blinding_dust).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def FOCUS_DISPATCH() -> IEffectBuilder:
        return EffectBuilder(BrigandAbilities.dispatch).add(EffectType.DURATION, 7.0)

    @staticmethod
    @named_effect
    def RIOT() -> IEffectBuilder:
        durations = {
            AbilityTier.Ancient.value: 11.0,
            AbilityTier.Grandmaster.value: 10.0,
            AbilityTier.Master.value: 9.0,
            AbilityTier.Expert.value: 8.0,
            AbilityTier.Adept.value: 8.0,
            AbilityTier.Journeyman.value: 7.0,
            AbilityTier.Apprentice.value: 7.0,
        }

        def duration_modifier(source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == BrigandAbilities.double_up:
                source_ability = source.ability()
                tier = source_ability.census.tier_int
                return durations[tier]
            return None

        return EffectBuilder(EffectScopeType.PLAYER).set(EffectType.DURATION, duration_modifier)

    @staticmethod
    @named_effect
    def CRIMSON_SWATH() -> IEffectBuilder:
        durations = {
            AbilityTier.Ancient.value: 30.0 - 28.0,
            AbilityTier.Grandmaster.value: 30.0 - 26.0,
            AbilityTier.Master.value: 30.0 - 25.0,
            AbilityTier.Expert.value: 30.0 - 24.0,
            AbilityTier.Adept.value: 30.0 - 23.0,
            AbilityTier.Journeyman.value: 30.0 - 22.0,
            AbilityTier.Apprentice.value: 30.0 - 20.0,
        }

        def reuse_modifier(source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == BrigandAbilities.forced_arbitration or target_ability.locator == BrigandAbilities.barroom_negotiation:
                source_ability = source.ability()
                tier = source_ability.census.tier_int
                return durations[tier]
            return None

        def priority_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == BrigandAbilities.forced_arbitration:
                return AbilityPriority.COMBO
            return None

        return EffectBuilder(EffectScopeType.PLAYER).set(EffectType.BASE_REUSE, reuse_modifier).set(EffectType.PRIORITY, priority_modifier)


class EnchanterEffects:
    @staticmethod
    @named_effect
    def FOCUS_PEACE_OF_MIND() -> IEffectBuilder:
        return EffectBuilder(EnchanterAbilities.peace_of_mind).add(EffectType.DURATION, 5.0)

    @staticmethod
    @named_effect
    def CHANNELED_FOCUS(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(EnchanterAbilities.channeled_focus).add(EffectType.BASE_REUSE, -15.0 * aa_points)

    @staticmethod
    @named_effect
    def ACADEM(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(CoercerAbilities.intellectual_remedy).mul(EffectType.DURATION, 0.1 * aa_points)


class IllusionistEffects:
    @staticmethod
    @named_effect
    def ENHANCE_CURE_MAGIC_ILLUSIONIST() -> IEffectBuilder:
        return EffectBuilder(MageAbilities.cure_magic).set(EffectType.BASE_CASTING, 0.0)

    @staticmethod
    @named_effect
    def HASTENED_MANA_FLOW(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(EnchanterAbilities.mana_flow).mul(EffectType.DURATION, -0.1 * aa_points)

    @staticmethod
    @named_effect
    def CHROMATIC_ILLUSION(aa_points: int) -> IEffectBuilder:
        reuse = [30.0, 20.0, 10.0][aa_points - 1]
        return EffectBuilder(IllusionistAbilities.chromatic_illusion).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def ENHANCE_FLASH_OF_BRILLIANCE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(IllusionistAbilities.flash_of_brilliance).add(EffectType.DURATION, 3.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_SAVANTE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(IllusionistAbilities.savante).add(EffectType.DURATION, 5.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_ILLUSORY_ALLIES(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(IllusionistAbilities.phantom_troupe).add(EffectType.DURATION, 1.0 * aa_points).add(EffectType.BASE_REUSE, -6.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_SPEECHLESS(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(IllusionistAbilities.speechless).add(EffectType.DURATION, 0.3 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_ENTRANCE(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(IllusionistAbilities.entrance).add(EffectType.DURATION, 1.5 * aa_points).add(EffectType.BASE_CASTING, -0.1 * aa_points)


class CoercerEffects:
    @staticmethod
    @named_effect
    def ENHANCE_MANA_FLOW(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(EnchanterAbilities.mana_flow).add(EffectType.BASE_REUSE, -2.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_ABSORB_MAGIC(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(MageAbilities.absorb_magic).add(EffectType.BASE_REUSE, -1.0 * aa_points)

    @staticmethod
    @named_effect
    def ETHER_BALANCE(aa_points: int) -> IEffectBuilder:
        reuse = [180.0, 120.0, 60.0][aa_points - 1]
        return EffectBuilder(CoercerAbilities.ether_balance).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def MIND_CONTROL(aa_points: int) -> IEffectBuilder:
        reuse = [180.0, 135.0, 90.0][aa_points - 1]
        return EffectBuilder(CoercerAbilities.mind_control).set(EffectType.BASE_REUSE, reuse)

    @staticmethod
    @named_effect
    def ENHANCE_CHANNEL(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(CoercerAbilities.channel).add(EffectType.BASE_REUSE, -60.0 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_STUPEFY(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(CoercerAbilities.stupefy).add(EffectType.BASE_CASTING, -0.1 * aa_points)

    @staticmethod
    @named_effect
    def HASTENED_MANA(aa_points: int) -> IEffectBuilder:
        def reuse_modifier(_source: EffectTarget, target: EffectTarget, _base_value: TEffectValue) -> Optional[TEffectValue]:
            target_ability = target.ability()
            if target_ability.locator == EnchanterAbilities.mana_cloak or target_ability.locator == EnchanterAbilities.aura_of_power:
                return -12.0 * aa_points
            return None

        assert 1 <= aa_points <= 5
        return EffectBuilder(EffectScopeType.PLAYER).add(EffectType.BASE_REUSE, reuse_modifier)

    @staticmethod
    @named_effect
    def SIRENS_STARE() -> IEffectBuilder:
        return EffectBuilder(EnchanterAbilities.mana_flow).set(EffectType.BASE_CASTING, 0.0)

    @staticmethod
    @named_effect
    def MIND_MASTERY() -> IEffectBuilder:
        return EffectBuilder(CoercerAbilities.manaward).set(EffectType.BASE_CASTING, 0.0).add(EffectType.BASE_REUSE, -120.0)


class ConjurorEffects:
    @staticmethod
    @named_effect
    def FOCUS_ELEMENTAL_TOXICITY() -> IEffectBuilder:
        return EffectBuilder(SummonerAbilities.elemental_toxicity).add(EffectType.DURATION, 5.0)

    @staticmethod
    @named_effect
    def ENHANCE_ELEMENTAL_TOXICITY(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 10
        return EffectBuilder(SummonerAbilities.elemental_toxicity).add(EffectType.DURATION, 0.4 * aa_points)

    @staticmethod
    @named_effect
    def FOCUS_SACRIFICE() -> IEffectBuilder:
        return EffectBuilder(ConjurorAbilities.sacrifice).mul(EffectType.DURATION, -0.25)

    @staticmethod
    @named_effect
    def SACRIFICIAL_LAMB(aa_points: int) -> IEffectBuilder:
        assert 1 <= aa_points <= 5
        return EffectBuilder(ConjurorAbilities.sacrifice).mul(EffectType.DURATION, -0.05 * aa_points)

    @staticmethod
    @named_effect
    def ENHANCE_CURE_MAGIC_CONJUROR() -> IEffectBuilder:
        return EffectBuilder(MageAbilities.cure_magic).set(EffectType.BASE_CASTING, 0.0)
