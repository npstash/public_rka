from rka.components.events.event_system import EventSystem
from rka.eq2.master import IRuntime
from rka.eq2.master.game.automation import logger
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.scripting.scripts.ui_interaction_scripts import AcceptCommission
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.shared.flags import MutableFlags


class PlayerAutomation:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        EventSystem.get_main_bus().subscribe(MasterEvents.CLIENT_REGISTERED(), self.__start_automation)
        EventSystem.get_main_bus().subscribe(MasterEvents.CLIENT_UNREGISTERED(), self.__stop_automation)

    def __start_automation(self, event: MasterEvents.CLIENT_REGISTERED):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        EventSystem.get_main_bus().subscribe(CombatEvents.PLAYER_DIED(player=player), self.__on_death)
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.COMMISSION_OFFERED(offered_player=player, crafter_is_my_player=True), self.__on_commission)

    def __stop_automation(self, event: MasterEvents.CLIENT_UNREGISTERED):
        player = self.__runtime.player_mgr.get_player_by_client_id(event.client_id)
        EventSystem.get_main_bus().unsubscribe(CombatEvents.PLAYER_DIED(player=player), self.__on_death)
        EventSystem.get_main_bus().unsubscribe(PlayerInfoEvents.COMMISSION_OFFERED(offered_player=player, crafter_is_my_player=True), self.__on_commission)

    def __on_commission(self, event: PlayerInfoEvents.COMMISSION_OFFERED):
        script = AcceptCommission(player_sel=event.offered_player, craft_count_limit=1, time_limit=10.0)
        self.__runtime.processor.run_auto(script)

    def __on_death(self, event: CombatEvents.PLAYER_DIED):
        allow_autorez = False
        if event.player.is_local() and MutableFlags.AUTO_ACCEPT_REZ and MutableFlags.AUTO_ACCEPT_REZ_MAIN_PLAYER:
            allow_autorez = True
        if event.player.is_remote() and MutableFlags.AUTO_ACCEPT_REZ:
            allow_autorez = True
        if allow_autorez:
            logger.info(f'Attempting to accept rez on {event.player} or revive')
            self.__runtime.request_ctrl.request_rez_or_revive(event.player)
