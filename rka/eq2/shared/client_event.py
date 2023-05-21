from __future__ import annotations

from typing import Dict, Type, Match

import regex as re

from rka.components.events import EventStub, Event


class ClientEvent(Event):
    def __init__(self, **kwargs):
        Event.__init__(self, **kwargs)

    def set_client_id(self, client_id: str):
        self.set_param('client_id', client_id)

    def get_client_id(self) -> str:
        return self.get_param('client_id')

    def set_timestamp(self, timestamp: float):
        self.set_param('timestamp', timestamp)

    def get_timestamp(self) -> float:
        return self.get_param('timestamp')

    def clone(self) -> ClientEvent:
        # noinspection PyTypeChecker
        return Event.clone(self)


class ParserEvent(ClientEvent):
    def __init__(self, **kwargs):
        ClientEvent.__init__(self, **kwargs)

    def match(self) -> Match:
        # noinspection PyUnresolvedReferences
        match = re.match(self.parse_filter, self.matched_text)
        return match

    def clone(self) -> ParserEvent:
        # noinspection PyTypeChecker
        return Event.clone(self)


class ClientEventStub(EventStub):
    def __init__(self, event_params: Dict[str, Type]):
        assert 'client_id' in event_params.keys()
        assert 'timestamp' in event_params.keys()
        EventStub.__init__(self, event_params)

    def get_event_base_class(self) -> Type[Event]:
        return ClientEvent


class ParserEventStub(ClientEventStub):
    def __init__(self, event_params: Dict[str, Type]):
        ClientEventStub.__init__(self, event_params)

    def get_event_base_class(self) -> Type[Event]:
        return ParserEvent


def client_event(**kwargs) -> EventStub:
    return ClientEventStub(kwargs)


def parser_event(**kwargs) -> EventStub:
    return ParserEventStub(kwargs)
