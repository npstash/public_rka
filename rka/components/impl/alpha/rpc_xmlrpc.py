import threading
import time
import xmlrpc.client
import xmlrpc.server
from threading import Condition
from xmlrpc.client import ServerProxy, Transport

from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.log_service import LogService
from rka.components.network.rpc import IServiceHost, AbstractConnection
from rka.log_configs import LOG_RPC

logger = LogService(LOG_RPC)


class XMLRPCHost(IServiceHost):
    def __init__(self, nifaddr: str, port: int, service):
        self.__nifaddr = nifaddr
        self.__port = port
        self.__service = service
        self.__rpc_server = None
        self.__last_shutdown = 0.0
        self.__restart_failures = 0
        self.__max_restart_failures = 3
        self.__recurrent_failure_time_window = 2.0
        self.__startup_done = False
        self.__startup_condition = Condition()

    def __run(self):
        assert self.__rpc_server is None
        nifaddr = self.__nifaddr
        port = self.__port
        service = self.__service
        logger.info(f'creating RPC host at {nifaddr}:{port}, service {service}')
        server = xmlrpc.server.SimpleXMLRPCServer((self.__nifaddr, self.__port), allow_none=True, logRequests=False, use_builtin_types=True,
                                                  requestHandler=xmlrpc.server.SimpleXMLRPCRequestHandler, bind_and_activate=False)
        server.allow_reuse_address = False
        try:
            with server:
                self.__rpc_server = server
                server.register_instance(self.__service)
                server.server_bind()
                server.server_activate()
                with self.__startup_condition:
                    self.__startup_done = True
                    self.__startup_condition.notify_all()
                logger.info(f'activated RPC host at {nifaddr}:{port}, service {service}')
                server.serve_forever()
                logger.info(f'serve_forever exit for RPC host at {nifaddr}:{port}, service {service}')
        except Exception as e:
            logger.error(f'exception {e} when running RPC host at {nifaddr}:{port}, service {service}')
            try:
                server.server_close()
            except OSError as _e2:
                logger.warn(f'Failed to close socket in {self}: {_e2}')
                pass
            time_since_last_shutdown = time.time() - self.__last_shutdown
            logger.error(f'time since last shutdown: {time_since_last_shutdown}')
            if time_since_last_shutdown <= self.__recurrent_failure_time_window:
                self.__restart_failures += 1
                logger.error(f'delay restarting RPC service by: {self.__recurrent_failure_time_window / 2}')
                time.sleep(self.__recurrent_failure_time_window / 2)
            else:
                logger.error(f'resetting failure count')
                self.__restart_failures = 0
            if self.__restart_failures < self.__max_restart_failures:
                logger.error(f'restarting RPC service at {nifaddr}:{port}, service {service}')
                self.start()
            else:
                logger.error(f'max failure count reached, giving up')
            raise
        finally:
            self.__last_shutdown = time.time()
            logger.debug(f'Thread {threading.current_thread().name} exiting')

    def get_address(self) -> str:
        return self.__nifaddr

    def start(self):
        service = self.__service
        addr = self.__nifaddr + ':' + str(self.__port)
        RKAThread(name=f'XMLRPC service for {service}, {addr}', target=self.__run).start()

    def wait_until_started(self, timeout: float) -> bool:
        exit_at = time.time() + timeout
        with self.__startup_condition:
            while not self.__startup_done and timeout > 0.0:
                self.__startup_condition.wait(timeout)
                timeout = exit_at - time.time()
        return self.__startup_done

    def close(self):
        if self.__rpc_server is not None:
            logger.info(f'shutdown RPC host at {self.__nifaddr}, service {self.__service}')
            self.__rpc_server.shutdown()
        self.__rpc_server = None


class _TimeoutTransport(Transport):
    def __init__(self, timeout, use_datetime=0):
        self.timeout = timeout
        Transport.__init__(self, use_datetime)

    def make_connection(self, host):
        connection = Transport.make_connection(self, host)
        connection.timeout = self.timeout
        return connection


class _TimeoutServerProxy(ServerProxy):
    def __init__(self, uri, timeout, *args, **kwargs):
        kwargs['transport'] = _TimeoutTransport(timeout=timeout, use_datetime=kwargs.get('use_datetime', 0))
        ServerProxy.__init__(self, uri, *args, **kwargs)


class XMLRPCConnection(AbstractConnection):
    TIMEOUT = 15.0

    def __init__(self, local_address: str, remote_address: str, port: int):
        AbstractConnection.__init__(self, local_address, remote_address)
        host = f'http://{remote_address}:{port}'
        logger.debug(f'init connection object to RPC host at {host}')
        self.__rpc_proxy = _TimeoutServerProxy(host, timeout=XMLRPCConnection.TIMEOUT, allow_none=True, use_builtin_types=True, verbose=False)

    def get_proxy(self) -> object:
        return self.__rpc_proxy

    def close(self):
        proxy = self.__rpc_proxy
        if proxy is not None:
            proxy('close')()
            self.__rpc_proxy = None
            logger.debug(f'closing connection {self}')
