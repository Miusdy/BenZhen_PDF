from __future__ import annotations

from .config import ConversionConfig
from .models import PageKind


def classify_page(
    text: str,
    quality: float,
    image_area_ratio: float,
    drawing_count: int,
    config: ConversionConfig,
) -> PageKind:
    stripped = text.strip()
    if not stripped and image_area_ratio < 0.01 and drawing_count == 0:
        return PageKind.BLANK
    if not stripped and image_area_ratio >= 0.10:
        return PageKind.SCANNED
    if quality < config.text_quality_threshold:
        return PageKind.GARBLED
    if stripped and image_area_ratio >= 0.20:
        return PageKind.MIXED
    return PageKind.TEXT

