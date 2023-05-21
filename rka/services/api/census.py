from __future__ import annotations

import enum
from typing import Dict, Iterable, Union, Optional

from rka.services.api import IService
from rka.util.util import NameEnum


class CensusOperand(enum.Enum):
    EQ = enum.auto()
    NOT_EQ = enum.auto()
    LESS_EQ = enum.auto()
    MORE_EQ = enum.auto()
    LIKE = enum.auto()
    STARTS_WITH = enum.auto()


TCensusField = Union[str, int, float]
TCensusStruct = Dict[str, Union[TCensusField, Dict[str, Union[TCensusField, Dict[str, Union[TCensusField, Dict[str, TCensusField]]]]]]]


class CensusObject:
    def __init__(self, json: Optional[str], object_map: Optional[TCensusStruct]):
        assert json or object_map
        self.__json = json
        self.__object_map = object_map

    def get_json(self) -> str:
        if not self.__json:
            import json
            self.__json = json.dumps(self.__object_map)
        return self.__json

    def get_object_map(self) -> TCensusStruct:
        if not self.__object_map:
            import json
            self.__object_map = json.loads(self.__json)
        return self.__object_map

    def get_object_id(self) -> Union[int, str]:
        object_map = self.get_object_map()
        if 'id' in object_map:
            return object_map['id']
        json_str = self.get_json()
        return json_str

    @staticmethod
    def from_json(json_str: str) -> CensusObject:
        return CensusObject(json_str, None)

    @staticmethod
    def from_object_map(object_map: TCensusStruct) -> CensusObject:
        return CensusObject(None, object_map)


class CensusCacheOpts(NameEnum):
    FROM_CACHE_ONLY = enum.auto()


class IQuery:
    def query_id(self) -> str:
        raise NotImplementedError()

    def cached_result_ts(self) -> Optional[float]:
        raise NotImplementedError()

    def show_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        raise NotImplementedError()

    def run_query(self) -> Iterable[CensusObject]:
        raise NotImplementedError()


class IQueryBuilder:
    def add_parameter(self, parameter: str, value: TCensusField, operand: CensusOperand) -> IQueryBuilder:
        raise NotImplementedError()

    def add_option(self, option: str, value: str) -> IQueryBuilder:
        raise NotImplementedError()

    def set_limit(self, limit: Optional[int]) -> IQueryBuilder:
        raise NotImplementedError()

    def fetch_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        raise NotImplementedError()

    def build(self) -> IQuery:
        raise NotImplementedError()


# noinspection PyAbstractClass
class ICensus(IService):
    def new_query_builder(self, collection: str) -> IQueryBuilder:
        raise NotImplementedError()

    def get_latency(self) -> float:
        raise NotImplementedError()
