import tempfile
import time
from typing import Optional

import cv2.cv2 as cv2
import numpy as np
import pytesseract
from PIL.Image import Image
from pytesseract import Output

from rka.components.cleanup import CleanupManager
from rka.components.io.log_service import LogService
from rka.components.ui.capture import Capture
from rka.components.ui.iocrservice import IOCRService
from rka.eq2.shared.flags import MutableFlags
from rka.log_configs import LOG_CAPTURING

logger = LogService(LOG_CAPTURING)


# noinspection PyMethodMayBeStatic
class TesseractOCR(IOCRService):
    def __init__(self):
        self.debug_preparing_steps = False
        self.debug_preparing_result = False
        self.save_original_images = True
        self.save_prepared_images = True

    def convert_image(self, image) -> np.ndarray:
        if isinstance(image, Image):
            image = np.asarray(image)
        elif isinstance(image, Capture):
            image = image.get_array()
        assert isinstance(image, np.ndarray), image
        return image

    def show_image(self, image):
        image = self.convert_image(image)
        cv2.imshow('show_capture', image)
        cv2.moveWindow('show_capture', 100, 50)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def get_temp_filename_and_make_dir(self, info, ext) -> str:
        import os  # werid it has to be imported
        filename = os.path.join(tempfile.gettempdir(), 'tesseract', f'ocr_{int(time.time())}_{info}_{ext}.png')
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return filename

    def save_image(self, image, info):
        filename = self.get_temp_filename_and_make_dir(info, 'saved')
        cv2.imwrite(filename, image)

    def save_image_to_temp(self, orig_image: np.ndarray, prepared_image: np.ndarray, info: Optional[str] = None):
        if MutableFlags.SAVE_OCR_IMAGES:
            import os  # werid it has to be imported
            if self.save_original_images:
                filename = self.get_temp_filename_and_make_dir(info, 'orig')
                cv2.imwrite(filename, orig_image)
            if self.save_prepared_images:
                filename = self.get_temp_filename_and_make_dir(info, 'prepared')
                cv2.imwrite(filename, orig_image)
        if self.debug_preparing_result and not self.debug_preparing_steps:
            self.show_image(prepared_image)

    def show_image_prepare_step(self, image: np.ndarray):
        if self.debug_preparing_steps:
            self.show_image(image)

    def prepare_image_autoinvert_to_black_text(self, image: np.ndarray) -> np.ndarray:
        # if image is mostly dark - invert it (black text preferred)
        img_sum = np.sum(image, axis=(0, 1))
        mid_gray_sum = image.size * 128
        if img_sum < mid_gray_sum:
            image = 255 - image
        self.show_image_prepare_step(image)
        return image

    def prepare_image_invert_to_black_text(self, image: np.ndarray, font_color: Optional[int] = None) -> np.ndarray:
        if font_color is None:
            # try to autodetect font color - it is expected that bacgkround will cover most of area
            return self.prepare_image_autoinvert_to_black_text(image)
        elif font_color <= 10:
            # already blackish
            return image
        elif font_color >= 245:
            # is white, just invert
            image = 255 - image
        else:
            # not really expected
            logger.warn(f'Gray font color - autoinvert: {font_color}')
            return self.prepare_image_autoinvert_to_black_text(image)
        self.show_image_prepare_step(image)
        return image

    def prepare_image_grayscale(self, bgr_image: np.ndarray) -> np.ndarray:
        image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
        self.show_image_prepare_step(image)
        return image

    def prepare_image_upscale(self, image: np.ndarray, scale=3.0) -> np.ndarray:
        # larger image works better for OCR
        image = cv2.resize(image, (0, 0), fx=scale, fy=scale, interpolation=None)
        self.show_image_prepare_step(image)
        return image

    def prepare_image_bordered(self, image: np.ndarray, border=3, color=255) -> np.ndarray:
        # tesseract bugs out if text touches edges
        bg_image = np.zeros((image.shape[0] + border * 2, image.shape[1] + border * 2), np.uint8) + color
        np.copyto(bg_image[border:-border, border:-border], image)
        self.show_image_prepare_step(bg_image)
        return bg_image

    def prepare_image_binary_threshold(self, image: np.ndarray, th_value=0) -> np.ndarray:
        mode = cv2.THRESH_OTSU if not th_value else 0
        image = cv2.threshold(image, th_value, 255, cv2.THRESH_BINARY + mode)[1]
        self.show_image_prepare_step(image)
        return image

    def prepare_image_erode_noise(self, image: np.ndarray, kernel_size=4, iters=3) -> np.ndarray:
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        image = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel, iterations=iters)
        self.show_image_prepare_step(image)
        return image

    def prepare_image_add_contour(self, image: np.ndarray) -> np.ndarray:
        cnts = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        for c in cnts:
            cv2.drawContours(image, [c], -1, 255, thickness=1)
        self.show_image_prepare_step(image)
        return image

    def prepare_image_mask_white_level(self, image: np.ndarray, whitelevel=180) -> np.ndarray:
        h, w, z = image.shape
        for y in range(h):
            for x in range(w):
                c = image[y, x].astype(np.int32)
                if c[0] < whitelevel or c[1] < whitelevel or c[2] < whitelevel:
                    image[y, x] = [0, 0, 0]
                    continue
        self.show_image_prepare_step(image)
        return image

    def prepare_image_mask_white_distance(self, image: np.ndarray, whiterange=15) -> np.ndarray:
        h, w, z = image.shape
        for y in range(h):
            for x in range(w):
                c = image[y, x].astype(np.int32)
                if abs(c[0] - c[1]) > whiterange or abs(c[0] - c[2]) > whiterange or abs(c[1] - c[2]) > whiterange:
                    image[y, x] = [0, 0, 0]
                    continue
        self.show_image_prepare_step(image)
        return image

    def modify_image_add_bounding_boxes(self, image: np.ndarray, ocred_data) -> np.ndarray:
        n_boxes = len(ocred_data['level'])
        for i in range(n_boxes):
            (x, y, w, h) = (ocred_data['left'][i], ocred_data['top'][i], ocred_data['width'][i], ocred_data['height'][i])
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        self.show_image_prepare_step(image)
        return image

    def ocr_normal_line_of_text_no_bg(self, orig_image, info: Optional[str] = None, lang: Optional[str] = None, chars: Optional[str] = None,
                                      font_color: Optional[int] = None) -> str:
        orig_image = self.convert_image(orig_image)
        image = orig_image.copy()
        image = self.prepare_image_grayscale(image)
        image = self.prepare_image_invert_to_black_text(image, font_color=font_color)
        # image = self.prepare_image_upscale(image)
        image = self.prepare_image_bordered(image)
        self.save_image_to_temp(orig_image, image, info)
        config = '--psm 7'
        if chars:
            config += f' -c tessedit_char_whitelist={chars}'
        ocred_string = pytesseract.image_to_string(image, lang=lang, config=config)
        return ocred_string.strip()

    def ocr_tiny_text_no_bg(self, orig_image, info: Optional[str] = None, lang: Optional[str] = None, chars: Optional[str] = None,
                            font_color: Optional[int] = None) -> str:
        orig_image = self.convert_image(orig_image)
        image = orig_image.copy()
        image = self.prepare_image_grayscale(image)
        image = self.prepare_image_invert_to_black_text(image, font_color=font_color)
        image = self.prepare_image_upscale(image, scale=8.0)
        image = self.prepare_image_bordered(image)
        self.save_image_to_temp(orig_image, image, info)
        config = '--psm 7'
        if chars:
            config += f' -c tessedit_char_whitelist={chars}'
        ocred_string = pytesseract.image_to_string(image, lang=lang, config=config)
        return ocred_string.strip()

    def ocr_single_digit_with_bg_noise(self, orig_image, info: Optional[str] = None, lang: Optional[str] = None,
                                       font_color: Optional[int] = None) -> Optional[int]:
        orig_image = self.convert_image(orig_image)
        image = orig_image.copy()
        # image = self.prepare_image_upscale(image, scale=10.0)
        image = self.prepare_image_mask_white_distance(image, 20)
        image = self.prepare_image_mask_white_level(image, 200)
        image = self.prepare_image_grayscale(image)
        # image = self.prepare_image_upscale(image, scale=3.0)
        # image = self.prepare_image_erode_noise(image, kernel_size=3, iters=4)
        image = self.prepare_image_invert_to_black_text(image, font_color=font_color)
        image = self.prepare_image_bordered(image, border=10)
        # image = self.prepare_image_add_contour(image)
        config = '--psm 10 -c tessedit_char_whitelist=0123456789'
        ocred_data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT, config=config)
        # image = self.modify_image_add_bounding_boxes(image, ocred_data)
        self.save_image_to_temp(orig_image, image, info)
        all_digits = [int(number_str) for number_str in ocred_data['text'] if number_str]
        if not all_digits:
            return None
        return all_digits[0]


if __name__ == '__main__':
    # MutableFlags.SAVE_OCR_IMAGES.true()

    import os

    # temp_path = 'D:\\storage\\temp\\tesseract\\test'
    # ocr_files = [os.path.join(temp_path, f) for f in os.listdir(temp_path) if os.path.isfile(os.path.join(temp_path, f))
    #              and f.startswith('ocr_')
    #              and f.endswith('_orig.png')]
    # ocr_files = [os.path.join(temp_path, 'font\\new one.png')]
    # ocr_files = [os.path.join(temp_path, '1.png')]
    # ocr_files = [os.path.join(temp_path, f) for f in os.listdir(temp_path) if os.path.isfile(os.path.join(temp_path, f))]
    ocr_ = TesseractOCR()
    ocr_.debug_preparing_steps = False
    ocr_.debug_preparing_result = False
    ocr_.save_original_images = False
    ocr_.save_prepared_images = False
    # print(ocr.get_temp_filename_and_make_dir(0, 'x'))
    # for f in ocr_files:
    #     img = cv2.imread(f)
    #     text = ocr.ocr_tiny_text_no_bg(img, chars='/0123456789')
    #     print(f'TEXT is: "{text}" from {f}')

    CleanupManager.close_all()
