from rka.components.ui.hotkeys import IHotkeyFilter
from rka.eq2.master import IRuntime
from rka.eq2.master.control import IHotkeySpec
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.ability import HOIcon
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.shared import ClientFlags


class CommonKeysTriggers:
    @staticmethod
    def move_all_or_selected(runtime: IRuntime, follow: bool):
        selection_id = runtime.overlay.get_selection_id()
        player = runtime.player_mgr.get_online_player_by_overlay_id(selection_id)
        main_player = runtime.playerstate.get_main_player()
        if not player or not main_player or player.is_local():
            if follow:
                runtime.automation.autopilot.all_players_follow_main_player()
            else:
                runtime.automation.autopilot.all_players_move_to_main_player()
        else:
            if follow:
                runtime.automation.autopilot.player_follow_player(player, main_player)
            else:
                runtime.automation.autopilot.player_move_to_player(player, main_player)

    @staticmethod
    def register_common_group_movement_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        request_ctrl = runtime.request_ctrl
        keyfilter.add_keys('consume alt f', lambda: request_ctrl.request_follow(player=None))
        keyfilter.add_keys('consume control f', lambda: request_ctrl.request_stop_follow(player=None))
        keyfilter.add_keys('consume shift f', lambda: request_ctrl.request_toggle_sprint(player=None))
        keyfilter.add_keys('consume alt control f', lambda: CommonKeysTriggers.move_all_or_selected(runtime, False))
        keyfilter.add_keys('consume alt control shift f', lambda: CommonKeysTriggers.move_all_or_selected(runtime, True))
        keyfilter.add_keys('consume alt b', lambda: request_ctrl.request_toggle_crouch(player=None))
        keyfilter.add_keys('consume alt space', lambda: request_ctrl.request_jump(player=None))

    @staticmethod
    def register_common_group_control_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        request_ctrl = runtime.request_ctrl
        # interaction with zone
        keyfilter.add_keys('consume alt o', lambda: request_ctrl.request_click_object_in_center(player=None))
        keyfilter.add_keys('consume alt p', lambda: request_ctrl.request_group_click_at_mouse_small())
        keyfilter.add_keys('consume control p', lambda: request_ctrl.request_group_click_at_mouse_large())
        # group management
        keyfilter.add_keys('consume control alt r', lambda: request_ctrl.request_group_reset_zones())
        keyfilter.add_keys('consume alt y', lambda: request_ctrl.request_accept_once(player=None))
        keyfilter.add_keys('consume shift y', lambda: request_ctrl.request_accept_continued(player=None))
        keyfilter.add_keys('consume control y', lambda: request_ctrl.request_accept_all(player=None))
        keyfilter.add_keys('consume alt i', lambda: request_ctrl.request_group_accept_invite())
        # permanent buffs
        keyfilter.add_keys('consume shift t', lambda: request_ctrl.request_group_permanent_buffs())
        keyfilter.add_keys('consume alt s', lambda: request_ctrl.request_group_summon_pets())

    @staticmethod
    def register_common_group_combat_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        request_ctrl = runtime.request_ctrl
        # combat control
        keyfilter.add_keys('consume alt d', lambda: request_ctrl.request_group_attack(autoface=True))
        keyfilter.add_keys('consume shift d', lambda: request_ctrl.request_group_verdicts())
        keyfilter.add_keys('consume control d', lambda: request_ctrl.request_group_stop_combat())
        keyfilter.add_keys('consume alt control d', lambda: request_ctrl.request_group_stop_all())
        # special abilities
        keyfilter.add_keys('consume alt control t', lambda: runtime.combatstate.clear_player_targets())
        keyfilter.add_keys('consume control t', lambda: request_ctrl.request_aggro_to(player=None))
        keyfilter.add_keys('consume alt h', lambda: request_ctrl.request_HO_advance([HOIcon.Hammer, HOIcon.Lightning, HOIcon.Dagger], max_hits=2))
        keyfilter.add_keys('consume control h', lambda: request_ctrl.request_HO_default_starter())
        # curing
        keyfilter.add_keys('consume z', lambda: request_ctrl.request_group_cure_now())
        keyfilter.add_keys('consume alt z', lambda: request_ctrl.request_cure_me())
        keyfilter.add_keys('consume shift z', lambda: request_ctrl.request_keep_curing_me())
        keyfilter.add_keys('consume control z', lambda: request_ctrl.request_cure_curse_me())
        keyfilter.add_keys('consume alt control z', lambda: request_ctrl.toggle_group_cures())
        # emergencies
        keyfilter.add_keys('consume alt g', lambda: request_ctrl.request_feign_death(player=None))
        keyfilter.add_keys('consume alt v', lambda: request_ctrl.request_group_emergency())
        keyfilter.add_keys('consume shift v', lambda: request_ctrl.request_group_hard_combat())
        keyfilter.add_keys('consume alt control v', lambda: request_ctrl.request_emergency_rez())
        # combos
        keyfilter.add_keys('consume rcontrol 1', lambda: request_ctrl.request_combo_implosion())
        keyfilter.add_keys('consume rcontrol 2', lambda: request_ctrl.request_combo_etherflash())
        keyfilter.add_keys('consume rcontrol 3', lambda: request_ctrl.request_combo_compounding_foce())
        keyfilter.add_keys('consume rcontrol 4', lambda: request_ctrl.request_combo_manaschism())
        keyfilter.add_keys('consume rcontrol 5', lambda: request_ctrl.request_combo_cascading())
        keyfilter.add_keys('consume rcontrol 6', lambda: request_ctrl.request_combo_levinbolt())
        keyfilter.add_keys('consume rcontrol 8', lambda: request_ctrl.request_combo_ethershadow())
        # frequent combat actions
        keyfilter.add_keys('consume 6', lambda: request_ctrl.request_group_dispel())
        keyfilter.add_keys('consume alt 4', lambda: request_ctrl.request_group_heal_now())
        keyfilter.add_keys('consume alt 7', lambda: request_ctrl.request_group_power_feed_now())
        keyfilter.add_keys('consume control 7', lambda: request_ctrl.request_power_drain_now())
        # infrequent combat actions
        keyfilter.add_keys('consume alt F1', lambda: request_ctrl.request_group_prepull_buffs())
        keyfilter.add_keys('consume alt F2', lambda: request_ctrl.request_group_stop_and_boss_combat())
        keyfilter.add_keys('consume alt F3', lambda: request_ctrl.request_group_ascension_nukes())
        keyfilter.add_keys('consume alt F4', lambda: request_ctrl.request_group_timelord())
        # special requests
        keyfilter.add_keys('consume alt F5', lambda: request_ctrl.request_powerpainforce_links('powerlink'))
        keyfilter.add_keys('consume alt F6', lambda: request_ctrl.request_powerpainforce_links('painlink'))
        keyfilter.add_keys('consume alt F7', lambda: request_ctrl.request_powerpainforce_links('forcelink'))

    @staticmethod
    def register_formation_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        # running a formation
        keyfilter.add_keys('consume control F1', lambda: runtime.automation.autopilot.apply_formation("1"))
        keyfilter.add_keys('consume control F2', lambda: runtime.automation.autopilot.apply_formation("2"))
        keyfilter.add_keys('consume control F3', lambda: runtime.automation.autopilot.apply_formation("3"))
        keyfilter.add_keys('consume control F4', lambda: runtime.automation.autopilot.apply_formation("4"))
        keyfilter.add_keys('consume control F5', lambda: runtime.automation.autopilot.apply_formation("5"))
        keyfilter.add_keys('consume control F6', lambda: runtime.automation.autopilot.apply_formation("6"))
        keyfilter.add_keys('consume control F7', lambda: runtime.automation.autopilot.apply_formation("7"))
        keyfilter.add_keys('consume control F8', lambda: runtime.automation.autopilot.apply_formation("8"))
        keyfilter.add_keys('consume control F9', lambda: runtime.automation.autopilot.apply_formation("9"))
        # storing a formation
        keyfilter.add_keys('consume alt control F1', lambda: runtime.automation.autopilot.store_formation("1"))
        keyfilter.add_keys('consume alt control F2', lambda: runtime.automation.autopilot.store_formation("2"))
        keyfilter.add_keys('consume alt control F3', lambda: runtime.automation.autopilot.store_formation("3"))
        keyfilter.add_keys('consume alt control F4', lambda: runtime.automation.autopilot.store_formation("4"))
        keyfilter.add_keys('consume alt control F5', lambda: runtime.automation.autopilot.store_formation("5"))
        keyfilter.add_keys('consume alt control F6', lambda: runtime.automation.autopilot.store_formation("6"))
        keyfilter.add_keys('consume alt control F7', lambda: runtime.automation.autopilot.store_formation("7"))
        keyfilter.add_keys('consume alt control F8', lambda: runtime.automation.autopilot.store_formation("8"))
        keyfilter.add_keys('consume alt control F9', lambda: runtime.automation.autopilot.store_formation("9"))

    @staticmethod
    def register_common_solo_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        # autocombat
        keyfilter.add_keys('consume F7', lambda: runtime.automation.autocombat.toggle_afk_autocombat())
        keyfilter.add_keys('consume F8', lambda: runtime.automation.autocombat.toggle_group_autocombat())
        keyfilter.add_keys('consume F9', lambda: runtime.automation.autocombat.toggle_defense_rotation())
        keyfilter.add_keys('consume F10', lambda: runtime.automation.autocombat.toggle_dps_rotation())

    @staticmethod
    def register_common_group_keys(runtime: IRuntime, keyfilter: IHotkeyFilter):
        CommonKeysTriggers.register_common_group_movement_keys(runtime, keyfilter)
        CommonKeysTriggers.register_common_group_control_keys(runtime, keyfilter)
        CommonKeysTriggers.register_common_group_combat_keys(runtime, keyfilter)
        CommonKeysTriggers.register_formation_keys(runtime, keyfilter)
        keyfilter.add_keys('2', lambda: runtime.request_ctrl.request_group_aoe_combat())
        keyfilter.add_keys('4', lambda: runtime.request_ctrl.request_group_boss_combat())


class DefaultMainPlayerHotkeySpec(IHotkeySpec):
    def __init__(self, player: IPlayer):
        self.__player = player
        self.__forwarder = KeyRepeaterSpec(player)

    def get_spec_count(self) -> int:
        return 4

    def register_keys(self, runtime: IRuntime, spec_id: int, keyfilter: IHotkeyFilter) -> str:
        runtime.request_ctrl.change_primary_player(self.__player)
        if spec_id == 0:
            CommonKeysTriggers.register_common_solo_keys(runtime, keyfilter)
            CommonKeysTriggers.register_common_group_keys(runtime, keyfilter)
            keyfilter.add_keys(['1', 'divide'], lambda: runtime.request_ctrl.request_group_normal_combat())
            return 'Group'
        elif spec_id == 1:
            CommonKeysTriggers.register_common_solo_keys(runtime, keyfilter)
            keyfilter.add_keys(['1', 'divide'], lambda: runtime.request_ctrl.request_solo_normal_combat())
            return 'Solo'
        elif spec_id == 2:
            CommonKeysTriggers.register_common_solo_keys(runtime, keyfilter)
            CommonKeysTriggers.register_common_group_keys(runtime, keyfilter)
            keyfilter.add_keys(['1', 'divide'], runtime.request_ctrl.request_group_spam_dps)
            return 'DPS Spam'
        elif spec_id == 3:
            return self.__forwarder.register_keys(runtime, 0, keyfilter)
        assert False


class KeyRepeaterSpec(IHotkeySpec):
    def __init__(self, player: IPlayer):
        self.__player = player

    def keypress_relay(self, runtime: IRuntime, key: str):
        # TODO this doesnt work when another key is pressed before previous one is released
        action = action_factory.new_action().key(key=key)
        player_id = runtime.overlay.get_selection_id()
        player = runtime.player_mgr.get_online_player_by_overlay_id(player_id)
        if not player:
            return
        if player == self.__player:
            players = runtime.player_mgr.get_players(and_flags=ClientFlags.Remote, min_status=PlayerStatus.Zoned)
        else:
            players = [player]
        for player in players:
            action.post_async(player.get_client_id())

    def get_spec_count(self) -> int:
        return 1

    def register_keys(self, runtime: IRuntime, spec_id: int, keyfilter: IHotkeyFilter) -> str:
        runtime.request_ctrl.change_primary_player(self.__player)
        CommonKeysTriggers.register_common_group_keys(runtime, keyfilter)
        keyfilter.add_keys(['1', 'divide'], lambda: runtime.request_ctrl.request_group_normal_combat())
        keyfilter.add_keys(['down w', 'down s', 'down a', 'down d', 'down q', 'down e', 'down space'], lambda k, s: self.keypress_relay(runtime, k))
        keyfilter.add_keys(['up w', 'up s', 'up a', 'up d', 'up q', 'up e', 'up space'], lambda k, s: self.keypress_relay(runtime, k))
        return 'Forward movement keys'
