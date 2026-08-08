from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz.fuzz import ratio

from .models import ExtractionMethod
from .utils import normalize_text

CRITICAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "amount": re.compile(r"(?:¥|￥|USD|RMB)?\s*\d[\d,]*(?:\.\d{1,2})?\s*(?:元|万元|美元)?"),
    "date": re.compile(r"(?:\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{1,2}:\d{2})"),
    "percentage": re.compile(r"\d+(?:\.\d+)?%"),
    "id": re.compile(r"\b\d{17}[\dXx]\b"),
    "phone": re.compile(r"(?<!\d)(?:1\d{10}|0\d{2,3}[- ]?\d{7,8})(?!\d)"),
    "account": re.compile(r"\b\d{12,19}\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "url": re.compile(r"https?://[^\s]+"),
    "clause_or_model": re.compile(r"\b[A-Z]{1,6}[-_/]?\d{2,}[A-Z0-9._/-]*\b|第[一二三四五六七八九十百\d]+条"),
}


def extract_critical_fields(text: str) -> dict[str, set[str]]:
    return {name: set(pattern.findall(text)) for name, pattern in CRITICAL_PATTERNS.items()}


def critical_conflicts(original: str, ocr: str) -> list[str]:
    left = extract_critical_fields(original)
    right = extract_critical_fields(ocr)
    return [name for name in CRITICAL_PATTERNS if left[name] != right[name] and (left[name] or right[name])]


@dataclass(frozen=True)
class ReconciliationResult:
    text: str
    method: ExtractionMethod
    confidence: float
    needs_review: bool
    reasons: list[str]
    critical_fields: list[str]
    similarity: float


def reconcile(
    original: str,
    ocr: str,
    original_quality: float,
    ocr_confidence: float,
    quality_threshold: float,
    ocr_threshold: float,
    disagreement_threshold: float,
    review_threshold: float,
) -> ReconciliationResult:
    original = normalize_text(original)
    ocr = normalize_text(ocr)
    similarity = ratio(original, ocr) / 100.0 if original and ocr else 0.0
    conflicts = critical_conflicts(original, ocr) if original and ocr else []
    reasons: list[str] = []

    if original_quality >= quality_threshold:
        text, method, confidence = original, ExtractionMethod.PDF_TEXT, original_quality
    elif ocr and ocr_confidence >= ocr_threshold:
        text, method, confidence = ocr, ExtractionMethod.OCR, ocr_confidence
        reasons.append("原文字层质量不足，切换为 OCR")
    elif original_quality >= ocr_confidence:
        text, method, confidence = original, ExtractionMethod.PDF_TEXT, original_quality
        reasons.append("两路结果均不可靠，保留较高质量的原文字层")
    else:
        text, method, confidence = ocr, ExtractionMethod.OCR, ocr_confidence
        reasons.append("两路结果均不可靠，保留较高置信度的 OCR")

    if original and ocr and similarity < disagreement_threshold:
        reasons.append(f"原文字层与 OCR 相似度较低（{similarity:.1%}）")
    if conflicts:
        reasons.append("关键内容冲突：" + "、".join(conflicts))
    if not text:
        reasons.append("未获得可用内容")
    needs_review = confidence < review_threshold or bool(conflicts) or bool(
        original and ocr and similarity < disagreement_threshold
    )
    return ReconciliationResult(
        text=text,
        method=method,
        confidence=round(confidence, 4),
        needs_review=needs_review,
        reasons=reasons,
        critical_fields=conflicts,
        similarity=round(similarity, 4),
    )

