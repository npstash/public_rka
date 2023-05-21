from threading import Barrier
from typing import Optional, List, Union, Callable

from rka.components.concurrency.rkathread import RKAThread
from rka.components.io.injector import IInjector
from rka.components.network.discovery import INodeDiscoveryClient, INodeDiscoveryServer, INetworkDiscovery
from rka.components.network.rpc import IServiceHost, IConnection
from rka.components.ui.automation import IAutomation
from rka.components.ui.capture import ICaptureService
from rka.components.ui.cursor_capture import ICursorCapture
from rka.components.ui.hotkeys import IHotkeyService, IHotkeyFilter, RKAHotkeyFilter, HotkeyEventPumpType
from rka.components.ui.iocrservice import IOCRService
from rka.components.ui.notification import INotificationService
from rka.components.ui.overlay import IOverlay
from rka.components.ui.tts import ITTS


class InjectorFactory:
    @staticmethod
    def create_injector(path: str, prefix: Optional[str] = None, postifx: Optional[str] = None, **kargs) -> IInjector:
        from rka.components.impl.alpha.injector_namedpipes import NamedPipeInjector
        return NamedPipeInjector(path, prefix, postifx, **kargs)


class NotificationFactory:
    @staticmethod
    def create_service(credentials_mgr) -> INotificationService:
        from rka.components.impl.alpha.discord_bot import DiscordNotificationService
        return DiscordNotificationService(credentials_mgr)


class TTSFactory:
    @staticmethod
    def create_tts() -> ITTS:
        from rka.components.impl.alpha.tts_ttsx3 import TTSX3Service
        return TTSX3Service()

    @staticmethod
    def create_group_tts(*args) -> ITTS:
        from rka.components.impl.alpha.discord_gtts_tts import DiscordTTSService
        return DiscordTTSService(*args)


class HotkeyServiceFactory:
    @staticmethod
    def create_service(service_type=HotkeyEventPumpType.SERVICE_TYPE_CURRENT_THREAD_PUMP) -> IHotkeyService:
        from rka.components.impl.beta.hotkey_pywinhook import PyWinHookHotkeys
        return PyWinHookHotkeys(service_type)

    @staticmethod
    def create_filter(keys: Union[List[str], str] = None, callback: Callable[[Optional[str], Optional[IHotkeyService]], None] = None) -> IHotkeyFilter:
        return RKAHotkeyFilter(keys, callback)


class AutomationFactory:
    @staticmethod
    def create_automation() -> IAutomation:
        from rka.components.impl.beta.automation_autoit_win32gui import AutoitWin32GuiAutomation
        return AutoitWin32GuiAutomation()


class DiscoveryFactory:
    @staticmethod
    def create_network_discovery(service_id: str, filtered_nifaddrs: Optional[List[str]] = None) -> INetworkDiscovery:
        from rka.components.impl.alpha.discovery_netifaces import NetifacesNetworkDiscovery
        return NetifacesNetworkDiscovery(service_id, filtered_nifaddrs)

    @staticmethod
    def create_node_discovery_server(server_id: str, bcast_port: int) -> INodeDiscoveryServer:
        from rka.components.impl.alpha.discovery_udp_bcast import UDPBCNodeDiscoveryServer
        return UDPBCNodeDiscoveryServer(server_id, bcast_port)

    @staticmethod
    def create_node_discovery_client(client_id: str, discovery_port: int) -> INodeDiscoveryClient:
        from rka.components.impl.alpha.discovery_udp_bcast import UDPBCNodeDiscoveryClient
        return UDPBCNodeDiscoveryClient(client_id, discovery_port)


class ServiceHostFactory:
    @staticmethod
    def create_service_host(nifaddr: str, port: int, service) -> IServiceHost:
        from rka.components.impl.alpha.rpc_xmlrpc import XMLRPCHost
        return XMLRPCHost(nifaddr, port, service)


class ConnectionFactory:
    @staticmethod
    def create_connection(local_address: str, remote_address: str, port: int) -> IConnection:
        from rka.components.impl.alpha.rpc_xmlrpc import XMLRPCConnection
        return XMLRPCConnection(local_address, remote_address, port)


class OverlayFactory:
    @staticmethod
    def create_overlay(selection_slots: int) -> IOverlay:
        from rka.components.impl.alpha.overlay_qt5 import Qt5Overlay
        return Qt5Overlay(selection_slots)

    @staticmethod
    def create_overlay_on_new_thread(selection_slots: int) -> IOverlay:
        overlay: Optional[IOverlay] = None
        barrier = Barrier(2)

        def notify_stared():
            barrier.wait()

        def start_overlay():
            nonlocal overlay
            overlay = OverlayFactory.create_overlay(selection_slots)
            barrier.wait()
            overlay.runloop()

        overlay_thread = RKAThread('QT overlay thread', target=start_overlay)
        overlay_thread.start()
        barrier.wait()
        overlay.queue_event(notify_stared)
        barrier.wait()
        return overlay


class CaptureFactory:
    @staticmethod
    def create_capture_service() -> ICaptureService:
        from rka.components.impl.beta.capture_win32_opencv import Win32OpenCVCaptureService
        return Win32OpenCVCaptureService()


class OCRServiceFactory:
    @staticmethod
    def create_ocr_service() -> IOCRService:
        from rka.components.impl.alpha.ocr_tesseract import TesseractOCR
        return TesseractOCR()


class CursorCaptureFactory:
    @staticmethod
    def create_cursor_capture() -> ICursorCapture:
        from rka.components.impl.alpha.win32_cursor_capture import Win32CursorCapture
        return Win32CursorCapture()
