from rka.components.events import event, Events
from rka.eq2.master.parsing import IDPSParser


class MasterEvents(Events):
    CLIENT_REGISTERED = event(client_id=str)
    CLIENT_UNREGISTERED = event(client_id=str)
    CLIENT_CONFIGURED = event(client_id=str)
    NEW_DPS_PARSER = event(dps_parser=IDPSParser)


if __name__ == '__main__':
    MasterEvents.update_stub_file()
