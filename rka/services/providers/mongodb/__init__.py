from threading import RLock
from typing import Optional, Type, List

from pymongo import MongoClient

from rka.components.cleanup import Closeable
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_DATABASE
from rka.services.api import IServiceProvider, IService
from rka.services.api.mongodb import IMongoDBService

logger = LogService(LOG_DATABASE)


class MongoDBClientConfig:
    def __init__(self, service_uri: str, tls_certificate_filepath: str, tls_certificate_file_password: Optional[str] = None):
        self.service_uri = service_uri
        self.tls_certificate_filepath = tls_certificate_filepath
        self.tls_certificate_file_password = tls_certificate_file_password

    def start_mongo_client(self, event_listeners: Optional[List] = None) -> MongoClient:
        logger.info('Starting new mongo client')
        kwargs = {
            'serverSelectionTimeoutMS': 10.0,
            'tls': True,
            'connect': False,
            'tlsCertificateKeyFile': self.tls_certificate_filepath,
        }
        if event_listeners:
            kwargs['event_listeners'] = event_listeners
        if self.tls_certificate_file_password:
            kwargs['tlsCertificateKeyFilePassword'] = self.tls_certificate_file_password
        client = MongoClient(self.service_uri, **kwargs)
        return client


class MongoDBService(IMongoDBService, Closeable):
    def __init__(self, config: MongoDBClientConfig):
        Closeable.__init__(self, explicit_close=False)
        self.__config = config
        self.__lock = RLock()
        self.__mongo_client: Optional[MongoClient] = None

    def get_client(self) -> Optional[MongoClient]:
        with self.__lock:
            if self.__mongo_client:
                return self.__mongo_client
            self.__mongo_client = self.__config.start_mongo_client()
            return self.__mongo_client

    def __close_client(self):
        try:
            if self.__mongo_client:
                logger.info('Closing mongo client')
                self.__mongo_client.close()
            self.__mongo_client = None
        except Exception as e:
            logger.warn(f'Problem while closing mongo DB {e}')

    def client_operation_failed(self):
        with self.__lock:
            self.__close_client()

    def close(self):
        with self.__lock:
            self.__close_client()
        Closeable.close(self)

    def is_finalized(self) -> bool:
        return self.is_closed()


class MongoDBServiceProvider(IServiceProvider):
    def __init__(self, config: MongoDBClientConfig):
        self.__config = config

    def service_type(self) -> Type[IService]:
        return IMongoDBService

    def provide_service(self) -> IService:
        return MongoDBService(self.__config)
