from typing import Optional, Dict

import regex as re

from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.game.ability.generated_abilities import ConjurorAbilities
from rka.eq2.master.game.automation import IChatCommand, ChatMessage
from rka.eq2.master.game.automation import logger
from rka.eq2.master.game.automation.chatterbot import SillyChat
from rka.eq2.master.game.gameclass import GameClasses
from rka.eq2.master.game.scripting.framework import PlayerScriptingFramework
from rka.eq2.master.game.scripting.scripts.combat_monitoring_scripts import MeasureAbilityDps, PeriodicAnnouncement
from rka.eq2.parsing.parsing_util import ANY_COMBATANT_G


class ChatterCommands:
    def __init__(self):
        self.authorize_commands = {
            r'it\'?s me,? ?(your )?master': CCAuthorized(),
        }

        self.remote_player_commands = {
            '(list )?commands': CCListCommands(self),
            'invite( (me|.+))?': CCInvite(),
            '(call|cot|summon) me': CCSummonMe(),
            'follow( (me|.+))?': CCFollow(),
            'keep follow(ing)?( (me|.+))?': CCKeepFollowing(),
            'target( (me|.+))?': CCTarget(),
            'stop( |_)?follow(ing)?': CCStopFollow(),
            'accept': CCAccept(),
            'leave( |_)?group': CCLeaveGroup(),
            '(slash( |_)?)?command': CCSlashCommand(),
            'reset zones': CCResetZones(),
            'click middle': CCClickMiddle(),
            '.*': CCChatter(),
        }

        self.local_player_commands = {
            'help measure': CCHelpMeasureDPS(),
            'measure': CCMeasureDPS(),
        }

    @staticmethod
    def interpret_command(runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage, command_dict: Dict[str, IChatCommand]) -> bool:
        for cmd_pattern, cmd_handler in command_dict.items():
            if re.match(cmd_pattern, message.tell):
                if cmd_handler.run_command(runtime, psf, message):
                    return True
        return False


class CCHelpMeasureDPS(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        responses = [
            CCMeasureDPS.measure_pattern,
            CCMeasureDPS.target_pattern,
            CCMeasureDPS.min_damage_pattern,
            CCMeasureDPS.max_ranks_pattern,
            CCMeasureDPS.frequency_pattern,
            'measure incoming dps on training dummy; to group min 10b max 2 ranks every 2s'
        ]
        for response in responses:
            runtime.overlay.log_event(response, Severity.High)
            print(response)
        return True


class CCMeasureDPS(IChatCommand):
    measure_pattern = fr'measure (outgoing|incoming|ability) dps(?: (?:to|on|by|from|with|of))? ({ANY_COMBATANT_G});?'
    target_pattern = r' to (raid|group|say|overlay|tell(?: to)? (\w+))'
    min_damage_pattern = r' min ([\d,]+)(k|m|b|t)?'
    max_ranks_pattern = r' max (\d+) ranks'
    frequency_pattern = r' every (\d+)(?: ?sec|s)?'

    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        # full RE: https://regex101.com/r/GkwmrL/1
        # example: measure outgoing dps of Playername to group every 3s min 200k
        remaining_tell = message.tell
        match = re.match(CCMeasureDPS.measure_pattern, remaining_tell)
        if not match:
            return False
        measure_type = match.group(1)
        measure_target = match.group(2)
        if measure_type == 'incoming':
            attacker_name = None
            target_name = measure_target
            ability_name = None
        elif measure_type == 'ability':
            attacker_name = None
            target_name = None
            ability_name = measure_target.lower()
        elif measure_type == 'outgoing':
            attacker_name = measure_target
            target_name = None
            ability_name = None
        else:
            logger.error(f'pattern error {measure_type} vs {message.tell}')
            return False
        measure_destination = PeriodicAnnouncement.DESTINATION_OVERLAY
        repeat_rate = 4.0
        period = 3.0
        min_damage = 0
        max_ranks = 5
        while True:
            remaining_tell = remaining_tell[len(match.group(0)):]
            if not remaining_tell:
                break
            match = re.match(CCMeasureDPS.target_pattern, remaining_tell)
            if match:
                destination_name = match.group(1)
                if destination_name.startswith('raid'):
                    measure_destination = PeriodicAnnouncement.DESTINATION_RAID
                elif destination_name.startswith('group'):
                    measure_destination = PeriodicAnnouncement.DESTINATION_GROUP
                elif destination_name.startswith('say'):
                    measure_destination = PeriodicAnnouncement.DESTINATION_SAY
                elif destination_name.startswith('overlay'):
                    measure_destination = PeriodicAnnouncement.DESTINATION_OVERLAY
                elif destination_name.startswith('tell'):
                    measure_destination = PeriodicAnnouncement.DESTINATION_TELL + match.group(2)
                continue
            match = re.match(CCMeasureDPS.frequency_pattern, remaining_tell)
            if match:
                repeat_rate = int(match.group(1))
                period = max(3.0, repeat_rate / 2)
                continue
            match = re.match(CCMeasureDPS.min_damage_pattern, remaining_tell)
            if match:
                min_damage = int(match.group(1).replace(',', ''))
                postfix = match.group(2)
                if postfix:
                    min_damage *= {'k': 10 ** 3, 'm': 10 ** 6, 'b': 10 ** 9, 't': 10 ** 12, 'z': 10 ** 15}[postfix]
                continue
            match = re.match(CCMeasureDPS.max_ranks_pattern, remaining_tell)
            if match:
                max_ranks = int(match.group(1))
                continue
            runtime.overlay.log_event(f'Unrecognized measure option {remaining_tell}', Severity.High)
            break
        runtime.overlay.log_event(f'Measure {measure_type} DPS of {measure_target}', Severity.Normal)
        runtime.overlay.log_event(f'to {measure_destination} every {repeat_rate} sec', Severity.Normal)
        runtime.overlay.log_event(f'min hit {min_damage}, max ranks {max_ranks}', Severity.Normal)
        script = MeasureAbilityDps(attacker_name, target_name, ability_name, max_ranks, period, min_damage, repeat_rate, measure_destination)
        runtime.request_ctrl.processor.run_auto(script)
        return True


class CCFollow(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        follow_match = re.match('follow(?: (.*))?', message.tell)
        if not follow_match:
            return False
        person_to_follow = follow_match.group(1)
        if not person_to_follow or person_to_follow.lower() == 'me':
            person_to_follow = message.from_player_name
        psf.follow(person_to_follow)
        return True


class CCKeepFollowing(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        follow_match = re.match('keep follow(?:ing)?(?: (.*))?', message.tell)
        if not follow_match:
            return False
        person_to_follow = follow_match.group(1)
        # if no target - recover default follow
        if not person_to_follow:
            runtime.playerstate.set_follow_target(psf.get_player(), None)
            psf.follow(message.from_player_name)
            return
        if person_to_follow.lower() == 'me':
            person_to_follow = message.from_player_name
        runtime.playerstate.set_follow_target(psf.get_player(), person_to_follow)
        psf.follow(person_to_follow)
        return True


class CCTarget(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        target_match = re.match('target(?: (.*))?', message.tell)
        if not target_match:
            return False
        target_name = target_match.group(1)
        if not target_name:
            runtime.combatstate.set_default_target(psf.get_player(), None)
            return True
        if target_name.lower() == 'me':
            target_name = message.from_player_name
        runtime.combatstate.set_default_target(psf.get_player(), target_name)
        return True


class CCStopFollow(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        psf.stop_follow()
        return True


class CCAccept(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        psf.try_click_accepts()
        return True


class CCSlashCommand(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        pattern = 'command '
        start_from = message.tell.find(pattern)
        if start_from == -1:
            return False
        start_from += len(pattern)
        command = message.tell[start_from:].strip()
        logger.info(f'Custom command to {message.to_player}: {command}')
        psf.command_async(command)
        return True


class CCInvite(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        invite_match = re.match('invite(?: (.*))?', message.tell)
        if not invite_match:
            return False
        person_to_invite = invite_match.group(1)
        if not person_to_invite or person_to_invite.lower() == 'me':
            person_to_invite = message.from_player_name
        psf.invite_to_group(person_to_invite)
        return True


class CCLeaveGroup(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage) -> bool:
        psf.leave_group()
        return True


class CCSummonMe(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        if message.to_player.is_class(GameClasses.Conjuror):
            if psf.cast_ability_async(ConjurorAbilities.call_of_the_hero, target=message.from_player_name):
                psf.send_tell(message.from_player_name, 'You\'re my hero!')
                return True
            else:
                psf.send_tell(message.from_player_name, 'not now')
        return False


class CCAuthorized(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        psf.send_tell(message.from_player_name, 'ok =)')
        return True


class CCListCommands(IChatCommand):
    def __init__(self, all_chatter_commands: ChatterCommands):
        self.all_chatter_commands = all_chatter_commands

    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        psf.send_tell(message.from_player_name, '; '.join(self.all_chatter_commands.remote_player_commands.keys()))
        return True


class CCResetZones(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        psf.reset_zones()
        return True


class CCClickMiddle(IChatCommand):
    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        psf.click_screen_middle()
        return True


class CCChatter(IChatCommand):
    def __init__(self):
        self.__chatterbot: Optional[SillyChat] = None

    def run_command(self, runtime: IRuntime, psf: PlayerScriptingFramework, message: ChatMessage):
        if not self.__chatterbot:
            self.__chatterbot = SillyChat(runtime)
        response = self.__chatterbot.get_response(message)
        if not response:
            return False
        psf.send_tell(message.from_player_name, response)
        return True
