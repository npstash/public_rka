import time
from typing import List

from rka.components.events import Event
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.eq2.master import RequiresRuntime
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.interfaces import IAbility, IAbilityMonitor, IRunningAbilityMonitor
from rka.log_configs import LOG_ABILITY_CASTING

logger = LogService(LOG_ABILITY_CASTING)


class AbstractAbilityMonitor(IAbilityMonitor):
    def __init__(self):
        pass

    def get_subscription_event(self, ability: IAbility) -> Event:
        raise NotImplementedError()

    def notify_monitor(self, ability: IAbility, event: Event, timestamp: float):
        raise NotImplementedError()

    def start_monitoring(self, ability: IAbility) -> IRunningAbilityMonitor:
        subscription_event = self.get_subscription_event(ability)
        running_monitor = RunningAbilityMonitor(self, ability, subscription_event)
        EventSystem.get_main_bus().subscribe(subscription_event, running_monitor.event_callback)
        return running_monitor


class RunningAbilityMonitor(IRunningAbilityMonitor):
    def __init__(self, monitor: AbstractAbilityMonitor, ability: IAbility, subscribed_event: Event):
        self.monitor = monitor
        self.ability = ability
        self.subscribed_event = subscribed_event

    def event_callback(self, event: Event):
        if 'timestamp' in event.param_names:
            timestamp = event.get_param('timestamp')
        else:
            timestamp = time.time()
        self.monitor.notify_monitor(self.ability, event, timestamp)

    def stop_monitoring(self):
        EventSystem.get_main_bus().unsubscribe(self.subscribed_event, self.event_callback)

    def start_for_clone(self, ability: IAbility) -> IRunningAbilityMonitor:
        return self.monitor.start_monitoring(ability)


class EventAbilityCastingStartedMonitor(AbstractAbilityMonitor):
    def __init__(self, event_template: Event):
        AbstractAbilityMonitor.__init__(self)
        self.event_template = event_template

    def get_subscription_event(self, ability: IAbility) -> Event:
        return self.event_template

    def notify_monitor(self, ability: IAbility, event: Event, timestamp: float):
        ability.confirm_casting_started(cancel_action=True, when=timestamp)


class EventAbilityCastingCompletedMonitor(AbstractAbilityMonitor):
    def __init__(self, event_template: Event):
        AbstractAbilityMonitor.__init__(self)
        self.event_template = event_template

    def get_subscription_event(self, ability: IAbility) -> Event:
        return self.event_template

    def notify_monitor(self, ability: IAbility, event: Event, timestamp: float):
        ability.confirm_casting_completed(cancel_action=True, when=timestamp)


class EventAbilityExpirationMonitor(AbstractAbilityMonitor):
    def __init__(self, event_template: Event):
        AbstractAbilityMonitor.__init__(self)
        self.event_template = event_template

    def get_subscription_event(self, ability: IAbility) -> Event:
        return self.event_template

    def notify_monitor(self, ability: IAbility, event: Event, timestamp: float):
        ability.expire_duration(when=timestamp)


class WardExpirationMonitor(AbstractAbilityMonitor):
    def __init__(self):
        AbstractAbilityMonitor.__init__(self)

    def get_subscription_event(self, ability: IAbility) -> Event:
        if ability.get_target():
            target_name = ability.get_target().get_target_name()
            event = CombatParserEvents.WARD_EXPIRED(caster_name=ability.player.get_player_name(), ability_name=ability.ext.ability_name, target_name=target_name)
        else:
            event = CombatParserEvents.WARD_EXPIRED(caster_name=ability.player.get_player_name(), ability_name=ability.ext.ability_name)
        return event

    def notify_monitor(self, ability: IAbility, event: Event, timestamp: float):
        ability.expire_duration(when=timestamp)


class BulwarkCastingCompletedMonitor(AbstractAbilityMonitor, RequiresRuntime):
    def __init__(self):
        AbstractAbilityMonitor.__init__(self)
        RequiresRuntime.__init__(self)

    def get_subscription_event(self, ability: IAbility) -> Event:
        return CombatEvents.BULWARK_APPLIED()

    def notify_monitor(self, ability: IAbility, event: CombatEvents.BULWARK_APPLIED, timestamp: float):
        runtime = self.get_runtime()
        logger.debug(f'bulwark monitor: ability={ability}, event={event}')
        is_main_group = False
        protected_player = runtime.player_mgr.get_player_by_name(event.applied_by)
        if protected_player:
            # bulwark applied by one of my players
            is_main_group = protected_player.is_in_group_with(ability.player)
            logger.debug(f'bulwark monitor: protected_player={protected_player}, is_main_group={is_main_group}')
        elif ability.player.get_client_config_data().group_id.is_main_group():
            # check if bulwark is applied by an unknown player in main group; else its unknown
            if runtime.zonestate.is_player_in_main_group(event.applied_by):
                is_main_group = True
            logger.debug(f'bulwark monitor: bulwark for main grp, is_main_group={is_main_group}')
        if not is_main_group:
            logger.info(f'ignore bulwark event: from other group: {event}')
            return
        logger.info(f'bulwark event from: {event.applied_by}. is_main_group: {is_main_group}')
        ability.confirm_casting_completed(cancel_action=True, when=timestamp)


class DefaultMonitorsFactory:
    @staticmethod
    def create_default_monitors(ability: IAbility) -> List[IAbilityMonitor]:
        monitors = list()
        if ability.ext.ward_expires and not (ability.census.does_not_expire or ability.ext.maintained):
            monitors.append(WardExpirationMonitor())
        return monitors
