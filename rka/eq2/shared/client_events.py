from rka.components.events import Events
from rka.eq2.shared.client_event import parser_event, client_event


class ClientEvents(Events):
    CLIENT_REQUEST = client_event(client_id=str, request=str, timestamp=float)
    PARSER_MATCH = parser_event(client_id=str, parse_filter=str, preparsed_log=bool, matched_text=str, timestamp=float)


if __name__ == '__main__':
    ClientEvents.update_stub_file()
