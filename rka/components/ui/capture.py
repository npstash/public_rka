from __future__ import annotations

import base64
import enum
import json
import math
from io import BytesIO
from typing import Union, Tuple, List, Optional

import PIL.Image
import numpy

from rka.components.resources import Resource
from rka.components.ui.automation import IAutomation


class Rect:
    @staticmethod
    def from_point_and_shape(point: Point, shape: Shape) -> Rect:
        return Rect(x1=point.x, y1=point.y, w=shape.width, h=shape.heigth)

    @staticmethod
    def from_points(point1: Point, point2: Point) -> Rect:
        return Rect(x1=point1.x, y1=point1.y, x2=point2.x, y2=point2.y)

    def __init__(self, x1: int, y1: int, x2: Optional[int] = None, y2: Optional[int] = None, w: Optional[int] = None, h: Optional[int] = None):
        assert (x2 is not None and w is None) or (x2 is None and w is not None), f'{x2} {w}'
        assert (y2 is not None and h is None) or (y2 is None and h is not None), f'{y2} {h}'
        self.x1 = x1
        self.y1 = y1
        # Rect coordinates are inclusive, need to -1 form shape
        self.x2 = x2 if x2 is not None else x1 + w - 1
        self.y2 = y2 if y2 is not None else y1 + h - 1

    def __str__(self) -> str:
        return self.to_tuple().__str__()

    def encode_rect(self) -> str:
        d = {'x1': self.x1, 'y1': self.y1, 'x2': self.x2, 'y2': self.y2}
        return json.dumps(d)

    def point1(self) -> Point:
        return Point(self.x1, self.y1)

    def point2(self) -> Point:
        return Point(self.x2, self.y2)

    def middle(self) -> Point:
        return Point((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def shift(self, x: int, y: int) -> Rect:
        return Rect(x1=self.x1 + x, y1=self.y1 + y, x2=self.x2 + x, y2=self.y2 + y)

    def height(self) -> int:
        return self.y2 - self.y1 + 1

    def width(self) -> int:
        return self.x2 - self.x1 + 1

    def includes(self, other: Rect) -> int:
        return other.x1 >= self.x1 and other.y1 >= self.y1 and other.x2 <= self.x2 and other.y2 <= self.y2

    def overlaps(self, other: Rect) -> int:
        if self.x2 < other.x1 or other.x2 < self.x1:
            return False
        if self.y2 < other.y1 or other.y2 < self.y1:
            return False
        return True

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2, self.y2

    def to_PIL_tuple(self) -> Tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2 + 1, self.y2 + 1

    @staticmethod
    def decode_rect(s: str) -> Rect:
        d = json.loads(s)
        return Rect(x1=d['x1'], y1=d['y1'], x2=d['x2'], y2=d['y2'])


class Shape:
    def __init__(self, width: int, heigth: int):
        self.width = width
        self.heigth = heigth

    def __str__(self) -> str:
        return f'width={self.width}, heigth={self.heigth}'


class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __str__(self) -> str:
        return self.to_tuple().__str__()

    def encode_point(self) -> str:
        d = {'x': self.x, 'y': self.y}
        return json.dumps(d)

    def to_tuple(self) -> Tuple[int, int]:
        return self.x, self.y

    def distance(self, to: Union[Point, Tuple[int, int]]) -> float:
        if isinstance(to, Point):
            to = (to.x, to.y)
        return math.dist((self.x, self.y), to)

    def rotate(self, origin: Union[Point, Tuple[int, int]], angle: float) -> Point:
        """
        Rotate a point counterclockwise by a given angle around a given origin.

        The angle should be given in radians.
        """
        if isinstance(origin, Point):
            origin = (origin.x, origin.y)
        ox, oy = origin
        px, py = (self.x, self.y)
        qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
        qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
        return Point(int(qx), int(qy))

    def angle(self, other: Union[Point, Tuple[int, int]]) -> float:
        if isinstance(other, Point):
            other = (other.x, other.y)
        ox, oy = other
        return math.atan2(oy - self.y, ox - self.x)

    @staticmethod
    def decode_point(s: str) -> Point:
        d = json.loads(s)
        return Point(d['x'], d['y'])


class Offset:
    ABSOLUTE = 0
    REL_WIND_BOX = 1
    REL_CAPT_BOX = 2
    REL_FIND_BOX = 3
    REL_FIND_MID = 4
    __names = ['ABSOLUTE', 'REL_WIND_BOX', 'REL_CAPT_BOX', 'REL_FIND_BOX', 'REL_FIND_MID']

    def __init__(self, x: int, y: int, anchor: int):
        self.x = x
        self.y = y
        self.anchor = anchor

    def __str__(self) -> str:
        return f'Offset[x:{self.x}, y:{self.y}, anchor:{Offset.__names[self.anchor]}]'

    def calc_xy(self, window_abs_box: Rect, capture_abs_box: Rect, find_rel_box: Rect, result_wnd_relative: bool) -> Tuple[int, int]:
        if self.anchor == Offset.ABSOLUTE:
            x = self.x
            y = self.y
        elif self.anchor == Offset.REL_WIND_BOX:
            x = self.x + window_abs_box.x1
            y = self.y + window_abs_box.y1
        elif self.anchor == Offset.REL_CAPT_BOX:
            x = self.x + capture_abs_box.x1
            y = self.y + capture_abs_box.y1
        elif self.anchor == Offset.REL_FIND_BOX:
            x = self.x + capture_abs_box.x1 + find_rel_box.x1
            y = self.y + capture_abs_box.y1 + find_rel_box.y1
        elif self.anchor == Offset.REL_FIND_MID:
            x = self.x + capture_abs_box.x1 + (find_rel_box.x1 + find_rel_box.x2) // 2
            y = self.y + capture_abs_box.y1 + (find_rel_box.y1 + find_rel_box.y2) // 2
        else:
            assert False
        if result_wnd_relative:
            x -= window_abs_box.x1
            y -= window_abs_box.y1
        return x, y

    def encode_offset(self) -> str:
        d = {'x': self.x, 'y': self.y, 'anchor': self.anchor}
        return json.dumps(d)

    @staticmethod
    def decode_offset(s: str) -> Offset:
        d = json.loads(s)
        return Offset(d['x'], d['y'], d['anchor'])


class Radius:
    def __init__(self, x: int, y: int, r: int):
        self.x = x
        self.y = y
        self.r = r

    def __str__(self) -> str:
        return f'[{self.x},{self.y},{self.r}]'

    def encode_radius(self) -> str:
        d = {'x': self.x, 'y': self.y, 'r': self.r}
        return json.dumps(d)

    def rect(self) -> Rect:
        return Rect(x1=self.x - self.r, y1=self.y - self.r, x2=self.x + self.r, y2=self.y + self.r)

    @staticmethod
    def decode_radius(s: str) -> Radius:
        d = json.loads(s)
        return Radius(d['x'], d['y'], d['r'])


class CaptureMode(enum.IntEnum):
    COLOR = enum.auto()
    GRAY = enum.auto()
    BW = enum.auto()
    DEFAULT = GRAY


class CaptureWindowFlags(enum.IntFlag):
    DEFAULT_TO_FOREGROUND = enum.auto()
    ACTIVATE_WINDOW = enum.auto()
    IGNORE_NOT_MATCHING = 0
    DEFAULTS = DEFAULT_TO_FOREGROUND | ACTIVATE_WINDOW


# window and resulting capture box dimensions x1, y1, x2, y2 are absolute
# argument dimensions can be relative (default) or absolute
class CaptureArea:
    def __init__(self, mode=CaptureMode.DEFAULT, wintitle: Optional[str] = None, winflags=CaptureWindowFlags.DEFAULTS):
        self.wintitle = wintitle
        self.mode = mode
        self.winflags = winflags
        self.__encoded = None

    def __str__(self):
        if not self.__encoded:
            self.__encoded = self.encode_area()
        return self.__encoded

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return self.__str__().__hash__()

    def __eq__(self, other):
        return self.__str__() == other.__str__()

    def set_default_wintitle(self, wintitle: str):
        if self.wintitle is None:
            self.wintitle = wintitle

    def encode_area(self) -> str:
        d = {'area_type': 'window_area', 'mode': self.mode, 'wintitle': self.wintitle, 'winflags': self.winflags}
        return json.dumps(d)

    @staticmethod
    def decode_area(s: str) -> CaptureArea:
        d = json.loads(s)
        area_type = d['area_type']
        mode = CaptureMode(d['mode']) if 'mode' in d.keys() else CaptureMode.DEFAULT
        wintitle = d['wintitle'] if 'wintitle' in d.keys() else None
        winflags = CaptureWindowFlags(d['winflags']) if 'winflags' in d.keys() else CaptureWindowFlags.DEFAULTS
        if area_type == 'window_area':
            ca = CaptureArea(mode=mode, wintitle=wintitle, winflags=winflags)
        elif area_type == 'rect_area':
            ca = RectCapture(rect=Rect(x1=d['x1'], y1=d['y1'], x2=d['x2'], y2=d['y2']), relative=d['relative'], mode=mode, wintitle=wintitle, winflags=winflags)
        elif area_type == 'radius_area':
            ca = RadiusCapture(radius=Radius(d['x'], d['y'], d['r']), relative=d['relative'], mode=mode, wintitle=wintitle, winflags=winflags)
        else:
            assert False
        return ca

    def get_capture_bbox(self, window_bbox: Rect) -> Rect:
        return window_bbox

    def capture_rect(self, rect: Rect, relative: bool) -> CaptureArea:
        return RectCapture(rect=rect, relative=relative, mode=self.mode, wintitle=self.wintitle, winflags=self.winflags)

    def capture_radius(self, radius: Radius, relative: bool) -> CaptureArea:
        return RadiusCapture(radius=radius, relative=relative, mode=self.mode, wintitle=self.wintitle, winflags=self.winflags)

    def get_bounding_box(self) -> Rect:
        raise NotImplementedError()


class RectCapture(CaptureArea):
    def __init__(self, rect: Rect, relative: bool, mode: CaptureMode, wintitle: Optional[str] = None, winflags=CaptureWindowFlags.DEFAULTS):
        CaptureArea.__init__(self, mode=mode, wintitle=wintitle, winflags=winflags)
        self.rect = rect
        self.relative = relative

    def encode_area(self) -> str:
        d = {'area_type': 'rect_area', 'mode': self.mode, 'wintitle': self.wintitle, 'winflags': self.winflags,
             'x1': self.rect.x1, 'y1': self.rect.y1, 'x2': self.rect.x2, 'y2': self.rect.y2, 'relative': self.relative}
        return json.dumps(d)

    def get_capture_bbox(self, window_bbox: Rect) -> Rect:
        l, t, r, b = self.rect.x1, self.rect.y1, self.rect.x2, self.rect.y2
        if self.relative:
            l, t, r, b = l + window_bbox.x1, t + window_bbox.y1, r + window_bbox.x1, b + window_bbox.y1
        return Rect(x1=max(l, window_bbox.x1), y1=max(t, window_bbox.y1), x2=min(r, window_bbox.x2), y2=min(b, window_bbox.y2))

    def get_bounding_box(self) -> Rect:
        return self.rect


class RadiusCapture(CaptureArea):
    def __init__(self, radius: Radius, relative: bool, mode: CaptureMode, wintitle: Optional[str] = None, winflags=CaptureWindowFlags.DEFAULTS):
        CaptureArea.__init__(self, mode=mode, wintitle=wintitle, winflags=winflags)
        self.radius = radius
        self.relative = relative

    def encode_area(self) -> str:
        d = {'area_type': 'radius_area', 'mode': self.mode, 'wintitle': self.wintitle, 'winflags': self.winflags,
             'x': self.radius.x, 'y': self.radius.y, 'r': self.radius.r, 'relative': self.relative}
        return json.dumps(d)

    def get_capture_bbox(self, window_bbox: Rect) -> Rect:
        l, t, r, b = self.radius.x - self.radius.r, self.radius.y - self.radius.r, self.radius.x + self.radius.r, self.radius.y + self.radius.r
        if self.relative:
            l, t, r, b = l + window_bbox.x1, t + window_bbox.y1, r + window_bbox.x1, b + window_bbox.y1
        return Rect(x1=max(l, window_bbox.x1), y1=max(t, window_bbox.y1), x2=min(r, window_bbox.x2), y2=min(b, window_bbox.y2))

    def get_bounding_box(self) -> Rect:
        return self.radius.rect()


class MatchMethod(enum.IntEnum):
    TM_CCOEFF_NORMED = 0
    TM_CCORR_NORMED = 1
    TM_SQDIFF_NORMED = 2


class MatchPattern:
    def __init__(self):
        self.tags: Optional[List[str]] = None
        self.capture: Optional[Capture] = None
        self.min_scale: Optional[float] = None
        self.max_scale: Optional[float] = None
        self.match_method = MatchMethod.TM_CCOEFF_NORMED

    def __str__(self):
        if self.capture is not None:
            return 'capture:[image_array]'
        return self.encode_pattern()

    def encode_pattern(self) -> str:
        d = dict()
        if self.tags is not None:
            d['tags'] = ';'.join(self.tags)
        elif self.capture is not None:
            d['capture'] = self.capture.encode_capture()
        else:
            d['tags'] = 'all'
        if self.min_scale is not None and self.max_scale is not None:
            d['min_scale'] = self.min_scale
            d['max_scale'] = self.max_scale
        if self.match_method is not None:
            d['match_method'] = self.match_method
        return json.dumps(d)

    def set_scale(self, min_scale: float, max_scale: float) -> MatchPattern:
        self.min_scale = min_scale
        self.max_scale = max_scale
        return self

    def set_match_method(self, match_method: MatchMethod) -> MatchPattern:
        self.match_method = match_method
        return self

    def get_mode(self) -> CaptureMode:
        if self.capture is not None:
            return self.capture.mode
        return CaptureMode.DEFAULT

    @staticmethod
    def decode_pattern(s: str) -> MatchPattern:
        d = json.loads(s)
        if 'tags' in d.keys():
            tags_str = d['tags']
            if tags_str == 'all':
                pattern = MatchPattern.all_tags()
            else:
                pattern = MatchPattern.by_tags(tags_str.split(';'))
        elif 'capture' in d.keys():
            pattern = MatchPattern.by_capture(Capture.decode_capture(d['capture']))
        else:
            pattern = MatchPattern.all_tags()
        if 'min_scale' in d.keys() and 'max_scale' in d.keys():
            min_scale = d['min_scale']
            max_scale = d['max_scale']
            pattern.set_scale(min_scale=min_scale, max_scale=max_scale)
        if 'match_method' in d.keys():
            pattern.match_method = d['match_method']
        return pattern

    @staticmethod
    def all_tags() -> MatchPattern:
        pm = MatchPattern()
        return pm

    @staticmethod
    def by_tag(tag: Union[str, Resource]) -> MatchPattern:
        if isinstance(tag, Resource):
            tag = tag.resource_id
        assert isinstance(tag, str)
        pm = MatchPattern()
        pm.tags = [tag]
        return pm

    @staticmethod
    def by_tags(tags: List[Union[str, Resource]]) -> MatchPattern:
        assert isinstance(tags, list)
        tags_copy = list()
        for tag in tags:
            if isinstance(tag, Resource):
                tag = tag.resource_id
            assert isinstance(tag, str)
            tags_copy.append(tag)
        pm = MatchPattern()
        pm.tags = tags_copy
        return pm

    @staticmethod
    def by_capture(capture: Capture) -> MatchPattern:
        pm = MatchPattern()
        pm.capture = capture
        return pm


class Capture:
    def __init__(self, mode=CaptureMode.GRAY):
        self.mode = mode
        self.image: Optional[PIL.Image.Image] = None
        self.array: Optional[numpy.ndarray] = None
        self.__encoded = None

    def __str__(self):
        fmt = self.image.format if self.image else None
        shape = self.array.shape if self.array else None
        return f'Capture[mode:{self.mode}, {fmt}, {shape}]'

    def get_image(self) -> PIL.Image.Image:
        if self.image is None:
            self.image = PIL.Image.fromarray(self.array)
        return self.image

    def get_array(self) -> numpy.array:
        if self.array is None:
            # noinspection PyTypeChecker
            self.array = numpy.array(self.image)
        return self.array

    def crop(self, rect: Rect) -> Capture:
        img = self.get_image()
        cropped = img.crop(rect.to_PIL_tuple())
        return Capture.from_image(image=cropped, mode=self.mode)

    @staticmethod
    def from_array(array: numpy.ndarray, mode: CaptureMode) -> Capture:
        capture = Capture(mode=mode)
        capture.array = array.copy()
        capture.image = PIL.Image.fromarray(array)
        return capture

    @staticmethod
    def from_image(image: PIL.Image.Image, mode: CaptureMode) -> Capture:
        capture = Capture(mode=mode)
        capture.image = image
        return capture

    @staticmethod
    def from_file(filename: str, mode: CaptureMode) -> Capture:
        # TODO image colorspace should be autodetected, not provided by mode
        capture = Capture(mode=mode)
        capture.image = PIL.Image.open(filename)
        return capture

    def encode_capture(self) -> str:
        if self.__encoded is None:
            buffered = BytesIO()
            self.get_image().save(buffered, format='PNG')
            encoded = base64.b64encode(buffered.getvalue())
            encoded = encoded.decode('ascii')
            assert isinstance(encoded, str)
            self.__encoded = encoded
        return f'mode:{self.mode},encoded:{self.__encoded}'

    @staticmethod
    def decode_capture(s: str) -> Capture:
        assert isinstance(s, str), s
        assert s.startswith('mode:')
        enc_i = s.find(',encoded:')
        assert enc_i > 0
        mode_str = s[len('mode:'):enc_i]
        mode = CaptureMode(int(mode_str))
        encoded_str = s[enc_i + len(',encoded:'):]
        f = BytesIO(base64.b64decode(encoded_str))
        img = PIL.Image.open(f)
        return Capture.from_image(image=img, mode=mode)


class ICaptureService:
    def show_capture(self, capture: Capture, rect: Optional[Rect] = None):
        raise NotImplementedError()

    def load_pattern(self, path: str, tag: str) -> bool:
        raise NotImplementedError()

    def save_capture_as_tag(self, capture: Capture, tag: str) -> bool:
        raise NotImplementedError()

    def find_capture_match(self, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None) -> Optional[Tuple[str, Rect]]:
        raise NotImplementedError()

    def find_multiple_capture_match(self, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None,
                                    max_matches: Optional[int] = None) -> List[Tuple[str, Rect]]:
        raise NotImplementedError()

    def click_capture_match(self, automation: IAutomation, patterns: MatchPattern, capture_area: CaptureArea, threshold: Optional[float] = None,
                            max_clicks: Optional[int] = None, click_delay: Optional[float] = None, click_offset: Optional[Offset] = None) -> bool:
        raise NotImplementedError()

    def get_capture(self, capture_area: CaptureArea) -> Optional[Capture]:
        raise NotImplementedError()

    def close_capture_service(self):
        pass
