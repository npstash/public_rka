from __future__ import annotations

import faulthandler
import time
import traceback
from typing import Dict, Tuple, List, Callable, Union, Optional, Any

from PyQt5 import QtCore
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from rka.components.cleanup import Closeable
from rka.components.concurrency.rkascheduler import RKAScheduler
from rka.components.concurrency.workthread import RKAFuture
from rka.components.io.log_service import LogService, LogLevel
from rka.components.ui.capture import Rect
from rka.components.ui.overlay import IOverlay, Severity, OvTimerStage, OvWarning, OvPlotHandler, OvPlotHandlerResult
from rka.eq2.shared.shared_workers import shared_worker
from rka.log_configs import LOG_UI_OVERLAY

logger = LogService(LOG_UI_OVERLAY)
event_logger = LogService(LogLevel.DETAIL)

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
SPACER_SIZE = 5
MAIN_WINDOW_X = 365
MAIN_WINDOW_Y = 70
MAIN_WINDOW_WIDTH = SCREEN_WIDTH - MAIN_WINDOW_X - SPACER_SIZE
MAIN_WINDOW_HEIGHT = SCREEN_HEIGHT - MAIN_WINDOW_Y - SPACER_SIZE
OPTION_DIALOG_WIDTH = 500
MAP_DIALOG_WIDTH = 800
MAP_DIALOG_HEIGHT = 500

EVENTS_PANEL_WIDTH = 320
EVENTS_PANEL_HEIGHT = 300
STATUS_PANEL_WIDTH = 200
STATUS_PANEL_HEIGHT = 20
TIMER_PANEL_WIDTH = 200
TIMER_PANEL_HEIGHT = MAIN_WINDOW_HEIGHT - STATUS_PANEL_HEIGHT - EVENTS_PANEL_HEIGHT
PARSE_PANEL_WIDTH = 170
PARSE_PANEL_HEIGHT = 175
LEFT_PANEL_WIDTH = max(STATUS_PANEL_WIDTH, EVENTS_PANEL_WIDTH, TIMER_PANEL_WIDTH)
WARNING_PANEL_WIDTH = MAIN_WINDOW_WIDTH - LEFT_PANEL_WIDTH - PARSE_PANEL_WIDTH

faulthandler.enable(all_threads=True)


def _print_exceptions(func):
    def print_eat_exceptions_fn(*_args, **_kwargs):
        try:
            func(*_args, **_kwargs)
        except Exception as e:
            logger.error(f'error in Qt thread {e} while executing {func}')
            traceback.print_exc()

    return print_eat_exceptions_fn


font_large_bold = QFont('Arial', 144, QFont.Bold)
font_medium_bold = QFont('Arial', 10, QFont.Bold)
font_small = QFont('Arial', 8)
font_small_bold = QFont('Arial', 8, QFont.Bold)
font_small_narrow = QFont('Arial Narrow', 8)
font_small_mono = QFont('Lucida Console', 8)
color_green_transparent = QColor(0, 255, 0, 85)
color_blue_transparent = QColor(0, 0, 200, 50)
color_darkgreen_transparent = QColor(0, 127, 0, 50)
color_lightred_transparent = QColor(175, 0, 0, 75)
color_cyan_transparent = QColor(0, 255, 255, 150)
color_red_transparent = QColor(255, 0, 0, 100)
color_gray_transparent = QColor(127, 127, 127, 50)
color_black_transparent = QColor(0, 0, 0, 100)
color_green_opaque = QColor(0, 255, 0, 255)
color_white_opaque = QColor(255, 255, 255, 255)
color_white_transp = QColor(255, 255, 255, 160)

TIMERS_UPDATE_PERIOD = 0.2


class OvTimerData:
    stage_colors = [color_gray_transparent, color_gray_transparent, None, color_gray_transparent, color_black_transparent, color_black_transparent]
    severity_colors = [color_blue_transparent, color_green_transparent, color_red_transparent, color_red_transparent]

    def __init__(self, name, severity: Severity, duration: float, casting: float, reuse: float, expire: float, direction: int,
                 warnings: Optional[List[OvWarning]], replace_stage: OvTimerStage):
        assert name is not None
        assert isinstance(severity, Severity)
        self.name = name
        self.severity = severity
        self.direction = direction
        self.expires = expire is not None
        self.casting = casting if casting else 0.001
        self.duration = duration if duration else 0.001
        self.reuse = reuse if reuse else 0.001
        self.expire = expire if expire else 0.001
        self.started_at: Optional[float] = None
        self.warnings = list(warnings) if warnings else []
        self.replace_stage = replace_stage

    def start(self):
        if self.started_at and self.replace_stage > OvTimerStage.Ready:
            current_stage, _, _ = self.get_stage()
            if current_stage < self.replace_stage:
                return
        self.started_at = time.time()
        for warning in self.warnings:
            warning.reset()

    def __get_progress(self, start: float, now: float, end: float) -> float:
        if self.direction > 0:
            td = now - start
        else:
            td = end - now
        return td

    def call_warnings(self):
        if not self.started_at or not self.warnings:
            return
        casting_start_at = self.started_at
        duration_start_at = self.started_at + self.casting
        reuse_start_at = duration_start_at + self.duration
        waitexpire_start_at = reuse_start_at + self.reuse
        waitexpire_end_at = waitexpire_start_at + self.expire
        for warning in self.warnings:
            if warning.has_fired():
                continue
            if warning.stage == OvTimerStage.Casting:
                checkpoint_time = casting_start_at
            elif warning.stage == OvTimerStage.Duration:
                checkpoint_time = duration_start_at
            elif warning.stage == OvTimerStage.Reuse:
                checkpoint_time = reuse_start_at
            elif warning.stage == OvTimerStage.Expire:
                checkpoint_time = waitexpire_start_at
            elif warning.stage == OvTimerStage.Expired:
                checkpoint_time = waitexpire_end_at
            else:
                logger.warn(f'Wrong warning stage {warning.stage}')
                return
            checkpoint_time += warning.offset
            diff = time.time() - checkpoint_time
            if -TIMERS_UPDATE_PERIOD < diff < TIMERS_UPDATE_PERIOD:
                warning.fire_warning(shared_worker)

    def get_stage(self) -> (OvTimerStage, float, float):
        if not self.started_at:
            return OvTimerStage.Ready, 0.0, self.duration
        now = time.time()
        casting_end_at = self.started_at + self.casting
        running_end_at = casting_end_at + self.duration
        waitreuse_end_at = running_end_at + self.reuse
        waitexpire_end_at = waitreuse_end_at + self.expire
        if self.started_at <= now < casting_end_at:
            progress = self.__get_progress(self.started_at, now, casting_end_at)
            return OvTimerStage.Casting, progress, self.casting
        if casting_end_at <= now <= running_end_at:
            progress = self.__get_progress(casting_end_at, now, running_end_at)
            return OvTimerStage.Duration, progress, self.duration
        if running_end_at < now <= waitreuse_end_at:
            progress = self.__get_progress(running_end_at, now, waitreuse_end_at)
            return OvTimerStage.Reuse, progress, self.reuse
        if waitreuse_end_at < now < waitexpire_end_at:
            progress = self.__get_progress(waitreuse_end_at, now, waitexpire_end_at)
            return OvTimerStage.Expire, progress, self.expire
        if self.expires:
            return OvTimerStage.Expired, 0.0, 0.0
        else:
            self.started_at = None
            return OvTimerStage.Ready, 0.0, self.duration

    def get_text_and_colors(self) -> Tuple[str, Any, Any]:
        stage, value, max_value = self.get_stage()
        if max_value % 1.0 < 0.01:
            max_value_text = f'{int(max_value)}'
        else:
            max_value_text = '{:.1f}'.format(max_value)
        if stage == OvTimerStage.Ready or stage == OvTimerStage.Expire:
            text = 'READY'
            text_color = color_green_opaque
        elif stage == OvTimerStage.Expired:
            text = ''
            text_color = color_white_opaque
        else:
            value_text = '{:.1f}'.format(value)
            text = f'{value_text} / {max_value_text}'
            text_color = color_white_opaque
        if stage == OvTimerStage.Duration:
            bar_color = OvTimerData.severity_colors[self.severity]
        else:
            bar_color = OvTimerData.stage_colors[stage]
        return text, bar_color, text_color


class OvEventLogData:
    # noinspection PyUnresolvedReferences
    severity_colors = [Qt.white, Qt.cyan, Qt.green, Qt.red]
    severity_duration = [3.5, 15.0, 45.0, -1.0]

    def __init__(self, event_text: Optional[str], severity: Severity, event_id: str):
        self.event_text = event_text
        self.severity = severity
        self.event_id = event_id

    def get_color(self):
        return OvEventLogData.severity_colors[self.severity]

    def get_duration(self):
        return OvEventLogData.severity_duration[self.severity]


class OvStatusSlot:
    # noinspection PyUnresolvedReferences
    status_fg_colors = [Qt.white, Qt.yellow, Qt.black, Qt.black]
    status_bg_colors = [QColor(20, 20, 20, 100), QColor(130, 130, 130, 120), QColor(0, 255, 0, 120), QColor(255, 0, 0, 120)]
    selected_bg_colors = [QColor(70, 70, 70, 200), QColor(150, 150, 150, 255), QColor(0, 255, 0, 200), QColor(255, 0, 0, 200)]

    def __init__(self, slot_id: int, status_name: Optional[str], severity: Severity):
        self.__slot_id = slot_id
        self.__status_name = status_name
        self.__severity = severity

    def get_slot_id(self) -> int:
        return self.__slot_id

    def get_foreground_color(self, _current_selction_id: int) -> Union[int, QColor]:
        return OvStatusSlot.status_fg_colors[int(self.__severity)]

    def get_background_color(self, current_selction_id: int) -> Union[int, QColor]:
        if self.__slot_id == current_selction_id:
            return OvStatusSlot.selected_bg_colors[int(self.__severity)]
        return OvStatusSlot.status_bg_colors[int(self.__severity)]

    def get_text(self, _current_selction_id: int) -> str:
        if not self.__status_name:
            return ''
        return self.__status_name[:3]


class OptionDialog(QDialog):
    class LabelledQListWidgetItem(QListWidgetItem):
        def __init__(self, text: str, label: Any):
            QListWidgetItem.__init__(self, text)
            self.label = label

    def __init__(self, parent, title: str, options: List[Any], result_cb: Callable[[Any], None]):
        QDialog.__init__(self, parent=parent, flags=Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.__result_cb = result_cb
        self.setWindowTitle(title)
        layout = QStackedLayout()
        self.setLayout(layout)
        option_list = QListWidget()
        option_list.setFont(font_small_narrow)
        # noinspection PyUnresolvedReferences
        option_list.itemDoubleClicked.connect(self.item_double_click)
        for option in options:
            option_list.addItem(OptionDialog.LabelledQListWidgetItem(str(option), option))
        layout.addWidget(option_list)
        n = max(min(len(options), 25), 10)
        height = n * (option_list.fontInfo().pixelSize() + 4) + 12
        self.__geometry = (MAIN_WINDOW_X + MAIN_WINDOW_WIDTH - OPTION_DIALOG_WIDTH,
                           MAIN_WINDOW_Y + MAIN_WINDOW_HEIGHT - PARSE_PANEL_HEIGHT - height - 30,
                           OPTION_DIALOG_WIDTH, height)
        self.setGeometry(*self.__geometry)

    def item_double_click(self, item: OptionDialog.LabelledQListWidgetItem):
        selected_option_test = item.text()
        selected_option_label = item.label
        logger.debug(f'OptionDialog selected: {selected_option_test}')
        shared_worker.push_task(lambda: self.__result_cb(selected_option_label))
        self.close()

    def moveEvent(self, event: QMoveEvent):
        self.setGeometry(*self.__geometry)


class PlotDialog(QDialog):
    def __init__(self, parent, title: str, handler: OvPlotHandler):
        QDialog.__init__(self, parent=parent, flags=Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.__handler = handler
        self.setWindowTitle(title)
        self.setGeometry(MAIN_WINDOW_X + MAIN_WINDOW_WIDTH // 2 - MAP_DIALOG_WIDTH // 2,
                         MAIN_WINDOW_Y + MAIN_WINDOW_HEIGHT // 2 - MAP_DIALOG_HEIGHT // 2,
                         MAP_DIALOG_WIDTH, MAP_DIALOG_HEIGHT)
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        self.__figure = Figure(figsize=(1, 1))
        self.__canvas = FigureCanvasQTAgg(self.__figure)
        self.__axes = self.__canvas.figure.subplots()
        self.__layout = QStackedLayout()
        self.setLayout(self.__layout)
        self.__layout.addWidget(self.__canvas)
        self.plot(False)
        self.__connect_ids = list()
        self.__connect_ids.append(self.__figure.canvas.mpl_connect('button_press_event', self.on_mouse_down))
        self.__connect_ids.append(self.__figure.canvas.mpl_connect('button_release_event', self.on_mouse_up))
        self.__connect_ids.append(self.__figure.canvas.mpl_connect('motion_notify_event', self.on_mouse_move))

    def closeEvent(self, event):
        for cid in self.__connect_ids:
            self.__figure.canvas.mpl_disconnect(cid)
        self.__handler.on_close()

    def __do_result(self, result: OvPlotHandlerResult):
        if result == OvPlotHandlerResult.Close:
            self.close()
        elif result == OvPlotHandlerResult.Refresh:
            self.plot(True)

    @_print_exceptions
    def plot(self, repaint: bool):
        if repaint:
            self.__axes.cla()
        self.__handler.plot(self.__axes)
        if repaint:
            self.__figure.canvas.draw_idle()

    @_print_exceptions
    def on_mouse_down(self, event):
        if not event.xdata or not event.ydata:
            return
        loc_x = float(event.xdata)
        loc_y = float(event.ydata)
        if event.dblclick:
            logger.info(f'on_mouse_double_click: x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}')
            result = self.__handler.on_mouse_double_click(loc_x, loc_y)
        else:
            logger.info(f'on_mouse_button_press: x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}, button={event.button}')
            result = self.__handler.on_mouse_button_press(loc_x, loc_y, event.button)
        self.__do_result(result)

    @_print_exceptions
    def on_mouse_up(self, event):
        if not event.xdata or not event.ydata:
            return
        loc_x = float(event.xdata)
        loc_y = float(event.ydata)
        logger.info(f'on_mouse_button_release: x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}')
        result = self.__handler.on_mouse_button_release(loc_x, loc_y)
        self.__do_result(result)

    @_print_exceptions
    def on_mouse_move(self, event):
        if not event.xdata or not event.ydata:
            return
        loc_x = float(event.xdata)
        loc_y = float(event.ydata)
        logger.info(f'on_mouse_move: x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}')
        result = self.__handler.on_mouse_move(loc_x, loc_y)
        self.__do_result(result)


class OverlayWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self, None, flags=Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # noinspection PyTypeChecker,PyUnresolvedReferences
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(QRect(MAIN_WINDOW_X, MAIN_WINDOW_Y, MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT))
        # noinspection PyArgumentList
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setMaximumSize(self.width(), self.height())

    def paintEvent(self, event=None):
        painter = QPainter(self)
        painter.setOpacity(0.0)
        painter.setBrush(Qt.white)
        painter.setPen(QPen(Qt.white))
        painter.drawRect(self.rect())


class Qt5Overlay(IOverlay, Closeable, QObject):
    __application = None

    __sig_show_dialog = QtCore.pyqtSignal(str, list, object)
    __sig_get_text = QtCore.pyqtSignal(str, object)
    __sig_get_confirm = QtCore.pyqtSignal(str, object)
    __sig_show_warning = QtCore.pyqtSignal(str, float, object)
    __sig_hide_warning = QtCore.pyqtSignal()
    __sig_add_log = QtCore.pyqtSignal(OvEventLogData)
    __sig_remove_log = QtCore.pyqtSignal(OvEventLogData)
    __sig_set_status = QtCore.pyqtSignal(OvStatusSlot)
    __sig_start_timer = QtCore.pyqtSignal(OvTimerData)
    __sig_update_timers = QtCore.pyqtSignal()
    __sig_del_timer = QtCore.pyqtSignal(str)
    __sig_update_parser = QtCore.pyqtSignal(str)
    __sig_hide_parser = QtCore.pyqtSignal()
    __sig_display_plot = QtCore.pyqtSignal(str, OvPlotHandler)
    __sig_set_tint = QtCore.pyqtSignal(int, int, int, int, float)
    __sig_show = QtCore.pyqtSignal()
    __sig_hide = QtCore.pyqtSignal()
    __sig_queue_event = QtCore.pyqtSignal(object)
    __sig_close = QtCore.pyqtSignal()

    def __init__(self, selection_slots: int):
        Closeable.__init__(self, explicit_close=False)
        QObject.__init__(self)
        self.__client_status: Dict[int, Tuple[OvStatusSlot, QLabel]] = dict()
        self.__timers: Dict[str, Tuple[OvTimerData, QProgressBar]] = dict()
        self.__events: List[OvEventLogData] = list()
        self.__running = False
        self.__hide_warning_future: Optional[RKAFuture] = None
        self.__clear_tint_future: Optional[RKAFuture] = None
        self.__selection_id = 0
        self.__selection_slots = selection_slots

        self.__sig_show_dialog.connect(self.__show_dialog)
        self.__sig_get_text.connect(self.__get_text)
        self.__sig_get_confirm.connect(self.__get_confirm)
        self.__sig_show_warning.connect(self.__show_warning)
        self.__sig_hide_warning.connect(self.__hide_warning)
        self.__sig_add_log.connect(self.__log_event)
        self.__sig_remove_log.connect(self.__remove_event)
        self.__sig_set_status.connect(self.__set_status)
        self.__sig_start_timer.connect(self.__start_timer)
        self.__sig_update_timers.connect(self.__update_timers)
        self.__sig_del_timer.connect(self.__del_timer)
        self.__sig_update_parser.connect(self.__update_parser)
        self.__sig_hide_parser.connect(self.__hide_parser)
        self.__sig_display_plot.connect(self.__display_plot)
        self.__sig_set_tint.connect(self.__set_screen_tint)
        self.__sig_show.connect(self.__show)
        self.__sig_hide.connect(self.__hide)
        self.__sig_queue_event.connect(self.__queue_event)
        self.__sig_close.connect(self.__close)

        self.__scheduler = RKAScheduler('Event log expiration scheduler')
        self.__parse_list_hide_future: Optional[RKAFuture] = None

        self.__setup_ui()

    @_print_exceptions
    def __setup_ui(self):
        if Qt5Overlay.__application is None:
            Qt5Overlay.__application = QApplication([])

        self.__window = OverlayWindow()
        self.__hide_count = 1
        self.__timer_subscribed = False
        self.window_layout = QHBoxLayout()
        central_widget = self.__window.centralWidget()
        central_widget.setLayout(self.window_layout)
        palette = QPalette()
        palette.setColor(QPalette.Foreground, Qt.transparent)
        palette.setColor(QPalette.Background, Qt.transparent)
        central_widget.setPalette(palette)
        central_widget.setAutoFillBackground(True)

        self.leftpane_layout = QVBoxLayout()
        self.leftpane_layout.setContentsMargins(1, 1, 1, 1)
        self.leftpane_layout.setSpacing(2)
        self.center_layout = QGridLayout()
        self.rightpane_layout = QVBoxLayout()
        self.window_layout.addLayout(self.leftpane_layout)
        self.window_layout.addLayout(self.center_layout)
        self.window_layout.addLayout(self.rightpane_layout)

        # left pane - status, events, timers
        # noinspection PyArgumentList
        self.leftpane_box = QWidget()
        self.leftpane_box.setMinimumWidth(LEFT_PANEL_WIDTH)
        self.leftpane_box.setMaximumWidth(LEFT_PANEL_WIDTH)
        # noinspection PyArgumentList
        self.status_box = QWidget()
        self.status_box.setMinimumWidth(STATUS_PANEL_WIDTH)
        self.status_box.setMaximumWidth(STATUS_PANEL_WIDTH)
        self.status_box.setMinimumHeight(STATUS_PANEL_HEIGHT)
        self.status_box.setMaximumHeight(STATUS_PANEL_HEIGHT)
        # noinspection PyArgumentList
        self.events_box = QWidget()
        self.events_box.setMinimumWidth(EVENTS_PANEL_WIDTH)
        self.events_box.setMaximumWidth(EVENTS_PANEL_WIDTH)
        self.events_box.setMinimumHeight(EVENTS_PANEL_HEIGHT)
        self.events_box.setMaximumHeight(EVENTS_PANEL_HEIGHT)
        # noinspection PyArgumentList
        self.timers_box = QWidget()
        self.timers_box.setMinimumWidth(TIMER_PANEL_WIDTH)
        self.timers_box.setMaximumWidth(TIMER_PANEL_WIDTH)
        self.timers_box.setMaximumHeight(TIMER_PANEL_HEIGHT)
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(1, 1, 1, 1)
        self.status_layout.setSpacing(2)
        self.timers_layout = QFormLayout()
        self.timers_layout.setContentsMargins(1, 1, 1, 1)
        self.timers_layout.setSpacing(3)
        self.events_layout = QVBoxLayout()
        self.events_layout.setContentsMargins(1, 1, 1, 1)
        self.events_layout.setSpacing(2)
        self.status_box.setLayout(self.status_layout)
        self.timers_box.setLayout(self.timers_layout)
        self.events_box.setLayout(self.events_layout)
        # noinspection PyArgumentList
        self.leftpane_layout.addWidget(self.status_box)
        # noinspection PyArgumentList
        self.leftpane_layout.addWidget(self.events_box)
        # noinspection PyArgumentList
        self.leftpane_layout.addWidget(self.timers_box)

        # center pane - warnings
        self.warning_label = QLabel('')
        self.warning_label.setMinimumWidth(WARNING_PANEL_WIDTH)
        self.warning_label.setMaximumWidth(WARNING_PANEL_WIDTH)
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setFont(font_large_bold)
        palette = QPalette()
        palette.setColor(QPalette.Foreground, Qt.red)
        palette.setColor(QPalette.Background, Qt.transparent)
        self.warning_label.setPalette(palette)
        self.center_layout.addWidget(self.warning_label)

        # right pane - dps parse
        self.parse_list = QListWidget()
        self.parse_list.setMinimumWidth(PARSE_PANEL_WIDTH)
        self.parse_list.setMaximumWidth(PARSE_PANEL_WIDTH)
        self.parse_list.setMinimumHeight(PARSE_PANEL_HEIGHT)
        self.parse_list.setMaximumHeight(PARSE_PANEL_HEIGHT)
        self.parse_list.setAutoFillBackground(True)
        self.parse_list.setFont(font_small_mono)
        self.parse_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.parse_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.parse_list.setFrameStyle(QFrame.NoFrame)
        self.parse_list_visible_palette = QPalette()
        self.parse_list_visible_palette.setColor(QPalette.Text, Qt.yellow)
        self.parse_list_visible_palette.setColor(QPalette.Base, Qt.transparent)
        self.parse_list_visible_palette.setColor(QPalette.Background, Qt.black)
        self.parse_list_invisible_palette = QPalette()
        self.parse_list_invisible_palette.setColor(QPalette.Text, Qt.transparent)
        self.parse_list_invisible_palette.setColor(QPalette.Base, Qt.transparent)
        self.parse_list_invisible_palette.setColor(QPalette.Background, Qt.transparent)
        self.parse_list.setPalette(self.parse_list_invisible_palette)
        self.rightpane_layout.addWidget(self.parse_list, alignment=Qt.AlignBottom)

        class LabelClickCb(object):
            def __init__(self, overlay: Qt5Overlay, slot_id_: int):
                self.__slot_id = slot_id_
                self.__overlay = overlay

            def __call__(self, *args, **kwargs):
                self.__overlay.set_selection_id(self.__slot_id)

        # client status boxes
        for slot_id in range(self.__selection_slots):
            label = QLabel()
            label.setAutoFillBackground(True)
            label.setFont(font_small_narrow)
            label.mousePressEvent = LabelClickCb(self, slot_id)
            # noinspection PyArgumentList
            self.status_layout.addWidget(label)
            status_data = OvStatusSlot(slot_id=slot_id, status_name=None, severity=Severity.Low)
            self.__client_status[slot_id] = (status_data, label)
            self.__set_status(status_data)

        self.event_list = QListWidget()
        self.event_list.setAutoFillBackground(True)
        self.event_list.setFont(font_small_narrow)
        self.event_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.event_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.event_list.setFrameStyle(QFrame.NoFrame)
        palette = QPalette()
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Base, Qt.transparent)
        palette.setColor(QPalette.Background, Qt.transparent)
        self.event_list.setPalette(palette)
        # noinspection PyArgumentList
        self.events_layout.addWidget(self.event_list)

    @_print_exceptions
    def __set_status(self, status_data: OvStatusSlot):
        logger.debug(f'__set_status: {status_data.get_text(self.__selection_id)}')
        selection_id = status_data.get_slot_id()
        if selection_id not in self.__client_status.keys():
            logger.warn(f'__set_status: cannot show status {status_data.get_text(self.__selection_id)}')
            return
        _, label = self.__client_status[selection_id]
        self.__client_status[status_data.get_slot_id()] = (status_data, label)
        label.setText(status_data.get_text(self.__selection_id))
        label.setAlignment(Qt.AlignCenter)
        palette = QPalette()
        palette.setColor(QPalette.Foreground, status_data.get_foreground_color(self.__selection_id))
        palette.setColor(QPalette.Background, status_data.get_background_color(self.__selection_id))
        label.setPalette(palette)

    @_print_exceptions
    def __start_timer(self, timer: OvTimerData):
        logger.debug(f'__start_timer: {timer.name}')
        if timer.name in self.__timers.keys():
            # update the timer
            old_timer, timer_bar = self.__timers[timer.name]
            assert isinstance(old_timer, OvTimerData)
            old_stage, _, _ = old_timer.get_stage()
            logger.debug(f'__start_timer: old_stage: {old_stage}, replace_stage: {timer.replace_stage}')
            if old_stage >= timer.replace_stage:
                self.__timers[timer.name] = (timer, timer_bar)
            timer.start()
            return
        timer_label = QLabel(timer.name)
        palette = QPalette()
        palette.setColor(QPalette.Foreground, Qt.white)
        palette.setColor(QPalette.Background, QColor(255, 255, 255, 10))
        timer_label.setPalette(palette)
        timer_label.setFont(font_medium_bold)
        timer_label.setAutoFillBackground(True)
        timer_label.setMaximumWidth(80)
        timer_bar = QProgressBar()
        timer_bar.setFont(font_medium_bold)
        timer_bar.setMinimumHeight(20)
        timer_bar.setMaximumHeight(50)
        self.timers_layout.addRow(timer_label, timer_bar)
        first_timer = len(self.__timers) == 0
        self.__timers[timer.name] = (timer, timer_bar)
        self.__update_timer(timer.name)
        if first_timer:
            self.__scheduler.schedule(lambda: self.__sig_update_timers.emit(), delay=TIMERS_UPDATE_PERIOD)

    @_print_exceptions
    def __update_timer(self, timer_name: str):
        timer, timer_bar = self.__timers[timer_name]
        stage, value, max_value = timer.get_stage()
        if logger.get_level() <= LogLevel.DEBUG:
            logger.debug(f'__update_timer_bars: {timer_name}, stage: {stage}, value: {value}, max_value: {max_value}')
        bar_value = int(value * 10)
        bar_max_value = int(max_value * 10)
        if stage >= OvTimerStage.Expired:
            self.__del_timer(timer_name)
            return
        text, bar_color, text_color = timer.get_text_and_colors()
        style = f"""
        QProgressBar{{
            border: 1px solid transparent;
            text-align: center;
            color: rgba{text_color.getRgb()};
            background-color: rgba(255, 255, 255, 0);
        }}
        QProgressBar::chunk{{
            background-color: rgba{bar_color.getRgb()};
        }}"""
        timer_bar.setFormat(text)
        timer_bar.setStyleSheet(style)
        timer_bar.setMaximum(bar_max_value)
        timer_bar.setValue(bar_value)
        timer.call_warnings()

    @_print_exceptions
    def __update_timers(self):
        timer_names = list(self.__timers.keys())
        for timer_name in timer_names:
            self.__update_timer(timer_name)
        if self.__timers:
            self.__scheduler.schedule(lambda: self.__sig_update_timers.emit(), delay=TIMERS_UPDATE_PERIOD)

    @_print_exceptions
    def __del_timer(self, timer_name: str):
        if timer_name not in self.__timers:
            logger.debug(f'__del_timer: no such timer {timer_name}')
            return
        logger.debug(f'__del_timer: {timer_name}')
        timer, timer_bar = self.__timers[timer_name]
        del self.__timers[timer_name]
        self.timers_layout.removeRow(timer_bar)

    @_print_exceptions
    def __remove_event(self, event: OvEventLogData):
        logger.debug(f'__remove_event: {event.event_text}')
        try:
            event_idx = self.__events.index(event)
            self.__events.remove(event)
            self.event_list.takeItem(event_idx)
        except ValueError:
            logger.info(f'__remove_event: not found {event.event_text}')

    @_print_exceptions
    def __log_event(self, event_data: OvEventLogData):
        if event_data.event_id is not None:
            for event in self.__events:
                if event.event_id == event_data.event_id:
                    self.__remove_event(event)
                    break
        if event_data.event_text:
            item = QListWidgetItem(event_data.event_text)
            item.setForeground(event_data.get_color())
            item.setData(Qt.UserRole, item)
            self.event_list.addItem(item)
            self.event_list.scrollToBottom()
            if event_data.get_duration() > 0:
                self.__scheduler.schedule(lambda: self.__sig_remove_log.emit(event_data), event_data.get_duration())
            self.__events.append(event_data)

    @_print_exceptions
    def __update_parser(self, parsestr: str):
        self.parse_list.clear()
        for line in parsestr.split('\n'):
            self.parse_list.addItem(line)
        if self.__parse_list_hide_future:
            self.parse_list.setPalette(self.parse_list_visible_palette)
            self.__parse_list_hide_future.cancel_future()
            self.__parse_list_hide_future = None
        self.__parse_list_hide_future = self.__scheduler.schedule(lambda: self.__sig_hide_parser.emit(), delay=60.0)

    @_print_exceptions
    def __hide_parser(self):
        self.__parse_list_hide_future = None
        self.parse_list.setPalette(self.parse_list_invisible_palette)

    @_print_exceptions
    def __display_plot(self, title: str, handler: OvPlotHandler):
        logger.debug(f'__display_plot: create window {title}')
        dialog = PlotDialog(self.__window, title, handler)
        dialog.show()

    @_print_exceptions
    def __show_warning(self, warning_text: str, duration: float, conditional_text: str):
        current_warning_text = self.warning_label.text()
        logger.debug(f'__show_warning: {warning_text} for {duration} if current warning is {conditional_text}')
        if conditional_text is not None:
            if current_warning_text != conditional_text:
                return
        current_warning_future = self.__hide_warning_future
        if current_warning_future is not None:
            current_warning_future.cancel_future()
        self.__hide_warning_future = self.__scheduler.schedule(lambda: self.__sig_hide_warning.emit(), duration)
        logger.detail(f'set warning text {warning_text}')
        self.warning_label.setText(warning_text)

    def __set_screen_tint(self, r: int, g: int, b: int, a: int, duration: float):
        logger.debug(f'__set_screen_tint: {(r, g, b, a)} {duration}')
        palette = QPalette()
        palette.setColor(QPalette.Background, QColor(r, g, b, a))
        self.__window.centralWidget().setPalette(palette)
        clear_tint_future = self.__clear_tint_future
        if clear_tint_future:
            clear_tint_future.cancel_future()
        self.__clear_tint_future = self.__scheduler.schedule(lambda: self.__reset_screen_tint(), delay=duration)

    def __reset_screen_tint(self):
        palette = QPalette()
        palette.setColor(QPalette.Background, Qt.transparent)
        self.__window.centralWidget().setPalette(palette)
        self.__clear_tint_future = None

    @_print_exceptions
    def __hide_warning(self):
        logger.debug(f'__hide_warning')
        self.__hide_warning_future = None
        self.warning_label.setText('')

    @_print_exceptions
    def __show_dialog(self, title: str, options: List[Any], result_cb: Callable[[Any], None]):
        logger.debug(f'__show_dialog: create dialog {title}, options {options}')
        dialog = OptionDialog(self.__window, title, options, result_cb)
        dialog.show()

    @_print_exceptions
    def __get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        logger.debug(f'__get_text: create dialog {title}')
        # noinspection PyCallByClass, PyArgumentList
        text, ok_pressed = QInputDialog.getText(self.__window, title, 'Input text:')
        if not ok_pressed:
            text = None
        shared_worker.push_task(lambda: result_cb(text))

    @_print_exceptions
    def __get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        logger.debug(f'__get_confirm: create dialog {title}')
        # noinspection PyCallByClass, PyArgumentList
        choice = QMessageBox.question(self.__window, 'Confirm?', title)
        shared_worker.push_task(lambda: result_cb(choice == QMessageBox.Yes))

    @_print_exceptions
    def __runloop(self):
        self.__running = True
        Qt5Overlay.__application.exec()
        self.__running = False

    def __cb_update_timers(self):
        self.__sig_update_timers.emit()

    def __cb_update_parser(self):
        self.__sig_update_parser.emit()

    @_print_exceptions
    def __show(self):
        logger.debug(f'__show: {self.__hide_count}')
        self.__hide_count -= 1
        if self.__hide_count == 0:
            self.__window.show()

    @_print_exceptions
    def __hide(self):
        logger.debug(f'__hide: {self.__hide_count}')
        self.__hide_count += 1
        if self.__hide_count == 1:
            self.__window.hide()

    @_print_exceptions
    def __queue_event(self, callback: Callable):
        logger.debug(f'__queue_event: {callback}')
        callback()

    @_print_exceptions
    def __close(self):
        logger.debug(f'__close')
        self.__window.close()
        self.__application.quit()

    def set_status(self, selection_id: int, status_name: str, severity: Severity):
        assert 0 <= selection_id < self.__selection_slots
        assert isinstance(status_name, str)
        assert isinstance(severity, Severity)
        if not self.__running:
            logger.error('set_status: QT mainloop not running')
            return
        logger.info(f'set_status: {selection_id} {status_name} {severity}')
        status_data = OvStatusSlot(selection_id, status_name, severity)
        self.__sig_set_status.emit(status_data)

    def get_max_selection_id(self) -> int:
        return self.__selection_slots

    def get_selection_id(self) -> int:
        return self.__selection_id

    def set_selection_id(self, selection_id: int):
        assert isinstance(selection_id, int)
        if not self.__running:
            logger.error('set_selection_id: QT mainloop not running')
            return
        old_selection_id = self.__selection_id
        self.__selection_id = selection_id
        if selection_id not in self.__client_status.keys():
            logger.warn(f'set_selection_id: unknown id {selection_id}')
            return
        status_data, _ = self.__client_status[old_selection_id]
        self.__sig_set_status.emit(status_data)
        status_data, _ = self.__client_status[selection_id]
        self.__sig_set_status.emit(status_data)

    def start_timer(self, name: str, duration: float, casting: Optional[float] = None, reuse: Optional[float] = None,
                    expire: Optional[float] = None, direction=-1, severity=Severity.Low, warnings: Optional[List[OvWarning]] = None,
                    replace_stage=OvTimerStage.Ready):
        assert isinstance(name, str)
        assert isinstance(duration, float)
        assert isinstance(direction, int)
        assert isinstance(severity, Severity)
        assert isinstance(replace_stage, OvTimerStage)
        if not self.__running:
            logger.error('start_timer: QT mainloop not running')
            return
        logger.info(f'start_timer: {name} {duration} {casting} {reuse} {expire} {direction} {severity} {warnings} {replace_stage}')
        timer = OvTimerData(name=name, severity=severity, casting=casting, duration=duration, reuse=reuse, expire=expire, direction=direction,
                            warnings=warnings, replace_stage=replace_stage)
        timer.start()
        self.__sig_start_timer.emit(timer)

    def del_timer(self, name: str):
        assert isinstance(name, str)
        if not self.__running:
            logger.error('del_timer: QT mainloop not running')
            return
        logger.info(f'del_timer: {name}')
        self.__sig_del_timer.emit(name)

    def log_event(self, event_text: Optional[str], severity: Severity = Severity.Low, event_id: Optional[str] = None):
        assert not event_text or isinstance(event_text, str)
        assert isinstance(severity, Severity)
        # displaying logs in overlay leads to recursion - i.e. no logs here
        logger.info(f'log_event[{severity.name}]: {event_text}')
        event_logger.debug(f'log_event[{severity.name}]: {event_text}')
        if not self.__running:
            return
        event_log = OvEventLogData(event_text=event_text, severity=severity, event_id=event_id)
        self.__sig_add_log.emit(event_log)

    def display_warning(self, warning_text: str, duration: Optional[float] = None, conditional_text: Optional[str] = None):
        assert isinstance(warning_text, str)
        if not self.__running:
            logger.error('display_warning: QT mainloop not running')
            return
        logger.info(f'display_warning: {warning_text} for {duration} if current warning is {conditional_text}')
        if duration is None:
            duration = 4.0
        self.__sig_show_warning.emit(warning_text, duration, conditional_text)

    def display_dialog(self, title: str, options: List[Any], result_cb: Callable[[Any], None]):
        assert isinstance(title, str)
        assert isinstance(options, List)
        if not self.__running:
            logger.error('display_dialog: QT mainloop not running')
            return
        logger.info(f'display_dialog: {title}, options {options} ')
        self.__scheduler.schedule(lambda: self.__sig_show_dialog.emit(title, options, result_cb), delay=0.5)

    def display_plot(self, title: str, handler: OvPlotHandler):
        logger.info(f'display_plot')
        self.__sig_display_plot.emit(title, handler)

    def get_text(self, title: str, result_cb: Callable[[Optional[str]], None]):
        assert isinstance(title, str)
        assert isinstance(result_cb, Callable)
        self.__scheduler.schedule(lambda: self.__sig_get_text.emit(title, result_cb), delay=0.5)

    def get_confirm(self, title: str, result_cb: Callable[[bool], None]):
        assert isinstance(title, str)
        assert isinstance(result_cb, Callable)
        self.__scheduler.schedule(lambda: self.__sig_get_confirm.emit(title, result_cb), delay=0.5)

    def update_parse_window(self, parse: str):
        logger.info(f'update_parse_window')
        self.__sig_update_parser.emit(parse)

    def set_screen_tint(self, r: int, g: int, b: int, a: int, duration: float):
        logger.info(f'set_screen_tint: {(r, g, b, a)} {duration}')
        self.__sig_set_tint.emit(r, g, b, a, duration)

    def runloop(self):
        logger.info(f'runloop')
        self.__runloop()

    def queue_event(self, callback: Callable):
        logger.info(f'queue_event: {callback}')
        self.__sig_queue_event.emit(callback)

    def show(self):
        if not self.__running:
            logger.error('show: QT mainloop not running')
            return
        logger.info(f'show')
        self.__sig_show.emit()

    def hide(self):
        if not self.__running:
            logger.error('hide: QT mainloop not running')
            return
        logger.info(f'hide')
        self.__sig_hide.emit()

    def close(self):
        logger.info(f'close')
        if self.__running:
            self.__scheduler.close()
        self.__sig_close.emit()
        Closeable.close(self)

    def get_window_rect(self) -> Rect:
        return Rect(x1=MAIN_WINDOW_X, y1=MAIN_WINDOW_Y, w=MAIN_WINDOW_WIDTH, h=MAIN_WINDOW_HEIGHT)

    def is_capture_safe(self, capture_rect: Rect) -> bool:
        dicrty_rect = Rect(x1=MAIN_WINDOW_X, y1=MAIN_WINDOW_Y, w=STATUS_PANEL_WIDTH, h=STATUS_PANEL_HEIGHT)
        if dicrty_rect.overlaps(capture_rect):
            return False
        dicrty_rect = Rect(x1=MAIN_WINDOW_X, y1=MAIN_WINDOW_Y + STATUS_PANEL_HEIGHT, w=EVENTS_PANEL_WIDTH, h=EVENTS_PANEL_HEIGHT)
        if dicrty_rect.overlaps(capture_rect):
            return False
        dicrty_rect = Rect(x1=MAIN_WINDOW_X, y1=MAIN_WINDOW_Y + STATUS_PANEL_HEIGHT + EVENTS_PANEL_HEIGHT,
                           w=TIMER_PANEL_WIDTH, h=TIMER_PANEL_HEIGHT)
        if dicrty_rect.overlaps(capture_rect):
            return False
        return True
