from enum import auto

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_APPCONTROL
from rka.util.util import NameEnum

logger = LogService(LOG_APPCONTROL)


class PermanentUIEvents(NameEnum):
    ZONE = auto()
    HOTKEYS = auto()
    TARGET = auto()
    MONK_DEFENSE = auto()
    MONK_OFFENSE = auto()
    GROUP_AUTOCOMBAT = auto()
    AFK_AUTOCOMBAT = auto()
    OOZ = auto()

    def str(self) -> str:
        return self.value
