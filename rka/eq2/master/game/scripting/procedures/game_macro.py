from rka.eq2.configs.shared.rka_constants import SERVER_REACT_DELAY
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.scripting import RepeatMode
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit, Procedure


class MacroBuilder(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)

    def start_new_macro(self, hotbar: int, slot: int, macro_name: str) -> bool:
        cmd = self._get_player_toolkit().build_command(f'createmacrofromability 0 {hotbar} {slot}\n')
        self._get_player_toolkit().call_player_action(cmd, delay=SERVER_REACT_DELAY)
        if not self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_FIELD_MACRO_NAME, repeat=RepeatMode.REPEAT_ON_FAIL, threshold=0.7):
            return False
        self._get_player_toolkit().call_player_action(action_factory.new_action().text(macro_name))
        return True

    def add_command_to_current_macro(self, macro_line: str):
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_ADD_STEP, repeat=RepeatMode.DONT_REPEAT)
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_FIELD_MACRO_COMMAND, repeat=RepeatMode.DONT_REPEAT)
        self._get_player_toolkit().call_player_action(action_factory.new_action().text(macro_line))

    def finish_current_macro(self):
        self._get_player_toolkit().click_match(pattern=ui_patterns.PATTERN_BUTTON_MACRO_OK, repeat=RepeatMode.DONT_REPEAT)
