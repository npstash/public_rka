from typing import Dict, Any

from rka.components.events import Event
from rka.components.events.event_system import EventSystem
from rka.eq2.configs.shared.hosts import host_configs
from rka.eq2.master import IRuntime
from rka.eq2.master.control import logger
from rka.eq2.master.control.client_controller import ClientConfig
from rka.eq2.master.control.master_bridge import MasterBridge
from rka.eq2.master.master_events import MasterEvents
from rka.eq2.shared.control.action_id import ActionID
from rka.eq2.shared.control.interpreter import AbstractInterpreter


class MasterInterpreter(AbstractInterpreter):
    def __init__(self, runtime: IRuntime, bridge: MasterBridge):
        self.__bridge = bridge
        self.__runtime = runtime

    def _interpret_action(self, action_id: ActionID, command: Dict[str, Any]) -> Any:
        if action_id == ActionID.EVENT_OCCUR:
            client_id = command['client_id']
            event_name = command['event_name']
            event_params = command['event_params']
            event_type = Event.get_event_type_from_name(event_name)
            event = event_type().from_params(event_params)
            bus = self.__runtime.remote_client_event_system.get_bus(client_id)
            if not bus:
                logger.warn(f'Event bus for {client_id} not available')
                return False
            bus.post(event)
            return True
        elif action_id == ActionID.REMOTE_HOSTNAME:
            client_id = command['client_id']
            hostname = command['hostname']
            self.configure_remote_client_hostname(client_id, hostname)
            return True
        # do not call super method, do not allow standard control actions
        logger.error(f'master: cannot interpret unknown action: {command}')
        return None

    # noinspection PyMethodMayBeStatic
    def configure_remote_client_hostname(self, client_id: str, hostname: str):
        if hostname not in host_configs.keys():
            logger.error(f'received unknown hostname from remote client: {client_id}, {hostname}')
            return
        logger.info(f'configure_remote_client_hostname: cid:{client_id}, {hostname}')
        client_config = ClientConfig.get_client_config(client_id)
        client_config.set_inputs_config(host_configs[hostname].get_input_config())
        client_config.set_current_host_id(host_configs[hostname].host_id)
        EventSystem.get_main_bus().post(MasterEvents.CLIENT_CONFIGURED(client_id=client_id))
