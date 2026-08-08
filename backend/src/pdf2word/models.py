from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractionMethod(str, Enum):
    PDF_TEXT = "pdf_text"
    OCR = "ocr"
    RECONCILED = "reconciled"
    NONE = "none"


class PageKind(str, Enum):
    TEXT = "text"
    SCANNED = "scanned"
    MIXED = "mixed"
    GARBLED = "garbled"
    BLANK = "blank"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_sequence(cls, values: list[float] | tuple[float, float, float, float]) -> BoundingBox:
        return cls(x0=values[0], y0=values[1], x1=values[2], y1=values[3])


class Character(BaseModel):
    text: str
    bbox: BoundingBox
    font: str = ""
    size: float = 0.0
    flags: int = 0


class TextLine(BaseModel):
    text: str
    bbox: BoundingBox
    characters: list[Character] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    issue_type: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    page: int
    bbox: BoundingBox | None = None
    message: str
    current_text: str = ""
    original_text: str = ""
    ocr_text: str = ""
    confidence: float = 0.0
    critical_fields: list[str] = Field(default_factory=list)


class ContentBlock(BaseModel):
    id: str
    type: Literal["paragraph", "heading", "list", "table", "image", "footnote", "header", "footer"]
    text: str = ""
    source_page: int
    source_bbox: BoundingBox
    method: ExtractionMethod = ExtractionMethod.NONE
    confidence: float = 0.0
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    original_text: str = ""
    ocr_text: str = ""
    lines: list[TextLine] = Field(default_factory=list)
    style: dict[str, Any] = Field(default_factory=dict)
    table_rows: list[list[str]] = Field(default_factory=list)
    image_path: str | None = None


class PageResult(BaseModel):
    page_number: int
    width: float
    height: float
    kind: PageKind
    quality_score: float
    quality_reasons: list[str] = Field(default_factory=list)
    blocks: list[ContentBlock] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
    used_ocr: bool = False
    text_character_count: int = 0
    image_count: int = 0


class DocumentMetadata(BaseModel):
    input_path: str
    input_name: str
    file_sha256: str
    total_pages: int
    encrypted: bool = False
    title: str = ""
    author: str = ""


class DocumentIR(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    schema_version: str = "1.0.0"
    metadata: DocumentMetadata
    pages: list[PageResult] = Field(default_factory=list)
    issues: list[ReviewIssue] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversionSummary(BaseModel):
    input_file: str
    file_sha256: str
    total_pages: int
    processed_pages: int
    text_pages: int
    ocr_pages: int
    mixed_pages: int
    blank_pages: int
    low_confidence_blocks: int
    garbled_pages: int
    critical_conflicts: int
    table_count: int
    image_count: int
    review_issue_count: int
    overall_confidence: float
    elapsed_seconds: float
    status: JobStatus
    quality_gate_passed: bool
    output_docx: str | None = None
    intermediate_path: str | None = None
    error: str | None = None


class PreflightResult(BaseModel):
    input_path: str
    input_name: str
    file_size: int
    total_pages: int
    encrypted: bool
    has_text_layer: bool
    estimated_scan_pages: int
    estimated_ocr_pages: int
    estimated_seconds: int
    estimated_temp_bytes: int


class ProgressEvent(BaseModel):
    type: Literal["progress", "page_complete", "review_issue", "error", "complete"]
    job_id: str
    stage: str
    current_page: int = 0
    total_pages: int = 0
    progress: float = 0.0
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


def write_json_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DocumentIR.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
