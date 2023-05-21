from __future__ import annotations

from threading import RLock
from typing import Optional, Dict, Type, Generic, TypeVar

from rka.services.api import IServiceProvider, IService

ServiceType = TypeVar('ServiceType', bound=IService)


class ServiceBroker:
    __instance: Optional[ServiceBroker] = None

    @staticmethod
    def get_broker() -> ServiceBroker:
        if not ServiceBroker.__instance:
            ServiceBroker.__instance = ServiceBroker()
        return ServiceBroker.__instance

    def __init__(self):
        self.__access_lock = RLock()
        self.__providers: Dict[Type[IService], IServiceProvider] = dict()
        self.__services: Dict[Type[IService], IService] = dict()

    def install_provider(self, provider: IServiceProvider):
        with self.__access_lock:
            self.__providers[provider.service_type()] = provider

    def get_service(self, service_type: Generic[ServiceType]) -> ServiceType:
        with self.__access_lock:
            if service_type in self.__services:
                service = self.__services[service_type]
                if service.is_finalized():
                    del self.__services[service_type]
            if service_type not in self.__services:
                self.__services[service_type] = self.__providers[service_type].provide_service()
            return self.__services[service_type]
