import time
from enum import Enum


def to_bool(obj) -> bool:
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj == 'True'
    if isinstance(obj, int):
        return obj != 0
    assert False, f'unrecognized object type {obj}'


class NameEnum(Enum):
    def __init__(self, _: str):
        pass

    # noinspection PyMethodParameters
    def _generate_next_value_(name, start, count, last_values):
        return name


class RateGuard:
    def __init__(self, rate: float):
        self.__rate = rate
        self.__last_timestamp = 0.0

    def next(self) -> bool:
        now = time.time()
        if now - self.__last_timestamp > self.__rate:
            self.__last_timestamp = now
            return True
        return False
