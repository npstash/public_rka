import time
from typing import Optional, List

import regex as re

from rka.components.events.event_system import EventSystem
from rka.components.ui.overlay import Severity
from rka.eq2.configs.shared.game_constants import CURRENT_MAX_LEVEL
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability import AbilityTier
from rka.eq2.master.game.ability.generated_abilities import ThugAbilities
from rka.eq2.master.game.effect.effects import ThugEffects
from rka.eq2.master.game.events.chat import ChatEvents
from rka.eq2.master.game.events.combat import CombatEvents
from rka.eq2.master.game.events.combat_parser import CombatParserEvents
from rka.eq2.master.game.events.requesting import RequestEvents
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import TellType
from rka.eq2.master.parsing import CombatantType
from rka.eq2.master.triggers import logger, ITrigger
from rka.eq2.master.triggers.trigger_actions import TimerTriggerAction, FormattedLogTriggerAction
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.master.triggers.trigger_util import TriggerUtil
from rka.eq2.parsing.parsing_util import ANY_PLAYER_G, ANY_PLAYER_L, ANY_COMBATANT_L, ANY_COMBATANTS, ANY_PET_L, ANY_PLAYER_INCL_YOU_G, ANY_PLAYERS_INCL_YOUR
from rka.eq2.shared.client_events import ClientEvents
from rka.eq2.shared.flags import MutableFlags


class CombatTriggers(PlayerTriggerFactory):
    def __init__(self, runtime: IRuntime, player: IPlayer):
        PlayerTriggerFactory.__init__(self, runtime, player)

    def local_trigger__enemy_killed(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            killer_name = match.group(1)
            killer_is_you = TriggerUtil.is_you(killer_name)
            if killer_is_you:
                killer_name = self.get_player().get_player_name()
            enemy_name = match.group(2)
            enemy_is_you = TriggerUtil.is_you(enemy_name)
            if enemy_is_you:
                enemy_name = self.get_player().get_player_name()
            logger.info(f'{enemy_name} killed by {killer_name}')
            killed_player = self.get_runtime().player_mgr.get_player_by_name(enemy_name)
            if not killed_player:
                event = CombatEvents.ENEMY_KILL(killer_name=killer_name, enemy_name=enemy_name, killer_you=killer_is_you)
                EventSystem.get_main_bus().call(event)

        trigger = self.new_trigger()
        trigger.add_parser_events(rf'({ANY_COMBATANT_L}) (?:has|have) killed (.*)\.')
        trigger.add_parser_events(rf'({ANY_COMBATANTS}) {ANY_PET_L} (?:has|have) killed (.*)\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__bulwark_is_up(self) -> ITrigger:
        def action(event: ClientEvents.PARSER_MATCH):
            player_name = event.match().group(1)
            logger.info(f'Bulwark confirmed from: {player_name}')
            EventSystem.get_main_bus().call(CombatEvents.BULWARK_APPLIED(applied_by=player_name, timestamp=event.timestamp))

        trigger = self.new_trigger()
        trigger.add_parser_events(rf'({ANY_PLAYER_L}) applies a bulwark to the group\.')
        trigger.add_action(action)
        return trigger

    def local_trigger__request_set_target(self) -> ITrigger:
        def action(event: ChatEvents.PLAYER_TELL):
            match = re.match('Let\'s kill (.*)', event.tell)
            if not match:
                return
            target_name = match.group(1)
            if target_name == '<no target>':
                target_name = None
            player_selector = self.get_runtime().playerselectors.zoned_remote_by_selection_or_all()
            self.get_runtime().combatstate.set_players_target(players=player_selector.resolve_players(), target_name=target_name)

        trigger = self.new_trigger()
        subs_event = ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(), to_local=True)
        trigger.add_bus_event(subs_event, filter_cb=lambda e: e.tell.startswith('Let\'s kill '))
        trigger.add_action(action)
        return trigger

    def local_trigger__request_balanced_synergy(self) -> ITrigger:
        compiled_re = re.compile(r'[SPMF]?([Bb]alanced|[Ss]ynergy).*')

        def action(event: ChatEvents.PLAYER_TELL):
            if not compiled_re.match(event.tell):
                return
            player_name = event.from_player_name
            logger.info(f'{player_name} requested SYNERGY')
            player = self.get_runtime().player_mgr.get_player_by_name(player_name)
            local_player_request = True if player and player.is_local() else False
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_BALANCED_SYNERGY(player_name=player_name, local_player_request=local_player_request))

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(tell_type=TellType.group, to_local=True))
        trigger.add_action(action)
        return trigger

    def triggers__balanced_synergy(self) -> List[ITrigger]:
        def synergy_status_action(event: ClientEvents.PARSER_MATCH):
            caster_name = TriggerUtil.strip_s(event.match().group(1))
            if TriggerUtil.is_you(caster_name):
                caster_name = self.get_runtime().player_mgr.get_player_by_client_id(event.client_id).get_player_name()
                my_player = True
            else:
                my_player = True if self.get_runtime().player_mgr.get_player_by_name(caster_name) else False
            if 'synergizes' in event.matched_text:
                EventSystem.get_main_bus().call(CombatEvents.PLAYER_SYNERGIZED(caster_name=caster_name, my_player=my_player, reported_by_player=self.get_player()))
            else:
                EventSystem.get_main_bus().call(CombatEvents.PLAYER_SYNERGY_FADES(caster_name=caster_name, my_player=my_player, reported_by_player=self.get_player()))

        def synergy_completed(_event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.GROUP_SYNERGY_COMPLETED(reported_by_player=self.get_player()))

        trigger_1 = self.new_trigger()
        trigger_1.add_parser_events(fr'({ANY_PLAYER_INCL_YOU_G}) synergizes with the group\.$')
        trigger_1.add_parser_events(fr'({ANY_PLAYERS_INCL_YOUR}) synergy fades\.$')
        trigger_1.add_action(synergy_status_action)

        trigger_2 = self.new_trigger()
        trigger_2.add_parser_events(TriggerUtil.regex_for_color_emote(r'You feel a synergy with your group\.'))
        trigger_2.add_action(synergy_completed)
        return [trigger_1, trigger_2]

    def trigger__ability_reset(self) -> ITrigger:
        def action(_event: ClientEvents.PARSER_MATCH):
            self.get_player().aspects.last_readyup_time = time.time()
            if MutableFlags.ENABLE_RESET_EVENTS:
                EventSystem.get_main_bus().call(CombatEvents.READYUP(player=self.get_player()))

        trigger = self.new_trigger()
        trigger.add_parser_events(r'Readied Up!')
        trigger.add_action(action)
        return trigger

    def local_trigger__request_cure_curse_target(self) -> ITrigger:
        say_re = re.compile(rf'({ANY_PLAYER_G}) run before bus, get tired')

        def action(event: ChatEvents.PLAYER_TELL):
            target_name = say_re.match(event.tell).group(1)
            self.get_runtime().overlay.log_event(f'Cure curse {target_name}', Severity.Normal)
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_CURE_CURSE(target_name=target_name))

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(), tell_type=TellType.say, to_local=True),
                              filter_cb=lambda event: say_re.match(event.tell) is not None)
        trigger.add_action(action)
        return trigger

    def local_trigger__request_cure_detrim_target(self) -> ITrigger:
        say_re = re.compile(rf'({ANY_PLAYER_G}) run behind bus, get exhausted')

        def action(event: ChatEvents.PLAYER_TELL):
            target_name = say_re.match(event.tell).group(1)
            self.get_runtime().overlay.log_event(f'Cure detrim {target_name}', Severity.Normal)
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_CURE(target_name=target_name))
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_INTERCEPT(target_name=target_name))

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(), tell_type=TellType.say, to_local=True),
                              filter_cb=lambda event: say_re.match(event.tell) is not None)
        trigger.add_action(action)
        return trigger

    def local_trigger__request_deathsave_target(self) -> ITrigger:
        say_re_1 = re.compile(rf'({ANY_PLAYER_G}) piss in wind, wind piss back')
        say_re_2 = re.compile(rf'({ANY_PLAYER_G}) leap off cliff, jump to conclusion')

        def action(event: ChatEvents.PLAYER_TELL):
            match = say_re_1.match(event.tell)
            if not match:
                match = say_re_2.match(event.tell)
            target_name = match.group(1)
            self.get_runtime().overlay.log_event(f'Deatsave {target_name}', Severity.Normal)
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_DEATHSAVE(target_name=target_name))

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(), tell_type=TellType.say, to_local=True),
                              filter_cb=lambda event: say_re_1.match(event.tell) or say_re_2.match(event.tell))
        trigger.add_action(action)
        return trigger

    def local_trigger__request_interrupts(self) -> ITrigger:
        def action(_event: ChatEvents.PLAYER_TELL):
            self.get_runtime().overlay.log_event(f'Request Interrupt', Severity.Normal)
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_INTERRUPT())

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(),
                                                     tell_type=TellType.say, tell='Look! Your fly is open!', to_local=True))
        trigger.add_action(action)
        return trigger

    def local_trigger__request_stuns(self) -> ITrigger:
        def action(_event: ChatEvents.PLAYER_TELL):
            self.get_runtime().overlay.log_event(f'Request Stun', Severity.Normal)
            EventSystem.get_main_bus().call(RequestEvents.REQUEST_STUN())

        trigger = self.new_trigger()
        trigger.add_bus_event(ChatEvents.PLAYER_TELL(from_player_name=self.get_player().get_player_name(),
                                                     tell_type=TellType.say, tell='Look! It\'s an ass behind you!', to_local=True))
        trigger.add_action(action)
        return trigger

    def local_trigger__ascension_combo(self) -> ITrigger:
        return self.log_trigger(r'Your (.+) surges with power', 'COMBO', Severity.Low)

    def local_trigger__timer_traumatic_swipe(self) -> ITrigger:
        runtime = self.get_runtime()

        def action(event: CombatParserEvents.COMBAT_HIT):
            player = runtime.player_mgr.create_dummy_player(event.attacker_name)
            ability_factory = runtime.custom_ability_factory
            census_consts = ThugAbilities.traumatic_swipe.get_census_object_by_tier(CURRENT_MAX_LEVEL, AbilityTier.AA)
            ability = ability_factory.create_ability(ThugAbilities.traumatic_swipe, player, census_consts)
            ability.set_target(event.target_name)
            ability.set_effect_builder(ThugEffects.TRAUMATIC_SWIPE())
            ability.confirm_casting_completed(cancel_action=False, when=event.timestamp)

        trigger = self.new_trigger()
        subsc_event = CombatParserEvents.COMBAT_HIT(ability_name=ThugAbilities.traumatic_swipe.get_canonical_name(), target_type=CombatantType.NPC, is_multi=False)
        trigger.add_bus_event(subsc_event)
        trigger.add_action(action)
        trigger.add_action(TimerTriggerAction(runtime, name='Swipe {$target_name}', severity=Severity.Low, duration=30.0))
        trigger.add_action(FormattedLogTriggerAction(runtime, '{$attacker_name} SWIPED {$target_name}', Severity.Normal))
        return trigger

    def local_triggers__barrage(self) -> List[ITrigger]:
        runtime = self.get_runtime()
        player_name = self.get_player().get_player_name()
        color_named_g1 = TriggerUtil.regex_for_any_named_color_g1()
        npc_named_g1 = TriggerUtil.regex_for_any_named_anpc_g1()

        def is_your_group(target_name: Optional[str] = None) -> bool:
            return not target_name or target_name.lower() == player_name.lower() or runtime.zonestate.is_player_in_main_group(target_name)

        def readied(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = match.group(1)
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_READIED(caster_name=caster_name))

        def prepared(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = match.group(1)
            target_name = match.group(2) if len(match.groups()) > 1 else None
            your_group = is_your_group(target_name)
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_PREPARED(caster_name=caster_name, target_name=target_name, your_group=your_group))

        def prepared_your_group(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = TriggerUtil.strip_s(match.group(1))
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_PREPARED(caster_name=caster_name, target_name=player_name, your_group=True))

        def prepared_other_group(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = match.group(1)
            target_name = TriggerUtil.strip_s(match.group(2))
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_PREPARED(caster_name=caster_name, target_name=target_name, your_group=False))

        def cancelled(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = match.group(1)
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_CANCELLED(caster_name=caster_name))

        def released(event: ClientEvents.PARSER_MATCH):
            match = event.match()
            caster_name = match.group(1)
            target_name = match.group(2) if len(match.groups()) > 1 else None
            EventSystem.get_main_bus().call(CombatEvents.BARRAGE_RELEASED(caster_name=caster_name, target_name=target_name))

        trigger_cancel = self.new_trigger()
        trigger_cancel.add_parser_events(f'{color_named_g1} cancels the barrage')
        trigger_cancel.add_action(cancelled)

        trigger_ready = self.new_trigger()
        trigger_ready.add_parser_events(f'{color_named_g1} readies a barrage')
        trigger_ready.add_action(readied)

        trigger_prepare = self.new_trigger()
        trigger_prepare.add_parser_events(f'{color_named_g1} prepares to unleash a barrage of attacks(?: toward ({ANY_PLAYER_INCL_YOU_G}))?')
        trigger_prepare.add_parser_events(f'{npc_named_g1} surges and strikes the target')
        trigger_prepare.add_parser_events(f'{color_named_g1} prepares to strike with')
        trigger_prepare.add_action(prepared)

        trigger_prepare_your_group = self.new_trigger()
        trigger_prepare_your_group.add_parser_events(
            rf'{color_named_g1} prepares to unleash a mighty \w+ in ({ANY_PLAYERS_INCL_YOUR}) group\'s direction! You may want to protect them somehow')
        trigger_prepare_your_group.add_action(prepared_your_group)

        trigger_prepare_other_group = self.new_trigger()
        trigger_prepare_other_group.add_parser_events(
            rf'{color_named_g1} prepares to unleash a mighty \w+ in ({ANY_PLAYERS_INCL_YOUR}) group\'s direction! They will need to protect them somehow')
        trigger_prepare_other_group.add_action(prepared_other_group)

        trigger_release = self.new_trigger()
        trigger_release.add_parser_events(f'{color_named_g1} releases a barrage of attacks(?: at ({ANY_PLAYER_INCL_YOU_G}))?')
        trigger_release.add_action(released)

        return [trigger_cancel, trigger_ready, trigger_prepare, trigger_prepare_your_group, trigger_prepare_other_group, trigger_release]

    def local_triggers__heroic_opportunities(self) -> List[ITrigger]:

        def chain_started(event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.HO_CHAIN_STARTED(caster_name=event.match().group(1)))

        def chain_broken(event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.HO_CHAIN_BROKEN(caster_name=event.match().group(1)))

        def triggered(event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.HO_TRIGGERED(caster_name=event.match().group(1), ho_name=event.match().group(2)))

        def advanced(event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.HO_ADVANCED(caster_name=event.match().group(1), ho_name=event.match().group(2)))

        def completed(event: ClientEvents.PARSER_MATCH):
            EventSystem.get_main_bus().call(CombatEvents.HO_COMPLETED(caster_name=event.match().group(1), ho_name=event.match().group(2)))

        trigger_HO_chain = self.new_trigger()
        trigger_HO_chain.add_parser_events(f'({ANY_PLAYER_INCL_YOU_G}) triggers? a starter chain')
        trigger_HO_chain.add_action(chain_started)

        break_HO_chain = self.new_trigger()
        break_HO_chain.add_parser_events(f'({ANY_PLAYER_INCL_YOU_G}) broke the starter chain')
        break_HO_chain.add_action(chain_broken)

        trigger_HO_trigger = self.new_trigger()
        trigger_HO_trigger.add_parser_events(f'({ANY_PLAYER_INCL_YOU_G}) trigger(?:s|ed) ([A-Z].+)\\.$')
        trigger_HO_trigger.add_action(triggered)

        trigger_HO_advance = self.new_trigger()
        trigger_HO_advance.add_parser_events(f'({ANY_PLAYER_INCL_YOU_G}) advances? ([A-Z].+)\\.$')
        trigger_HO_advance.add_action(advanced)

        trigger_HO_complete = self.new_trigger()
        trigger_HO_complete.add_parser_events(f'({ANY_PLAYER_INCL_YOU_G}) completes? ([A-Z].+)\\.$')
        trigger_HO_complete.add_action(completed)

        return [trigger_HO_chain, break_HO_chain, trigger_HO_trigger, trigger_HO_advance, trigger_HO_complete]
