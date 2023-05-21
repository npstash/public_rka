from __future__ import annotations

from enum import auto
from typing import Any, Dict, Set

from rka.util.util import NameEnum


class Modifier(NameEnum):
    lcontrol = auto()
    rcontrol = auto()
    control = auto()
    lshift = auto()
    rshift = auto()
    shift = auto()
    lalt = auto()
    ralt = auto()
    alt = auto()

    def generalize(self) -> Modifier:
        if self.is_control():
            return Modifier.control
        if self.is_alt():
            return Modifier.alt
        if self.is_shift():
            return Modifier.shift
        return self

    def lmodifier(self) -> Modifier:
        if self.is_control():
            return Modifier.lcontrol
        if self.is_alt():
            return Modifier.lalt
        if self.is_shift():
            return Modifier.lshift
        return self

    def rmodifier(self) -> Modifier:
        if self.is_control():
            return Modifier.rcontrol
        if self.is_alt():
            return Modifier.ralt
        if self.is_shift():
            return Modifier.rshift
        return self

    def is_control(self):
        return self == Modifier.lcontrol or self == Modifier.rcontrol or self == Modifier.control

    def is_alt(self):
        return self == Modifier.lalt or self == Modifier.ralt or self == Modifier.alt

    def is_shift(self):
        return self == Modifier.lshift or self == Modifier.rshift or self == Modifier.shift


modifier_values = set(item.value for item in Modifier)


class BindingModifier(NameEnum):
    consume = auto()
    release = auto()
    up = auto()
    down = auto()
    repeat = auto()


class Binding(object):
    def __init__(self, keyspec: str, key: str, raw_modifiers: Set[str]):
        self.keyspec = keyspec
        self.key = key
        self.raw_modifiers = raw_modifiers
        self.modifiers = [modifier for modifier in Modifier if modifier.name in raw_modifiers]
        self.control = False
        self.alt = False
        self.shift = False
        self.win = False
        if Modifier.control.value in raw_modifiers or Modifier.lcontrol.value in raw_modifiers or Modifier.rcontrol.value in raw_modifiers:
            self.control = True
        if Modifier.alt.value in raw_modifiers or Modifier.lalt.value in raw_modifiers or Modifier.ralt.value in raw_modifiers:
            self.alt = True
        if Modifier.shift.value in raw_modifiers or Modifier.lshift.value in raw_modifiers or Modifier.rshift.value in raw_modifiers:
            self.shift = True
        self.consume = BindingModifier.consume.value in raw_modifiers
        self.release = BindingModifier.release.value in raw_modifiers
        self.down = BindingModifier.down.value in raw_modifiers
        self.up = BindingModifier.up.value in raw_modifiers
        if not self.down and not self.up:
            self.down = True
            self.up = True
        self.repeat = BindingModifier.repeat.value in raw_modifiers
        self.params: Dict[str, Any] = dict()

    def __hash__(self):
        return hash(self.keyspec)

    def __eq__(self, other):
        if not isinstance(other, Binding):
            return False
        return other.keyspec == self.keyspec

    @staticmethod
    def parse_hotkey_spec(keyspec: str) -> Binding:
        words = keyspec.split(' ')
        key = words[-1]
        raw_modifiers = {modifier.lower() for modifier in words[:-1]}
        return Binding(keyspec, key.lower(), raw_modifiers)
