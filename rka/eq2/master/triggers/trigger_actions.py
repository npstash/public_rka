import time
import traceback
from typing import List, Optional, Match, Generator, Tuple

import regex as re

from rka.components.events import Event
from rka.components.ui.overlay import Severity, OvTimerStage, OvWarning
from rka.eq2.master import IRuntime
from rka.eq2.master.game.effect import EffectType
from rka.eq2.master.game.interfaces import IAbility, IPlayer, EffectTarget
from rka.eq2.master.triggers import ITriggerAction, logger
from rka.eq2.shared.client_event import ClientEvent
from rka.eq2.shared.client_events import ClientEvents


def quote_param(quote: bool, param_str_val: str) -> str:
    if quote:
        if len(param_str_val) >= 2:
            if (param_str_val[0] == '"' and param_str_val[-1] == '"') or param_str_val[0] == '\'' and param_str_val[-1] == '\'':
                param_str_val = param_str_val[1:-1]
        param_str_val = param_str_val.replace('"', r'\"')
        return f'"{param_str_val}"'
    return param_str_val


__rgx_find_common_vars = re.compile(r'{\$\$(\w+)}')


def replace_common_vars(player: IPlayer, text: str, quote: bool) -> str:
    result = text
    for match_param_var in re.finditer(__rgx_find_common_vars, text):
        if not match_param_var.lastindex:
            continue
        param_name = match_param_var.group(1)
        param_str_val = ''
        if player and param_name == 'player':
            param_str_val = player.get_player_name()
        param_str_val = quote_param(quote, param_str_val)
        result = result.replace(match_param_var.group(), param_str_val)
    return result


__rgx_find_match_group = re.compile(r'{\$(\d+)}')


def replace_match_groups(text: str, match: Match, quote: bool) -> str:
    result = text
    for match_param_gid in re.finditer(__rgx_find_match_group, text):
        if not match_param_gid.lastindex:
            continue
        param_gid = int(match_param_gid.group(1))
        param_str_val = match.group(param_gid)
        param_str_val = param_str_val if param_str_val is not None else ''
        param_str_val = quote_param(quote, param_str_val)
        result = result.replace(match_param_gid.group(), param_str_val)
    return result


__rgx_find_event_params = re.compile(r'{\$([\w.]+)}')


def replace_event_params(text: str, event: Event, quote: bool) -> str:
    result = text
    for match_param_var in re.finditer(__rgx_find_event_params, text):
        if not match_param_var.lastindex:
            continue
        variable_path_split = match_param_var.group(1).split('.')
        if not variable_path_split:
            continue
        current_segment_object = event
        for path_segment in variable_path_split:
            try:
                current_segment_object = current_segment_object.__getattribute__(path_segment)
            except AttributeError as e:
                logger.error(f'replace_event_params: {e}')
                logger.error(f'text: {text}. event: {event}. var: {match_param_var}. segments: {variable_path_split}. attribute {path_segment}')
                continue
        param_str_val = str(current_segment_object) if current_segment_object is not None else ''
        param_str_val = quote_param(quote, param_str_val)
        result = result.replace(match_param_var.group(), param_str_val)
    return result


def replace_variables(player: IPlayer, text: str, event: Optional[Event], quote: bool) -> str:
    text = replace_common_vars(player, text, quote)
    if isinstance(event, ClientEvents.PARSER_MATCH):
        return replace_match_groups(text, event.match(), quote)
    elif event:
        return replace_event_params(text, event, quote)
    return text


class BaseTriggerAction(ITriggerAction):
    def __init__(self, runtime: IRuntime):
        ITriggerAction.__init__(self, runtime)

    def _get_event_player(self, event: Event) -> IPlayer:
        if isinstance(event, ClientEvent):
            return self.get_runtime().player_mgr.get_player_by_client_id(event.get_client_id())
        return self.get_runtime().playerstate.get_main_player()

    def action(self, event: Event):
        raise NotImplementedError()


@DeprecationWarning
class AbilityTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, ability: IAbility):
        BaseTriggerAction.__init__(self, runtime)
        self.ability = ability

    def action(self, event: Event):
        if isinstance(event, ClientEvents.PARSER_MATCH):
            timestamp = event.timestamp
        else:
            timestamp = None
        self.ability.confirm_casting_completed(cancel_action=True, when=timestamp)


class TimerTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, name: str, severity: Severity, duration: float, casting=0.0, reuse=0.0, expire=0.0,
                 effect_target: Optional[EffectTarget] = None, replace_at_stage=OvTimerStage.Ready):
        BaseTriggerAction.__init__(self, runtime)
        self.name = name
        self.severity = severity
        self.duration = duration
        self.casting = casting
        self.reuse = reuse
        self.expire = expire
        self.warnings: List[OvWarning] = list()
        self.effect_target = effect_target
        self.replace_at_stage = replace_at_stage
        self.__recent_event: Optional[Event] = None

    def add_warning(self, warning_stage: OvTimerStage, warning_offset: float, trigger_action: ITriggerAction):
        warning_spec = OvWarning(stage=warning_stage, offset=warning_offset, action=lambda: self.__fire_warning_action(trigger_action),
                                 user_object=trigger_action)
        self.warnings.append(warning_spec)

    def iter_warnings(self) -> Generator[Tuple[OvTimerStage, float, ITriggerAction], None, None]:
        for warning in self.warnings:
            yield warning.stage, warning.offset, warning.user_object

    def __fire_warning_action(self, trigger_action: ITriggerAction):
        if self.__recent_event is None:
            logger.warn(f'No event has been set prior to warning in {self}')
            return
        trigger_action.action(self.__recent_event)

    def action(self, event: Event):
        self.__recent_event = event
        casting = self.casting
        reuse = self.reuse
        if self.effect_target:
            casting_speed = self.get_runtime().effects_mgr.apply_effects(effect_type=EffectType.CASTING_SPEED,
                                                                         apply_target=self.effect_target, base_value=casting)
            casting /= 1 + casting_speed / 100.0
            total_reuse = self.reuse + self.duration
            reuse_speed = self.get_runtime().effects_mgr.apply_effects(effect_type=EffectType.REUSE_SPEED,
                                                                       apply_target=self.effect_target, base_value=total_reuse)
            reuse /= 1 + reuse_speed / 100.0
            reuse -= self.duration
        player = self._get_event_player(event)
        name = replace_variables(player, self.name, event, False)
        self.get_runtime().overlay.start_timer(name=name, severity=self.severity, casting=casting, duration=self.duration, reuse=reuse,
                                               expire=self.expire, warnings=self.warnings, replace_stage=self.replace_at_stage)


class AbilityTimerTriggerAction(TimerTriggerAction):
    def __init__(self, runtime: IRuntime, ability: IAbility, severity: Optional[Severity] = Severity.Normal, new_name: Optional[str] = None, expire=0.0,
                 effect_target: Optional[EffectTarget] = None, replace_at_stage=OvTimerStage.Ready):
        casting = ability.get_casting_secs()
        duration = ability.get_duration_secs()
        reuse = ability.get_reuse_secs()
        if new_name is None:
            new_name = ability.ext.ability_name
        if severity is None:
            severity = ability.ext.timer_severity
        if severity is None:
            severity = Severity.Low
        if severity <= Severity.Low:
            reuse = 0.0
        TimerTriggerAction.__init__(self, runtime, new_name, severity=severity, duration=duration, casting=casting, reuse=reuse, expire=expire,
                                    effect_target=effect_target, replace_at_stage=replace_at_stage)


class LogTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, message: str, severity: Severity):
        BaseTriggerAction.__init__(self, runtime)
        self.message = message
        self.severity = severity

    def action(self, event: Event):
        player = self._get_event_player(event)
        message = replace_variables(player, self.message, event, False)
        self.get_runtime().overlay.log_event(event_text=message, severity=self.severity)


class FormattedLogTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, text: str, severity: Severity):
        BaseTriggerAction.__init__(self, runtime)
        self.text = text
        self.severity = severity

    def action(self, event: Event):
        player = self._get_event_player(event)
        text = replace_variables(player, self.text, event, False)
        self.get_runtime().overlay.log_event(event_text=text, severity=self.severity)


class WarningTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, warning_text: str, duration: Optional[float] = None, conditional_text: Optional[str] = None):
        BaseTriggerAction.__init__(self, runtime)
        self.warning_text = warning_text
        self.duration = duration
        self.conditional_text = conditional_text

    def action(self, event: Event):
        player = self._get_event_player(event)
        warning_text = replace_variables(player, self.warning_text, event, False)
        self.get_runtime().overlay.display_warning(warning_text=warning_text, duration=self.duration, conditional_text=self.conditional_text)


class TTSTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, tts_say: str, interrupts=True):
        BaseTriggerAction.__init__(self, runtime)
        self.tts_say = tts_say if tts_say is not None else ''
        self.interrupts = interrupts

    def action(self, event: Event):
        player = self._get_event_player(event)
        tts_say = replace_variables(player, self.tts_say, event, False)
        self.get_runtime().tts.say(tts_say, interrupts=self.interrupts)


class TTSFormattedTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, tts_say: str, interrupts=True):
        BaseTriggerAction.__init__(self, runtime)
        self.tts_say = tts_say
        self.interrupts = interrupts

    def action(self, event: Event):
        player = self._get_event_player(event)
        tts_say = replace_variables(player, self.tts_say, event, False)
        self.get_runtime().tts.say(tts_say, interrupts=self.interrupts)


class AlertTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, major=True):
        BaseTriggerAction.__init__(self, runtime)
        self.__major = major

    def action(self, event: Event):
        if self.__major:
            self.get_runtime().alerts.major_trigger()
        else:
            self.get_runtime().alerts.minor_trigger()


class ScriptTriggerAction(BaseTriggerAction):
    def __init__(self, runtime: IRuntime, player: IPlayer, code: str):
        BaseTriggerAction.__init__(self, runtime)
        self.player = player
        self.code = code
        # convenience singleton
        from rka.eq2.master.game.scripting.scripts.trigger_scripts import TriggerScripts, Context
        self.__ctx_class = Context
        self.scripts = TriggerScripts.get_trigger_scripts_instance(runtime)
        # build actual code
        self.__actual_code = self.__parse_code()

    def __parse_code(self) -> str:
        functions_re = re.compile(r'([a-zA-Z0-9_]+)\((\))?')
        parse_code = self.code
        functions_matched: List[Tuple[int, str, str]] = list()  # start_index, str_to_replace, replacement_str
        for match in functions_re.finditer(parse_code):
            start_idx = match.start()
            fn_name = match.group(1)
            if start_idx and (parse_code[start_idx - 1] == '.' or parse_code[start_idx - 1] == '$'):
                # ignore member function calls
                continue
            if fn_name in __builtins__:
                # dont change standard function calls
                continue
            if hasattr(self.scripts, fn_name):
                if match.group(2):
                    # has closing bracket and no args
                    fn_call = f'self.scripts.{fn_name}(ctx)'
                else:
                    fn_call = f'self.scripts.{fn_name}(ctx, '
                functions_matched.append((start_idx, match.group(0), fn_call))
            else:
                raise ValueError(f'Unknown function: {fn_name}, in: {self.code}')
        if not functions_matched:
            raise ValueError(f'No script functions in: {self.code}')
        current_index = 0
        result_code = ''
        for start_idx, fn_name, fn_call in functions_matched:
            result_code += parse_code[current_index:start_idx]
            result_code += fn_call
            current_index += len(fn_name)
        result_code += parse_code[current_index:]
        return result_code

    def action(self, event: Event):
        ctx = self.__ctx_class(self.player, event, time.time())
        local_vars = {'self': self, 'ctx': ctx}
        try:
            parametrized_code = replace_variables(self.player, self.__actual_code, event, True)
        except Exception as e:
            logger.error(f'Error parametrizing variables: {e}')
            logger.error(f'event is: {event}')
            logger.error(f'code is: {self.__actual_code}')
            return
        try:
            # noinspection PyArgumentList
            exec(parametrized_code, local_vars)
        except ValueError as e:
            logger.warn(f'Value Error: {e}')
        except Exception as e:
            traceback.print_exc()
            logger.error(f'Code error: {e}')
            logger.error(f'Code is: {parametrized_code}')
