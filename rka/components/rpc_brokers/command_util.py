from typing import List, Any, Dict

from rka.components.io.log_service import LogLevel
from rka.eq2.shared.control.action_id import ACTION_ID_KEY
from rka.util.util import to_bool


def is_command_returning(command) -> bool:
    return is_command_blocking(command) and is_command_sync(command)


def is_command_blocking(command) -> bool:
    assert isinstance(command, dict)
    block = False
    if 'block' in command.keys():
        blockval = command['block']
        if isinstance(blockval, bool):
            block = blockval
        elif isinstance(blockval, str):
            block = to_bool(blockval)
    return block


def is_command_sync(command) -> bool:
    if isinstance(command, list):
        return is_any_command_sync(command)
    assert isinstance(command, dict)
    sync = False
    if 'sync' in command.keys():
        syncval = command['sync']
        if isinstance(syncval, bool):
            sync = syncval
        elif isinstance(syncval, str):
            sync = to_bool(syncval)
    return sync


def is_any_command_returning(commands) -> bool:
    for command in commands:
        if is_command_returning(command):
            return True
    return False


def is_any_command_blocking(commands: List[Dict[str, Any]]) -> bool:
    for command in commands:
        if is_command_blocking(command):
            return True
    return False


def is_any_command_sync(commands: List[Dict[str, Any]]) -> bool:
    for command in commands:
        if is_command_sync(command):
            return True
    return False


# sync command is processed in the RPC thread on the remote side and is able to return a result.
# should be used with blocking flag, otherwise it has no practical meaning
# return values: None, None (without blocking)
# return values: <connection status>, <command result> (with blocking)
def set_command_sync(command: Dict[str, Any], sync: bool):
    command['sync'] = sync


# blocking command means that dispatch is blocked until the command is actaully sent.
# if it also sync, then command is returning.
# return values: <connection status>, None
def set_command_blocking(command: Dict[str, Any], block: bool):
    command['block'] = block


# processed on the remote side, returning command returns a result form its execution. needs to be sync and blocking.
# use with care, it will block BOTH threads - local and remote, unitl command is executed.
# if the command processed on remote side sends back another blocking command, it will deadlock.
# return values: <connection status>, <command result>
def set_command_returning(command: Dict[str, Any], ret: bool):
    set_command_blocking(command, ret)
    set_command_sync(command, ret)


def make_ping_command() -> Dict[str, Any]:
    ping_command = {'ping': True, 'sync': False, 'block': False}
    return ping_command


def is_ping_command(command: Dict[str, Any]) -> bool:
    return 'ping' in command and command['ping']


def is_any_ping_command(commands: List[Dict[str, Any]]) -> bool:
    for command in commands:
        if is_ping_command(command):
            return True
    return False


def command_debug_str(log_level: LogLevel, command: Dict[str, Any]) -> str:
    if not isinstance(command, dict):
        return str(command)
    if log_level <= LogLevel.DETAIL:
        return str(command)
    if ACTION_ID_KEY in command:
        result = command[ACTION_ID_KEY]
    else:
        result = ''
    if log_level <= LogLevel.DEBUG:
        result += str(list(command.keys()))
    if result:
        return result
    return str(list(command.keys()))


def commands_debug_str(log_level: LogLevel, commands: List[Dict[str, Any]]) -> str:
    commands_str = ', '.join(map(lambda command: command_debug_str(log_level, command), commands))
    return f'[{commands_str}]'
