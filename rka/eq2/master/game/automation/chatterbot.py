from typing import Optional, List

from rka.eq2.master import HasRuntime
from rka.eq2.master.game.automation import ChatMessage


class SillyChat:
    def __init__(self, runtime: HasRuntime):
        self.__runtime = runtime

    @staticmethod
    def __has_keyword(message: str, keywords: List[str]) -> bool:
        for keyword in keywords:
            if keyword in message:
                return True
        return False

    # noinspection PyMethodMayBeStatic
    def get_response(self, message: ChatMessage) -> Optional[str]:
        message = message.tell.lower()
        if SillyChat.__has_keyword(message, ['hi', 'hello', 'hey', 'hiya', 'greetings']):
            return 'hello'
        elif 'hug' in message:
            return '/hugs'
        return None
