from typing import Union, List, Optional

from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.triggers import ITrigger, IPlayerTrigger
from rka.eq2.master.triggers.trigger import PlayerTrigger
from rka.eq2.master.triggers.trigger_actions import TTSTriggerAction, LogTriggerAction
from rka.eq2.master.triggers.trigger_subscribers import EventSubscriberToolkit


class PlayerTriggerFactory:
    def __init__(self, runtime: IRuntime, player: IPlayer):
        self.__runtime = runtime
        self.__player = player

    def get_runtime(self) -> IRuntime:
        return self.__runtime

    def get_player(self) -> IPlayer:
        return self.__player

    def new_trigger(self, name: Optional[str] = None) -> IPlayerTrigger:
        return PlayerTrigger(self.__runtime, self.__player.get_client_id(), name)

    def voice_trigger(self, parse_filters: Union[str, List[str]], message: str) -> ITrigger:
        trigger = self.new_trigger(name=f'TTS: {message}')
        if not isinstance(parse_filters, list):
            parse_filters = [parse_filters]
        for parse_filter in parse_filters:
            EventSubscriberToolkit.add_parser_events_to_trigger(trigger=trigger, parse_filters=parse_filter)
        trigger.add_action(TTSTriggerAction(self.__runtime, message, interrupts=True))
        trigger.add_action(LogTriggerAction(self.__runtime, message, Severity.Low))
        return trigger

    def log_trigger(self, parse_filters: Union[str, List[str]], message: str, severity: Severity) -> ITrigger:
        trigger = self.new_trigger(name=f'LOG: {message}')
        if not isinstance(parse_filters, list):
            parse_filters = [parse_filters]
        for parse_filter in parse_filters:
            EventSubscriberToolkit.add_parser_events_to_trigger(trigger=trigger, parse_filters=parse_filter)
        trigger.add_action(LogTriggerAction(self.__runtime, message, severity))
        return trigger
