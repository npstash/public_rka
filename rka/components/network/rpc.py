from typing import Any


class IServiceHost(object):
    def get_address(self) -> str:
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def wait_until_started(self, timeout: float) -> bool:
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class IConnection(object):
    def get_proxy(self) -> Any:
        raise NotImplementedError()

    def get_remote_address(self) -> str:
        raise NotImplementedError()

    def get_local_address(self) -> str:
        raise NotImplementedError()

    def valid_for(self, remote_address: str) -> bool:
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


# noinspection PyAbstractClass
class AbstractConnection(IConnection):
    def __init__(self, local_address: str, remote_address: str):
        IConnection.__init__(self)
        assert remote_address is not None
        assert local_address is not None
        self.__remote_address = remote_address
        self.__local_address = local_address

    def __str__(self) -> str:
        local = self.__local_address
        remote = self.__remote_address
        return f'Connection[{type(self)} from {local} to {remote}]'

    def get_remote_address(self) -> str:
        return self.__remote_address

    def get_local_address(self) -> str:
        return self.__local_address

    def valid_for(self, remote_address: str) -> bool:
        return self.get_proxy() is not None and self.__remote_address == remote_address
