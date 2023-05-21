from __future__ import annotations

from typing import List

from rka.eq2.master import BuilderTools
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.ability.ability_builder import AbilityStore
from rka.eq2.master.game.ability.generated_abilities import LocalAbilities, RemoteAbilities, ItemsAbilities
from rka.eq2.master.game.effect.effects import GeneralEffects
from rka.eq2.master.game.gameclass import GameClasses, GameClass
from rka.eq2.master.game.interfaces import IPlayer, IAbility, IEffectBuilder


class PlayerClassBase:
    def __init__(self, class_level: int):
        assert class_level is not None
        self.class_level = class_level
        self.ability_stores: List[AbilityStore] = list()
        self.class_effects: List[IEffectBuilder] = list()
        self.abilities_defined = False
        self.effects_defined = False

    def add_subclass(self, game_subclass: GameClass):
        store = AbilityStore(game_subclass, self.class_level)
        self.ability_stores.append(store)
        return store

    def fill_missing_ability_tiers(self, tier: AbilityTier):
        for ability_store in self.ability_stores:
            ability_store.fill_missing_ability_tiers(tier)

    def build_class_abilities(self, player: IPlayer, builder_tools: BuilderTools) -> List[IAbility]:
        debug_msg = f'{player}, {self.__class__}'
        assert self.abilities_defined, debug_msg
        assert self.effects_defined, debug_msg
        registered_abilities = list()
        ability_factory = builder_tools.registered_ability_factory
        for ability_store in self.ability_stores:
            abilities = ability_store.build_stored_abilities(player=player, builder_tools=builder_tools, ability_factory=ability_factory)
            for ability in abilities:
                builder_tools.ability_reg.register_ability(ability)
            registered_abilities += abilities
        return registered_abilities

    def define_class_abilities(self, player: IPlayer):
        self._define_class_abilities(player)

    def _define_class_abilities(self, _player: IPlayer):
        self.abilities_defined = True

    def define_class_effects(self, player: IPlayer):
        self._define_class_effects(player)

    def _define_class_effects(self, _player: IPlayer):
        self.effects_defined = True

    def standard_action_bindings(self, player: IPlayer):
        raise ValueError()


class LocalClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.local = self.add_subclass(GameClasses.Local)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        # prepare - injector prefixes and postfixes per class
        self.local.builder(LocalAbilities.prepare).census_data(casting=0.0, reuse=0.0, recovery=0.0, duration=600.0)

    def _define_class_effects(self, player: IPlayer):
        super()._define_class_effects(player)
        self.class_effects.append(GeneralEffects.LOCAL_PLAYER_CASTING_DELAY())


class RemoteClass(PlayerClassBase):
    def __init__(self, class_level: int):
        PlayerClassBase.__init__(self, class_level)
        self.remote = self.add_subclass(GameClasses.Remote)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        inputs = player.get_inputs()
        # abilities built by default
        # /ics_combatautoface 0/1 - rotate camera view.
        # /ics_playercombatautoface 0/1 - rotate the avatar
        follow = self.remote.builder(RemoteAbilities.follow).census_data(casting=0.0, reuse=1.0, recovery=0.0)
        follow_cmd = 'combat_filter 1\nics_combatautoface 0\nics_playercombatautoface 0\nstand\nfollow {}'
        follow.non_census_injection_use_ability_on_target_builder_fn(lambda target: follow_cmd.format(target))
        follow.build()
        stop_follow = self.remote.builder(RemoteAbilities.stop_follow).census_data(casting=0.0, reuse=1.0, recovery=0.0)
        stop_follow_cmd = 'stopfollow\nics_combatautoface 0\nics_playercombatautoface 1'
        stop_follow.non_census_injection_use_ability_str(stop_follow_cmd)
        stop_follow.build()
        combat = self.remote.builder(RemoteAbilities.combat).census_data(casting=0.0, reuse=1.0, recovery=0.0)
        combat_cmd = 'pet attack\nmerc attack\nautoattack 1\nics_combatautoface 0\nics_playercombatautoface 1'
        combat.non_census_injection_use_ability_str(combat_cmd)
        combat.build()
        combat_autoface = self.remote.builder(RemoteAbilities.combat_autoface).census_data(casting=0.0, reuse=1.0, recovery=0.0)
        combat_autoface_cmd = 'pet attack\nmerc attack\nautoattack 1\nics_combatautoface 1\nics_playercombatautoface 1'
        combat_autoface.non_census_injection_use_ability_str(combat_autoface_cmd)
        combat_autoface.build()
        stop_combat = self.remote.builder(RemoteAbilities.stop_combat).census_data(casting=0.0, reuse=1.0, recovery=0.0)
        stop_combat_cmd = 'cl\npet backoff\nmerc backoff\nautoattack 0'
        stop_combat.non_census_injection_use_ability_str(stop_combat_cmd)
        stop_combat.cancel_spellcast()
        stop_combat.build()
        reset_zones = self.remote.builder(RemoteAbilities.reset_zones)
        reset_zones.census_data(casting=0.0, reuse=1.0, recovery=0.5)
        reset_zones.non_census_injection_use_ability_str('reset_all_zone_timers yes')
        reset_zones.command()
        reset_zones.build()
        self.remote.builder(RemoteAbilities.crouch).census_data(casting=0.0, reuse=0.0, recovery=0.0).action(inputs.keyboard.crouch).build()
        self.remote.builder(RemoteAbilities.jump).census_data(casting=0.0, reuse=0.0, recovery=0.0).action(inputs.keyboard.jump).build()
        self.remote.builder(RemoteAbilities.sprint).census_data(casting=0.0, reuse=5.0, recovery=0.5).build()
        self.remote.builder(RemoteAbilities.dps).census_data(casting=2.0, reuse=3.0, recovery=1.0, beneficial=False).build()
        self.remote.builder(RemoteAbilities.feign_death).census_data(casting=2.0, reuse=30 * 60.0, recovery=0.0).cancel_spellcast().build()

    def standard_action_bindings(self, player: IPlayer):
        inputs = player.get_inputs()
        ### hotbar 1
        self.remote.builder(RemoteAbilities.dps).action(inputs.hotbar1.hotkey1)
        ### hotbar 2
        self.remote.builder(RemoteAbilities.feign_death).action(inputs.hotbar2.hotkey11)
        self.remote.builder(RemoteAbilities.sprint).action(inputs.hotbar2.hotkey12)
        ### hotbar 4
        self.remote.builder(RemoteAbilities.combat).action(inputs.hotbar4.hotkey9)
        self.remote.builder(RemoteAbilities.stop_combat).action(inputs.hotbar4.hotkey10)
        self.remote.builder(RemoteAbilities.follow).action(inputs.hotbar4.hotkey11).target(GameClasses.Local)
        self.remote.builder(RemoteAbilities.stop_follow).action(inputs.hotbar4.hotkey12)


class ItemsClass(PlayerClassBase):
    def __init__(self):
        PlayerClassBase.__init__(self, 1)
        self.items = self.add_subclass(GameClasses.Items)

    def _define_class_abilities(self, player: IPlayer):
        super()._define_class_abilities(player)
        # \aITEM <use this number> <dont use this number> 0 0 0:[item name]\/a
        self.items.builder(ItemsAbilities.quelule_cocktail).item_id(684938096).census_data(casting=4.0, reuse=16.0 * 60.0, recovery=1.0, duration=10.0, beneficial=False)
        self.items.builder(ItemsAbilities.forgiveness_potion).item_id(2133278538).census_data(casting=1.0, reuse=5.0, recovery=1.0, duration=0.0)
        self.items.builder(ItemsAbilities.call_of_the_veteran).item_id(2549080242).census_data(casting=2.0, reuse=60 * 60.0, recovery=1.0, duration=0.0)
        self.items.builder(ItemsAbilities.critical_thinking).census_data(casting=0.75, reuse=4.0 * 60.0, recovery=1.0, duration=15.0)
        self.items.builder(ItemsAbilities.noxious_effusion).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-1043671356)
        self.items.builder(ItemsAbilities.poison_fingers).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(1715925784)
        self.items.builder(ItemsAbilities.divine_embrace).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-431763565)
        self.items.builder(ItemsAbilities.mindworms).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(2074843234)
        self.items.builder(ItemsAbilities.voidlink).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-1956483762)
        self.items.builder(ItemsAbilities.embrace_of_frost).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-1412342922)
        self.items.builder(ItemsAbilities.flames_of_yore).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-648136824)
        self.items.builder(ItemsAbilities.essence_of_smash).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-1766406031)
        self.items.builder(ItemsAbilities.prepaded_cutdown).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(1168858692)
        self.items.builder(ItemsAbilities.piercing_gaze).census_data(casting=4.0, reuse=1.0, recovery=1.0, duration=30 * 60.0).item_id(-387147097)
