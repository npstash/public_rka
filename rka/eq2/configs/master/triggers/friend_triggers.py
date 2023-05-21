from typing import List

from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.ability.generated_abilities import WardenAbilities
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.triggers import ITrigger
from rka.eq2.master.triggers.trigger_actions import AbilityTimerTriggerAction
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory


class FriendTriggers(PlayerTriggerFactory):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        PlayerTriggerFactory.__init__(self, runtime, player)

    def triggers__standard_warden_tells(self) -> List[ITrigger]:
        runtime = self.get_runtime()
        all_triggers: List[ITrigger] = list()
        player_name = 'Warden'
        player = runtime.player_mgr.create_dummy_player(player_name)
        ability_factory = runtime.custom_ability_factory
        ## infuriating_thorns
        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell='Infuriating Thorns', to_local=True))
        census = WardenAbilities.infuriating_thorns.get_census_object_by_tier(player.get_level(GameClasses.Warden), AbilityTier.Master)
        ability = ability_factory.create_ability(WardenAbilities.infuriating_thorns, player, census)
        trigger.add_action(AbilityTimerTriggerAction(runtime, ability, expire=120.0))
        all_triggers.append(trigger)
        ## cyclone
        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell='Cyclone', to_local=True))
        census = WardenAbilities.cyclone.get_census_object_by_tier(player.get_level(GameClasses.Warden), AbilityTier.AA)
        ability = ability_factory.create_ability(WardenAbilities.cyclone, player, census)
        trigger.add_action(AbilityTimerTriggerAction(runtime, ability, expire=120.0))
        all_triggers.append(trigger)
        ## nature's renewal
        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell='Nature\'s Renewal', to_local=True))
        census = WardenAbilities.natures_renewal.get_census_object_by_tier(player.get_level(GameClasses.Warden), AbilityTier.Master)
        ability = ability_factory.create_ability(WardenAbilities.natures_renewal, player, census)
        trigger.add_action(AbilityTimerTriggerAction(runtime, ability, expire=120.0))
        all_triggers.append(trigger)
        ## tunare's watch
        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell='Tunare\'s Watch', to_local=True))
        census = WardenAbilities.tunares_watch.get_census_object_by_tier(player.get_level(GameClasses.Warden), AbilityTier.Master)
        ability = ability_factory.create_ability(WardenAbilities.tunares_watch, player, census)
        trigger.add_action(AbilityTimerTriggerAction(runtime, ability, expire=120.0))
        all_triggers.append(trigger)
        return all_triggers
