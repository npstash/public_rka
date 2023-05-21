from __future__ import annotations

from threading import Condition, RLock
from typing import List, Optional, Set

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.automation import ChatMessage, logger
from rka.eq2.master.game.automation.chatter_commands import ChatterCommands
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.player import TellType
from rka.eq2.master.game.scripting.framework import PlayerScriptTask


class MessageAuthorization:
    def __init__(self):
        self.__authorized_players: Set[str] = set()

    def auhtorize_player(self, player_name: str):
        self.__authorized_players.add(player_name)

    def auhtorize_player_message(self, runtime: IRuntime, message: ChatMessage) -> bool:
        # only allow tells from own or authorized players
        from_player = runtime.player_mgr.get_player_by_name(message.from_player_name)
        if from_player:
            return True
        is_authorized = message.from_player_name in self.__authorized_players
        if is_authorized:
            return True
        return False


class ConversationPump:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        self.__lock = RLock()
        self.__conversation_agent_script: Optional[ConversationAgentScript] = None
        EventSystem.get_main_bus().subscribe(ChatEvents.PLAYER_TELL(), self.player_message)

    def player_message(self, event: ChatEvents.PLAYER_TELL):
        with self.__lock:
            if self.__conversation_agent_script:
                assert isinstance(self.__conversation_agent_script, ConversationAgentScript)
                if not self.__conversation_agent_script.is_running():
                    self.__conversation_agent_script = None
            if not self.__conversation_agent_script:
                logger.info(f'Starting ConversationAgentScript because of {event}')
                self.__conversation_agent_script = ConversationAgentScript()
                self.__runtime.processor.run_auto(self.__conversation_agent_script)
        self.__conversation_agent_script.message_to_player(ChatMessage.from_event(event))


class ConversationAgentScript(PlayerScriptTask):
    def __init__(self):
        PlayerScriptTask.__init__(self, description='Conversation Agent Script', duration=-1.0)
        self.__commands: List[ChatMessage] = list()
        self.__commands_lock = Condition()
        self.__authorizator = MessageAuthorization()
        self.__chatter_commands = ChatterCommands()
        self.set_silent()
        self.set_singleton(override_previous=True)

    def close(self):
        super().close()
        with self.__commands_lock:
            self.__commands_lock.notify()

    def message_to_player(self, message: ChatMessage):
        with self.__commands_lock:
            self.__commands.append(message)
            self.__commands_lock.notify()

    def _run(self, _runtime: IRuntime):
        while self.__handle_one_message():
            pass

    def __allow_message(self, message: ChatMessage) -> bool:
        # can be None
        from_player = self.get_runtime().player_mgr.get_player_by_name(message.from_player_name)
        # only local player can receive its own messages (group/raid tells)
        if message.to_local:
            if from_player and from_player.is_local():
                return True
            return False
        # allow message to remote players, except when they are received by local player
        if not message.to_player.is_remote():
            return False
        # for remote players, only read private tells
        if message.tell_type != TellType.tell:
            return False
        psf = self.get_player_scripting_framework(message.to_player)
        authorize = ChatterCommands.interpret_command(self.get_runtime(), psf, message, self.__chatter_commands.authorize_commands)
        if authorize:
            self.get_runtime().overlay.log_event(f'Authorized {message.from_player_name} with {message.tell}', Severity.High)
            self.__authorizator.auhtorize_player(message.from_player_name)
        authorized = self.__authorizator.auhtorize_player_message(self.get_runtime(), message)
        if not authorized:
            notification_msg = f'Unauthorized "{message.tell}" from {message.from_player_name}'
            self.get_runtime().overlay.log_event(notification_msg, Severity.High)
            self.get_runtime().notification_service.post_notification(notification_msg)
            return False
        return True

    def __handle_one_message(self) -> bool:
        with self.__commands_lock:
            while not self.__commands and self.is_running():
                self.__commands_lock.wait()
        if not self.is_running():
            return False
        message = self.__commands.pop(0)
        if not self.__allow_message(message):
            return True
        psf = self.get_player_scripting_framework(message.to_player)
        if message.to_player.is_local():
            ChatterCommands.interpret_command(self.get_runtime(), psf, message, self.__chatter_commands.local_player_commands)
        else:
            self.get_runtime().overlay.log_event(f'Coversation: {message.tell} to {message.to_player}', Severity.Normal)
            ChatterCommands.interpret_command(self.get_runtime(), psf, message, self.__chatter_commands.remote_player_commands)
        return True
