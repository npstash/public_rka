from __future__ import annotations

import copy
import datetime
from enum import auto
from json.encoder import JSONEncoder
from typing import Optional, Dict, Any, List

from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.rka_constants import PARSE_CENSUS_EFFECTS
from rka.eq2.master.game.ability import AbilityEffectTarget, AbilityPriority, AbilityType, HOIcon, CombatRequirement, EffectLifeFlags, AbilitySpecial, AbilityTier
from rka.eq2.master.game.census import CensusTopFields, CensusNestedFields
from rka.eq2.master.game.player import PlayerStatus
from rka.services.api.census import TCensusStruct
from rka.util.util import NameEnum


class ExtFields(NameEnum):
    # general information
    classname = auto()
    ability_id = auto()
    ability_name = auto()
    shared_name = auto()
    effect_name = auto()
    priority = auto()
    priority_adjust = auto()
    effect_target = auto()
    has_census = auto()
    cannot_modify = auto()
    # special ability types
    cure = auto()
    power = auto()
    drain = auto()
    interrupt = auto()
    dispel = auto()
    stun = auto()
    stifle = auto()
    daze = auto()
    mesmerize = auto()
    fear = auto()
    root = auto()
    move = auto()
    resurrect = auto()
    deathsave = auto()
    ward_expires = auto()
    # duration traits
    harmonize = auto()
    maintained = auto()
    # casting allowances
    cast_when_casting = auto()
    cast_when_reusing = auto()
    cast_when_alive = auto()
    cast_when_dead = auto()
    cast_in_combat = auto()
    cast_min_state = auto()
    # resetting and expiring
    expire_on_zone = auto()
    expire_on_death = auto()
    expire_on_attack = auto()
    expire_on_move = auto()
    reset_on_readyup = auto()
    # UI notifications
    log_severity = auto()
    timer_severity = auto()


class AbilityExtConsts:
    def __init__(self):
        # general information
        self.__orig_ability_ext_data_ref: Optional[Dict[str, str]] = None
        self.classname: Optional[str] = None
        self.ability_id: Optional[str] = None
        self.ability_name: Optional[str] = None
        self.shared_name: Optional[str] = None
        self.effect_name: Optional[str] = None
        self.priority: Optional[int] = None
        self.priority_adjust: Optional[int] = None
        self.effect_target: Optional[AbilityEffectTarget] = None
        self.has_census: Optional[bool] = None
        self.cannot_modify: Optional[bool] = None
        # special ability types
        self.cure: Optional[bool] = None
        self.power: Optional[bool] = None
        self.drain: Optional[bool] = None
        self.interrupt: Optional[bool] = None
        self.dispel: Optional[bool] = None
        self.stun: Optional[bool] = None
        self.stifle: Optional[bool] = None
        self.daze: Optional[bool] = None
        self.mesmerize: Optional[bool] = None
        self.fear: Optional[bool] = None
        self.root: Optional[bool] = None
        self.move: Optional[bool] = None
        self.resurrect: Optional[bool] = None
        self.deathsave: Optional[bool] = None
        self.ward_expires: Optional[bool] = None
        # duration traits
        self.harmonize: Optional[int] = None
        self.maintained: Optional[bool] = None
        # casting allowances
        self.cast_when_casting: Optional[bool] = None
        self.cast_when_reusing: Optional[bool] = None
        self.cast_when_alive: Optional[bool] = None
        self.cast_when_dead: Optional[bool] = None
        self.cast_in_combat: Optional[bool] = None
        self.cast_min_state: Optional[PlayerStatus] = None
        # resetting and expiring
        self.expire_on_zone: Optional[bool] = None
        self.expire_on_death: Optional[bool] = None
        self.expire_on_attack: Optional[bool] = None
        self.expire_on_move: Optional[bool] = None
        self.reset_on_readyup: Optional[bool] = None
        # UI notifications
        self.log_severity: Optional[Severity] = None
        self.timer_severity: Optional[Severity] = None
        # not in spreadsheet / ext fields (set manually in builder)
        self.cancel_spellcast = False
        # consistency check
        for field_name in ExtFields.__dict__.keys():
            if field_name.startswith('_'):
                continue
            assert field_name in self.__dict__.keys()
        # cached
        self.__control_effect = AbilitySpecial.NoEffect
        # calculated fields
        self.has_damage = EffectLifeFlags.NA
        self.has_heals = EffectLifeFlags.NA
        self.has_power = EffectLifeFlags.NA
        self.has_buff = EffectLifeFlags.NA
        self.has_debuff = EffectLifeFlags.NA
        self.has_summons = EffectLifeFlags.NA
        self.has_aggro = EffectLifeFlags.NA
        self.combat_requirement = CombatRequirement.Any

    def describe(self) -> Dict[str, Any]:
        result: Dict[str, Any] = dict()
        for prop_name in self.__orig_ability_ext_data_ref.keys():
            result[prop_name] = self.__getattribute__(prop_name)
        return result

    @staticmethod
    def get_ext_property(ext_field: ExtFields, values: Dict[str, Any], defaults: Optional[Dict[str, Any]]):
        prop_value = values[ext_field.value]
        if prop_value is None or prop_value == '':
            if not defaults:
                # no value has been found anywhere
                return None
            return AbilityExtConsts.get_ext_property(ext_field, defaults, None)
        if isinstance(prop_value, int):
            assert prop_value == 1 or prop_value == 0
            return prop_value == 1
        if isinstance(prop_value, float):
            return prop_value
        if isinstance(prop_value, bool):
            return prop_value
        if isinstance(prop_value, str) and (prop_value.lower() == 'true' or prop_value.lower() == 'false'):
            return prop_value.lower() == 'true'
        if ext_field == ExtFields.priority:
            return int(AbilityPriority[prop_value])
        if ext_field == ExtFields.cast_min_state:
            return PlayerStatus[prop_value]
        if ext_field == ExtFields.timer_severity or ext_field == ExtFields.log_severity:
            return Severity[prop_value]
        if ext_field == ExtFields.effect_target:
            return AbilityEffectTarget[prop_value]
        return prop_value

    def set_ext_data(self, ext_data_dict_ref: Dict[str, Any], defaults: Dict[str, Any]):
        self.__orig_ability_ext_data_ref = ext_data_dict_ref
        for ext_field in ExtFields:
            setattr(self, ext_field.value, AbilityExtConsts.get_ext_property(ext_field, ext_data_dict_ref, defaults))
        if not self.shared_name:
            self.shared_name = self.ability_name
        if not self.effect_name:
            self.effect_name = self.ability_name
        self.__calculate_special_effect()

    def make_copy(self) -> AbilityExtConsts:
        return copy.copy(self)

    def __calculate_special_effect(self):
        self.__control_effect = AbilitySpecial.NoEffect
        map_special = {
            AbilitySpecial.Stun: self.stun,
            AbilitySpecial.Stifle: self.stifle,
            AbilitySpecial.Daze: self.daze,
            AbilitySpecial.Mesmerize: self.mesmerize,
            AbilitySpecial.Fear: self.fear,
            AbilitySpecial.Root: self.root,
            AbilitySpecial.Cure: self.cure,
            AbilitySpecial.Power: self.power,
            AbilitySpecial.Drain: self.drain,
            AbilitySpecial.Interrupt: self.interrupt,
            AbilitySpecial.Dispel: self.dispel,
        }
        for special, field in map_special.items():
            if field:
                self.__control_effect |= special

    def has_special_effect(self, control_effect=AbilitySpecial.Control) -> bool:
        return self.__control_effect & control_effect

    def is_dispelable_maintained_buff(self) -> bool:
        return self.priority == AbilityPriority.DISPELLABLE_PASSIVE_BUFF

    def is_maintained_buff(self) -> bool:
        return self.priority == AbilityPriority.DISPELLABLE_PASSIVE_BUFF or self.priority == AbilityPriority.MAINTAINED_BUFF

    def is_combo(self) -> bool:
        return self.priority == AbilityPriority.COMBO

    def is_essential(self) -> bool:
        return self.priority >= AbilityPriority.MANUAL_REQUEST


class AbilityCensusConsts:
    @staticmethod
    def get_top_field_names() -> List[str]:
        field_names = [field.name for field in CensusTopFields]
        if not PARSE_CENSUS_EFFECTS:
            field_names.remove(CensusTopFields.effect_list.name)
        return field_names

    @staticmethod
    def get_mandatory_field_names() -> List[str]:
        # remove from the result the list of fields which should not cause re-downloading census data
        # (it might be missing in some records for example, or DB update is not yet desired)
        field_names = [field.name for field in CensusTopFields]
        field_names.remove(CensusTopFields.classes.name)
        field_names.remove(CensusTopFields.tier_name.name)
        field_names.remove(CensusTopFields.effect_list.name)
        return field_names

    def __init__(self):
        self.name: Optional[str] = None
        self.name_lower: Optional[str] = None
        self.casting = 0.0
        self.reuse = 0.0
        self.recovery = 0.0
        self.duration = 0.0
        self.beneficial = False
        self.max_targets = 1
        self.tier_int = AbilityTier.Apprentice.value
        self.level = 0
        self.crc: Optional[int] = None
        self.type = AbilityType.ability
        self.does_not_expire = False
        self.icon_heroic_op = HOIcon.NotAvailable

    def set_census_data(self, census_data: TCensusStruct):
        if isinstance(census_data, AbilityCensusConsts):
            self.name = census_data.name
            self.name_lower = census_data.name_lower
            self.casting = census_data.casting
            self.reuse = census_data.reuse
            self.recovery = census_data.recovery
            self.duration = census_data.duration
            self.beneficial = census_data.beneficial
            self.max_targets = census_data.max_targets
            self.tier_int = census_data.tier_int
            self.level = census_data.level
            self.crc = census_data.crc
            self.type = census_data.type
            self.does_not_expire = census_data.does_not_expire
            self.icon_heroic_op = census_data.icon_heroic_op
        else:
            self.name = census_data[CensusTopFields.name.value]
            self.name_lower = census_data[CensusTopFields.name_lower.value]
            self.casting = census_data[CensusTopFields.cast_secs_hundredths.value] / 100.0
            self.reuse = census_data[CensusTopFields.recast_secs.value]
            self.recovery = census_data[CensusTopFields.recovery_secs_tenths.value] / 100.0
            self.duration = census_data[CensusTopFields.duration.value][CensusNestedFields.max_sec_tenths.value] / 10.0
            self.does_not_expire = int(census_data[CensusTopFields.duration.value][CensusNestedFields.does_not_expire.value]) > 0
            if self.does_not_expire:
                self.duration = -1.0
            self.beneficial = census_data[CensusTopFields.beneficial.value] != 0
            self.max_targets = census_data[CensusTopFields.max_targets.value]
            self.tier_int = census_data[CensusTopFields.tier.value]
            self.level = census_data[CensusTopFields.level.value]
            self.crc = census_data[CensusTopFields.crc.value]
            self.type = AbilityType[census_data[CensusTopFields.type.value]]
            icon_heroic_op_id = census_data[CensusTopFields.icon.value][CensusNestedFields.icon_heroic_op.value]
            self.icon_heroic_op = HOIcon(icon_heroic_op_id)

    def make_copy(self) -> AbilityExtConsts:
        return copy.copy(self)


class PersistentSharedVarsFields(NameEnum):
    last_cast_time = auto()
    last_expired_time = auto()
    last_target_name = auto()
    last_effective_casting = auto()
    last_effective_reuse = auto()
    last_effective_recovery = auto()
    last_effective_duration = auto()
    last_confirm_time = auto()


class AbilitySharedVars:
    CAST_TIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

    class SharedVarsJSONEncoder(JSONEncoder):
        def default(self, o):
            if isinstance(o, AbilitySharedVars):
                return {k: v for k, v in o.__dict__.items() if k in PersistentSharedVarsFields.__members__}
            if isinstance(o, datetime.datetime):
                return o.strftime(AbilitySharedVars.CAST_TIME_FORMAT)
            return super().default(o)

    def __init__(self):
        # serializable fields start with 'last_'
        self.last_cast_time: Optional[datetime.datetime] = None
        self.last_expired_time: Optional[datetime.datetime] = None
        self.last_target_name: Optional[str] = None
        self.last_effective_casting = 0.0
        self.last_effective_reuse = 0.0
        self.last_effective_recovery = 0.0
        self.last_effective_duration = 0.0
        self.last_confirm_time = 0.0
        # fields not saved as persistent
        self.enabled_at: Optional[float] = 0.0  # None means the ability is disabled
        self.previous_last_cast_time: Optional[datetime.datetime] = None

    def set_shared_vars(self, var_data_dict: Dict):
        if var_data_dict[PersistentSharedVarsFields.last_cast_time.value] is not None:
            self.last_cast_time = datetime.datetime.strptime(var_data_dict[PersistentSharedVarsFields.last_cast_time.value], AbilitySharedVars.CAST_TIME_FORMAT)
        else:
            self.last_cast_time = None
        if var_data_dict[PersistentSharedVarsFields.last_expired_time.value] is not None:
            self.last_expired_time = datetime.datetime.strptime(var_data_dict[PersistentSharedVarsFields.last_expired_time.value], AbilitySharedVars.CAST_TIME_FORMAT)
        else:
            self.last_expired_time = None
        self.last_target_name = var_data_dict.get(PersistentSharedVarsFields.last_target_name.value, None)
        self.last_effective_casting = float(var_data_dict.get(PersistentSharedVarsFields.last_effective_casting.value, 0.0))
        self.last_effective_reuse = float(var_data_dict.get(PersistentSharedVarsFields.last_effective_reuse.value, 0.0))
        self.last_effective_recovery = float(var_data_dict.get(PersistentSharedVarsFields.last_effective_recovery.value, 0.0))
        self.last_effective_duration = float(var_data_dict.get(PersistentSharedVarsFields.last_effective_duration.value, 0.0))
        self.last_confirm_time = float(var_data_dict.get(PersistentSharedVarsFields.last_confirm_time.value, 0.0))
