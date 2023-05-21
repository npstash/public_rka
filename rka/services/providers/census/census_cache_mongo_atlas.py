from __future__ import annotations

import time
from threading import Semaphore
from typing import Dict, Optional, Union, Tuple, Iterable, Type, Set

from pymongo.errors import PyMongoError

from rka.components.cleanup import Closeable
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_CENSUS
from rka.services.api import IServiceProvider, IService
from rka.services.api.census import CensusOperand, TCensusField, CensusObject, IQueryBuilder, IQuery, ICensus, TCensusStruct, CensusCacheOpts
from rka.services.api.mongodb import IMongoDBService

logger = LogService(LOG_CENSUS)


class CensusMongoAtlasCacheQuery(IQuery):
    __mongo_query_operands = {
        CensusOperand.EQ: lambda value_: {'$eq': value_},
        CensusOperand.NOT_EQ: lambda value_: {'$ne': value_},
        CensusOperand.LESS_EQ: lambda value_: {'$lte': value_},
        CensusOperand.MORE_EQ: lambda value_: {'$gte', value_},
        CensusOperand.LIKE: lambda value_: {'$regex': f'.*{value_}.*'},
        CensusOperand.STARTS_WITH: lambda value_: {'$regex': f'{value_}.*'},
    }

    def __init__(self, mongo_service: IMongoDBService, database_name: str, collection: str, subject_query: IQuery,
                 params: Dict[str, Tuple[TCensusField, CensusOperand]], cache_options: Dict[str, str],
                 limit: Optional[int], access_guard: Semaphore):
        self.__mongo_service = mongo_service
        self.__database_name = database_name
        self.__collection = collection
        self.__subject_query = subject_query
        self.__params = params
        self.__cache_options = cache_options
        self.__limit = limit
        self.__access_guard = access_guard
        self.__show_fields: Set[str] = set()

    def query_id(self) -> str:
        return self.__subject_query.query_id()

    def cached_result_ts(self) -> Optional[float]:
        try:
            client = self.__mongo_service.get_client()
            db = client.get_database(self.__database_name)
            collection = db.get_collection('queries')
            query_id = self.query_id()
            doc = collection.find_one(filter={
                'query_id': query_id,
            })
        except PyMongoError as e:
            logger.warn(f'cached_result_ts: failed to connect to Mongo DB with {e}')
            self.__mongo_service.client_operation_failed()
            return None
        if not doc:
            return None
        return doc['timestamp']

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

    def __make_filter(self) -> Dict[str, TCensusField]:
        query_filter = dict()
        for param_name, (param_value, param_operand) in self.__params.items():
            mongo_search_doc = CensusMongoAtlasCacheQuery.__mongo_query_operands[param_operand](param_value)
            query_filter[param_name] = mongo_search_doc
        return query_filter

    def __fetch_from_subject_and_cache(self):
        query_id = self.query_id()
        logger.debug(f'CensusMongoAtlasCacheQuery fetching from subject: {query_id}')
        try:
            client = self.__mongo_service.get_client()
            db = client.get_database(self.__database_name)
            collection = db.get_collection(self.__collection)
            any_results_cached = False
            for result in self.__subject_query.run_query():
                result_id = result.get_object_id()
                logger.detail(f'CensusMongoAtlasCacheQuery storing object: {result}')
                collection.replace_one(filter={
                    'id': result_id
                }, replacement=result.get_object_map(), upsert=True)
                any_results_cached = True
            if not any_results_cached:
                logger.warn(f'run_query: no results received from {self.__subject_query}')
                return
            queries_collection = db.get_collection('queries')
            query_trace = {
                'query_id': self.query_id(),
                'timestamp': time.time()
            }
            queries_collection.replace_one(filter={
                'query_id': query_trace['query_id'],
            }, replacement=query_trace, upsert=True)
        except PyMongoError as e:
            logger.warn(f'run_query: failed to connect to Mongo DB with {e}')
            self.__mongo_service.client_operation_failed()
            return

    def __run_query_from_cache(self) -> Iterable[CensusObject]:
        try:
            search_filter = self.__make_filter()
            client = self.__mongo_service.get_client()
            db = client.get_database(self.__database_name)
            collection = db.get_collection(self.__collection)
            if self.__limit:
                cursor = collection.find(filter=search_filter, limit=self.__limit)
            else:
                cursor = collection.find(filter=search_filter)
            for doc in cursor:
                # remove Atlas ID field, its not JSON-serializable and not needed
                if '_id' in doc:
                    del doc['_id']
                census_object = CensusObject.from_object_map(doc)
                yield census_object
        except PyMongoError as e:
            logger.warn(f'run_query: failed to connect to Mongo DB with {e}')
            self.__mongo_service.client_operation_failed()
            return

    def run_query(self) -> Iterable[CensusObject]:
        query_id = self.query_id()
        logger.info(f'CensusMongoAtlasCacheQuery query run: {query_id}')
        try:
            self.__access_guard.acquire()
            if CensusCacheOpts.FROM_CACHE_ONLY.value not in self.__cache_options:
                if not self.cached_result_ts():
                    self.__fetch_from_subject_and_cache()
            return self.__run_query_from_cache()
        finally:
            self.__access_guard.release()


class CensusMongoAtlasCacheQueryBuilder(IQueryBuilder):
    def __init__(self, subject: ICensus, collection: str, mongo_service: IMongoDBService, database_name: str, access_guard: Semaphore):
        self.__subject = subject
        self.__collection = collection
        self.__mongo_service = mongo_service
        self.__database_name = database_name
        self.__parameters: Dict[str, Tuple[TCensusField, CensusOperand]] = dict()
        self.__cache_options: Dict[str, str] = dict()
        self.__subject_options: Dict[str, str] = dict()
        self.__fetch_fields: Set[str] = set()
        self.__limit: Optional[int] = None
        self.__access_guard = access_guard

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
        subject_query_builder = self.__subject.new_query_builder(self.__collection)
        for param_name, (param_value, param_operand) in self.__parameters.items():
            subject_query_builder.add_parameter(param_name, param_value, param_operand)
        for option_name, option_value in self.__subject_options.items():
            subject_query_builder.add_option(option_name, option_value)
        subject_query_builder.set_limit(self.__limit)
        subject_query = subject_query_builder.build()
        query = CensusMongoAtlasCacheQuery(mongo_service=self.__mongo_service,
                                           database_name=self.__database_name,
                                           collection=self.__collection,
                                           subject_query=subject_query,
                                           params=self.__parameters,
                                           cache_options=self.__cache_options,
                                           limit=self.__limit,
                                           access_guard=self.__access_guard)
        return query


class CensusMongoAtlasCache(ICensus, Closeable):
    def __init__(self, subject: ICensus, database_name: str):
        Closeable.__init__(self, explicit_close=False)
        self.__subject = subject
        self.__database_name = database_name
        from rka.services.broker import ServiceBroker
        self.__mongo_service: IMongoDBService = ServiceBroker.get_broker().get_service(IMongoDBService)
        self.__latency: Optional[float] = None
        self.__access_guard = Semaphore(1)

    def close(self):
        if isinstance(self.__subject, Closeable):
            self.__subject.close()
        Closeable.close(self)

    def is_finalized(self) -> bool:
        return self.is_closed()

    def new_query_builder(self, collection: str) -> IQueryBuilder:
        return CensusMongoAtlasCacheQueryBuilder(subject=self.__subject,
                                                 collection=collection,
                                                 mongo_service=self.__mongo_service,
                                                 database_name=self.__database_name,
                                                 access_guard=self.__access_guard)

    def get_latency(self) -> float:
        if self.__latency is not None:
            return self.__latency
        client = self.__mongo_service.get_client()
        try:
            # dont include first connection time in the measurement
            client.server_info()
            start = time.time()
            db = client.get_database(self.__database_name)
            db.command('ping')
        except PyMongoError as e:
            logger.warn(f'get_latency: failed to connect to Mongo DB with {e}')
            self.__mongo_service.client_operation_failed()
            # will make the latency very large
            start = 0.0
        self.__latency = time.time() - start
        return self.__latency


class CensusMongoAtlasCacheProvider(IServiceProvider):
    def __init__(self, subject_provider: IServiceProvider, database_name: str):
        self.__subject_provider = subject_provider
        self.__database_name = database_name

    def service_type(self) -> Type[IService]:
        return ICensus

    def provide_service(self) -> IService:
        subject_service = self.__subject_provider.provide_service()
        return CensusMongoAtlasCache(subject=subject_service, database_name=self.__database_name)
