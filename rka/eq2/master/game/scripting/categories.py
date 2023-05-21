from enum import Enum


class ScriptCategory(Enum):
    QUICKSTART = 'Quick start'
    PLAYERSTATE = 'Player state control'
    MOVEMENT = 'Movement & Travel'
    COMBAT = 'Combat and measurements'
    INVENTORY = 'Inventory usage'
    OVERSEERS = 'Overseers'
    HOST_CONTROL = 'Remote host control'
    TRADESKILL = 'Tradeskill'
    UI_AUTOMATION = ' UI automation'
    TEST = 'Test Scripts'
