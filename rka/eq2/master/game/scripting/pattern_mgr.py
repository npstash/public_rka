import time
from typing import List

from rka.components.common_events import CommonEvents
from rka.components.events.event_system import EventSystem
from rka.components.io.log_service import LogService
from rka.components.resources import ResourceBundleManager
from rka.components.ui.capture import Capture, CaptureMode
from rka.components.ui.overlay import Severity
from rka.eq2.master import IRuntime
from rka.eq2.master.control.action import action_factory
from rka.eq2.master.game.player import PlayerStatus
from rka.log_configs import LOG_RESOURCE_MGT

logger = LogService(LOG_RESOURCE_MGT)


class PatternManager:
    def __init__(self, runtime: IRuntime):
        self.__runtime = runtime
        EventSystem.get_main_bus().subscribe(CommonEvents.RESOURCE_BUNDLE_ADDED(), self.__bundle_added)
        client_ids = self.__get_online_clients()
        self.__load_all_bundles(client_ids, False)

    def __get_online_clients(self) -> List[str]:
        return [player.get_client_id() for player in self.__runtime.player_mgr.get_players(min_status=PlayerStatus.Online)]

    # noinspection PyMethodMayBeStatic
    def __notify_resource_loaded(self, client_id: str, resource_name: str):
        logger.debug(f'{client_id} sent {resource_name}')

    # noinspection PyMethodMayBeStatic
    def __load_bundle(self, bundle_id: str, client_ids: List[str], sync: bool):
        for client_id in client_ids:
            loading_start = time.time()
            bundle = ResourceBundleManager.get_bundle(bundle_id)
            count = 0
            for resource in bundle.list_resources():
                resource.set_content(factory_cb=lambda: Capture.from_file(filename=resource.filename, mode=CaptureMode.COLOR))
                capture = resource.get_content()
                action = action_factory.new_action().save_capture(capture=capture, tag=resource.resource_id)
                logger.detail(f'{client_id} loading {resource.resource_name}')
                if sync:
                    action.call_action(client_id)
                    logger.debug(f'{client_id} loaded {resource.resource_name}')
                else:
                    action.post_async(client_id, completion_cb=lambda _: self.__notify_resource_loaded(client_id, resource.resource_name))
                count += 1
            loading_time = time.time() - loading_start
            sync_str = 'loaded' if sync else 'posted'
            self.__runtime.overlay.log_event(f'{client_id} {sync_str} {count} resources in {loading_time:.1f}s from {bundle.bundle_name()}', Severity.Low)

    def __load_all_bundles(self, client_ids: List[str], sync: bool):
        for bundle in ResourceBundleManager.iter_bundles():
            self.__load_bundle(bundle.bundle_id(), client_ids, sync)

    def __bundle_added(self, event: CommonEvents.RESOURCE_BUNDLE_ADDED):
        logger.info(f'__bundle_added: {event}')
        # send this bundle to all known clients
        client_ids = self.__get_online_clients()
        self.__load_bundle(event.bundle_id, client_ids, False)

    def send_patterns_to_client(self, client_id: str, sync: bool):
        logger.info(f'send_patterns_to_client: {client_id}')
        # send all known bundles to this client
        self.__load_all_bundles([client_id], sync)
