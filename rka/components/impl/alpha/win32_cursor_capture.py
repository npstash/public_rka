import ctypes.wintypes
import hashlib
import time
from typing import Tuple, Optional

from rka.components.ui.cursor_capture import ICursorCapture, Base64CursorCapture


def align_size_to_word(size_unaligned) -> int:
    word_size = ctypes.sizeof(ctypes.c_int)
    if size_unaligned % word_size == 0:
        return size_unaligned
    return size_unaligned + word_size - (size_unaligned % word_size)


def error_check(result, *_args):
    if result == 0:
        raise ValueError(ctypes.WinError)
    return result


user32 = ctypes.WinDLL('user32.dll')
gdi32 = ctypes.WinDLL('gdi32.dll')
BI_RGB = 0
DIB_RGB_COLORS = 0


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.wintypes.DWORD),
        ('flags', ctypes.wintypes.DWORD),
        ('hCursor', ctypes.wintypes.HANDLE),
        ('ptScreenPos', ctypes.wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ('fIcon', ctypes.wintypes.BOOL),
        ('xHotspot', ctypes.wintypes.DWORD),
        ('yHotspot', ctypes.wintypes.DWORD),
        ('hbmMask', ctypes.wintypes.HBITMAP),
        ('hbmColor', ctypes.wintypes.HBITMAP),
    ]

    def __del__(self, ):
        if self.hbmMask:
            DeleteObject(self.hbmMask)
            self.hbmMask = None
        if self.hbmColor:
            DeleteObject(self.hbmColor)
            self.hbmColor = None


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ('bmType', ctypes.wintypes.LONG),
        ('bmWidth', ctypes.wintypes.LONG),
        ('bmHeight', ctypes.wintypes.LONG),
        ('bmWidthBytes', ctypes.wintypes.LONG),
        ('bmPlanes', ctypes.wintypes.WORD),
        ('bmBitsPixel', ctypes.wintypes.WORD),
        ('bmBits', ctypes.wintypes.LPVOID),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ('rgbRed', ctypes.wintypes.BYTE),
        ('rgbGreen', ctypes.wintypes.BYTE),
        ('rgbBlue', ctypes.wintypes.BYTE),
        ('rgbReserved', ctypes.wintypes.BYTE),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', RGBQUAD),
    ]


class BitmapPlusPalette(ctypes.Structure):
    # noinspection PyTypeChecker
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', RGBQUAD * 256),
    ]


DeleteObject = gdi32.DeleteObject
DeleteObject.argtypes = [ctypes.wintypes.HGDIOBJ]
DeleteObject.restype = ctypes.wintypes.BOOL
DeleteObject.errcheck = error_check

CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.argtypes = [ctypes.wintypes.HDC]
CreateCompatibleDC.restype = ctypes.wintypes.HDC
CreateCompatibleDC.errcheck = error_check

GetObjectA = gdi32.GetObjectA
GetObjectA.argtypes = [ctypes.wintypes.HBITMAP, ctypes.wintypes.INT, ctypes.wintypes.LPVOID]
GetObjectA.restype = ctypes.wintypes.INT
GetObjectA.errcheck = error_check

GetDIBits = gdi32.GetDIBits
GetDIBits.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HBITMAP, ctypes.wintypes.UINT, ctypes.wintypes.UINT,
                      ctypes.wintypes.LPVOID, ctypes.POINTER(BitmapPlusPalette), ctypes.wintypes.UINT]
GetDIBits.restype = ctypes.wintypes.INT
GetDIBits.errcheck = error_check

DeleteDC = gdi32.DeleteDC
DeleteDC.argtypes = [ctypes.wintypes.HDC]
DeleteDC.restype = ctypes.wintypes.BOOL
DeleteDC.errcheck = error_check

GetCursorInfo = user32.GetCursorInfo
GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
GetCursorInfo.restype = ctypes.wintypes.BOOL
GetCursorInfo.errcheck = error_check

GetIconInfo = user32.GetIconInfo
GetIconInfo.argtypes = [ctypes.wintypes.HICON, ctypes.POINTER(ICONINFO)]
GetIconInfo.restype = ctypes.wintypes.BOOL
GetIconInfo.errcheck = error_check

GetDC = user32.GetDC
GetDC.argtypes = [ctypes.wintypes.HWND]
GetDC.restype = ctypes.wintypes.HDC
GetDC.errcheck = error_check

ReleaseDC = user32.ReleaseDC
ReleaseDC.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC]
ReleaseDC.restype = ctypes.wintypes.INT
ReleaseDC.errcheck = error_check


class Win32CursorCapture(ICursorCapture):
    def __init__(self):
        pass

    def get_cursor_base64_bitmaps(self) -> Tuple[Optional[Base64CursorCapture], Optional[Base64CursorCapture]]:
        cursor_info = CURSORINFO()
        icon_info = ICONINFO()
        cursor_info.cbSize = ctypes.sizeof(cursor_info)
        GetCursorInfo(ctypes.byref(cursor_info))
        if not cursor_info.hCursor:
            return None, None
        GetIconInfo(cursor_info.hCursor, ctypes.byref(icon_info))
        hdc = GetDC(0)
        mask = None
        color = None
        if icon_info.hbmMask:
            mask = self.__get_bitmap(hdc, icon_info.hbmMask)
        if icon_info.hbmColor:
            color = self.__get_bitmap(hdc, icon_info.hbmColor)
        ReleaseDC(0, hdc)
        return mask, color

    def get_cursor_fingerprint(self) -> Optional[bytes]:
        mask, color = self.get_cursor_base64_bitmaps()
        if not mask and not color:
            return None
        md5 = hashlib.md5()
        if mask:
            md5.update(mask.raw_image)
        if color:
            md5.update(color.raw_image)
        return md5.digest()

    @staticmethod
    def __get_bitmap(hdc, hbitmap) -> Base64CursorCapture:
        if not hbitmap or not hdc:
            raise ValueError()
        mem_dc = CreateCompatibleDC(hdc)
        bitmap = BITMAP()
        stored = GetObjectA(hbitmap, ctypes.sizeof(bitmap), ctypes.byref(bitmap))
        assert stored > 0
        buffer_width_bytes = align_size_to_word(bitmap.bmWidthBytes)
        size = buffer_width_bytes * bitmap.bmHeight
        # noinspection PyTypeChecker
        copied_bits = (ctypes.c_ubyte * size)()
        bmi = BitmapPlusPalette()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = bitmap.bmWidth
        bmi.bmiHeader.biHeight = bitmap.bmHeight
        bmi.bmiHeader.biBitCount = bitmap.bmBitsPixel
        bmi.bmiHeader.biPlanes = bitmap.bmPlanes
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = 0
        bmi.bmiHeader.biXPelsPerMeter = 0
        bmi.bmiHeader.biYPelsPerMeter = 0
        bmi.bmiHeader.biClrUsed = 0
        bmi.bmiHeader.biClrImportant = 0
        scan_lines = GetDIBits(mem_dc, hbitmap, 0, bitmap.bmHeight, copied_bits, ctypes.byref(bmi), DIB_RGB_COLORS)
        assert scan_lines > 0
        capture_result = Base64CursorCapture()
        capture_result.bits_per_pixel = bitmap.bmBitsPixel
        capture_result.heigth = scan_lines
        capture_result.width = bitmap.bmWidth
        image_width_bytes = (bitmap.bmWidth * bitmap.bmBitsPixel) >> 3
        # noinspection PyTypeChecker
        unaligned_bits = (ctypes.c_ubyte * (image_width_bytes * bitmap.bmHeight))()
        for y in range(bitmap.bmHeight):
            for x in range(image_width_bytes):
                unaligned_bits[y * image_width_bytes + x] = copied_bits[y * buffer_width_bytes + x]
        capture_result.raw_image = bytes(unaligned_bits)
        DeleteDC(mem_dc)
        return capture_result


if __name__ == '__main__':
    while True:
        capture = Win32CursorCapture()
        _mask, _color = capture.get_cursor_base64_bitmaps()
        if _mask:
            _mask.print_cursor_debug()
        if _color:
            _color.print_cursor_debug()
        h = capture.get_cursor_fingerprint()
        if h:
            print(h)
        time.sleep(5.0)
