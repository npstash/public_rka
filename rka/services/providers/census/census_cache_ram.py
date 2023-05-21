from __future__ import annotations

import json
import os
import tempfile
import time
from threading import RLock
from typing import Dict, Optional, Union, Tuple, Iterable, Type, Set, Any, Mapping

from rka.components.cleanup import Closeable
from rka.components.io.log_service import LogService, LogLevel
from rka.log_configs import LOG_CENSUS
from rka.services.api import IServiceProvider, IService
from rka.services.api.census import CensusOperand, TCensusField, CensusObject, IQueryBuilder, IQuery, ICensus, TCensusStruct, CensusCacheOpts

logger = LogService(LOG_CENSUS)


class CensusObjectMatching:
    operand_functions = {
        CensusOperand.EQ: lambda test_value, census_value: test_value == census_value,
        CensusOperand.NOT_EQ: lambda test_value, census_value: test_value != census_value,
        CensusOperand.LESS_EQ: lambda test_value, census_value: int(census_value) <= int(test_value),
        CensusOperand.MORE_EQ: lambda test_value, census_value: int(census_value) >= int(test_value),
        CensusOperand.LIKE: lambda test_value, census_value: str(test_value) in str(census_value),
        CensusOperand.STARTS_WITH: lambda test_value, census_value: str(census_value).startswith(str(test_value)),
    }

    @staticmethod
    def get_field_value(field_path: str, census_object_map: TCensusStruct) -> Tuple[bool, Any]:
        field_path_segments = field_path.split('.')
        result_value = census_object_map
        for field_path_segment in field_path_segments:
            if not isinstance(result_value, Mapping) or field_path_segment not in result_value:
                logger.warn(f'did not find path segment in {result_value}')
                return False, None
            result_value = result_value[field_path_segment]
        return True, result_value

    @staticmethod
    def is_field_matched(param_value: TCensusField, param_op: CensusOperand, census_value: TCensusField) -> bool:
        return CensusObjectMatching.operand_functions[param_op](param_value, census_value)

    @staticmethod
    def is_object_matched(params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject) -> bool:
        object_matched = True
        for param_name, (param_value, param_op) in params.items():
            census_object_map = census_object.get_object_map()
            field_found, census_value = CensusObjectMatching.get_field_value(param_name, census_object_map)
            if not field_found:
                object_matched = False
                break
            if not CensusObjectMatching.is_field_matched(param_value, param_op, census_value):
                object_matched = False
                break
        return object_matched


class CachePersistence:
    @staticmethod
    def load_saved_data(file: str) -> Optional:
        logger.info(f'Loading data from {file}')
        try:
            tempdir = tempfile.gettempdir()
            cache_dir = os.path.join(tempdir, 'census_cache')
            os.makedirs(cache_dir, exist_ok=True)
            filename = os.path.join(cache_dir, f'{file}.json')
            if not os.path.exists(filename):
                return None
            with open(filename, 'r') as file:
                return json.load(file)
        except OSError as e:
            logger.warn(f'could not load cached data "{file}", due to {e}')
            return None

    @staticmethod
    def save_cached_data(file: str, data):
        logger.info(f'Saving data to {file}')
        try:
            tempdir = tempfile.gettempdir()
            cache_dir = os.path.join(tempdir, 'census_cache')
            os.makedirs(cache_dir, exist_ok=True)
            filename = os.path.join(cache_dir, f'{file}.json')
            with open(filename, 'w') as file:
                json.dump(data, file, indent=2)
        except OSError as e:
            logger.warn(f'Could not save cached data "{file}", due to {e}')


class ICachedCollectionContainer:
    def has_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject) -> bool:
        raise NotImplementedError()

    def add_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject):
        raise NotImplementedError()

    def iter_values(self, params: Dict[str, Tuple[TCensusField, CensusOperand]]) -> Iterable[CensusObject]:
        raise NotImplementedError()


class FlatCachedCollectionContainer(ICachedCollectionContainer, Closeable):
    def __init__(self, collection: str, persistence: bool):
        Closeable.__init__(self, explicit_close=False)
        self.__collection = collection
        self.__persistence = persistence
        self.__saved_objects: Dict[str, CensusObject] = dict()
        if persistence:
            loaded_objects = CachePersistence.load_saved_data(file=self.__collection)
            if loaded_objects:
                self.__saved_objects = {
                    object_id: CensusObject.from_object_map(census_data) for object_id, census_data in loaded_objects.items()
                }
        self.__collection_changed = False

    def close(self):
        if self.__persistence and self.__collection_changed:
            objects_to_save = {
                object_id: census_object.get_object_map() for object_id, census_object in self.__saved_objects.items()
            }
            CachePersistence.save_cached_data(file=self.__collection, data=objects_to_save)
        Closeable.close(self)

    def has_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject) -> bool:
        object_id = census_object.get_object_id()
        return object_id in self.__saved_objects

    def add_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject):
        object_id = census_object.get_object_id()
        self.__saved_objects[object_id] = census_object
        self.__collection_changed = True

    def iter_values(self, params: Dict[str, Tuple[TCensusField, CensusOperand]]) -> Iterable[CensusObject]:
        for value in self.__saved_objects.values():
            if CensusObjectMatching.is_object_matched(params, value):
                yield value


class MappedCachedCollectionContainer(ICachedCollectionContainer, Closeable):
    def __init__(self, collection: str, key_field: str, persistence: bool):
        Closeable.__init__(self, explicit_close=False)
        self.__collection = collection
        self.__key_field = key_field
        self.__persistence = persistence
        self.__saved_objects: Dict[str, Dict[str, CensusObject]] = dict()
        if persistence:
            loaded_objects = CachePersistence.load_saved_data(file=self.__collection)
            if loaded_objects:
                self.__saved_objects = {
                    key_value: {
                        object_id: CensusObject.from_object_map(census_data) for object_id, census_data in category.items()
                    } for key_value, category in loaded_objects.items()
                }
        self.__collection_changed = False

    def close(self):
        if self.__persistence and self.__collection_changed:
            objects_to_save = {
                key_value: {
                    object_id: census_object.get_object_map() for object_id, census_object in category.items()
                } for key_value, category in self.__saved_objects.items()
            }
            CachePersistence.save_cached_data(file=self.__collection, data=objects_to_save)
        Closeable.close(self)

    def __get_key_value(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject) -> str:
        if self.__key_field in query_params:
            param_value, param_op = query_params[self.__key_field]
            return param_value
        return census_object.get_object_map()[self.__key_field]

    def has_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject) -> bool:
        key_value = self.__get_key_value(query_params, census_object)
        if key_value not in self.__saved_objects:
            return False
        object_id = census_object.get_object_id()
        return object_id in self.__saved_objects[key_value]

    def add_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject):
        key_value = self.__get_key_value(query_params, census_object)
        if key_value not in self.__saved_objects:
            self.__saved_objects[key_value] = dict()
        object_id = census_object.get_object_id()
        self.__saved_objects[key_value][object_id] = census_object
        self.__collection_changed = True

    def iter_values(self, params: Dict[str, Tuple[TCensusField, CensusOperand]]) -> Iterable[CensusObject]:
        use_key = self.__key_field in params
        for key_value, category in self.__saved_objects.items():
            if use_key:
                param_value, param_op = params[self.__key_field]
                if not CensusObjectMatching.is_field_matched(param_value, param_op, key_value):
                    continue
            for value in category.values():
                if CensusObjectMatching.is_object_matched(params, value):
                    yield value


class CachedCollectionContainerFactory:
    @staticmethod
    def create_container(collection: str, persistence: bool) -> ICachedCollectionContainer:
        if collection in ['character']:
            return FlatCachedCollectionContainer(collection=collection, persistence=persistence)
        if collection == 'spell':
            return MappedCachedCollectionContainer(collection=collection, key_field='name_lower', persistence=persistence)
        if collection == 'item':
            return MappedCachedCollectionContainer(collection=collection, key_field='displayname_lower', persistence=persistence)
        assert False, collection


class CachedCollection(Closeable):
    def __init__(self, collection: str, persistence: bool):
        Closeable.__init__(self, explicit_close=False)
        self.__collection = collection
        self.__persistence = persistence
        self.__container = CachedCollectionContainerFactory.create_container(collection, persistence)
        self.__cached_queries: Dict[str, float] = dict()
        self.__lock = RLock()
        self.__queries_changed = False
        if persistence:
            loaded_queries = CachePersistence.load_saved_data(file=f'{collection}_queries')
            if loaded_queries:
                self.__cached_queries = loaded_queries

    def close(self):
        with self.__lock:
            if isinstance(self.__container, Closeable):
                self.__container.close()
            if self.__persistence and self.__queries_changed:
                CachePersistence.save_cached_data(file=f'{self.__collection}_queries', data=self.__cached_queries)
        Closeable.close(self)

    def get_collection(self) -> str:
        return self.__collection

    def get_query_ts(self, query_id: str) -> Optional[float]:
        with self.__lock:
            if query_id not in self.__cached_queries:
                return None
            return self.__cached_queries[query_id]

    def __set_query_ts(self, query_id: str, timestamp: float):
        with self.__lock:
            self.__cached_queries[query_id] = timestamp
            self.__queries_changed = True

    def __add_census_object(self, query_params: Dict[str, Tuple[TCensusField, CensusOperand]], census_object: CensusObject):
        with self.__lock:
            if logger.get_level() <= LogLevel.DETAIL:
                has_object = self.__container.has_census_object(query_params, census_object)
                verb_str = 'added to' if not has_object else 'replaced in'
                logger.detail(f'{verb_str} "{self.__collection}" RAM cache: {census_object}')
            self.__container.add_census_object(query_params, census_object)

    def __iter_objects(self, params: Dict[str, Tuple[TCensusField, CensusOperand]], limit: Optional[int]) -> Iterable[CensusObject]:
        with self.__lock:
            returned_count = 0
            for census_object in self.__container.iter_values(params):
                if limit and returned_count >= limit:
                    return
                returned_count += 1
                yield census_object

    def run_query(self, subject_query: IQuery, params: Dict[str, Tuple[TCensusField, CensusOperand]],
                  cache_options: Dict[str, str], limit: Optional[int]) -> Iterable[CensusObject]:
        query_id = subject_query.query_id()
        logger.info(f'RAM census cache query run: {query_id}')
        with self.__lock:
            if CensusCacheOpts.FROM_CACHE_ONLY.value not in cache_options:
                if not self.get_query_ts(query_id):
                    any_results_cached = False
                    for result in subject_query.run_query():
                        self.__add_census_object(query_params=params, census_object=result)
                        any_results_cached = True
                    if any_results_cached:
                        self.__set_query_ts(query_id, time.time())
            return self.__iter_objects(params=params, limit=limit)


class CensusRAMCacheQuery(IQuery):
    def __init__(self, cached_collection: CachedCollection, subject_query: IQuery,
                 params: Dict[str, Tuple[TCensusField, CensusOperand]], cache_options: Dict[str, str],
                 limit: Optional[int]):
        self.__cached_collection = cached_collection
        self.__subject_query = subject_query
        self.__params = params
        self.__cache_options = cache_options
        self.__limit = limit
        self.__show_fields: Set[str] = set()

    def query_id(self) -> str:
        return self.__subject_query.query_id()

    def cached_result_ts(self) -> Optional[float]:
        return self.__cached_collection.get_query_ts(self.query_id())

    def show_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        if isinstance(field_names, str):
            self.__show_fields.update(field_names.split(','))
        else:
            self.__show_fields.update(field_names)
        self.__subject_query.show_fields(field_names)
        return self

    def __filter_show_fields(self, census_result: TCensusStruct) -> TCensusStruct:
        if not self.__show_fields:
            return census_result
        census_result_fields = list(census_result.keys())
        for census_field in census_result_fields:
            if census_field not in self.__show_fields:
                del census_result[census_field]
        return census_result

    def run_query(self) -> Iterable[CensusObject]:
        return self.__cached_collection.run_query(self.__subject_query, self.__params, self.__cache_options, self.__limit)


class CensusRAMCacheQueryBuilder(IQueryBuilder):
    def __init__(self, subject: ICensus, cached_collection: CachedCollection):
        self.__subject = subject
        self.__cached_collection = cached_collection
        self.__parameters: Dict[str, Tuple[TCensusField, CensusOperand]] = dict()
        self.__cache_options: Dict[str, str] = dict()
        self.__subject_options: Dict[str, str] = dict()
        self.__fetch_fields: Set[str] = set()
        self.__limit: Optional[int] = None

    def add_parameter(self, parameter: str, value: TCensusField, operand: CensusOperand) -> IQueryBuilder:
        self.__parameters[parameter] = (value, operand)
        return self

    def add_option(self, option: str, value: str) -> IQueryBuilder:
        if option in CensusCacheOpts.__members__:
            self.__cache_options[option] = value
        self.__subject_options[option] = value
        return self

    def set_limit(self, limit: Optional[int]) -> IQueryBuilder:
        self.__limit = limit
        return self

    def fetch_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        if isinstance(field_names, str):
            self.__fetch_fields.update(field_names.split(','))
        else:
            self.__fetch_fields.update(field_names)
        return self

    def build(self) -> IQuery:
        subject_query_builder = self.__subject.new_query_builder(self.__cached_collection.get_collection())
        for param_name, (param_value, param_operand) in self.__parameters.items():
            subject_query_builder.add_parameter(param_name, param_value, param_operand)
        for option_name, option_value in self.__subject_options.items():
            subject_query_builder.add_option(option_name, option_value)
        subject_query_builder.set_limit(self.__limit)
        subject_query = subject_query_builder.build()
        query = CensusRAMCacheQuery(cached_collection=self.__cached_collection, subject_query=subject_query, params=self.__parameters,
                                    cache_options=self.__cache_options, limit=self.__limit)
        if self.__fetch_fields:
            query.show_fields(self.__fetch_fields)
        return query


class CensusRAMCache(ICensus, Closeable):
    def __init__(self, subject: ICensus, persistence: bool):
        Closeable.__init__(self, explicit_close=False)
        self.__subject = subject
        self.__persistence = persistence
        self.__cached_collections: Dict[str, CachedCollection] = dict()
        self.__cached_collections_lock = RLock()

    def close(self):
        for collection in self.__cached_collections.values():
            collection.close()
        if isinstance(self.__subject, Closeable):
            self.__subject.close()
        Closeable.close(self)

    def is_finalized(self) -> bool:
        return self.is_closed()

    def new_query_builder(self, collection: str) -> IQueryBuilder:
        with self.__cached_collections_lock:
            if collection not in self.__cached_collections:
                self.__cached_collections[collection] = CachedCollection(collection=collection, persistence=self.__persistence)
            cached_collection = self.__cached_collections[collection]
        return CensusRAMCacheQueryBuilder(subject=self.__subject, cached_collection=cached_collection)

    def get_latency(self) -> float:
        return 0.0


class CensusRAMCacheProvider(IServiceProvider):
    def __init__(self, subject_provider: IServiceProvider, persistence=True):
        self.__subject_provider = subject_provider
        self.__persistence = persistence

    def service_type(self) -> Type[IService]:
        return ICensus

    def provide_service(self) -> IService:
        subject_service = self.__subject_provider.provide_service()
        return CensusRAMCache(subject=subject_service, persistence=self.__persistence)
