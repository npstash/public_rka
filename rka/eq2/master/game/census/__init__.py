from enum import auto

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_CENSUS
from rka.util.util import NameEnum

logger = LogService(LOG_CENSUS)


class CensusTopFields(NameEnum):
    name = auto()
    name_lower = auto()
    cast_secs_hundredths = auto()
    recast_secs = auto()
    recovery_secs_tenths = auto()
    beneficial = auto()
    max_targets = auto()
    tier_name = auto()
    tier = auto()
    level = auto()
    crc = auto()
    type = auto()
    duration = auto()
    classes = auto()
    icon = auto()
    effect_list = auto()
    id = auto()


class CensusNestedFields(NameEnum):
    max_sec_tenths = auto()
    does_not_expire = auto()
    icon_heroic_op = auto()
