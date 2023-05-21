from typing import List

from rka.eq2.master.game.scripting.procedures.common import TriggerReaderProcedure
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit
from rka.eq2.shared.client_events import ClientEvents


class GroupMemberCheckerProcedure(TriggerReaderProcedure):
    def __init__(self, scripting: PlayerScriptingToolkit, whocommand='whogroup'):
        TriggerReaderProcedure.__init__(self, scripting, game_command=whocommand)
        self._get_trigger().add_parser_events(r'([A-Z]\w+) Lvl \d+.*')

    def _get_object(self, event: ClientEvents.PARSER_MATCH) -> str:
        return event.match().group(1)

    def get_group_members(self) -> List[str]:
        self.clear_last_results()
        self._get_trigger().start_trigger()
        try:
            self._get_new_result()
            # wait for remaining player names
            self._get_toolkit().sleep(0.3)
        finally:
            self._get_trigger().cancel_trigger()
        names = self.get_last_results()
        names.insert(0, self._get_player().get_player_name())
        return names
