from typing import Optional

from rka.eq2.shared.host import HostConfig, HostRole


class AppInfo(object):
    __host_config: Optional[HostConfig] = None
    __hostname: Optional[str] = None

    @staticmethod
    def set_host_config(host_config):
        assert host_config is not None
        AppInfo.__host_config = host_config

    @staticmethod
    def get_host_config() -> HostConfig:
        return AppInfo.__host_config

    @staticmethod
    def set_hostname(hostname: str):
        assert hostname is not None
        AppInfo.__hostname = hostname

    @staticmethod
    def get_hostname() -> str:
        return AppInfo.__hostname

    @classmethod
    def assert_master_role(cls):
        if not AppInfo.__host_config:
            return
        assert AppInfo.__host_config.host_role == HostRole.Master

    @classmethod
    def assert_slave_role(cls):
        if not AppInfo.__host_config:
            return
        assert AppInfo.__host_config.host_role == HostRole.Slave
