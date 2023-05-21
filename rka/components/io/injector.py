from typing import Optional


class IInjector(object):
    def get_name(self) -> str:
        raise NotImplementedError()

    def set_injection_prefix(self, injection_body):
        raise NotImplementedError()

    def set_injection_postfix(self, injection_body):
        raise NotImplementedError()

    def inject_command(self, command: str, command_id: str, once: bool, pass_through: bool, duration: Optional[float] = None) -> bool:
        raise NotImplementedError()

    def remove_command(self, command_id) -> bool:
        raise NotImplementedError()

    def close(self):
        pass


class InjectorDelegate(IInjector):
    def __init__(self):
        self.__target: Optional[IInjector] = None

    def get_name(self) -> str:
        return self.__target.get_name()

    def set_target(self, target: IInjector):
        self.__target = target

    def set_injection_prefix(self, injection_body):
        self.__target.set_injection_prefix(injection_body)

    def set_injection_postfix(self, injection_body):
        self.__target.set_injection_postfix(injection_body)

    def inject_command(self, command: str, command_id: str, once: bool, pass_through: bool, duration: Optional[float] = None) -> bool:
        return self.__target.inject_command(command=command, command_id=command_id, once=once, pass_through=pass_through, duration=duration)

    def remove_command(self, command_id) -> bool:
        return self.__target.remove_command(command_id)

    def close(self):
        self.__target.close()
