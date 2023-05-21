from rka.components.cleanup import Closeable
from rka.eq2.master import IRuntime
from rka.eq2.master.game.automation.autocombat import Autocombat
from rka.eq2.master.game.automation.autopilot import Autopilot
from rka.eq2.master.game.automation.conversation import ConversationPump
from rka.eq2.master.game.automation.player_automation import PlayerAutomation
from rka.eq2.master.game.automation.safetymonitor import SafetyMonitor
from rka.eq2.master.game.automation.screen_automation import ScreenAutomation
from rka.eq2.master.game.state.detriments import Autocure


class Automation(Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=True)
        self.autocombat = Autocombat(runtime)
        self.autopilot = Autopilot(runtime)
        self.conversation = ConversationPump(runtime)
        self.autocure = Autocure(runtime, runtime.request_ctrl)
        self.player_reactions = PlayerAutomation(runtime)
        self.security = SafetyMonitor(runtime)
        self.screen_reactions = ScreenAutomation(runtime)

    def close(self):
        self.screen_reactions.close()
        Closeable.close(self)
