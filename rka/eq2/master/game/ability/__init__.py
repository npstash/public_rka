from __future__ import annotations

import enum
import os
from enum import auto

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_ABILITY
from rka.util.util import NameEnum

logger = LogService(LOG_ABILITY)

_LOCATION = f'{os.path.dirname(os.path.realpath(__file__))}'

injection_useability_template = 'useability {}'
injection_useabilityonplayer_template = 'useabilityonplayer "{}" {}'


def generated_ability_classes_filepath():
    return os.path.join(_LOCATION, 'generated_abilities.py')


class AbilityEffectTarget(enum.Enum):
    Enemy = auto()
    Encounter = auto()
    AOE = auto()
    Self = auto()
    GroupMember = auto()
    Ally = auto()
    Group = auto()
    Raid = auto()
    Any = auto()
    none = auto()


class EffectLifeFlags(enum.Flag):
    NA = auto()
    Ability = auto()
    Triggered = auto()
    Subeffect = auto()
    OverTime = auto()


class CombatRequirement(enum.Enum):
    Any = auto()
    CombatOnly = auto()
    NonCombatOnly = auto()


class AbilitySpecial(enum.IntFlag):
    NoEffect = 0
    Stun = auto()
    Stifle = auto()
    Daze = auto()
    Mesmerize = auto()
    Fear = auto()
    Root = auto()
    Cure = auto()
    Power = auto()
    Drain = auto()
    Interrupt = auto()
    Dispel = auto()
    Casting = Stun | Stifle | Mesmerize
    Autoattack = Daze | Stun | Mesmerize
    Mobility = Fear | Root | Stun | Mesmerize
    Control = Stun | Stifle | Daze | Mesmerize | Fear | Root
    Any = Stun | Stifle | Daze | Mesmerize | Fear | Root | Cure | Power | Drain | Interrupt | Dispel
    assert not Any & NoEffect


class AbilityTier(enum.IntEnum):
    Apprentice = 1
    Journeyman = 4
    Adept = 5
    Expert = 7
    Master = 9
    Grandmaster = 10
    Ancient = 11
    Celestial = 12
    Class = 3
    AA = 1
    Rank_1 = 1
    Rank_2 = 2
    Rank_3 = 3
    Rank_4 = 4
    Rank_5 = 5
    Rank_6 = 6
    Rank_7 = 7
    Rank_8 = 8
    Rank_9 = 9
    Rank_10 = 10
    Item = 0
    UnknownLowest = -100
    UnknownHighest = 100

    def is_wildcard(self) -> bool:
        return self == AbilityTier.UnknownHighest or self == AbilityTier.UnknownLowest


PRIORITY_SELECTION_MARGIN = 50
PRIORITY_ADJUSTMENT_MARGIN = 10


class AbilityPriority(enum.IntEnum):
    NONE = 0
    EXTRA_TRADESKILL = 10
    COMBAT = 20

    SINGLE_DIRECT_HEAL = 30

    MINOR_DIRECT_DPS = 40
    MINOR_AOE_DPS = 50
    MINOR_SINGLE_PROTECT = 60
    MINOR_BUFF = 70
    MINOR_DEBUFF = 80
    MINOR_GROUP_PROTECT = 90

    SINGLE_SMALL_POWER = 100
    SINGLE_REACTIVE_HEAL = 110
    SINGLE_HOT_HEAL = 120
    SINGLE_DIRECT_WARD = 130
    SINGLE_HOT_WARD = 140

    MAJOR_DIRECT_DPS = 150
    MAJOR_AOE_DPS = 160
    MAJOR_SINGLE_PROTECT = 170
    MAJOR_BUFF = 180
    MAJOR_DEBUFF = 190
    MAJOR_GROUP_PROTECT = 200

    CONTROL_EFFECT = 210
    GROUP_SMALL_POWER = 220
    GROUP_DIRECT_HEAL = 250  # higher increase

    GREATER_DIRECT_DPS = 260
    GREATER_AOE_DPS = 270
    GREATER_SINGLE_PROTECT = 280
    GREATER_BUFF = 290
    GREATER_DEBUFF = 300
    GREATER_GROUP_PROTECT = 310

    MAINTAINED_BUFF = 320
    POWER_DRAIN = 330
    SINGLE_IMMUNIZATION = 340
    SINGLE_POWER = 350

    GROUP_DIRECT_WARD = 380  # higher increase
    GROUP_HOT_WARD = 390  # higher increase
    SINGLE_CURE = 400
    GROUP_CURE = 430  # higher increase
    GROUP_REACTIVE_HEAL = 440
    GROUP_HOT_HEAL = 450
    GROUP_IMMUNIZATION = 460

    DISPELLABLE_PASSIVE_BUFF = 470
    CRITICAL_SINGLE_PROTECT = 480
    CRITICAL_BUFF = 490
    CRITICAL_DEBUFF = 500
    CRITICAL_GROUP_PROTECT = 540  # higher increase

    DISPEL = 560  # higher increase
    INTERRUPT = 570
    CURE_CURSE = 610  # higher increase

    GROUP_DIRECT_POWER = 640  # higher increase
    GROUP_HOT_POWER = 650

    COMBO = 660
    AGGRO_CONTROL = 670
    FREE_MOVE = 710  # higher increase

    MANUAL_REQUEST = 760  # higher increase
    EMERGENCY = 770
    CONTROL = 780
    SCRIPT = 1000  # higher increase


class HOIcon(enum.IntEnum):
    NotAvailable = -1
    Sword = 0
    FightingChance = 1
    Horn = 2
    Fist = 3
    Boot = 4
    Arm = 5
    Chalice = 12
    Circle = 13
    Hammer = 14
    Eye = 15
    Moon = 16
    DivineProvidence = 17
    Wand = 24
    Lightning = 25
    ArcaneAugur = 26
    Staff = 27
    Flame = 28
    Star = 29
    Dagger = 36
    Bow = 37
    Mask = 38
    LuckyBreak = 39
    Cloak = 40
    Coin = 41


class AbilityType(NameEnum):
    spells = auto()
    abilities = auto()
    arts = auto()
    ascension = auto()
    tradeskills = auto()
    item = auto()
    ability = auto()

    def __str__(self) -> str:
        return self.value
