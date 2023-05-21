import os
import random
from typing import Optional, List, Callable, Dict

import regex as re

from rka.components.impl.factories import NotificationFactory
from rka.components.ui.notification import INotificationService, MockNotificationService
from rka.eq2.configs import configs_root
from rka.eq2.master import IRuntime
from rka.eq2.master.ui.control_menu_ui import ControlMenuUIType
from rka.eq2.shared.flags import MutableFlags


class NotificationServiceProxy(INotificationService):
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__notification_service: Optional[INotificationService] = None
        self.__default_channel_id: Optional[int] = None
        self.__callback_commands: Optional[List[str]] = None
        self.__callback: Optional[Callable[[INotificationService, str], None]] = None
        self.__unmatched_callback: Optional[Callable[[INotificationService, str], None]] = None
        self.__is_mock = False
        self.__commands: Dict[str, Callable[[INotificationService], None]] = {'menu': self.__menu,
                                                                              'scripts': self.__scripts,
                                                                              'players': self.__players,
                                                                              'help': self.__help,
                                                                              }
        self.__started = False
        self.__create_service()

    def __handle_unmatched_command_internally(self, _service: INotificationService, command: str) -> bool:
        if self.__is_mock:
            return False
        # place to add command parsers/handlers here
        _command_lower = command.lower()
        return False

    def __matched_command_received(self, service: INotificationService, command: str):
        if command in self.__commands:
            self.__commands[command](service)
        elif self.__callback and self.__callback_commands and command in self.__callback_commands:
            self.__callback(service, command)

    def __unmatched_command_received(self, service: INotificationService, command: str):
        if self.__handle_unmatched_command_internally(service, command):
            return
        if self.__unmatched_callback:
            self.__unmatched_callback(service, command)

    def __menu(self, _service: INotificationService):
        self.__runtime.control_menu.select_menu(ControlMenuUIType.NOTIFICATION)

    def __scripts(self, _service: INotificationService):
        self.__runtime.control_menu.select_script(ControlMenuUIType.NOTIFICATION)

    def __players(self, service: INotificationService):
        message = [f'{p.get_player_name()} {p.get_status().name}' for p in self.__runtime.player_mgr.get_players()]
        service.post_notification('\n'.join(message))

    def __help(self, service: INotificationService):
        service.post_notification('\n'.join(self.__commands))

    def __set_all_commands(self):
        if not self.__notification_service:
            return
        commands = list(self.__commands.keys())
        if self.__callback_commands:
            commands += list(self.__callback_commands)
        self.__notification_service.set_commands(commands, self.__matched_command_received)

    def __create_service(self):
        if MutableFlags.ENABLE_NOTIFICATION_SERVICE:
            self.__notification_service = NotificationFactory.create_service(self.__runtime.credentials)
            self.__is_mock = False
        else:
            self.__notification_service = MockNotificationService()
            self.__is_mock = True
        if self.__default_channel_id:
            self.__notification_service.set_default_channel_id(self.__default_channel_id)
        self.__notification_service.set_callback_for_unmatched_commands(self.__unmatched_command_received)
        self.__set_all_commands()
        if self.__started:
            self.__notification_service.start()

    def __close_service(self):
        if not self.__notification_service:
            return
        self.__notification_service.close()
        self.__notification_service = None
        self.__is_mock = False

    def set_default_channel_id(self, channel_id: int):
        self.__default_channel_id = channel_id
        if self.__notification_service:
            self.__notification_service.set_default_channel_id(channel_id)

    def set_commands(self, callback_commands: List[str], callback: Callable[[INotificationService, str], None]):
        self.__callback_commands = callback_commands
        self.__callback = callback
        self.__set_all_commands()

    def set_callback_for_unmatched_commands(self, callback: Callable[[INotificationService, str], None]):
        self.__unmatched_callback = callback

    def post_notification(self, message: str, channel_id: Optional[int] = None):
        if (MutableFlags.ENABLE_NOTIFICATION_SERVICE and self.__is_mock) or (not MutableFlags.ENABLE_NOTIFICATION_SERVICE and not self.__is_mock):
            self.__close_service()
        if not self.__notification_service:
            self.__create_service()
        self.__notification_service.post_notification(message, channel_id)

    def start(self):
        if not self.__started:
            self.__notification_service.start()
        self.__started = True

    def close(self):
        if self.__started:
            self.__notification_service.close()
        self.__started = False
