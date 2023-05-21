import enum
from enum import auto

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_EFFECT

logger = LogService(LOG_EFFECT)


class EffectScopeType(enum.Enum):
    NON_PLAYER = auto()
    PLAYER = auto()
    GROUP = auto()
    RAID = auto()
    ABILITY = auto()


class EffectType(enum.Enum):
    DURATION = auto()
    BASE_REUSE = auto()
    BASE_CASTING = auto()
    CASTING_SPEED = auto()
    REUSE_SPEED = auto()
    RECOVERY_SPEED = auto()
    STEALTH = auto()
    RESET_ABILITY = auto()
    GRANT_ABILITY = auto()
    PRIORITY = auto()
