from typing import List, Dict, Union, Any

import regex as re

from rka.components.io.log_service import LogLevel, LogService
from rka.eq2.master.game.ability import AbilityEffectTarget, CombatRequirement, EffectLifeFlags, AbilityType
from rka.eq2.master.game.ability.ability_data import AbilityExtConsts, AbilityCensusConsts
from rka.eq2.master.game.census import CensusTopFields
from rka.log_configs import LOG_ABILITY_BUILDER
from rka.services.api.census import TCensusStruct

logger = LogService(LOG_ABILITY_BUILDER)


class AbilityCensusEffectParser:
    rgx_damage = [
        r'inflict.*\d+.*damage',
        r'reduces target\'s health to .*\d+',
    ]

    rgx_damage_dot = [
        r'inflict.*\d+.*damage.*every',
        r'increases threat.*\d+.*every',
    ]

    rgx_damage_aoe = [
        r'inflict.*\d+.*damage.*area of effect',
        r'(increases|decreases) threat.*\d+.*area of effect',
    ]

    rgx_aggro_control = [
        r'decreases threat.*\d+',
        r'increases threat.*\d+',
    ]

    rgx_heals = [
        r'wards.* against',
        r'heals.* \d+.*(?!of the damage the target receives)',
        r'restores.* health',
    ]

    rgx_reactive_heals = [
        r'heals.* \d+.* damage.* receive',
        r'restores.* damage.* receive',
    ]

    rgx_heals_hot = [
        r'wards.* against',
        r'heals.* \d+.* every',
        r'restores.* health.* every',
    ]

    rgx_power = [
        r'increases? power',
        r'restores?.* power',
    ]

    rgx_buff = [
        r'(improves|increase).* (double|fervor|haste|multi|ability|dps|crit|critical|mitigation|health|chance to block|trigger chance).*by \d+',
        r'(improves|increase).* (max power|agi|str|sta|wis|int|attributes|movement|weapon damage|hate gain|aggression|healing received).*by \d+',
        r'(improves|increase).* (hp regen|mana regen|number of ticks|crushing|piercing|slashing|ranged|autoattack|flurry).*by \d+',
        r'(improves|increase).* (focus|disruption|subjugation|ministration|ordination|healing|damage).*by \d+',
        r'(reduce|decrease).* (slow effect|base reuse|power cost|effective level|warding of).*by \d+',
        r'grants the group spell double attack',
        r'greatly increases maximum health',
        r'adds trigger chance',
        r'adds.*\d+.*to base',
        r'gives.*\d+.*(strikethrough)',
        r'caster.*(riposte|dodge|block).*\d+',
        r'(caster|target|group).* immune',
        r'grants immunity to',
        r'has.*\d+.*chance of having',
        r'reduces.*damage done to',
        r'will absorb.*damage',
        r'applies stoneskin',
        r'chance to intercept',
        r'allows.*for maximum damage',
        r'\d+%.*(dodge|parry|block) chance',
        r'feigns death',
        r'dispels.*\d+.*(curse|hostile)',
        r'prevents.*from being interrupted',
        r'resurrects',
        r'clears the reuse',
        r'lose.* less power',
        r'prevents druid delayed resurrection sickness',
        r'your next damage spell is \d+% more damaging',
        r'heals the target based on the amount',
        r'(improves|increase).* (potency).*by \d+',
    ]

    rgx_debuff = [
        r'(reduce|decrease).* (mitigation|agi|str|sta|wis|int|defense|parry|deflection|ability|haste|dps|fervor|weapon damage).*by \d+',
        r'(reduce|decrease).* (crushing|piercing|slashing|ranged|power of target|auto-attack|damage done by the next spell).*by \d+',
        r'(reduce|decrease).* (trigger percentage|max(imum)? health|autoattack).*by \d+',
        r'(increase).* (resistibility).*by \d+',
        r'(increase).* (agi|str|sta|wis|int).*by 0.0',
        r'grants a very high chance to force the target to miss their attacks',
        r'target will have their chance to hit with a weapon lowered',
        r'target will reduce the chance for one of their weapons\' auto-attack',
        r'increase.*damage done to target',
        r'reduces non-damage hostile spell duration',
        r'(reduce|decrease).* (combat mitigation|potency).*by \d+',
        r'(mesmerize|slow|daze|stifle|stuns|roots).*target',
        r'appl(y|ies) knockdown',
        r'forces target to',
        r'prevents target from changing',
    ]

    rgx_neutral = [
        r'(interrupt|blurs|throws).* target',
        r'dispels.*\d+.*beneficial',
        r'\d% of target\'s power consumed will also be drained',
        r'drains.* power for each effect dispelled',
        r'chance of making an additional attempt',
        r'increases the group\'s potency',
        r'prevents aoe',
        r'increases the damage of',
        r'teleport',
        r'transfers.* threat',
        r'(stifles|slows|roots|dazes) (caster|pet)',
        r'increases the power cost of all abilities',
        r'consumes \d+% of the caster\'s health instantly and every tick',
    ]

    rgx_combat_required = [
        r'must be engaged in combat',
    ]

    rgx_combat_prohibited = [
        r'cannot be cast during combat',
        r'this effect cannot be cast during combat',
    ]

    rgx_deathsave = [
        r'on death this spell',
    ]

    rgx_triggers_effect = [
        r'on (a|any) (combat|melee|hostile|spell)',
        r'when a combat art is',
        r'on a hit this spell',
        r'when damaged',
        r'when any damage is received',
    ]

    rgx_sub_effect = [
        r'appl(y|ies).*lasts',
        r'appl(y|ies).*on termination',
        r'applies .*\.',
        r'when target falls',
    ]

    rgx_summmons_pets = [
        r'summons',
    ]

    rgx_cant_modify = [
        r'cannot be modified',
    ]

    rgx_descriptions = [
        r'this attack may not be ',
        r'time of barroom negotiation',
        r'protects the caster\'s group members from enemy barrages',
        r'only wards damage that would lower',
        r'but this ability may not doublecast',
        r'(increases|reduces|decreases).* (success chance|durability|progress)',
        r'increases damage as mana is spent',
        r'when this spell wears off',
        r'damage of this ability scales',
        r'already active',
        r'not stack from',
        r'may stack up',
        r'increases the further',
        r'disables while under',
        r'if profession',
        r'are used within',
        r'if target is',
        r'will not cause enemies to attack',
        r'if (fighter|scout|mage|priest)',
        r'if level above',
        r'must be in front of',
        r'must be flanking or behind',
        r'meters away',
        r'if target is closer',
        r'does not receive',
        r'shapechanges',
        r'loses an increment',
        f'may increment',
        r'starts at.* increments',
        r'chance to dispel',
        r'enlarges',
        r'cannot cast',
        r'for each successful',
        r'does not trigger if',
        r'may trigger',
        r'can only trigger',
        r'only be triggered',
        r'triggers when',
        r'may only benefit',
        r'has a \d+% chance',
        r'must be hated',
        r'multiplied by the',
        r'multiplies the',
        r'if (under|above|over|at|between|not)',
        r'if (one|any) of the following',
        r'must be active',
        r'have one of each archtype',
        r'requires membership',
        r'if target is not epic',
        r'epic targets gain an immunity',
        r'does not affect epic targets',
        r'if target is standard or weaker',
        r'begins a heroic opportunity',
        r'this ability may be cast',
        r'ability terminates at',
        r'cannot be critically',
        r'grants a total',
        r'if aim or thrown weapon',
        r'requires bow or aim',
        r'if weapon equipped',
        r'resistibility increases against',
        r'dispelled when',
        r'adds hate positions',
        r'deals more to',
        r'ascension combo',
        r'you cannot cast this spell',
        r'regenerates',
        r'monitors',
        r'\[none\]',
        r'raid encounters',
        r'prevents you from recasting',
        r'certain creature strengths only',
        r'reveals the health',
        r'both accomplice and partners',
        r'cannot be cast',
        r'causes an unstable vortex',
    ]

    compiled_rgx: Dict[str, Any] = dict()

    @staticmethod
    def __match(effect: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if pattern not in AbilityCensusEffectParser.compiled_rgx:
                compiled_pattern = re.compile(pattern)
                AbilityCensusEffectParser.compiled_rgx[pattern] = compiled_pattern
            else:
                compiled_pattern = AbilityCensusEffectParser.compiled_rgx[pattern]
            if compiled_pattern.search(effect):
                return True
        return False

    @staticmethod
    def __assert(effect: str, condition: bool):
        if not condition:
            print(f'assert failed for "{effect}"')
        assert condition, effect

    @staticmethod
    def parse_census_effects(ext_data: AbilityExtConsts, census_data: TCensusStruct, census_object: AbilityCensusConsts):
        if CensusTopFields.effect_list.value not in census_data:
            logger.info(f'{ext_data.ability_name} has no effects list in census')
            return
        # noinspection PyTypeChecker
        effects_list: List[Dict[str, Union[str, int]]] = census_data[CensusTopFields.effect_list.value]
        is_triggered = False
        indent_trigger = -1
        is_subeffect = False
        indent_subeffect = -1
        is_on_death = False
        indent_on_death = -1
        cant_modify = False

        for effect_d in effects_list:
            effect_descr = str(effect_d['description']).lower()
            effect_indent = int(effect_d['indentation'])

            # reset some flags for the previous effect
            if effect_indent <= indent_trigger:
                is_triggered = False
                indent_trigger = -1
            if effect_indent <= indent_subeffect:
                is_subeffect = False
                indent_subeffect = -1
            if effect_indent <= indent_on_death:
                is_on_death = False
                indent_on_death = -1

            known_effects = 0

            target_enemy = ext_data.effect_target in [AbilityEffectTarget.Enemy, AbilityEffectTarget.Encounter, AbilityEffectTarget.AOE]
            target_ally = ext_data.effect_target in [AbilityEffectTarget.GroupMember, AbilityEffectTarget.Ally, AbilityEffectTarget.Group,
                                                     AbilityEffectTarget.Raid, AbilityEffectTarget.Self]
            target_self = ext_data.effect_target in [AbilityEffectTarget.Self]

            is_damage = False
            is_damage_aoe = False
            is_damage_dot = False
            is_heals = False
            is_heals_hot = False
            is_power = False
            is_buff = False
            is_debuff = False
            is_combat_only = False
            is_noncombat_only = False
            is_aggro_control = False
            is_summon = False

            # parse effect
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_combat_required):
                is_combat_only = True
                known_effects += 1
            elif AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_combat_prohibited):
                is_noncombat_only = True
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_deathsave):
                is_on_death = True
                indent_on_death = effect_indent
                known_effects += 1
            elif AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_triggers_effect):
                is_triggered = True
                indent_trigger = effect_indent
                known_effects += 1
            elif AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_sub_effect):
                is_subeffect = True
                indent_subeffect = effect_indent
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_damage):
                is_damage = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_damage_aoe):
                is_damage_aoe = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_damage_dot):
                is_damage_dot = True
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_neutral):
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_heals):
                is_heals = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_heals_hot):
                is_heals_hot = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_power):
                is_power = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_reactive_heals):
                is_heals = False
                is_buff = True
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_debuff):
                is_debuff = True
                known_effects += 1
            elif AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_buff):
                is_buff = True
                known_effects += 1

            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_summmons_pets):
                is_summon = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_aggro_control):
                is_aggro_control = True
                known_effects += 1
            if AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_cant_modify):
                cant_modify = True
                known_effects += 1

            if not known_effects and AbilityCensusEffectParser.__match(effect_descr, AbilityCensusEffectParser.rgx_descriptions):
                continue

            # set Ext fields
            if target_ally and is_debuff:
                is_debuff = False
            if target_self and is_damage and not is_damage_aoe:
                is_damage = False

            if is_combat_only:
                AbilityCensusEffectParser.__assert(effect_descr, not is_noncombat_only)
                ext_data.combat_requirement = CombatRequirement.NonCombatOnly
            if is_noncombat_only:
                AbilityCensusEffectParser.__assert(effect_descr, not is_combat_only)
                ext_data.combat_requirement = CombatRequirement.CombatOnly
            if is_debuff:
                if is_triggered:
                    ext_data.has_debuff = EffectLifeFlags.Triggered
                elif is_subeffect:
                    ext_data.has_debuff = EffectLifeFlags.Subeffect
                else:
                    AbilityCensusEffectParser.__assert(effect_descr, target_enemy)
                    ext_data.has_debuff = EffectLifeFlags.Ability
            if is_buff:
                if is_triggered:
                    ext_data.has_buff = EffectLifeFlags.Triggered
                elif is_subeffect:
                    ext_data.has_buff = EffectLifeFlags.Subeffect
                else:
                    ext_data.has_buff = EffectLifeFlags.Ability
            if is_damage:
                if is_triggered:
                    ext_data.has_damage |= EffectLifeFlags.Triggered
                elif is_subeffect:
                    if not target_enemy and not is_damage_aoe:
                        ext_data.has_damage |= EffectLifeFlags.Subeffect
                    else:
                        logger.warn(f'{ext_data.ability_id} - fail: not target_enemy and not is_damage_aoe')
                else:
                    if not target_enemy and not is_damage_aoe:
                        logger.warn(f'{ext_data.ability_id} - fail: target_enemy or is_damage_aoe')
                    ext_data.has_damage |= EffectLifeFlags.Ability
                if is_damage_dot:
                    ext_data.has_damage |= EffectLifeFlags.OverTime
            if is_heals and not is_on_death:
                if is_triggered:
                    ext_data.has_heals |= EffectLifeFlags.Triggered
                elif is_subeffect:
                    ext_data.has_heals |= EffectLifeFlags.Subeffect
                else:
                    ext_data.has_heals |= EffectLifeFlags.Ability
                if is_heals_hot:
                    ext_data.has_heals |= EffectLifeFlags.OverTime
            if is_power and not is_on_death:
                if is_triggered:
                    ext_data.has_power = EffectLifeFlags.Triggered
                elif is_subeffect:
                    ext_data.has_power = EffectLifeFlags.Subeffect
                else:
                    ext_data.has_power = EffectLifeFlags.Ability
            if is_summon:
                ext_data.has_summons = True
            if is_aggro_control:
                ext_data.has_aggro = True

            if not known_effects:
                logger.warn(f'{ext_data.ability_name} has unknown effect: {effect_indent * "    "}"{effect_descr}"')
                continue

        # calculate Harmonization
        rule = None
        if census_object.duration > 0 and not ext_data.cannot_modify:
            heals_ability = bool(ext_data.has_heals & EffectLifeFlags.Ability)
            heals_overtime = bool(ext_data.has_heals & EffectLifeFlags.OverTime)
            heals_triggered = bool(ext_data.has_heals & EffectLifeFlags.Triggered)

            dmg_ability = bool(ext_data.has_damage & EffectLifeFlags.Ability)
            dmg_overtime = bool(ext_data.has_damage & EffectLifeFlags.OverTime)
            dmg_subeffect = bool(ext_data.has_damage & EffectLifeFlags.Subeffect)

            debuff_ability = bool(ext_data.has_debuff & EffectLifeFlags.Ability)
            debuff_subeffect = bool(ext_data.has_debuff & EffectLifeFlags.Subeffect)

            buff_ability = bool(ext_data.has_buff & EffectLifeFlags.Ability)
            buff_subeffect = bool(ext_data.has_buff & EffectLifeFlags.Subeffect)

            # problem: when buff subeffect is modified, the same modification apply to ability, except when its not modifiable
            # change the entire parsing to make effect tree; subeffects need to propagate harmonization effect
            qualify_as_spell = census_object.type in [AbilityType.ascension, AbilityType.spells]
            qualify_as_ca = census_object.type == AbilityType.arts
            healing_ability = ((heals_overtime or heals_ability) and not heals_triggered)
            damage_ability = dmg_ability or dmg_subeffect
            beneficial_ability = buff_ability or buff_subeffect or census_object.beneficial
            hostile_ability = debuff_ability or debuff_subeffect or not census_object.beneficial

            if ext_data.has_summons and census_object.beneficial:
                rule = 1
                harmonize = 1.0
            elif ext_data.has_summons and not census_object.beneficial:
                rule = 2
                harmonize = 0.0
            elif dmg_overtime:
                rule = 3
                harmonize = -1.0
            elif qualify_as_spell and healing_ability:
                rule = 4
                harmonize = -1.0
            elif (damage_ability or hostile_ability) and buff_ability:
                rule = 5
                harmonize = 0.0
            elif qualify_as_spell and damage_ability and not beneficial_ability:
                rule = 6
                harmonize = -1.0
            elif qualify_as_ca and (healing_ability or ext_data.has_aggro):
                rule = 7
                harmonize = 0.0
            elif buff_subeffect and cant_modify:
                rule = 8
                harmonize = 0.0
            elif buff_subeffect and not cant_modify:
                rule = 9
                harmonize = 1.0
            else:
                rule = -1
                harmonize = 1.0
        else:
            harmonize = None

        if ((ext_data.has_power != EffectLifeFlags.NA) and not ext_data.power) or ((ext_data.has_power == EffectLifeFlags.NA) and ext_data.power):
            logger.warn(f'Power missmatch: {ext_data.ability_id} {ext_data.has_power} {ext_data.power}')

        if logger.get_level() <= LogLevel.DEBUG:
            if harmonize is not None:
                ext_harmonize = ext_data.harmonize if ext_data.harmonize is not None else 0
                compare_str = f'{ext_data.ability_id[:15]:15}, {harmonize:4} vs {ext_harmonize:4}:'
                data_str = f'{ext_data.has_damage}, {ext_data.has_heals}, {ext_data.has_buff}, {ext_data.has_debuff}, ' \
                           f'{ext_data.has_power}, {ext_data.has_summons}, {census_object.beneficial}, {rule}, {cant_modify}, ' \
                           f'{ext_data.has_aggro}, {census_object.type}'
            else:
                compare_str = f'{ext_data.ability_id[:15]:15}, {harmonize} vs {ext_data.harmonize}:'
                data_str = None
            if harmonize != ext_data.harmonize:
                print(f'Harmonization missmatch: {compare_str} {data_str}')
            elif harmonize is not None:
                print(f'Harmonization match: {compare_str} {data_str}')
        else:
            if harmonize != ext_data.harmonize:
                logger.warn(f'Harmonization missmatch: {ext_data.ability_name}: excel {ext_data.harmonize} vs calculated {harmonize}')
