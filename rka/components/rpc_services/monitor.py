import sys
import time
from typing import List, Optional, Dict, Any, Callable

from rka.components.rpc_brokers.command_util import is_any_command_sync, is_any_command_blocking, is_any_command_returning
from rka.components.rpc_services.client_proxy import ClientBrokerProxy


class CompletionToken:
    def __init__(self, cid, commands: List, completion_cb: Optional[Callable[[Optional[List]], None]] = None):
        self.__cid = cid
        self.__commands = commands
        self.__completion_cb = completion_cb
        self.__start = time.time()

    def __call__(self, results, *args, **kwargs):
        diff = time.time() - self.__start
        sync = is_any_command_sync(self.__commands)
        block = is_any_command_blocking(self.__commands)
        print(f'dispatch to {self.__cid} (b:{block},s:{sync}) took {diff}s, commands: {self.__commands}', file=sys.stderr)
        if self.__completion_cb is not None:
            self.__completion_cb(results)


class ClientBrokerMonitorProxy(ClientBrokerProxy):
    def __init__(self):
        ClientBrokerProxy.__init__(self)

    def __measured_send(self, client_id, commands: List[Dict[str, Any]]) -> (bool, Optional[List]):
        start = time.time()
        connected, result = ClientBrokerProxy.send_to_client(self, client_id, commands)
        end = time.time()
        diff = end - start
        sync = is_any_command_sync(commands)
        block = is_any_command_blocking(commands)
        print(f'call to {client_id} (b:{block},s:{sync}) took {diff}s, commands: {commands}', file=sys.stderr)
        return connected, result

    def send_to_client(self, client_id: str, commands: List[Dict[str, Any]],
                       completion_cb: Optional[Callable[[Optional[List]], None]] = None) -> (bool, Optional[List]):
        if is_any_command_returning(commands):
            return self.__measured_send(client_id, commands)
        wrapper_cb = CompletionToken(client_id, commands, completion_cb)
        return ClientBrokerProxy.send_to_client(self, client_id, commands, completion_cb=wrapper_cb)
