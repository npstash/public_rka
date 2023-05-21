from enum import auto

from rka.util.util import NameEnum

ACTION_ID_KEY = 'action_id'


class ActionID(NameEnum):
    # Slave->Master actions
    EVENT_OCCUR = auto()
    REMOTE_HOSTNAME = auto()

    # Master->Slave actions
    PARSER_SUBSCRIBE = auto()
    PARSER_UNSUBSCRIBE = auto()
    TESTLOG_INJECT = auto()
    EVENT_SUBSCRIBE = auto()
    EVENT_UNSUBSCRIBE = auto()
    GET_HOSTNAME = auto()

    # Commands (Master->Slave)
    KEY = auto()
    TEXT = auto()
    MOUSE = auto()
    DOUBLE_CLICK = auto()
    MOUSE_SCROLL = auto()
    WINDOW_ACTIVATE = auto()
    WINDOW_CHECK = auto()
    DELAY = auto()
    PROCESS = auto()
    INJECT_COMMAND = auto()
    REMOVE_INJECTED_COMMAND = auto()
    INJECT_PREFIX = auto()
    INJECT_POSTFIX = auto()
    FIND_CAPTURE_MATCH = auto()
    FIND_MULTIPLE_CAPTURE_MATCH = auto()
    CLICK_CAPTURE_MATCH = auto()
    GET_CAPTURE_MATCH = auto()
    SAVE_CAPTURE = auto()
    CAPTURE_CURSOR = auto()
    CURSOR_FINGERPRINT = auto()
