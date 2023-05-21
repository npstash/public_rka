import time
from time import sleep
from typing import Dict, Tuple, Optional, List

import cv2.cv2 as cv2
import numpy
import pywintypes
import win32con
import win32gui
from PIL import ImageGrab
from mss import mss

from rka.components.cleanup import Closeable
from rka.components.io.log_service import LogService
from rka.components.ui.automation import IAutomation, MouseCoordMode
from rka.components.ui.capture import ICaptureService, CaptureArea, Point, Rect, MatchPattern, Capture, MatchMethod, Offset, Shape, CaptureMode, CaptureWindowFlags
from rka.log_configs import LOG_CAPTURING

logger = LogService(LOG_CAPTURING)


def img_debug(title, image):
    print(f'------------ IMG_DEBUG: {title} ------------')
    cv2.imshow(title, image)
    cv2.resizeWindow(title, 200, 100)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


class FindPatternResult:
    def __init__(self, tag: str, value: float, scale: float, found_rect: Rect):
        self.tag = tag
        self.value = value
        self.scale = scale
        self.found_rect = found_rect

    def __str__(self):
        return f'FindPatternResult[{self.tag}, v={self.value}, s={self.scale}, {self.found_rect}]'


class Win32OpenCVCaptureService(ICaptureService, Closeable):
    def __init__(self):
        Closeable.__init__(self, explicit_close=False)
        self.__patterns_by_mode: Dict[CaptureMode, Dict[str, numpy.ndarray]] = dict()
        self.__default_threshold = 0.85
        self.__default_bw_binary_threshold = 180
        self.__restore_window = True
        self.__stamp = time.time()
        self.__mss = mss()

    def close_capture_service(self):
        self.close()

    def close(self):
        self.__mss.close()
        Closeable.close(self)

    def __time_mark(self, sid: str):
        now = time.time()
        logger.detail(f'time diff [{sid}]: {now - self.__stamp}')
        self.__stamp = now

    @staticmethod
    def __window_enumeration_handler(hwnd, top_windows):
        top_windows.append(hwnd)

    def __activate_window(self, wintitle: str, activate: bool) -> Optional[int]:
        assert wintitle is not None
        wintitle = wintitle.lower()
        logger.debug(f'__activate_window: {wintitle}')
        active_hwnd = win32gui.GetForegroundWindow()
        active_title = win32gui.GetWindowText(active_hwnd)
        if active_title and wintitle in active_title.lower():
            return active_hwnd
        if not activate:
            logger.detail(f'Ignore window activation for {wintitle}. active_title={active_title}')
            return None
        top_windows = list()
        win32gui.EnumWindows(Win32OpenCVCaptureService.__window_enumeration_handler, top_windows)
        for hwnd in top_windows:
            iter_title = win32gui.GetWindowText(hwnd)
            if iter_title and wintitle in iter_title.lower():
                p = win32gui.GetWindowPlacement(hwnd)
                if self.__restore_window and p[1] == win32con.SW_SHOWMINIMIZED:
                    win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
                # noinspection PyUnresolvedReferences
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except pywintypes.error as e:
                    logger.warn(f'__activate_window: error setting foreground window {e}')
                    return None
                for attempt in range(40):
                    sleep(0.025)
                    active_hwnd = win32gui.GetForegroundWindow()
                    if active_hwnd == hwnd:
                        return hwnd
                    attempt += 1
                logger.warn(f'__activate_window: failed to activate {hwnd}')
                return None
        logger.warn(f'__activate_window: not found')
        return None

    # MSS is faster but proven to be unstable after many screenshots
    def __mss_capture_screenshot(self, capture_bbox: Rect) -> numpy.ndarray:
        monitor = self.__mss.monitors[1]
        left = monitor["left"] + capture_bbox.x1
        top = monitor["top"] + capture_bbox.y1
        right = monitor["left"] + capture_bbox.x2
        lower = monitor["top"] + capture_bbox.y2
        bbox = (left, top, right, lower)
        # noinspection PyTypeChecker
        img = numpy.array(self.__mss.grab(bbox))
        # conversion from RGBA to BGR
        img = numpy.flip(img[:, :, :3], 2)
        return img

    # noinspection PyMethodMayBeStatic
    def __pil_capture_screenshot(self, capture_bbox: Rect) -> Optional[numpy.ndarray]:
        image = ImageGrab.grab(capture_bbox.to_PIL_tuple())
        # noinspection PyBroadException
        try:
            array = numpy.array(image)
        except Exception:
            logger.warn(f'__pil_capture_screenshot: capture_bbox={capture_bbox}, image.size={image.size}')
            return None
        else:
            logger.detail(f'__pil_capture_screenshot: capture_bbox={capture_bbox}, image.size={image.size}')
        converted_array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        return converted_array

    def __capture_window_color(self, capture_area: CaptureArea) -> Optional[Tuple[numpy.ndarray, Rect, Rect]]:
        logger.debug(f'__capture_window_color: {capture_area}')
        self.__time_mark('capture color window 1')
        hwnd = None
        if not capture_area.wintitle:
            if capture_area.winflags & CaptureWindowFlags.DEFAULT_TO_FOREGROUND:
                hwnd = win32gui.GetForegroundWindow()
        else:
            hwnd = self.__activate_window(capture_area.wintitle, capture_area.winflags & CaptureWindowFlags.ACTIVATE_WINDOW)
        if hwnd is None:
            return None
        # noinspection PyUnresolvedReferences
        try:
            window_bbox = win32gui.GetWindowRect(hwnd)
        except pywintypes.error:
            logger.warn(f'Invalid HWND for capturing {capture_area}. hwnd={hwnd}')
            return None
        window_bbox = Rect(x1=window_bbox[0], y1=window_bbox[1], x2=window_bbox[2], y2=window_bbox[3])
        capture_bbox = capture_area.get_capture_bbox(window_bbox)
        logger.detail(f'__capture_window_color: w_bbox {window_bbox}, c_bbox {capture_bbox}')
        self.__time_mark('capture color window 2')
        if capture_bbox.width() == 0 or capture_bbox.height() == 0:
            logger.warn(f'__capture_window_color: capture_area {capture_area}, window_bbox {window_bbox}, capture_bbox {capture_bbox}')
            return None
        array = self.__pil_capture_screenshot(capture_bbox)
        if array is None:
            return None
        self.__time_mark('capture color window END')
        return array, window_bbox, capture_bbox

    def __capture_window_grayscale(self, capture_area: CaptureArea, capture_scale=1.0) -> Optional[Tuple[numpy.ndarray, Rect, Rect]]:
        logger.debug(f'__capture_window_grayscale: {capture_area}')
        capture_result = self.__capture_window_color(capture_area)
        if capture_result is None:
            return None
        capture_bgr, w_bbox, c_bbox = capture_result
        capture_gray = cv2.cvtColor(capture_bgr, cv2.COLOR_BGR2GRAY)
        if abs(capture_scale - 1.0) > 0.01:
            capture_scaled = cv2.resize(capture_gray, (0, 0), fx=capture_scale, fy=capture_scale)
        else:
            capture_scaled = capture_gray
        assert isinstance(capture_scaled, numpy.ndarray)
        return capture_scaled, w_bbox, c_bbox

    def __capture_window(self, capture_area: CaptureArea) -> Optional[Tuple[numpy.ndarray, Rect, Rect]]:
        if capture_area.mode == CaptureMode.COLOR:
            return self.__capture_window_color(capture_area)
        capture_result = self.__capture_window_grayscale(capture_area)
        if capture_area.mode == CaptureMode.GRAY or not capture_result:
            return capture_result
        if capture_area.mode == CaptureMode.BW:
            gray_capture, w_bbox, c_bbox = capture_result
            bw_capture = self.__convert_gray_to_bw(gray_capture)
            return bw_capture, w_bbox, c_bbox
        return None

    @staticmethod
    def __min_max_loc(match_result: numpy.ndarray, match_method) -> Tuple[Point, float]:
        min_v, max_v, min_l, max_l = cv2.minMaxLoc(match_result)
        min_l = Point(min_l[0], min_l[1])
        max_l = Point(max_l[0], max_l[1])
        if match_method in [cv2.TM_SQDIFF_NORMED]:
            return min_l, 1 - min_v
        elif match_method in [cv2.TM_SQDIFF]:
            return min_l, -min_v
        return max_l, max_v

    @staticmethod
    def __threshold_locs(match_result: numpy.ndarray, match_method, threshold: float) -> List[Tuple[Point, float]]:
        if match_method in [cv2.TM_SQDIFF_NORMED, cv2.TM_SQDIFF]:
            locations = numpy.where(match_result <= threshold)
        else:
            locations = numpy.where(match_result >= threshold)
        results = list()
        for pt in zip(*locations[::-1]):
            # location uses int64 which is not what Point declares and is not serializable
            p = Point(int(pt[0]), int(pt[1]))
            mr = match_result[p.y, p.x]
            results.append((p, mr))
        return results

    __match_methods = {
        MatchMethod.TM_CCOEFF_NORMED: cv2.TM_CCOEFF_NORMED,
        MatchMethod.TM_CCORR_NORMED: cv2.TM_CCORR_NORMED,
        MatchMethod.TM_SQDIFF_NORMED: cv2.TM_SQDIFF_NORMED,
    }

    @staticmethod
    def __get_scale_list(patterns: MatchPattern) -> Tuple[List[float], float, float]:
        if patterns.min_scale is not None:
            min_scale = patterns.min_scale
            max_scale = patterns.max_scale
            num_scales = int(max(min((max_scale - min_scale) / 0.05, 13), 2))
        else:
            min_scale = 1.0
            max_scale = 1.0
            num_scales = 0
        all_scales = list(numpy.linspace(start=min_scale, stop=max_scale, num=num_scales, endpoint=True))
        for scale in list(all_scales):
            if abs(scale - 1.0) < 0.05:
                all_scales.remove(scale)
        all_scales.insert(0, 1.0)
        return all_scales, min_scale, max_scale

    @staticmethod
    def __get_scaled_pattern(scale: float, pattern: numpy.ndarray) -> numpy.ndarray:
        if scale != 1.0:
            scaled_pattern = cv2.resize(pattern, (0, 0), fx=scale, fy=scale)
        else:
            scaled_pattern = pattern
        return scaled_pattern

    def __find_pattern(self, patterns: MatchPattern, capture: numpy.ndarray, capture_mode: CaptureMode,
                       threshold: Optional[float] = None) -> Optional[FindPatternResult]:
        logger.debug(f'__find_pattern: patterns {patterns}, threshold {threshold}, capture shape {capture.shape}, mode {capture_mode}')
        self.__time_mark('capture matching start')
        first_check = True
        best_l: Optional[Point] = None
        best_v: Optional[float] = None
        best_shape: Optional[Shape] = None
        best_scale: Optional[float] = None
        best_tag: Optional[str] = None
        match_method = Win32OpenCVCaptureService.__match_methods[patterns.match_method.__int__()]
        use_patterns = self.__patterns_by_mode[capture_mode]
        if patterns.tags is not None:
            search_patterns = {tag: use_patterns[tag] for tag in patterns.tags}
        elif patterns.capture is not None:
            if capture_mode != patterns.capture.mode:
                raise ValueError(f'comparing incompatible capture modes {capture} vs {patterns.capture.mode}')
            search_patterns = {'array': patterns.capture.get_array()}
        else:
            search_patterns = use_patterns
        all_scales, min_scale, max_scale = Win32OpenCVCaptureService.__get_scale_list(patterns)
        logger.debug(f'__find_pattern: scales min_scale {min_scale}, max_scale {max_scale}, all_scales {all_scales}')
        for scale in all_scales:
            for tag, pattern in search_patterns.items():
                scaled_pattern = Win32OpenCVCaptureService.__get_scaled_pattern(scale, pattern)
                logger.detail(f'__find_pattern: scaled_pattern {tag} has shape {scaled_pattern.shape}')
                if scaled_pattern.shape[0] > capture.shape[0] or scaled_pattern.shape[1] > capture.shape[1]:
                    logger.warn(f'__find_pattern: scaled_pattern {tag} larger than capture')
                    continue
                match_result = cv2.matchTemplate(capture, scaled_pattern, match_method)
                found_l, found_v = Win32OpenCVCaptureService.__min_max_loc(match_result=match_result, match_method=match_method)
                logger.debug(f'__find_pattern: try scale {scale}, found_l {found_l}, found_v {found_v}')
                if first_check or found_v > best_v:
                    first_check = False
                    best_tag = tag
                    best_v = found_v
                    best_scale = scale
                    best_l = found_l
                    best_shape = Shape(width=scaled_pattern.shape[1], heigth=scaled_pattern.shape[0])
                    logger.debug(f'__find_pattern: best_v now {best_v} with tag {tag}')
        self.__time_mark('capture matching end')
        logger.debug('best match tag:{}, value:{:4.2f}/{:4.2f}, scale:{:4.2f}'.format(best_tag, best_v, threshold, best_scale))
        logger.debug(f'best match loc:{best_l}, shape:{best_shape}')
        if best_tag is None or (threshold is not None and best_v < threshold):
            return None
        find_pattern_shape = Rect.from_point_and_shape(best_l, best_shape)
        return FindPatternResult(best_tag, best_v, best_scale, find_pattern_shape)

    def __find_multiple_patterns(self, patterns: MatchPattern, capture: numpy.ndarray, capture_mode: CaptureMode,
                                 threshold: float, max_matches: Optional[int]) -> List[FindPatternResult]:
        logger.debug(f'__find_multiple_patterns: patterns {patterns}, threshold {threshold}, capture shape {capture.shape}, mode {capture_mode}')
        self.__time_mark('capture matching start')
        match_method = Win32OpenCVCaptureService.__match_methods[patterns.match_method.__int__()]
        use_patterns = self.__patterns_by_mode[capture_mode]
        if patterns.tags is not None:
            search_patterns = {tag: use_patterns[tag] for tag in patterns.tags}
        elif patterns.capture is not None:
            if capture_mode != patterns.capture.mode:
                raise ValueError(f'comparing incompatible capture modes {capture} vs {patterns.capture.mode}')
            search_patterns = {'array': patterns.capture.get_array()}
        else:
            search_patterns = use_patterns
        results: List[FindPatternResult] = list()
        all_scales, min_scale, max_scale = Win32OpenCVCaptureService.__get_scale_list(patterns)
        for scale in all_scales:
            for tag, pattern in search_patterns.items():
                pattern = Win32OpenCVCaptureService.__get_scaled_pattern(scale, pattern)
                logger.detail(f'__find_multiple_patterns: pattern {tag} has shape {pattern.shape}')
                if pattern.shape[0] > capture.shape[0] or pattern.shape[1] > capture.shape[1]:
                    logger.warn(f'__find_multiple_patterns: pattern {tag} larger than capture')
                    continue
                match_result = cv2.matchTemplate(capture, pattern, match_method)
                found_matches = Win32OpenCVCaptureService.__threshold_locs(match_result=match_result, match_method=match_method, threshold=threshold)
                logger.debug(f'__find_multiple_patterns: found a total of {len(found_matches)} matches for {tag}, scale {scale}')
                for (found_l, found_v) in found_matches:
                    shape = Shape(width=pattern.shape[1], heigth=pattern.shape[0])
                    find_pattern_rect = Rect.from_point_and_shape(point=found_l, shape=shape)
                    find_result = FindPatternResult(tag, found_v, 1.0, find_pattern_rect)
                    results.append(find_result)
        if len(results) > 1000:
            logger.warn(f'large amount of matches for {patterns} ({len(results)})')
        # sort matches by score
        results = list(sorted(results, key=lambda match_result_: match_result_.value, reverse=True))
        accepted_results: List[FindPatternResult] = list()
        # reject overlapping matches; start by accepting best matches
        for result in results:
            overlap_found = False
            for accepted_result in accepted_results:
                if result.found_rect.overlaps(accepted_result.found_rect):
                    overlap_found = True
                    break
            if overlap_found:
                continue
            logger.debug(f'__find_multiple_patterns: accepting {result}')
            accepted_results.append(result)
            if max_matches and len(accepted_results) >= max_matches:
                break
        self.__time_mark('capture matching end')
        return accepted_results

    def show_capture(self, capture: Capture, rect: Optional[Rect] = None):
        if rect is not None:
            pt1 = rect.point1().to_tuple() if rect is not None else None
            pt2 = rect.point2().to_tuple() if rect is not None else None
            cv2.rectangle(capture.get_array(), pt1=pt1, pt2=pt2, color=(255, 255, 255), thickness=4)
        image = capture.get_array()
        cv2.imshow('show_capture', image)
        cv2.moveWindow('show_capture', 100, 50)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # BW mode, for detecting features
    def __save_bw_pattern(self, pattern_bw, tag: str):
        assert pattern_bw is not None, tag
        if CaptureMode.BW not in self.__patterns_by_mode:
            self.__patterns_by_mode[CaptureMode.BW] = dict()
        self.__patterns_by_mode[CaptureMode.BW][tag] = pattern_bw

    def __convert_gray_to_bw(self, pattern_gray) -> numpy.ndarray:
        _, pattern_bw = cv2.threshold(pattern_gray, self.__default_bw_binary_threshold, 255, cv2.THRESH_BINARY)
        return pattern_bw

    # grayscale mode, higher tolerance
    def __save_gray_pattern(self, pattern_gray, tag: str):
        assert pattern_gray is not None, tag
        if CaptureMode.GRAY not in self.__patterns_by_mode:
            self.__patterns_by_mode[CaptureMode.GRAY] = dict()
        self.__patterns_by_mode[CaptureMode.GRAY][tag] = pattern_gray
        pattern_bw = self.__convert_gray_to_bw(pattern_gray)
        self.__save_bw_pattern(pattern_bw, tag)

    # color mode, original picture
    def __save_bgr_pattern(self, pattern_bgr, tag: str):
        assert pattern_bgr is not None, tag
        if CaptureMode.COLOR not in self.__patterns_by_mode:
            self.__patterns_by_mode[CaptureMode.COLOR] = dict()
        self.__patterns_by_mode[CaptureMode.COLOR][tag] = pattern_bgr
        pattern_gray = cv2.cvtColor(pattern_bgr, cv2.COLOR_BGR2GRAY)
        self.__save_gray_pattern(pattern_gray, tag)

    def load_pattern(self, path: str, tag: str) -> bool:
        try:
            # color mode, original picture
            pattern_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
            self.__save_bgr_pattern(pattern_bgr, tag)
            return True
        except IOError:
            pass
        return False

    def save_capture_as_tag(self, capture: Capture, tag: str) -> bool:
        logger.info(f'save_capture_as_tag: capture {capture}, tag {tag}')
        if not capture or not tag:
            return False
        if capture.mode == CaptureMode.COLOR:
            rgb_capture_array = capture.get_array()
            bgr_capture_array = cv2.cvtColor(rgb_capture_array, cv2.COLOR_RGB2BGR)
            self.__save_bgr_pattern(bgr_capture_array, tag)
        elif capture.mode == CaptureMode.GRAY:
            gray_capture_array = capture.get_array()
            self.__save_gray_pattern(gray_capture_array, tag)
        elif capture.mode == CaptureMode.BW:
            bw_capture_array = capture.get_array()
            self.__save_bw_pattern(bw_capture_array, tag)
        return True

    def find_capture_match(self, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None) -> Optional[Tuple[str, Rect]]:
        logger.info(f'find_capture_match_loc: capture_area {capture_area}, patterns {patterns}, threshold {threshold}')
        capture_result = self.__capture_window(capture_area)
        if capture_result is None:
            return None
        capture, w_bbox, c_bbox = capture_result
        if threshold is None:
            threshold = self.__default_threshold
        find_result = self.__find_pattern(patterns=patterns, capture=capture, capture_mode=capture_area.mode, threshold=threshold)
        if find_result is None:
            return None
        sx = c_bbox.x1 - w_bbox.x1
        sy = c_bbox.y1 - w_bbox.y1
        loc_rect = Rect(x1=find_result.found_rect.x1 + sx, y1=find_result.found_rect.y1 + sy, x2=find_result.found_rect.x2 + sx, y2=find_result.found_rect.y2 + sy)
        logger.info(f'find_capture_match_loc: tag {find_result.tag}, loc {loc_rect}, strength {find_result.value}, scale {find_result.scale}')
        return find_result.tag, loc_rect

    def find_multiple_capture_match(self, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None,
                                    max_matches: Optional[int] = None) -> List[Tuple[str, Rect]]:
        logger.info(f'find_multiple_capture_match: capture_area {capture_area}, patterns {patterns}, threshold {threshold}, max_matches {max_matches}')
        capture_result = self.__capture_window(capture_area)
        if capture_result is None:
            return []
        capture, w_bbox, c_bbox = capture_result
        sx = c_bbox.x1 - w_bbox.x1
        sy = c_bbox.y1 - w_bbox.y1
        if threshold is None:
            threshold = self.__default_threshold
        results = list()
        find_results = self.__find_multiple_patterns(patterns=patterns, capture=capture, capture_mode=capture_area.mode, threshold=threshold, max_matches=max_matches)
        for find_result in find_results:
            loc_rect = Rect(x1=find_result.found_rect.x1 + sx, y1=find_result.found_rect.y1 + sy, x2=find_result.found_rect.x2 + sx, y2=find_result.found_rect.y2 + sy)
            logger.info(f'find_multiple_capture_match: tag {find_result.tag}, loc {loc_rect}, strength {find_result.value}, scale {find_result.scale}')
            results.append((find_result.tag, loc_rect))
        return results

    def click_capture_match(self, automation: IAutomation, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None,
                            max_clicks: Optional[int] = None, click_delay: Optional[float] = None, click_offset: Optional[Offset] = None) -> bool:
        if threshold is None:
            threshold = self.__default_threshold
        if click_delay is None:
            click_delay = 0.1
        if max_clicks is None:
            max_clicks = 1
        if click_offset is None:
            click_offset = Offset(0, 0, Offset.REL_FIND_MID)
        logger.info(f'click_capture_match: capture_area {capture_area}, threshold {threshold}, patterns {patterns}')
        logger.info(f'click_capture_match: max_clicks {max_clicks}, every {click_delay}, click_offset {click_offset}')
        clicked = False
        clicks = 0
        if max_clicks > 30 or max_clicks < 0:
            max_clicks = 30
        while True:
            capture_result = self.__capture_window(capture_area)
            if capture_result is None:
                logger.error(f'click_capture_match: could not capture')
                return False
            capture, w_bbox, c_bbox = capture_result
            logger.debug(f'click_capture_match: capture done. w_bbox {w_bbox}, c_bbox {c_bbox}')
            find_result = self.__find_pattern(patterns=patterns, capture=capture, capture_mode=capture_area.mode, threshold=threshold)
            if not find_result:
                logger.info(f'click_capture_match: tag not found')
                break
            clicked = True
            if clicks >= max_clicks >= 0:
                logger.detail(f'click_capture_match: clicks done {clicks} >= {max_clicks} >= 0')
                break
            x, y = click_offset.calc_xy(w_bbox, c_bbox, find_result.found_rect, result_wnd_relative=True)
            logger.debug(f'click_capture_match: matched, clicking:{x}, {y}')
            automation.mouse_move(x, y, speed=2, coord_mode=MouseCoordMode.RELATIVE_WINDOW)
            sleep(0.1)
            automation.mouse_click('left')
            clicks += 1
            if clicks >= max_clicks >= 0:
                logger.detail(f'click_capture_match: clicks done (2) {clicks} >= {max_clicks} >= 0')
                break
            sleep(click_delay)
        return clicked

    def get_capture(self, capture_area: CaptureArea) -> Optional[Capture]:
        logger.info(f'capture_area: capture_area {capture_area}')
        capture_result = self.__capture_window(capture_area)
        if capture_result is None:
            return None
        capture, _, _ = capture_result
        return Capture.from_array(array=capture, mode=capture_area.mode)


if __name__ == '__main__':
    _service = Win32OpenCVCaptureService()
    sleep(1.0)
    _capture = Capture.from_file(r'D:\storage\workspace\pycharm\rka\rka\eq2\master\game\scripting\patterns\detrims\personal_icon_curse_1.png', mode=CaptureMode.COLOR)
    _service.save_capture_as_tag(_capture, '1')
    _pattern = MatchPattern.by_tag('1')
    _pattern.match_method = MatchMethod.TM_CCOEFF_NORMED
    _area = CaptureArea(mode=CaptureMode.COLOR, wintitle='Photos')
    _match = _service.find_multiple_capture_match(_pattern, _area)
    print(_match)
