from typing import List, Optional

from rka.components.ui.tts import ITTSSession
from rka.services.api import IService


class PSTriggerInfo:
    def __init__(self, trigger_id: int, title: str, pattern: str, message: Optional[str], private_sound: bool, timer: Optional[int]):
        self.trigger_id = trigger_id
        self.title = title
        self.pattern = pattern
        self.message = message
        self.private_sound = private_sound
        self.timer = timer

    def __str__(self):
        return f'trigger id="{self.trigger_id}" title="{self.title}" pattern="{self.pattern}" message="{self.message}" timer="{self.timer}"'


class PSTriggerEventData:
    def __init__(self, trigger_info: PSTriggerInfo, ps_payload: str, sender: str, message: Optional[str], voice_message: Optional[str]):
        self.trigger_info = trigger_info
        self.ps_payload = ps_payload
        self.sender = sender
        self.message = message
        self.voice_message = voice_message

    def __str__(self):
        return f'trigger message="{self.message}" sender="{self.sender}" payload="{self.ps_payload}" info="{self.trigger_info}"'


class IPSConnectorObserver:
    def trigger_event_received(self, trigger_event: PSTriggerEventData):
        pass

    def message_received(self, message: str):
        pass

    def command_received(self, command: str, params: List[str]):
        pass

    def client_list_received(self, clients: List[str]):
        pass

    def connector_closed(self):
        pass


# noinspection PyAbstractClass
class IPSConnector(IService, ITTSSession):
    def add_observer(self, observer: IPSConnectorObserver):
        raise NotImplementedError()

    def remove_observer(self, observer: IPSConnectorObserver):
        raise NotImplementedError()

    def send_trigger_event(self, trigger_id: int, line: str) -> bool:
        raise NotImplementedError()

    def send_message(self, message: str) -> bool:
        raise NotImplementedError()

    def send_tts(self, tts_message: str) -> bool:
        raise NotImplementedError()

    def start_connector(self) -> bool:
        raise NotImplementedError()

    def is_running(self) -> bool:
        raise NotImplementedError()

    def close_connector(self):
        raise NotImplementedError()

    def get_ready(self) -> bool:
        return self.start_connector()

    def say(self, text: str, interrupts=False) -> bool:
        if not self.is_running():
            if not self.start_connector():
                return False
        return self.send_tts(text)

    def is_session_open(self) -> bool:
        return self.is_running()

    def close_session(self):
        self.close_connector()
