from __future__ import annotations

import traceback
from typing import Optional, List, Any, Dict
from xml.dom import minidom as xmd

from rka.components.events import Event
from rka.components.ui.overlay import Severity, OvTimerStage
from rka.eq2.master.game import is_unknown_zone
from rka.eq2.master.triggers import logger, ITrigger, ITriggerWarningCodeFunctions
from rka.eq2.master.triggers.trigger_actions import TTSTriggerAction, AlertTriggerAction, WarningTriggerAction, LogTriggerAction, TimerTriggerAction, \
    ScriptTriggerAction
from rka.eq2.master.triggers.trigger_factory import PlayerTriggerFactory
from rka.eq2.master.triggers.trigger_subscribers import EventSubscriberToolkit
from rka.eq2.master.triggers.trigger_util import ACTXMLElement
from rka.eq2.shared.client_events import ClientEvents


class TriggerSpec:
    DEFAULT_CATEGORY = 'anywhere'

    def __init__(self):
        self.zone: Optional[str] = None
        self.zone_tier_specific = False
        self.allow_out_of_main_zone = False
        self.local_player = True
        self.remote_player = False
        self.variant = 0
        self.subscribe_event_name: Optional[str] = None
        self.subscribe_event_params: Optional[Dict[str, Any]] = None
        self.test_event_name: Optional[str] = None
        self.test_event_params: Optional[Dict[str, Any]] = None
        self.action_tts: Optional[str] = None
        self.action_log: Optional[str] = None
        self.action_alert = False
        self.action_warning: Optional[str] = None
        self.action_warning_duration: Optional[float] = None
        self.action_code_1: Optional[str] = None
        self.action_code_2: Optional[str] = None
        self.action_code_3: Optional[str] = None
        self.action_timer_name: Optional[str] = None
        self.action_timer_severity: Optional[int] = None
        self.action_timer_casting: Optional[float] = None
        self.action_timer_duration: Optional[float] = None
        self.action_timer_reuse: Optional[float] = None
        self.action_timer_expire: Optional[float] = None
        self.action_timer_warning_stage: Optional[str] = None
        self.action_timer_warning_offset: Optional[float] = None
        self.action_timer_warning_code: Optional[str] = None
        self.repeat_period = 0.0
        self.repeat_key: Optional[str] = None

    def short_str(self, limit=200) -> str:
        if self.zone is None:
            zone_str = TriggerSpec.DEFAULT_CATEGORY
        else:
            i = self.zone.find('[') if self.zone is not None else -1
            zone_str = f'{self.zone[:7]}..{self.zone[i - 4:i]}'
        event_str = self.key()
        return f'[{zone_str}] {event_str}'[:limit]

    @staticmethod
    def __sorted_params(params: Dict[str, Any]) -> Dict[str, Any]:
        sorted_params = {k: params[k] for k in sorted(params.keys())}
        return sorted_params

    def key(self) -> str:
        event_name = self.get_subscribe_event().value
        sorted_params = TriggerSpec.__sorted_params(self.subscribe_event_params)
        return f'{event_name}: {sorted_params}-{self.variant}'

    @staticmethod
    def from_act_trigger_xml(xml_str: str) -> Optional[TriggerSpec]:
        try:
            dom = xmd.parseString(xml_str)
        except Exception as e:
            logger.error(f'failed to parse trigger: {xml_str}')
            traceback.print_exc(e)
            return None
        trigger_nodes = dom.getElementsByTagName('Trigger')
        for trigger_node in trigger_nodes:
            trigger_spec = TriggerSpec()
            parse_filter = trigger_node.getAttribute('R')
            if parse_filter is None or parse_filter == '':
                logger.warn(f'missing parser filter in ACT XML {xml_str}')
                return None
            prefix = '.*' if parse_filter[0] != '^' else ''
            postfix = '.*' if parse_filter[-1] != '$' else ''
            trigger_spec.set_subscribe_event(ClientEvents.PARSER_MATCH(parse_filter=f'{prefix}{parse_filter}{postfix}', preparsed_log=False))
            zone = trigger_node.getAttribute('C')
            restrict_to_zone = trigger_node.getAttribute('CR') == 'T'
            if restrict_to_zone and parse_filter is not None and parse_filter != '':
                trigger_spec.zone = zone
            try:
                trigger_type = int(trigger_node.getAttribute('ST'))
            except ValueError:
                logger.warn(f'wrong trigger type in ACT XML {xml_str}')
                return None
            trigger_spec.action_log = f'ACT: {parse_filter}'
            if trigger_type == 1:
                trigger_spec.action_alert = True
            elif trigger_type == 3:
                tts = trigger_node.getAttribute('SD')
                if tts is not None and tts != '':
                    trigger_spec.action_tts = tts
                    trigger_spec.action_log = f'ACT: {tts}'
            return trigger_spec
        logger.warn(f'missing Trigger node in ACT XML {xml_str}')
        return None

    def get_subscribe_event(self) -> Event:
        event = Event.get_event_type_from_name(self.subscribe_event_name)()
        event.from_params(self.subscribe_event_params)
        return event

    def get_test_event(self) -> Optional[Event]:
        if not self.test_event_name:
            return None
        event = Event.get_event_type_from_name(self.subscribe_event_name)()
        event.from_params(self.test_event_params)
        return event

    def set_subscribe_event(self, event: Event):
        self.subscribe_event_name = event.name
        self.subscribe_event_params = TriggerSpec.__sorted_params(event.get_params())

    def set_test_event(self, event: Optional[Event]):
        if not event:
            self.test_event_params = None
            return
        self.test_event_name = event.name
        self.test_event_params = TriggerSpec.__sorted_params(event.get_params())

    def to_act_trigger_xml(self) -> Optional[str]:
        subscribe_event = self.get_subscribe_event()
        if not isinstance(subscribe_event, ClientEvents.PARSER_MATCH):
            logger.warn(f'Cannot export to ACT, must be Parser Event: {self}')
            return None
        dom = xmd.Document()
        node = ACTXMLElement('Trigger')
        node.ownerDocument = dom
        dom.appendChild(node)
        # cannot input # character after \ in the game chat for some reason
        ACT_corrected_parse_filter = subscribe_event.parse_filter.replace(r'\#', r'\.')
        # also force ACT to parse from the start, otherwise its doing a 'find'
        ACT_corrected_parse_filter = '^' + ACT_corrected_parse_filter
        node.setAttribute('R', ACT_corrected_parse_filter)
        if self.action_tts is not None:
            node.setAttribute('SD', self.action_tts)
            node.setAttribute('ST', '3')
        elif self.action_alert:
            node.setAttribute('SD', '')
            node.setAttribute('ST', '1')
        else:
            node.setAttribute('SD', '')
            node.setAttribute('ST', '0')
        node.setAttribute('C', self.zone if self.zone is not None else ' General')
        node.setAttribute('CR', 'T' if self.zone is not None else 'F')
        node.setAttribute('T', 'F')
        node.setAttribute('TN', '')
        node.setAttribute('Ta', 'F')
        return node.toxml()

    @staticmethod
    def from_dict(trigger_spec_dict: Dict) -> Optional[TriggerSpec]:
        if 'subscribe_event_name' in trigger_spec_dict:
            trigger_spec = TriggerSpec()
            trigger_spec.__dict__.update(trigger_spec_dict)
            return trigger_spec
        return None

    @staticmethod
    def __from_trigger(trigger: ITrigger, zone_name: Optional[str]) -> TriggerSpec:
        ts = TriggerSpec()
        original_spec = trigger.get_original_spec()
        if isinstance(original_spec, TriggerSpec):
            ts.zone = original_spec.zone
            ts.allow_out_of_main_zone = original_spec.allow_out_of_main_zone
            ts.local_player = original_spec.local_player
            ts.remote_player = original_spec.remote_player
        else:
            ts.zone = zone_name if not is_unknown_zone(zone_name) else None
        for trigger_action in trigger.iter_trigger_actions():
            trigger_action: Any = trigger_action
            if isinstance(trigger_action, TTSTriggerAction):
                ts.action_tts = trigger_action.tts_say
            if isinstance(trigger_action, AlertTriggerAction):
                ts.action_alert = True
            if isinstance(trigger_action, WarningTriggerAction):
                ts.action_warning = trigger_action.warning_text
                ts.action_warning_duration = trigger_action.duration
            if isinstance(trigger_action, LogTriggerAction):
                ts.action_log = trigger_action.message
            if isinstance(trigger_action, TimerTriggerAction):
                ts.action_timer_name = trigger_action.name
                ts.action_timer_severity = trigger_action.severity.value
                ts.action_timer_casting = trigger_action.casting
                ts.action_timer_duration = trigger_action.duration
                ts.action_timer_reuse = trigger_action.reuse
                ts.action_timer_expire = trigger_action.expire
                if len(trigger_action.warnings) > 1:
                    logger.warn(f'Cannot export all warnings from {trigger_action}')
                for stage, offset, action in trigger_action.iter_warnings():
                    if isinstance(action, TTSTriggerAction):
                        ts.action_timer_warning_code = f'{ITriggerWarningCodeFunctions.tts.__name__}({action.tts_say})'
                    elif isinstance(action, WarningTriggerAction):
                        ts.action_timer_warning_code = f'{ITriggerWarningCodeFunctions.warning.__name__}({action.warning_text})'
                    elif isinstance(action, LogTriggerAction):
                        ts.action_timer_warning_code = f'{ITriggerWarningCodeFunctions.msg.__name__}({action.message})'
                    elif isinstance(action, ScriptTriggerAction):
                        ts.action_timer_warning_code = action.code
                    else:
                        logger.warn(f'Unsupported warning action {action}')
                    ts.action_timer_warning_offset = offset
                    ts.action_timer_warning_stage = stage
                    break
            if isinstance(trigger_action, ScriptTriggerAction):
                if not ts.action_code_1:
                    ts.action_code_1 = trigger_action.code
                elif not ts.action_code_2:
                    ts.action_code_2 = trigger_action.code
                elif not ts.action_code_3:
                    ts.action_code_3 = trigger_action.code
                else:
                    logger.error(f'Too many code lines, cannot add {trigger_action.code}')
        ts.local_player = True
        ts.repeat_period = trigger.repeat_period
        ts.repeat_key = trigger.repeat_key
        return ts

    @staticmethod
    def from_trigger(trigger: ITrigger, zone_name: Optional[str]) -> List[TriggerSpec]:
        all_specs: List[TriggerSpec] = list()
        for registered_trigger_event in trigger.iter_trigger_events():
            if registered_trigger_event.has_filter_cb():
                logger.info(f'Dynamic filtered events cannot be exported')
                continue
            ts = TriggerSpec.__from_trigger(trigger, zone_name)
            ts.set_subscribe_event(registered_trigger_event.get_event())
            ts.set_test_event(registered_trigger_event.get_test_event())
            all_specs.append(ts)
        return all_specs

    def to_trigger(self, factory: PlayerTriggerFactory) -> ITrigger:
        player = factory.get_player()
        runtime = factory.get_runtime()
        trigger = factory.new_trigger()
        subscribe_event = self.get_subscribe_event()
        EventSubscriberToolkit.add_event_to_trigger(runtime=runtime, trigger=trigger, event=subscribe_event)
        test_event = self.get_test_event()
        if test_event is not None:
            trigger.set_test_event(test_event)
            trigger.clear_test_event_update_flag()
        if self.action_tts is not None:
            trigger.add_action(TTSTriggerAction(runtime, self.action_tts))
        if self.action_log is not None:
            trigger.add_action(LogTriggerAction(runtime, self.action_log, Severity.Normal))
        if self.action_alert:
            trigger.add_action(AlertTriggerAction(runtime))
        if self.action_warning is not None:
            duration = 2.0
            if self.action_warning_duration is not None:
                duration = self.action_warning_duration
            trigger.add_action(WarningTriggerAction(runtime, self.action_warning, duration=duration, conditional_text=''))
        if self.action_code_1 is not None:
            trigger.add_action(ScriptTriggerAction(runtime, player, self.action_code_1))
        if self.action_code_2 is not None:
            trigger.add_action(ScriptTriggerAction(runtime, player, self.action_code_2))
        if self.action_code_3 is not None:
            trigger.add_action(ScriptTriggerAction(runtime, player, self.action_code_3))
        if self.action_timer_name is not None:
            duration = 0.0
            if self.action_timer_duration is not None:
                duration = float(self.action_timer_duration)
            else:
                logger.warn(f'No duration specified for {self.action_timer_name} in {self}')
            severity = Severity.Low
            if self.action_timer_severity is not None:
                severity = Severity(self.action_timer_severity)
            casting = 0.0
            if self.action_timer_casting is not None:
                casting = float(self.action_timer_casting)
            reuse = 0.0
            if self.action_timer_reuse is not None:
                reuse = float(self.action_timer_reuse)
            expire = 0.0
            if self.action_timer_expire is not None:
                expire = float(self.action_timer_expire)
            timer_action = TimerTriggerAction(runtime, name=self.action_timer_name, severity=severity,
                                              casting=casting, duration=duration, reuse=reuse, expire=expire)
            if self.action_timer_warning_stage:
                warning_action = ScriptTriggerAction(runtime, player=player, code=self.action_timer_warning_code)
                offset = self.action_timer_warning_offset if self.action_timer_warning_offset else 0.0
                timer_action.add_warning(OvTimerStage.get_case_insensitive(self.action_timer_warning_stage), warning_offset=offset,
                                         trigger_action=warning_action)
            trigger.add_action(timer_action)
        trigger.repeat_period = self.repeat_period
        trigger.repeat_key = self.repeat_key
        trigger.save_original_spec(self)
        return trigger
