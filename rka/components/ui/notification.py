from __future__ import annotations

from typing import Optional, List, Callable


class INotificationService(object):
    def set_default_channel_id(self, channel_id: int):
        raise NotImplementedError()

    def set_commands(self, callback_commands: List[str], callback: Callable[[INotificationService, str], None]):
        raise NotImplementedError()

    def set_callback_for_unmatched_commands(self, callback: Callable[[INotificationService, str], None]):
        raise NotImplementedError()

    def post_notification(self, message: str, channel_id: Optional[int] = None):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def close(self):
        pass


class MockNotificationService(INotificationService):
    def set_default_channel_id(self, channel_id: int):
        pass

    def set_commands(self, callback_commands: List[str], callback: Callable[[INotificationService, str], None]):
        pass

    def set_callback_for_unmatched_commands(self, callback: Callable[[INotificationService, str], None]):
        pass

    def post_notification(self, message: str, channel_id: Optional[int] = None):
        print(f'### {message} ###')

    def start(self):
        pass

    def close(self):
        pass
