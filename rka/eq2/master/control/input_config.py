from __future__ import annotations

from typing import Dict

from rka.eq2.master.control import logger, Hotbar, SpecialActions, InputConfig, Keyboard
from rka.eq2.master.control.action import ActionDelegate


class HotbarDelegate(Hotbar):
    def __init__(self, registry: Dict[str, ActionDelegate], hotbar_num: int):
        Hotbar.__init__(self)
        name = f'hotbar{hotbar_num}'
        self.hotkey1 = ActionDelegate(registry, f'{name}-hotkey1')
        self.hotkey2 = ActionDelegate(registry, f'{name}-hotkey2')
        self.hotkey3 = ActionDelegate(registry, f'{name}-hotkey3')
        self.hotkey4 = ActionDelegate(registry, f'{name}-hotkey4')
        self.hotkey5 = ActionDelegate(registry, f'{name}-hotkey5')
        self.hotkey6 = ActionDelegate(registry, f'{name}-hotkey6')
        self.hotkey7 = ActionDelegate(registry, f'{name}-hotkey7')
        self.hotkey8 = ActionDelegate(registry, f'{name}-hotkey8')
        self.hotkey9 = ActionDelegate(registry, f'{name}-hotkey9')
        self.hotkey10 = ActionDelegate(registry, f'{name}-hotkey10')
        self.hotkey11 = ActionDelegate(registry, f'{name}-hotkey11')
        self.hotkey12 = ActionDelegate(registry, f'{name}-hotkey12')


class KeyboardDelegate(Keyboard):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        Keyboard.__init__(self)
        name = 'keyboard'
        self.crouch = ActionDelegate(registry, f'{name}-crouch')
        self.jump = ActionDelegate(registry, f'{name}-jump')


class SpecialActionsDelegate(SpecialActions):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        SpecialActions.__init__(self)
        name = 'special'
        self.consume_command_injection = ActionDelegate(registry, f'{name}-consume_command_injection')
        self.consume_ability_injection = ActionDelegate(registry, f'{name}-consume_ability_injection')
        self.select_nearest_npc = ActionDelegate(registry, f'{name}-select_nearest_npc')
        self.open_journal = ActionDelegate(registry, f'{name}-open_journal')
        self.open_character = ActionDelegate(registry, f'{name}-open_character')
        self.open_bags = ActionDelegate(registry, f'{name}-open_bags')


class InputConfigDelegate(InputConfig):
    def __init__(self):
        InputConfig.__init__(self)
        self.delegates: Dict[str, ActionDelegate] = dict()
        self.hotbar1 = HotbarDelegate(self.delegates, 1)
        self.hotbar2 = HotbarDelegate(self.delegates, 2)
        self.hotbar3 = HotbarDelegate(self.delegates, 3)
        self.hotbar4 = HotbarDelegate(self.delegates, 4)
        self.hotbar5 = HotbarDelegate(self.delegates, 5)
        self.hotbarUp11 = HotbarDelegate(self.delegates, 11)
        self.hotbarUp12 = HotbarDelegate(self.delegates, 12)
        self.crafting_hotbar = HotbarDelegate(self.delegates, 13)
        self.keyboard = KeyboardDelegate(self.delegates)
        self.special = SpecialActionsDelegate(self.delegates)

    def update_delegates(self, inputs: InputConfigDelegate):
        if inputs is self:
            return
        for name, delegate in self.delegates.items():
            if name in inputs.delegates.keys():
                logger.detail(f'Updating delegate for {name} of {inputs}')
                new_action = inputs.delegates[name].unwrap()
                delegate.set_action(new_action)
        self.screen = inputs.screen
        self.keyboard.update_keys(inputs.keyboard)
