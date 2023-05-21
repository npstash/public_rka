from typing import Optional


class IOCRService:
    def ocr_normal_line_of_text_no_bg(self, orig_image, info: Optional[str] = None, lang: Optional[str] = None, chars: Optional[str] = None,
                                      font_color: Optional[int] = None) -> str:
        raise NotImplementedError()

    def ocr_tiny_text_no_bg(self, orig_image, info: Optional[str] = None, lang: Optional[str] = None, chars: Optional[str] = None,
                            font_color: Optional[int] = None) -> str:
        raise NotImplementedError()

    def ocr_single_digit_with_bg_noise(self, image, info: Optional[str] = None, lang: Optional[str] = None,
                                       font_color: Optional[int] = None) -> Optional[int]:
        raise NotImplementedError()

    def show_image(self, image):
        raise NotImplementedError()

    def save_image(self, image, info):
        raise NotImplementedError()
