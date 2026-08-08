from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    array = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 11
    )
    return Image.fromarray(binary)

