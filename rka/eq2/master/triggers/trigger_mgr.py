from threading import RLock
from typing import List, Dict, Optional

from rka.components.cleanup import Closeable
from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game import is_unknown_zone
from rka.eq2.master.game.events.player_info import PlayerInfoEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.master.triggers import ITrigger, logger
from rka.eq2.master.triggers.combat_triggers import CombatTriggers
from rka.eq2.master.triggers.control_triggers import ControlTriggers
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.master.triggers.trigger_spec import TriggerSpec
from rka.eq2.master.triggers.trigger_util import TriggerUtil


class ZoneScriptTriggers(PlayerTriggerFactory):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        PlayerTriggerFactory.__init__(self, runtime, player)


class TriggerFactoryBundle:
    def __init__(self, runtime: IRuntime, player: IPlayer):
        self.combat = CombatTriggers(runtime, player)
        self.control = ControlTriggers(runtime, player)
        self.zone = ZoneScriptTriggers(runtime, player)
        self.created = PlayerTriggerFactory(runtime, player)


class TriggerManager(Closeable):
    def __init__(self, runtime: IRuntime):
        Closeable.__init__(self, explicit_close=False)
        self.__runtime = runtime
        self.__lock = RLock()
        self.__factories: Dict[str, TriggerFactoryBundle] = dict()
        self.__loaded_player_triggers: Dict[IPlayer, List[ITrigger]] = dict()
        self.__running_zone_triggers: Dict[IPlayer, List[ITrigger]] = dict()
        self.__running_zone_name = None
        EventSystem.get_main_bus().subscribe(PlayerInfoEvents.PLAYER_ZONE_CHANGED(), self.__event_zone_changed)

    def __get_factory(self, player: IPlayer) -> TriggerFactoryBundle:
        client_id = player.get_client_id()
        with self.__lock:
            if client_id not in self.__factories:
                self.__factories[client_id] = TriggerFactoryBundle(self.__runtime, player)
            return self.__factories[client_id]

    def __get_zone_trigger_list(self, player: IPlayer) -> List[ITrigger]:
        return self.__running_zone_triggers.setdefault(player, list())

    def __get_player_trigger_list(self, player: IPlayer) -> List[ITrigger]:
        if player not in self.__loaded_player_triggers.keys():
            self.__loaded_player_triggers[player] = list()
        return self.__loaded_player_triggers[player]

    def __get_player_triggers_from_db(self, player: IPlayer) -> List[ITrigger]:
        factory = self.__get_factory(player)
        all_triggers: List[ITrigger] = list()
        for trigger_spec in self.__runtime.trigger_db.iter_trigger_specs(None):
            assert trigger_spec.zone is None, trigger_spec
            if player.is_local() and not trigger_spec.local_player:
                continue
            if player.is_remote() and not trigger_spec.remote_player:
                continue
            trigger = trigger_spec.to_trigger(factory.created)
            all_triggers.append(trigger)
        return all_triggers

    def __get_zone_triggers_from_db(self, player: IPlayer, zone_name: str, allow_ooz_triggers: bool) -> List[ITrigger]:
        factory = self.__get_factory(player)
        all_triggers: List[ITrigger] = list()
        for trigger_spec in self.__runtime.trigger_db.iter_trigger_specs(zone_name):
            assert trigger_spec.zone is not None, trigger_spec
            if not allow_ooz_triggers and not trigger_spec.allow_out_of_main_zone:
                continue
            if not TriggerUtil.compare_zones(zone_name, trigger_spec.zone, ignore_tier=not trigger_spec.zone_tier_specific):
                continue
            if player.is_local() and not trigger_spec.local_player:
                continue
            if player.is_remote() and not trigger_spec.remote_player:
                continue
            trigger = trigger_spec.to_trigger(factory.zone)
            all_triggers.append(trigger)
        return all_triggers

    def get_player_triggers(self, player: IPlayer) -> List[ITrigger]:
        factory_bundle = self.__get_factory(player)
        all_triggers: List[ITrigger] = list()
        # embedded triggers
        all_triggers.append(factory_bundle.control.trigger__player_died())
        all_triggers.append(factory_bundle.control.trigger__player_revived())
        all_triggers.append(factory_bundle.control.trigger__player_tell())
        all_triggers.append(factory_bundle.control.trigger__item_received())
        all_triggers.append(factory_bundle.control.trigger__item_found_in_inventory())
        all_triggers.append(factory_bundle.control.trigger__location())
        all_triggers.append(factory_bundle.control.trigger__autofollow_broken())
        all_triggers.append(factory_bundle.control.trigger__cannot_autofollow())
        all_triggers.append(factory_bundle.control.trigger__camping())
        all_triggers.append(factory_bundle.control.trigger__friend_logged())
        all_triggers.append(factory_bundle.control.trigger__colored_emotes())
        all_triggers.append(factory_bundle.combat.trigger__ability_reset())
        all_triggers.extend(factory_bundle.combat.triggers__balanced_synergy())
        if player.is_local():
            # group control triggers
            all_triggers.append(factory_bundle.control.local_trigger__player_found_in_zone())
            all_triggers.append(factory_bundle.control.local_trigger__player_found_in_group())
            all_triggers.append(factory_bundle.control.local_trigger__player_found_in_raid())
            all_triggers.append(factory_bundle.control.local_trigger__player_joined_group())
            all_triggers.append(factory_bundle.control.local_trigger__player_left_group())
            all_triggers.append(factory_bundle.control.local_trigger__group_disbanded())
            all_triggers.append(factory_bundle.control.local_trigger__player_linkdead())
            all_triggers.append(factory_bundle.control.local_trigger__local_player_changed_zone())
            all_triggers.append(factory_bundle.control.local_trigger__cannot_accept_quest())
            all_triggers.append(factory_bundle.control.local_trigger__points_at())
            # combat event triggers
            all_triggers.append(factory_bundle.combat.local_trigger__enemy_killed())
            all_triggers.append(factory_bundle.combat.local_trigger__bulwark_is_up())
            all_triggers.append(factory_bundle.combat.local_trigger__timer_traumatic_swipe())
            all_triggers.append(factory_bundle.combat.local_trigger__ascension_combo())
            all_triggers.extend(factory_bundle.combat.local_triggers__barrage())
            all_triggers.extend(factory_bundle.combat.local_triggers__heroic_opportunities())
            # request triggers
            all_triggers.append(factory_bundle.combat.local_trigger__request_set_target())
            all_triggers.append(factory_bundle.combat.local_trigger__request_cure_curse_target())
            all_triggers.append(factory_bundle.combat.local_trigger__request_cure_detrim_target())
            all_triggers.append(factory_bundle.combat.local_trigger__request_deathsave_target())
            all_triggers.append(factory_bundle.combat.local_trigger__request_stuns())
            all_triggers.append(factory_bundle.combat.local_trigger__request_interrupts())
            all_triggers.append(factory_bundle.combat.local_trigger__request_balanced_synergy())
            # util triggers
            all_triggers.append(factory_bundle.control.local_trigger__act_trigger_found())
        elif player.is_remote():
            all_triggers.append(factory_bundle.control.remote_trigger__remote_player_changed_zone())
            all_triggers.append(factory_bundle.control.remote_trigger__commission_offered())
        # triggers from JSON files
        player_triggers_from_db = self.__get_player_triggers_from_db(player)
        loaded_player_triggers = self.__get_player_trigger_list(player)
        loaded_player_triggers.clear()
        loaded_player_triggers.extend(player_triggers_from_db)
        all_triggers.extend(player_triggers_from_db)
        return all_triggers

    def reload_zone_triggers(self, player: IPlayer):
        if player.get_status() != PlayerStatus.Zoned:
            return
        main_zone = self.__runtime.playerstate.get_main_player_zone()
        if not is_unknown_zone(main_zone):
            is_main_zone = main_zone == player.get_zone()
            self.__change_to_zone(player, player.get_zone(), player.get_zone(), allow_ooz_triggers=is_main_zone, update_changed_triggers=False)

    def __update_triggers_to_db(self, triggers: List[ITrigger], zone_name: Optional[str]):
        for trigger in triggers:
            if trigger.is_test_event_updated():
                trigger_specs = TriggerSpec.from_trigger(trigger, zone_name)
                for trigger_spec in trigger_specs:
                    self.__runtime.trigger_db.store_trigger_spec(trigger_spec)

    def close(self):
        with self.__lock:
            zone_triggers = list()
            for triggers in self.__running_zone_triggers.values():
                zone_triggers.extend(triggers)
            self.__update_triggers_to_db(zone_triggers, zone_name=self.__running_zone_name)
            player_triggers = list()
            for triggers in self.__loaded_player_triggers.values():
                player_triggers.extend(triggers)
            self.__update_triggers_to_db(player_triggers, zone_name=None)
        super().close()

    def __change_to_zone(self, player: IPlayer, old_zone_name: Optional[str], new_zone_name: Optional[str],
                         allow_ooz_triggers: bool, update_changed_triggers=True):
        logger.info(f'__change_to_zone: {old_zone_name} -> {new_zone_name}')
        if not is_unknown_zone(new_zone_name):
            new_zone_triggers = self.__get_zone_triggers_from_db(player, new_zone_name, allow_ooz_triggers)
            if new_zone_triggers:
                self.__runtime.overlay.log_event(f'{len(new_zone_triggers)} triggers for {player} in {new_zone_name}', Severity.Normal)
        else:
            new_zone_triggers = []
        with self.__lock:
            old_zone_triggers = self.__get_zone_trigger_list(player)
            if update_changed_triggers and not is_unknown_zone(old_zone_name):
                self.__update_triggers_to_db(old_zone_triggers, zone_name=old_zone_name)
            self.__running_zone_triggers[player] = new_zone_triggers
        for trigger in old_zone_triggers:
            trigger.cancel_trigger()
        for trigger in new_zone_triggers:
            trigger.start_trigger()

    def __event_zone_changed(self, event: PlayerInfoEvents.PLAYER_ZONE_CHANGED):
        if event.player.is_local():
            # include offline players, because player from event may have just gone offline
            same_zone_players = self.__runtime.player_mgr.find_players(lambda p: p.get_zone() == event.player.get_zone())
            for player in same_zone_players:
                self.__change_to_zone(player, event.from_zone, event.to_zone, allow_ooz_triggers=True)
        else:
            # player status update arrives first, before zoning
            if event.player.get_status() == PlayerStatus.Zoned:
                self.__change_to_zone(event.player, event.from_zone, event.to_zone, allow_ooz_triggers=True)
            elif event.player.get_status() == PlayerStatus.Logged:
                self.__change_to_zone(event.player, event.from_zone, event.to_zone, allow_ooz_triggers=False)

    def is_current_zone_trigger(self, player: IPlayer, trigger: ITrigger):
        with self.__lock:
            return trigger in self.__get_zone_trigger_list(player)

    def get_current_zone_triggers(self, player: IPlayer) -> List[ITrigger]:
        with self.__lock:
            return list(self.__get_zone_trigger_list(player))

    def add_trigger_for_main_player(self, trigger_spec: TriggerSpec, save_in_db):
        logger.debug(f'add_main_player_trigger {trigger_spec.short_str()}')
        if save_in_db:
            self.__runtime.trigger_db.store_trigger_spec(trigger_spec)
        main_player = self.__runtime.playerstate.get_main_player()
        if main_player is None:
            logger.warn(f'failed to add trigger {trigger_spec.short_str()} because main player is None')
            return
        factory = self.__get_factory(main_player)
        trigger = trigger_spec.to_trigger(factory.created)
        if trigger_spec.zone == main_player.get_zone():
            # zone triggers are managed separately from player triggers #TODO manage all triggers in one place
            self.__get_zone_trigger_list(main_player).append(trigger)
            trigger.start_trigger()
        elif not trigger_spec.zone:
            # not a zone-specific trigger
            self.__runtime.client_ctrl_mgr.add_client_trigger(main_player, trigger)
        else:
            # missmatch between trigger zone and main player zone
            logger.warn(f'New trigger has zone but is same as main player zone: {trigger_spec} vs {main_player} in {main_player.get_zone()}')
