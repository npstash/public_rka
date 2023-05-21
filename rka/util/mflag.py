from __future__ import annotations

from enum import Enum

from rka.components.common_events import CommonEvents
from rka.components.events.event_system import EventSystem


class MutableFlagEnum(Enum):
    def __init__(self, value):
        self._value_ = self._name_
        self.__flag = value

    def __bool__(self) -> bool:
        return self.__flag

    def __str__(self) -> str:
        return self._name_

    def __set_value(self, value: bool):
        if self.__flag != value:
            EventSystem.get_main_bus().post(CommonEvents.FLAG_CHANGED(flag_name=self._name_, new_value=value))
        self.__flag = value

    def false(self) -> MutableFlagEnum:
        self.__set_value(False)
        return self

    def true(self) -> MutableFlagEnum:
        self.__set_value(True)
        return self

    def toggle(self) -> MutableFlagEnum:
        self.__set_value(not self.__flag)
        return self
