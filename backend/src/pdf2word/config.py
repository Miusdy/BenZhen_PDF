from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class OcrMode(str, Enum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class ConversionMode(str, Enum):
    CONTENT_FIRST = "content-first"


class ConversionConfig(BaseModel):
    language: str = "chi_sim+eng"
    mode: ConversionMode = ConversionMode.CONTENT_FIRST
    ocr: OcrMode = OcrMode.AUTO
    dpi: int = Field(default=300, ge=150, le=600)
    review_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    text_quality_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    ocr_confidence_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    disagreement_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    max_workers: int = Field(default=2, ge=1, le=4)
    keep_intermediate: bool = False
    mark_review_in_docx: bool = True
    preserve_images: bool = True
    detect_tables: bool = True
    temp_dir: Path | None = None
    password: str | None = Field(default=None, exclude=True, repr=False)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if not value.strip() or any(ch.isspace() for ch in value):
            raise ValueError("OCR language must use Tesseract codes joined with '+'")
        return value

