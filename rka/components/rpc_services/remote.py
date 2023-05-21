import threading
import traceback
from typing import Union, List, Any, Dict, Callable, Optional

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkathread import RKAThread
from rka.components.impl.factories import ServiceHostFactory, DiscoveryFactory
from rka.components.io.log_service import LogLevel
from rka.components.network.discovery import INetworkDiscovery, INetworkFilter, INodeDiscovery
from rka.components.network.network_config import NetworkServiceConfig
from rka.components.network.rpc import IServiceHost
from rka.components.rpc_brokers.command_util import is_any_command_sync, command_debug_str, commands_debug_str
from rka.components.rpc_services import IInterpreter, logger


class InterpretException(Exception):
    def __init__(self, reason: str, print_trace=False):
        self.reason = reason
        self.print_trace = print_trace

    def __str__(self) -> str:
        return f'{InterpretException.__class__.__name__}: {self.reason}'


class ExecutionNode(Closeable):
    def __init__(self, this_node_id: str, interpreter: IInterpreter):
        Closeable.__init__(self, explicit_close=True)
        self.node_id = this_node_id
        self.__interpreter = interpreter
        self.__queue_lock = threading.Condition()
        self.__queue: List[Optional[List[Dict[str, Any]]]] = list()
        RKAThread(name=f'Service Dispatch {this_node_id}', target=self.__execute_loop).start()

    def __str__(self):
        return f'Remote Service [{self.node_id}]'

    def __execute_loop(self):
        while True:
            with self.__queue_lock:
                while len(self.__queue) == 0:
                    self.__queue_lock.wait()
                commands = self.__queue.pop(0)
            if commands is None:
                break
            self.__interpret_or_execute(commands)

    # noinspection PyMethodMayBeStatic
    def __log_failed_command_debug(self, commands: List[Union[Dict[str, Any], Callable]], failed_cmd_num: int):
        n_commands_lost = len(commands) - failed_cmd_num - 1
        if n_commands_lost:
            logger.info(f'Following commands are lost ({n_commands_lost})')
            for k in range(failed_cmd_num + 1, len(commands)):
                logger.info(f'{k - failed_cmd_num}. {commands[k]}')

    def __interpret_or_execute(self, commands: List[Union[Dict[str, Any], Callable]]) -> Optional[List]:
        # noinspection PyBroadException
        try:
            results: List[Any] = list()
            for i, command in enumerate(commands):
                if isinstance(command, dict):
                    if logger.get_level() <= LogLevel.DEBUG:
                        logger.debug(f'interpreting at {self.node_id} command {command_debug_str(LogLevel.DEBUG, command)}')
                    result = self.__interpreter.interpret(command)
                    results.append(result)
                    if not result:
                        logger.info(f'command {command_debug_str(LogLevel.INFO, command)} failed with {result}')
                        results.extend([None] * (len(commands) - i - 1))
                        self.__log_failed_command_debug(commands, i)
                        break
                elif callable(command):
                    if logger.get_level() <= LogLevel.DEBUG:
                        logger.debug(f'executing at {self.node_id} task {command}')
                    result = command()
                    results.append(result)
                else:
                    raise ValueError(command)
                if logger.get_level() <= LogLevel.DEBUG:
                    logger.debug(f'interpret result: {result}')
            return results
        except InterpretException as ie:
            logger.warn(f'command {commands} failed {ie}')
            if ie.print_trace:
                traceback.print_exc()
            return None
        except Exception as e:
            logger.error(f'command {commands} raised excetpion {e}')
            traceback.print_exc()
            return None

    def dispatch_sync(self, commands: List[Union[Dict[str, Any], Callable]]) -> Optional[List]:
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'dispatching sync at {self} command {commands_debug_str(LogLevel.DEBUG, commands)}')
        return self.__interpret_or_execute(commands)

    def dispatch_async(self, commands: List[Union[Dict[str, Any], Callable]]):
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'dispatching async at {self} command {commands_debug_str(LogLevel.DEBUG, commands)}')
        with self.__queue_lock:
            self.__queue.append(commands)
            self.__queue_lock.notify()

    def dispatch_auto(self, commands: List[Union[Dict[str, Any], Callable]]) -> Optional[List]:
        if is_any_command_sync(commands):
            return self.dispatch_sync(commands)
        else:
            self.dispatch_async(commands)
            return None

    def close(self):
        with self.__queue_lock:
            self.__queue.append(None)
            self.__queue_lock.notify()
        Closeable.close(self)


class Remote(ExecutionNode, INetworkFilter):
    def __init__(self, this_remote_id: str, network_service_config: NetworkServiceConfig, interpreter: IInterpreter):
        ExecutionNode.__init__(self, this_remote_id, interpreter)
        self.__rpchost_lock = threading.RLock()
        self.__is_closed = False
        self.__rpc_hosts: List[IServiceHost] = list()
        self.__nif_discovery: Optional[INetworkDiscovery] = None
        self.__node_discovery: Optional[INodeDiscovery] = None
        self.__single_rpc_host = False
        self.__network_service_config = network_service_config

    def _is_single_rpc_host(self) -> bool:
        return self.__single_rpc_host

    def _create_node_discovery(self) -> INodeDiscovery:
        raise NotImplementedError()

    def _get_service_object(self) -> object:
        raise NotImplementedError()

    def _start_services(self):
        self._stop_services()
        self.__nif_discovery = DiscoveryFactory.create_network_discovery(self.node_id, self.__network_service_config.filtered_nifs)
        self.__node_discovery = self._create_node_discovery()
        self.__single_rpc_host = False
        if not self.__network_service_config.filtered_nifs:
            if self._start_rpc_host('0.0.0.0', '255.255.255.255'):
                self.__single_rpc_host = True
            else:
                logger.error('Failed to start RPC host for all NIFs')
        self.__nif_discovery.set_nif_filter(self)
        self.__nif_discovery.add_network_found_observer(self.__on_network_found)
        self.__nif_discovery.add_network_lost_observer(self.__on_network_lost)
        self.__nif_discovery.start()
        self.__node_discovery.start()

    def _stop_services(self):
        if self.__nif_discovery:
            self.__nif_discovery.stop()
            self.__nif_discovery = None
        if self.__node_discovery:
            self.__node_discovery.stop()
            self.__node_discovery = None

    def accept_nifaddr(self, nifaddr: str, network: str) -> bool:
        filtered_nifs = self.__network_service_config.filtered_nifs
        return not filtered_nifs or nifaddr in filtered_nifs or network in filtered_nifs

    def __on_network_found(self, nifaddr: str, network: str):
        logger.debug(f'__network_found: {nifaddr}/{network}')
        host_started = self._is_single_rpc_host()
        if not host_started:
            logger.debug(f'__network_found: creating new RPC host')
            host_started = self._start_rpc_host(nifaddr, network)
        if host_started:
            logger.debug(f'__network_found: starting discovery')
            self.__node_discovery.add_nifaddr(nifaddr, network)

    def __on_network_lost(self, nifaddr: str, network: str):
        logger.debug(f'__network_lost: {nifaddr}/{network}, stopping discovery')
        self.__node_discovery.remove_nifaddr(nifaddr)
        if not self._is_single_rpc_host():
            logger.debug(f'__network_lost: closing RPC host')
            self._close_rpc_host(nifaddr)

    def _start_rpc_host(self, nifaddr: str, network: str) -> bool:
        service_wrapper = self._get_service_object()
        port = self.__network_service_config.port
        logger.debug(f'starting new RPC host on {nifaddr}:{port}')
        with self.__rpchost_lock:
            if self.__is_closed:
                logger.warn(f'cannot start RPC host on {nifaddr}:{port}, this Remote instance already closed')
                return False
            for rpc_host in self.__rpc_hosts:
                if rpc_host.get_address() == nifaddr:
                    logger.warn(f'cannot start RPC host RPC host on {nifaddr}:{port}, already exists')
                    return False
            if not self.accept_nifaddr(nifaddr, network):
                logger.debug(f'RPC host on {nifaddr}:{port} not started, NIF not accepted')
                return False
            rpc_host = ServiceHostFactory.create_service_host(nifaddr, port, service_wrapper)
            rpc_host.start()
            if not rpc_host.wait_until_started(10.0):
                logger.warn(f'RPC host on {nifaddr}:{port} did not start in timeout')
                rpc_host.close()
                return False
            self.__rpc_hosts.append(rpc_host)
            logger.debug(f'started RPC host on {nifaddr}:{port}')
            return True

    def _close_rpc_host(self, nifaddr: str):
        port = self.__network_service_config.port
        logger.info(f'closing RPC host on {nifaddr}:{port}')
        with self.__rpchost_lock:
            rpc_hosts_to_remove: List[IServiceHost] = list()
            for rpc_host in self.__rpc_hosts:
                if rpc_host.get_address() == nifaddr:
                    rpc_hosts_to_remove.append(rpc_host)
                    rpc_host.close()
                    logger.debug(f'RPC host on {nifaddr}:{port} closed')
            for rpc_host in rpc_hosts_to_remove:
                self.__rpc_hosts.remove(rpc_host)

    def _close_all_rpc_hosts(self):
        logger.info(f'closing all RPC hosts on {self.node_id}')
        with self.__rpchost_lock:
            hosts = list(self.__rpc_hosts)
            self.__rpc_hosts.clear()
        for rpc_host in hosts:
            rpc_host.close()

    def _restart_all_rpc_hosts(self):
        logger.info(f'restarting all RPC hosts on {self.node_id}')
        with self.__rpchost_lock:
            hosts = list(self.__rpc_hosts)
        for rpc_host in hosts:
            rpc_host.close()
            rpc_host.start()

    def close(self):
        self.__is_closed = True
        self._stop_services()
        self._close_all_rpc_hosts()
        ExecutionNode.close(self)
