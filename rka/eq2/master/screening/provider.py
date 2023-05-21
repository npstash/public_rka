from typing import Type

from rka.eq2.master.screening import IScreenReader
from rka.eq2.master.screening.screen_reader import ScreenReader
from rka.services.api import IServiceProvider, IService


class ScreenReaderProvider(IServiceProvider):
    def __init__(self, detection_perdiod: float):
        self.__detection_perdiod = detection_perdiod

    def service_type(self) -> Type[IService]:
        return IScreenReader

    def provide_service(self) -> IService:
        return ScreenReader(detect_period=self.__detection_perdiod)
