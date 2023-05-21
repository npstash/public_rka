from typing import Optional, Tuple

from rka.components.resources import Resource
from rka.components.ui.capture import Offset
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.rka_constants import SERVER_REACT_DELAY
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.game.scripting import RepeatMode, ScriptException
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.toolkit import Procedure, PlayerScriptingToolkit


class LoginProcedure(Procedure):
    STATUS_REACHED_COOLDOWN = 70.0
    SCREEN_REACHED_COOLDOWN = 20.0
    COOLDOWN_CHECK_PERIOD = 5.0

    def __init__(self, scripting: PlayerScriptingToolkit, target_player: Optional[IPlayer] = None):
        Procedure.__init__(self, scripting)
        self.target_player = target_player

    def __input_one_field(self, field_pattern: Resource, text: str) -> bool:
        offset = Offset(x=150, y=0, anchor=Offset.REL_FIND_MID)
        if not self._get_player_toolkit().click_match(pattern=field_pattern, repeat=RepeatMode.DONT_REPEAT, threshold=0.9,
                                                      click_offset=offset, delay=0.0):
            return False
        clear_field = action_factory.new_action().key('backspace', count=20).key('delete', count=20)
        if not self._get_player_toolkit().player_bool_action(clear_field):
            return False
        ac_type_text = action_factory.new_action().text(text, key_type_delay=0.2)
        if not self._get_player_toolkit().player_bool_action(ac_type_text):
            return False
        return True

    def is_in_login_screen(self) -> bool:
        self._get_player_toolkit().try_close_all_windows(close_externals=True)
        rect = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_FIELD_PASSWORD,
                                                            repeat=RepeatMode.DONT_REPEAT, threshold=0.9)
        return rect is not None

    def is_in_character_screen(self) -> bool:
        rect = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_PLAY, repeat=RepeatMode.DONT_REPEAT)
        return rect is not None

    def __proceed_non_login_screen(self) -> Tuple[bool, bool]:
        # check if character select menu
        if self.is_in_character_screen():
            self._get_runtime().overlay.log_event(f'Character screen login: {self.target_player}', Severity.Normal)
            clicked_play = self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_PLAY, repeat=RepeatMode.DONT_REPEAT, delay=SERVER_REACT_DELAY)
            return True, clicked_play
        # not character select menu, no password field -> assuming no login required
        self._get_runtime().overlay.log_event(f'Not in login screen: {self.target_player}', Severity.Normal)
        if self.target_player.get_status() < PlayerStatus.Logged:
            logger.warn(f'Login not required, but not Logged status {self.target_player}')
            self._get_runtime().request_ctrl.request_zone_discovery(self.target_player)
            self._get_toolkit().sleep(5.0)
        return False, True

    def __proceed_login_screen(self) -> Tuple[bool, bool]:
        self._get_runtime().overlay.log_event(f'Login {self.target_player} started', Severity.Normal)
        if self.target_player.is_logged():
            if self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_EQ2_MENU, repeat=RepeatMode.DONT_REPEAT):
                logger.info(f'Character {self.target_player} already logged in')
                return False, False
            logger.warn(f'Character {self.target_player} already logged in, but not in game (?)')
        key = self.target_player.get_client_config_data().cred_key
        credentials = self._get_runtime().credentials.get_credentials(key)
        if not credentials:
            logger.error(f'Could not read credentials for record key: {key}')
            return True, False
        if 'login' not in credentials or 'password' not in credentials:
            logger.error(f'Invalid credentials dict for record key: {key}')
            return True, False
        login = credentials['login']
        password = credentials['password']
        if not self.__input_one_field(field_pattern=ui_patterns.PATTERN_FIELD_USERNAME, text=login):
            return True, False
        if not self.__input_one_field(field_pattern=ui_patterns.PATTERN_FIELD_CHARNAME, text=self.target_player.get_player_name()):
            return True, False
        if not self.__input_one_field(field_pattern=ui_patterns.PATTERN_FIELD_WORLD, text=self.target_player.get_server().servername):
            return True, False
        for attempt in range(5):
            if not self.__input_one_field(field_pattern=ui_patterns.PATTERN_FIELD_PASSWORD, text=password):
                return True, False
            if not self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_LOGIN, repeat=RepeatMode.DONT_REPEAT, delay=5.0):
                return True, False
            # see if there isnt an immediate error
            while self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_LOGIN_PRESSED, repeat=RepeatMode.DONT_REPEAT):
                self._get_player_toolkit().sleep(1.0)
            if self._get_player_toolkit().try_click_ok(click_delay=SERVER_REACT_DELAY):
                continue
            # connection errors
            login_wait = 60
            # separate the loop condition to be able to catch exception
            try:
                while True:
                    if not self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_CANCEL, repeat=RepeatMode.DONT_REPEAT):
                        break
                    login_wait -= 1
                    if login_wait <= 0:
                        return True, False
                    self._get_player_toolkit().sleep(1.0)
                if self._get_player_toolkit().try_click_ok(click_delay=SERVER_REACT_DELAY):
                    continue
            except ScriptException:
                # it occurs when client changes and old one becomes unavailable, i.e. login succeeds
                return True, True
            # passed all checks, login successful
            return True, True
        return True, False

    # result: login_was_required: bool, login_succeeded: bool
    def login_player(self) -> Tuple[bool, bool]:
        if not self.target_player:
            self.target_player = self._get_player()
        if self.is_in_login_screen():
            return self.__proceed_login_screen()
        return self.__proceed_non_login_screen()

    # result: success, player_change
    def wait_for_login_start(self) -> Tuple[bool, bool]:
        if not self.target_player:
            self.target_player = self._get_player()
        login_started = False
        try:
            self._get_runtime().overlay.log_event(f'Login starting: {self.target_player}', Severity.Normal)
            for _ in range(60):
                loading_label = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_GFX_EVERQUEST_II_LOADING,
                                                                             repeat=RepeatMode.DONT_REPEAT)
                self._get_player_toolkit().sleep(1.0)
                if loading_label:
                    login_started = True
                    break
            self._get_runtime().overlay.log_event(f'Login started ({login_started}): {self.target_player}', Severity.Normal)
            return login_started, False
        except ScriptException:
            logger.info(f'When waiting for login start, {self._get_player()} logged out')
            return login_started, True

    # result: success, player_change
    def wait_for_login_complete(self) -> Tuple[bool, bool]:
        if not self.target_player:
            self.target_player = self._get_player()
        login_completed = False
        try:
            self._get_runtime().overlay.log_event(f'Login finishing: {self.target_player}', Severity.Low)
            for _ in range(60):
                loading_label = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_GFX_EVERQUEST_II_LOADING,
                                                                             repeat=RepeatMode.DONT_REPEAT)
                if not loading_label:
                    login_completed = True
                    break
                self._get_player_toolkit().sleep(1.0)
            self._get_runtime().overlay.log_event(f'Login finished ({login_completed}): {self.target_player}', Severity.Normal)
            return login_completed, False
        except ScriptException:
            logger.warn(f'When waiting for login finish, {self._get_player()} logged out')
            return login_completed, True

    def zoning_cooldown(self):
        if not self.target_player:
            self.target_player = self._get_player()
        self._get_runtime().overlay.log_event(f'Zoning cooldown for {self.target_player}', Severity.Normal)
        for _ in range(5):
            # TODO preferably try to get location until it is acquired?
            self._get_player_toolkit().sleep(2.0)
            if self._get_player_toolkit().try_close_all_windows():
                break
        self._get_runtime().overlay.log_event(f'Zoning cooldown for {self.target_player} completed', Severity.Normal)

    # result: player_change
    def login_cooldown(self) -> bool:
        if not self.target_player:
            self.target_player = self._get_player()
        self._get_runtime().overlay.log_event(f'Login cooldown for {self.target_player}', Severity.Normal)
        supposed_player_change = False
        status_reached = False
        screen_reached = False
        remaining_time = LoginProcedure.STATUS_REACHED_COOLDOWN + LoginProcedure.SCREEN_REACHED_COOLDOWN
        while remaining_time > 0.0:
            try:
                if not status_reached and self.target_player.get_status() >= PlayerStatus.Logged:
                    remaining_time = LoginProcedure.STATUS_REACHED_COOLDOWN if not screen_reached else LoginProcedure.SCREEN_REACHED_COOLDOWN
                    status_reached = True
                if not screen_reached and self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_BUTTON_EQ2_MENU,
                                                                                       repeat=RepeatMode.DONT_REPEAT):
                    remaining_time = LoginProcedure.SCREEN_REACHED_COOLDOWN if status_reached else LoginProcedure.STATUS_REACHED_COOLDOWN
                    screen_reached = True
                self._get_player_toolkit().sleep(LoginProcedure.COOLDOWN_CHECK_PERIOD)
                if not supposed_player_change:
                    self._get_player_toolkit().try_close_all_windows()
            except ScriptException:
                supposed_player_change = True
                break
            remaining_time -= LoginProcedure.COOLDOWN_CHECK_PERIOD
        self._get_runtime().overlay.log_event(
            f'Login cooldown for {self.target_player} finished, change: {supposed_player_change}, status: {status_reached}, screen: {screen_reached}',
            Severity.Normal)
        return supposed_player_change
