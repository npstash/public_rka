from __future__ import annotations

from typing import Dict

from rka.eq2.master.control.action import ActionDelegate, action_factory
from rka.eq2.master.control.input_config import HotbarDelegate, KeyboardDelegate, SpecialActionsDelegate
from rka.eq2.shared.host import HostRole


def _make_action_hotbar_mouse_1280(hotbar_num, hotkey_num):
    return action_factory.new_action().mouse(331 + int(33.7 * (hotkey_num - 1)), 775 - int(35 * (hotbar_num - 1)), speed=2)


def _make_action_hotbarup2_mouse_1280(hotkey_num):
    return action_factory.new_action().mouse(635 + int(33.7 * (hotkey_num - 1)), 55, speed=2)


def _make_action_hotbar_mouse_1920(hotbar_num, hotkey_num):
    return action_factory.new_action().mouse(700 + int(42 * (hotkey_num - 1)), 1065 - int(40 * (hotbar_num - 1)), speed=2)


def _make_action_hotbarsquare1_mouse_1920(hotkey_num):
    row = (hotkey_num - 1) // 4
    col = (hotkey_num - 1) % 4
    return action_factory.new_action().mouse(408 + int(col * 32), 1003 + int(row * 32), speed=2)


def _make_action_hotbarup2_mouse_1920(hotkey_num):
    return action_factory.new_action().mouse(635 + int(34 * (hotkey_num - 1)), 51, speed=2)


class Hotbar1_Common(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 1)
        self.hotkey1.set_action(action_factory.new_action().key('1'))
        self.hotkey2.set_action(action_factory.new_action().key('2'))
        self.hotkey3.set_action(action_factory.new_action().key('3'))
        self.hotkey4.set_action(action_factory.new_action().key('4'))
        self.hotkey5.set_action(action_factory.new_action().key('5'))
        self.hotkey6.set_action(action_factory.new_action().key('6'))
        self.hotkey7.set_action(action_factory.new_action().key('7'))
        self.hotkey8.set_action(action_factory.new_action().key('8'))
        self.hotkey9.set_action(action_factory.new_action().key('9'))
        self.hotkey10.set_action(action_factory.new_action().key('0'))
        self.hotkey11.set_action(action_factory.new_action().key('-'))
        self.hotkey12.set_action(action_factory.new_action().key('='))


class Hotbar2_Mouse_1280(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 2)
        self.hotkey1.set_action(_make_action_hotbar_mouse_1280(2, 1))
        self.hotkey2.set_action(_make_action_hotbar_mouse_1280(2, 2))
        self.hotkey3.set_action(_make_action_hotbar_mouse_1280(2, 3))
        self.hotkey4.set_action(_make_action_hotbar_mouse_1280(2, 4))
        self.hotkey5.set_action(_make_action_hotbar_mouse_1280(2, 5))
        self.hotkey6.set_action(_make_action_hotbar_mouse_1280(2, 6))
        self.hotkey7.set_action(_make_action_hotbar_mouse_1280(2, 7))
        self.hotkey8.set_action(action_factory.new_action().key('z'))
        self.hotkey9.set_action(action_factory.new_action().key('x'))
        self.hotkey10.set_action(action_factory.new_action().key('v'))
        self.hotkey11.set_action(action_factory.new_action().key('g'))
        self.hotkey12.set_action(action_factory.new_action().key('f'))


class Hotbar2_Mouse_1920(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 2)
        self.hotkey1.set_action(_make_action_hotbar_mouse_1920(2, 1))
        self.hotkey2.set_action(_make_action_hotbar_mouse_1920(2, 2))
        self.hotkey3.set_action(_make_action_hotbar_mouse_1920(2, 3))
        self.hotkey4.set_action(_make_action_hotbar_mouse_1920(2, 4))
        self.hotkey5.set_action(_make_action_hotbar_mouse_1920(2, 5))
        self.hotkey6.set_action(_make_action_hotbar_mouse_1920(2, 6))
        self.hotkey7.set_action(_make_action_hotbar_mouse_1920(2, 7))
        self.hotkey8.set_action(action_factory.new_action().key('z'))
        self.hotkey9.set_action(action_factory.new_action().key('x'))
        self.hotkey10.set_action(action_factory.new_action().key('v'))
        self.hotkey11.set_action(action_factory.new_action().key('g'))
        self.hotkey12.set_action(action_factory.new_action().key('f'))


class Hotbar3_Mouse_1280(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 3)
        self.hotkey1.set_action(_make_action_hotbar_mouse_1280(3, 1))
        self.hotkey2.set_action(_make_action_hotbar_mouse_1280(3, 2))
        self.hotkey3.set_action(_make_action_hotbar_mouse_1280(3, 3))
        self.hotkey4.set_action(_make_action_hotbar_mouse_1280(3, 4))
        self.hotkey5.set_action(_make_action_hotbar_mouse_1280(3, 5))
        self.hotkey6.set_action(_make_action_hotbar_mouse_1280(3, 6))
        self.hotkey7.set_action(_make_action_hotbar_mouse_1280(3, 7))
        self.hotkey8.set_action(_make_action_hotbar_mouse_1280(3, 8))
        self.hotkey9.set_action(_make_action_hotbar_mouse_1280(3, 9))
        self.hotkey10.set_action(_make_action_hotbar_mouse_1280(3, 10))
        self.hotkey11.set_action(_make_action_hotbar_mouse_1280(3, 11))
        self.hotkey12.set_action(_make_action_hotbar_mouse_1280(3, 12))


class Hotbar3_Mouse_1920(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 3)
        self.hotkey1.set_action(_make_action_hotbar_mouse_1920(3, 1))
        self.hotkey2.set_action(_make_action_hotbar_mouse_1920(3, 2))
        self.hotkey3.set_action(_make_action_hotbar_mouse_1920(3, 3))
        self.hotkey4.set_action(_make_action_hotbar_mouse_1920(3, 4))
        self.hotkey5.set_action(_make_action_hotbar_mouse_1920(3, 5))
        self.hotkey6.set_action(_make_action_hotbar_mouse_1920(3, 6))
        self.hotkey7.set_action(_make_action_hotbar_mouse_1920(3, 7))
        self.hotkey8.set_action(_make_action_hotbar_mouse_1920(3, 8))
        self.hotkey9.set_action(_make_action_hotbar_mouse_1920(3, 9))
        self.hotkey10.set_action(_make_action_hotbar_mouse_1920(3, 10))
        self.hotkey11.set_action(_make_action_hotbar_mouse_1920(3, 11))
        self.hotkey12.set_action(_make_action_hotbar_mouse_1920(3, 12))


class Hotbar4_Common(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 4)
        self.hotkey1.set_action(action_factory.new_action().key('numpad1'))
        self.hotkey2.set_action(action_factory.new_action().key('numpad2'))
        self.hotkey3.set_action(action_factory.new_action().key('numpad3'))
        self.hotkey4.set_action(action_factory.new_action().key('numpad4'))
        self.hotkey5.set_action(action_factory.new_action().key('numpad5'))
        self.hotkey6.set_action(action_factory.new_action().key('numpad6'))
        self.hotkey7.set_action(action_factory.new_action().key('numpad7'))
        self.hotkey8.set_action(action_factory.new_action().key('numpad8'))
        self.hotkey9.set_action(action_factory.new_action().key('numpad9'))
        self.hotkey10.set_action(action_factory.new_action().key('numpad0'))
        self.hotkey11.set_action(action_factory.new_action().key('substract'))
        self.hotkey12.set_action(action_factory.new_action().key('add'))


class Hotbar5_Mouse_1280(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 5)
        self.hotkey1.set_action(_make_action_hotbar_mouse_1280(5, 1))
        self.hotkey2.set_action(_make_action_hotbar_mouse_1280(5, 2))
        self.hotkey3.set_action(_make_action_hotbar_mouse_1280(5, 3))
        self.hotkey4.set_action(_make_action_hotbar_mouse_1280(5, 4))
        self.hotkey5.set_action(_make_action_hotbar_mouse_1280(5, 5))
        self.hotkey6.set_action(_make_action_hotbar_mouse_1280(5, 6))
        self.hotkey7.set_action(_make_action_hotbar_mouse_1280(5, 7))
        self.hotkey8.set_action(_make_action_hotbar_mouse_1280(5, 8))
        self.hotkey9.set_action(_make_action_hotbar_mouse_1280(5, 9))
        self.hotkey10.set_action(_make_action_hotbar_mouse_1280(5, 10))
        self.hotkey11.set_action(_make_action_hotbar_mouse_1280(5, 11))
        self.hotkey12.set_action(_make_action_hotbar_mouse_1280(5, 12))


class Hotbar5_Mouse_1920(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 5)
        self.hotkey1.set_action(_make_action_hotbarsquare1_mouse_1920(1))
        self.hotkey2.set_action(_make_action_hotbarsquare1_mouse_1920(2))
        self.hotkey3.set_action(_make_action_hotbarsquare1_mouse_1920(3))
        self.hotkey4.set_action(_make_action_hotbarsquare1_mouse_1920(4))
        self.hotkey5.set_action(_make_action_hotbarsquare1_mouse_1920(5))
        self.hotkey6.set_action(_make_action_hotbarsquare1_mouse_1920(6))
        self.hotkey7.set_action(_make_action_hotbarsquare1_mouse_1920(7))
        self.hotkey8.set_action(_make_action_hotbarsquare1_mouse_1920(8))
        self.hotkey9.set_action(_make_action_hotbarsquare1_mouse_1920(9))
        self.hotkey10.set_action(_make_action_hotbarsquare1_mouse_1920(10))
        self.hotkey11.set_action(_make_action_hotbarsquare1_mouse_1920(11))
        self.hotkey12.set_action(_make_action_hotbarsquare1_mouse_1920(12))


class HotbarUp2_Mouse_1280(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 12)
        self.hotkey1.set_action(_make_action_hotbarup2_mouse_1280(1))
        self.hotkey2.set_action(_make_action_hotbarup2_mouse_1280(2))
        self.hotkey3.set_action(_make_action_hotbarup2_mouse_1280(3))
        self.hotkey4.set_action(_make_action_hotbarup2_mouse_1280(4))
        self.hotkey5.set_action(_make_action_hotbarup2_mouse_1280(5))
        self.hotkey6.set_action(_make_action_hotbarup2_mouse_1280(6))
        self.hotkey7.set_action(_make_action_hotbarup2_mouse_1280(7))
        self.hotkey8.set_action(_make_action_hotbarup2_mouse_1280(8))
        self.hotkey9.set_action(_make_action_hotbarup2_mouse_1280(9))
        self.hotkey10.set_action(_make_action_hotbarup2_mouse_1280(10))
        self.hotkey11.set_action(_make_action_hotbarup2_mouse_1280(11))
        self.hotkey12.set_action(_make_action_hotbarup2_mouse_1280(12))


class HotbarUp2_Mouse_1920(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 12)
        self.hotkey1.set_action(_make_action_hotbarup2_mouse_1920(1))
        self.hotkey2.set_action(_make_action_hotbarup2_mouse_1920(2))
        self.hotkey3.set_action(_make_action_hotbarup2_mouse_1920(3))
        self.hotkey4.set_action(_make_action_hotbarup2_mouse_1920(4))
        self.hotkey5.set_action(_make_action_hotbarup2_mouse_1920(5))
        self.hotkey6.set_action(_make_action_hotbarup2_mouse_1920(6))
        self.hotkey7.set_action(_make_action_hotbarup2_mouse_1920(7))
        self.hotkey8.set_action(_make_action_hotbarup2_mouse_1920(8))
        self.hotkey9.set_action(_make_action_hotbarup2_mouse_1920(9))
        self.hotkey10.set_action(_make_action_hotbarup2_mouse_1920(10))
        self.hotkey11.set_action(_make_action_hotbarup2_mouse_1920(11))
        self.hotkey12.set_action(_make_action_hotbarup2_mouse_1920(12))


class CraftingHotbar_Common(HotbarDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        HotbarDelegate.__init__(self, registry, 13)
        self.hotkey1.set_action(action_factory.new_action().key('1'))
        self.hotkey2.set_action(action_factory.new_action().key('2'))
        self.hotkey3.set_action(action_factory.new_action().key('3'))
        self.hotkey4.set_action(action_factory.new_action().key('4'))
        self.hotkey5.set_action(action_factory.new_action().key('5'))
        self.hotkey6.set_action(action_factory.new_action().key('6'))


class Keyboard_Common(KeyboardDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate]):
        KeyboardDelegate.__init__(self, registry)
        self.crouch.set_action(action_factory.new_action().key('alt c'))
        self.jump.set_action(action_factory.new_action().key('space'))
        self.key_turn_left = 'a'
        self.key_turn_right = 'd'
        self.key_move_forward = 'w'
        self.key_move_backwards = 's'


class SpecialActions_Common(SpecialActionsDelegate):
    def __init__(self, registry: Dict[str, ActionDelegate], host_role: HostRole):
        SpecialActionsDelegate.__init__(self, registry)
        self.select_nearest_npc.set_action(action_factory.new_action().key('tab'))
        self.open_journal.set_action(action_factory.new_action().key('j'))
        self.open_character.set_action(action_factory.new_action().key('c'))
        self.open_bags.set_action(action_factory.new_action().key('b'))
        self.consume_command_injection.set_action(action_factory.new_action().key('multiply'))
        if host_role == HostRole.Slave:
            self.consume_ability_injection.set_action(action_factory.new_action().key('multiply'))
        else:
            self.consume_ability_injection.set_action(action_factory.new_action())  # a NOP
