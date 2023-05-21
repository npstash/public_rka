from json.encoder import JSONEncoder
from typing import Any, Optional

from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.location import Location
from rka.eq2.master.game.player import PlayerStatus
from rka.util.util import NameEnum


class EventParamSerializer(JSONEncoder):
    class Prefix:
        player = '$player='
        location = '$location='
        playerstatus = '$playerstatus='

    def __init__(self, runtime: IRuntime, **kwargs):
        JSONEncoder.__init__(self, **kwargs)
        self.runtime = runtime

    def map_intenum(self, data):
        if isinstance(data, PlayerStatus):
            return f'{EventParamSerializer.Prefix.playerstatus}{data.name}'
        if isinstance(data, dict):
            return {k: self.map_intenum(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [self.map_intenum(v) for v in data]
        return data

    def iterencode(self, o, _one_shot=False):
        o = self.map_intenum(o)
        return super().iterencode(o, _one_shot)

    def default(self, obj: Any) -> Any:
        if isinstance(obj, NameEnum):
            return obj.value
        elif isinstance(obj, IPlayer):
            return f'{EventParamSerializer.Prefix.player}{obj.get_player_name()}'
        elif isinstance(obj, Location):
            return f'{EventParamSerializer.Prefix.location}{obj.encode_location()}'
        return super().default(obj)

    @staticmethod
    def __get_params(s: str) -> str:
        return s[s.index('=') + 1:]

    def get_player(self, data: str) -> Optional[IPlayer]:
        return self.runtime.player_mgr.get_player_by_name(data)

    # noinspection PyMethodMayBeStatic
    def get_location(self, data: str) -> Location:
        return Location.decode_location(data)

    # noinspection PyMethodMayBeStatic
    def get_playerstatus(self, data: str) -> PlayerStatus:
        return PlayerStatus[data]

    def json_to_object(self, obj) -> Any:
        if isinstance(obj, str) and obj.startswith('$'):
            if obj.startswith(EventParamSerializer.Prefix.player):
                return self.get_player(EventParamSerializer.__get_params(obj))
            if obj.startswith(EventParamSerializer.Prefix.location):
                return self.get_location(EventParamSerializer.__get_params(obj))
            if obj.startswith(EventParamSerializer.Prefix.playerstatus):
                return self.get_playerstatus(EventParamSerializer.__get_params(obj))
        return obj
