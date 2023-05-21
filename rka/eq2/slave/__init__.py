from rka.app.app_info import AppInfo
from rka.components.io.log_service import LogService
from rka.log_configs import LOG_APPCONTROL

AppInfo.assert_slave_role()

logger = LogService(LOG_APPCONTROL)
