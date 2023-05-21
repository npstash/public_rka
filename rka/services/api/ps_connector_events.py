from typing import List

from rka.components.events import Events, event
from rka.services.api.ps_connector import PSTriggerEventData


class PSEvents(Events):
    TRIGGER_RECEIVED = event(trigger_event_data=PSTriggerEventData)
    COMMAND_RECEIVED = event(command=str, params=List[str])
    MESSAGE_RECEIVED = event(message=str)
    CLIENTS_RECEIVED = event(clients=List[str])
    DISCONNECTED = event()


if __name__ == '__main__':
    PSEvents.update_stub_file()
