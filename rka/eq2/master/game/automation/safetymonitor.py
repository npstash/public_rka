import time

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.player import TellType


class SafetyMonitor:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        EventSystem.get_main_bus().subscribe(ChatEvents.PLAYER_TELL(), self.check_tells)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.FRIEND_LOGGED(), self.check_friends)
        self.__known_gms = {'serl', 'woebot'}
        self.__last_tell = 0.0
        self.__last_logon = 0.0

    def check_tells(self, event: ChatEvents.PLAYER_TELL):
        now = time.time()
        if now - self.__last_tell < 30.0:
            return
        self.__last_tell = now
        if event.tell_type in [TellType.tell, TellType.say, TellType.shout, TellType.ooc]:
            if 'GM' in event.from_player_name or event.from_player_name.lower() in self.__known_gms or 'AFK check' in event.tell or 'GM ' in event.tell:
                msg = f'**GM** to {event.to_player}: {event.tell}'
                self.__runtime.tts.say(msg)
                self.__runtime.overlay.log_event(msg, Severity.Critical)
                self.__runtime.overlay.display_warning(warning_text=f'GM to {event.to_player.get_player_name()[:5]}', duration=10.0)
                self.__runtime.key_manager.pause(True)
                self.__runtime.request_ctrl.request_group_stop_all()
                self.__runtime.control_menu.stop_scripts()
                self.__runtime.processor.clear_processor()
                self.__runtime.notification_service.post_notification(msg)

    def check_friends(self, event: PlayerInfoEvents.FRIEND_LOGGED):
        now = time.time()
        if now - self.__last_logon < 3.0:
            return
        self.__last_logon = now
        if event.friend_name.lower() not in self.__known_gms:
            return
        event_id = f'GM {event.friend_name}'
        if event.login:
            msg = f'GM login {event.friend_name}'
            self.__runtime.tts.say(msg)
            self.__runtime.overlay.log_event(msg, Severity.Critical, event_id=event_id)
            self.__runtime.overlay.display_warning(warning_text=msg, duration=3.0)
            self.__runtime.notification_service.post_notification(msg)
        else:
            msg = f'GM logout {event.friend_name}'
            self.__runtime.tts.say(msg)
            self.__runtime.overlay.log_event(None, Severity.Critical, event_id=event_id)
