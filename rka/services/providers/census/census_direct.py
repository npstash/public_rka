from __future__ import annotations

import time
from threading import Semaphore
from typing import Dict, Optional, Union, Tuple, Iterable, Type, Set

import requests

from rka.components.io.log_service import LogService
from rka.log_configs import LOG_CENSUS
from rka.services.api import IServiceProvider, IService
from rka.services.api.census import CensusOperand, TCensusField, CensusObject, IQueryBuilder, IQuery, ICensus, TCensusStruct, CensusCacheOpts

logger = LogService(LOG_CENSUS)


class CensusServiceConfig:
    def __init__(self, service_url: str, account_name: Optional[str], grace_time: float, retry_count: int, concurrent_queries: int):
        self.service_url = service_url
        self.account_name = account_name
        self.grace_time = grace_time
        self.retry_count = retry_count
        self.concurrent_queries = concurrent_queries
        self.__last_request_timestamp = 0.0

    def wait_grace_time(self, grace_time: float):
        now = time.time()
        time_since_last_request = now - self.__last_request_timestamp
        if time_since_last_request < 0.0:
            time_since_last_request = grace_time
        if time_since_last_request < grace_time:
            remaining_grace_time = grace_time - time_since_last_request
        else:
            remaining_grace_time = grace_time
        time.sleep(remaining_grace_time)
        self.__last_request_timestamp = now


class CensusDirectQuery(IQuery):
    def __init__(self, service_config: CensusServiceConfig, query_url: str, query_id: str, limit: Optional[int], access_guard: Semaphore):
        self.__service_config = service_config
        self.__query_url = query_url
        self.__query_id = f'{query_id}#{limit}'
        self.__limit = limit
        self.__access_guard = access_guard
        self.__show_fields: Set[str] = set()

    def query_id(self) -> str:
        return self.__query_id

    def cached_result_ts(self) -> Optional[float]:
        return None

    def show_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        if isinstance(field_names, str):
            self.__show_fields.update(field_names.split(','))
        else:
            self.__show_fields.update(field_names)
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
        # make the limit at least 1, if set
        limit = max(self.__limit, 1) if self.__limit is not None else None
        logger.info(f'census query run: {self.__query_url} [limit={self.__limit}]')
        total_result_count = 0
        grace_time = self.__service_config.grace_time
        self.__access_guard.acquire()
        try:
            while True:
                # batch size is at most 100, if there is no limit, or limit is higher
                batch_limit = 100 if limit is None else min(limit - total_result_count, 100)
                request_url = f'{self.__query_url}&c:limit={batch_limit}&c:start={total_result_count}'
                logger.debug(f'census query run batch size {batch_limit} ({total_result_count}/{limit}): {request_url}')
                response = None
                # wait a grace time before a request
                self.__service_config.wait_grace_time(grace_time)
                for attempt in range(self.__service_config.retry_count):
                    try:
                        response = requests.get(request_url)
                        break
                    except OSError as e:
                        logger.warn(f'error fetching data from census: {e}')
                        time.sleep(20.0)
                        grace_time += 5.0
                if not response:
                    logger.warn(f'failed to fetch census data: {request_url}')
                    return
                try:
                    object_map = response.json()
                except Exception as json_error:
                    logger.warn(f'failed to decode census json result: {response.text}, error: {json_error}')
                    return
                if not object_map or 'returned' not in object_map:
                    logger.warn(f'failed to fetch census results with: {request_url}')
                    return
                declared_returned = int(object_map['returned'])
                logger.debug(f'received {declared_returned} census results')
                counted_returned = 0
                for value in object_map.values():
                    # one nested list is expected holding all returned objects
                    if isinstance(value, list):
                        for census_result in value:
                            if limit and total_result_count >= limit:
                                return
                            census_result = self.__filter_show_fields(census_result)
                            census_result_obj = CensusObject.from_object_map(census_result)
                            total_result_count += 1
                            counted_returned += 1
                            yield census_result_obj
                        break
                if counted_returned != declared_returned:
                    logger.warn(f'declared results is {declared_returned}, but {counted_returned} returned')
                if declared_returned < batch_limit:
                    logger.detail(f'no more items to return')
                    break
                if limit and total_result_count == limit:
                    break
            logger.debug(f'total census objects returned {total_result_count}')
        finally:
            self.__access_guard.release()


class CensusDirectQueryBuilder(IQueryBuilder):
    __census_operands = {
        CensusOperand.EQ: '=',
        CensusOperand.NOT_EQ: '=!',
        CensusOperand.LESS_EQ: '=[',
        CensusOperand.MORE_EQ: '=]',
        CensusOperand.LIKE: '=*',
        CensusOperand.STARTS_WITH: '=^',
    }

    def __init__(self, service_config: CensusServiceConfig, collection: str, access_guard: Semaphore):
        self.__service_config = service_config
        self.__collection = collection
        self.__access_guard = access_guard
        self.__parameters: Dict[str, Tuple[TCensusField, CensusOperand]] = dict()
        self.__options: Dict[str, str] = dict()
        self.__limit: Optional[int] = None

    def add_parameter(self, parameter: str, value: TCensusField, operand: CensusOperand) -> IQueryBuilder:
        self.__parameters[parameter] = (value, operand)
        return self

    def add_option(self, option: str, value: str) -> IQueryBuilder:
        if option in CensusCacheOpts.__members__:
            # ignore cache-only options
            return self
        self.__options[option] = value
        return self

    def set_limit(self, limit: Optional[int]) -> IQueryBuilder:
        self.__limit = limit
        return self

    def fetch_fields(self, field_names: Union[str, Iterable[str]]) -> IQueryBuilder:
        if isinstance(field_names, str):
            self.add_option('show', field_names)
        else:
            self.add_option('show', ','.join(field_names))
        return self

    def build(self) -> IQuery:
        args = []
        for param_name, (param_value, operand) in self.__parameters.items():
            args.append(f'{param_name}{CensusDirectQueryBuilder.__census_operands[operand]}{param_value}')
        for option_name, option_value in self.__options.items():
            args.append(f'c:{option_name}={option_value}')
        query_args = '&'.join(args)
        query_id = f'https://census.daybreakgames.com/get/eq2/{self.__collection}?{query_args}'
        if self.__service_config.account_name:
            query_url = f'https://census.daybreakgames.com/s:{self.__service_config.account_name}/get/eq2/{self.__collection}?{query_args}'
        else:
            query_url = f'https://census.daybreakgames.com/get/eq2/{self.__collection}?{query_args}'
        return CensusDirectQuery(service_config=self.__service_config, query_url=query_url, query_id=query_id,
                                 limit=self.__limit, access_guard=self.__access_guard)


class CensusDirect(ICensus):
    def __init__(self, service_config: CensusServiceConfig):
        self.__service_config = service_config
        self.__access_guard = Semaphore(service_config.concurrent_queries)

    def is_finalized(self) -> bool:
        return False

    def new_query_builder(self, collection: str) -> IQueryBuilder:
        return CensusDirectQueryBuilder(service_config=self.__service_config, collection=collection, access_guard=self.__access_guard)

    def get_latency(self) -> float:
        return 2.0 + self.__service_config.grace_time


class CensusDirectProvider(IServiceProvider):
    def __init__(self, account_name: Optional[str]):
        self.__account_name = account_name

    def service_type(self) -> Type[IService]:
        return ICensus

    def provide_service(self) -> IService:
        service_config = CensusServiceConfig(service_url='https://census.daybreakgames.com/get/eq2/',
                                             account_name=self.__account_name,
                                             grace_time=5.0,
                                             retry_count=3,
                                             concurrent_queries=1)
        return CensusDirect(service_config=service_config)
