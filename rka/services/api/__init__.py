from typing import Type


class IService:
    def is_finalized(self) -> bool:
        raise NotImplementedError()


class IServiceProvider:
    def service_type(self) -> Type[IService]:
        raise NotImplementedError()

    def provide_service(self) -> IService:
        raise NotImplementedError()
