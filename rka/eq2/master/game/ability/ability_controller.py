import datetime
import time

from rka.components.events.event_system import CloseableSubscriber, EventSystem
from rka.eq2.master import IRuntime, RequiresRuntime
from rka.eq2.master.game.ability import AbilityType
from rka.eq2.master.game.ability.ability_filter import AbilityFilter
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.object_state import ObjectStateEvents
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import TAbilityFilter, IPlayer, IAbilityMonitorConfigurator, IAbilityMonitor, IAbility
from rka.eq2.master.game.player import PlayerStatus


class AbilityController(CloseableSubscriber):
    def __init__(self, runtime: IRuntime):
        CloseableSubscriber.__init__(self, EventSystem.get_main_bus())
        self.__runtime = runtime
        # zone change -> reset ability
        self.subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__expire_abilities_zone_change)
        # group change -> reset ability
        self.subscribe(PlayerInfoEvents.PLAYER_JOINED_GROUP(my_player=True), lambda event: self.__expire_abilities_group_change(event.player))
        self.subscribe(PlayerInfoEvents.PLAYER_LEFT_GROUP(my_player=True), lambda event: self.__expire_abilities_group_change(event.player))
        self.subscribe(PlayerInfoEvents.PLAYER_GROUP_DISBANDED(), lambda event: self.__expire_abilities_group_change(event.main_player))
        # death or revive -> reset ability
        self.subscribe(CombatEvents.PLAYER_REVIVED(), lambda event: self.__expire_abilities_death(event.player))
        self.subscribe(CombatEvents.PLAYER_DIED(), lambda event: self.__expire_abilities_death(event.player))
        self.subscribe(CombatEvents.PLAYER_DEATHSAVED(), self.__expire_abilities_deathsaved)
        # login/logout -> start/stop ability monitoring
        self.subscribe(ObjectStateEvents.PLAYER_STATUS_CHANGED(), self.__monitor_abilities)
        # ability reset
        self.subscribe(CombatEvents.READYUP(), self.__reset_abilities)

    def __monitor_abilities(self, event: ObjectStateEvents.PLAYER_STATUS_CHANGED):
        class RuntimeConfigurator(IAbilityMonitorConfigurator):
            def __init__(self, runtime: IRuntime):
                self.__runtime = runtime

            def configure_monitor(self, _ability: IAbility, ability_monitor: IAbilityMonitor):
                if isinstance(ability_monitor, RequiresRuntime):
                    ability_monitor.set_runtime(self.__runtime)

        logged_in = event.from_status < PlayerStatus.Logged <= event.to_status
        logged_out = event.from_status >= PlayerStatus.Logged > event.to_status
        if not logged_in and not logged_out:
            return
        configurator = RuntimeConfigurator(self.__runtime)
        for ability in self.__runtime.ability_reg.find_abilities(lambda a: a.player == event.player):
            if logged_in:
                ability.start_ability_monitoring(configurator)
            else:
                ability.stop_ability_monitoring()

    def __reset_abilities(self, event: CombatEvents.READYUP):
        # its enough to reset one variant, they share timers
        variants = set()
        for ability in self.__runtime.ability_reg.find_abilities(lambda a: a.player == event.player and a.ability_unique_key() not in variants):
            variants.add(ability.ability_unique_key())
            if not ability.ext.has_census or not ability.census.level or ability.ext.cannot_modify:
                continue
            if ability.census.type == AbilityType.ascension or not ability.ext.reset_on_readyup:
                continue
            if event.player.get_last_cast_ability() == ability:
                continue
            if ability.ext.maintained and not ability.is_duration_expired():
                continue
            if event.player.is_class(GameClasses.Fighter) or event.player.is_class(GameClasses.Scout):
                if ability.census.type == AbilityType.arts:
                    ability.reset_reuse()
            elif event.player.is_class(GameClasses.Priest) or event.player.is_class(GameClasses.Mage):
                if ability.census.type == AbilityType.spells:
                    ability.reset_reuse()

    def __expire_abilities_zone_change(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        self.__expire_abilities(AbilityFilter().resets_on_zone_change().is_sustained_by(sustainer=event.player, target=event.player))

    def __expire_abilities_deathsaved(self, event: CombatEvents.PLAYER_DEATHSAVED):
        self.__expire_abilities(AbilityFilter().is_deathsave().is_sustained_by(sustainer=None, target=event.player))

    def __expire_abilities_death(self, player: IPlayer):
        self.__expire_abilities(AbilityFilter().resets_on_death().is_sustained_by(sustainer=player, target=player))

    def __expire_abilities_group_change(self, player: IPlayer):
        self.__expire_abilities(AbilityFilter().is_sustained_to_group(player))

    def __expire_abilities(self, ability_filter: TAbilityFilter) -> int:
        reset_count = 0
        now_ts = time.time()
        now_dt = datetime.datetime.fromtimestamp(now_ts)
        abilities_to_reset = self.__runtime.ability_reg.find_abilities(ability_filter)
        for ability in abilities_to_reset:
            ability.expire_duration(now_dt)
            reset_count += 1
        return reset_count
