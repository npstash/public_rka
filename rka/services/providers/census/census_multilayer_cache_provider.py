from typing import Type

from rka.services.api import IServiceProvider, IService
from rka.services.api.census import ICensus
from rka.services.providers.census.census_cache_mongo_atlas import CensusMongoAtlasCacheProvider
from rka.services.providers.census.census_cache_ram import CensusRAMCacheProvider
from rka.services.providers.census.census_direct import CensusDirectProvider


class MultilayerCensusCacheProvider(IServiceProvider):
    def __init__(self, mongo_database: str, census_service_name: str, file_cache: bool):
        direct_provider = CensusDirectProvider(account_name=census_service_name)
        mongo_provider = CensusMongoAtlasCacheProvider(subject_provider=direct_provider, database_name=mongo_database)
        self.__ram_provider = CensusRAMCacheProvider(subject_provider=mongo_provider, persistence=file_cache)

    def service_type(self) -> Type[IService]:
        return ICensus

    def provide_service(self) -> IService:
        return self.__ram_provider.provide_service()
