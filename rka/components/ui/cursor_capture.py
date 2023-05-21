import base64
import math
from enum import auto, IntEnum
from typing import Optional, Tuple, Dict, Any


class ECursorBitmapType(IntEnum):
    MASK = auto()
    COLOR = auto()


class Base64CursorCapture(object):
    def __init__(self):
        self.bitmap_type: Optional[ECursorBitmapType] = None
        self.base64encoded: Optional[bytes] = None
        self.raw_image: Optional[bytes] = None
        self.width = 0
        self.heigth = 0
        self.bits_per_pixel = 0

    def __reduce_color(self, pixel) -> int:
        if self.bits_per_pixel == 32 or self.bits_per_pixel == 24:
            ch1 = (pixel >> 0) & 0xFF
            ch2 = (pixel >> 8) & 0xFF
            ch3 = (pixel >> 16) & 0xFF
            r = (ch1 + ch2 + ch3) // 3
        else:
            r = pixel
        return r & 0xFF

    def __get_mask(self) -> int:
        if self.bits_per_pixel < 32:
            return (1 << self.bits_per_pixel) - 1
        return 0xFFFFFFFF

    def __restore_byte_array(self):
        assert self.base64encoded
        self.raw_image = base64.b64decode(self.base64encoded)

    def __restore_base64_encoded_str(self):
        assert self.raw_image
        self.base64encoded = base64.b64encode(self.raw_image)

    def print_cursor_debug(self):
        if not self.raw_image:
            self.__restore_byte_array()
        mask = self.__get_mask()
        for y in range(self.heigth):
            for x in range(self.width):
                idx = y * self.width + x
                byte_offset = (idx * self.bits_per_pixel) >> 3
                bit_offset = (idx * self.bits_per_pixel) % 8
                if self.bits_per_pixel <= 8:
                    bit_offset = 7 - bit_offset
                pixel = self.raw_image[byte_offset]
                remaining_bytes = math.ceil(self.bits_per_pixel / 8) - 1
                for r_b in range(remaining_bytes):
                    pixel += self.raw_image[byte_offset + r_b] << ((r_b + 1) * 8)
                pixel &= mask << bit_offset
                pixel >>= bit_offset
                pixel = self.__reduce_color(pixel)
                print(f'{pixel:02x}', end=' ')
            print('')

    def save_to_dict(self) -> Dict[str, Any]:
        if not self.base64encoded:
            self.__restore_base64_encoded_str()
        return {
            'base64data': self.base64encoded,
            'width': self.width,
            'heigth': self.heigth,
            'bits_per_pixel': self.bits_per_pixel,
        }

    def restore_from_dict(self, stored: Dict[str, Any]):
        self.raw_image = None
        self.base64encoded = stored['base64data']
        self.width = stored['base64data']
        self.heigth = stored['base64data']
        self.bits_per_pixel = stored['bits_per_pixel']


class ICursorCapture(object):
    def get_cursor_base64_bitmaps(self) -> Tuple[Optional[Base64CursorCapture], Optional[Base64CursorCapture]]:
        raise NotImplementedError()

    def get_cursor_fingerprint(self) -> Optional[bytes]:
        raise NotImplementedError()
