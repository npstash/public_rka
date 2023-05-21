from typing import Optional

from pymongo import MongoClient

from rka.services.api import IService


# noinspection PyAbstractClass
class IMongoDBService(IService):
    def get_client(self) -> Optional[MongoClient]:
        raise NotImplementedError()

    def client_operation_failed(self):
        raise NotImplementedError()
