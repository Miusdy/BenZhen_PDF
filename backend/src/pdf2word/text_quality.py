from __future__ import annotations

import math
import unicodedata
from collections import Counter

from .utils import normalize_text


def _ratio(count: int, total: int) -> float:
    return count / max(total, 1)


def score_text(text: str, visible_area_ratio: float = 0.0) -> tuple[float, list[str]]:
    text = normalize_text(text)
    if not text:
        reasons = ["未提取到文字"]
        if visible_area_ratio > 0.15:
            reasons.append("页面可见内容较多但文字层为空")
        return 0.0, reasons

    chars = [ch for ch in text if not ch.isspace()]
    total = len(chars)
    replacement = sum(ch == "�" for ch in chars)
    private_use = sum(unicodedata.category(ch) == "Co" for ch in chars)
    control = sum(unicodedata.category(ch) in {"Cc", "Cf"} for ch in chars)
    valid = sum(
        ch.isalnum() or unicodedata.category(ch).startswith("P") or "\u4e00" <= ch <= "\u9fff"
        for ch in chars
    )
    repeats = max(Counter(chars).values(), default=0)

    penalties: list[tuple[float, str]] = []
    if replacement:
        penalties.append((min(0.5, _ratio(replacement, total) * 4), "包含 Unicode 替换字符"))
    if private_use:
        penalties.append((min(0.5, _ratio(private_use, total) * 3), "私用区字符比例异常"))
    if control:
        penalties.append((min(0.35, _ratio(control, total) * 5), "包含异常控制字符"))
    invalid_ratio = 1.0 - _ratio(valid, total)
    if invalid_ratio > 0.2:
        penalties.append((min(0.35, invalid_ratio), "字母、数字、中文和标点比例异常"))
    if total >= 30 and _ratio(repeats, total) > 0.45:
        penalties.append((0.25, "疑似大量重复字符"))
    if visible_area_ratio > 0.30 and total < 15:
        penalties.append((0.35, "页面可见内容很多但提取文字过少"))

    length_bonus = min(0.12, math.log10(total + 1) * 0.05)
    score = max(0.0, min(1.0, 0.90 + length_bonus - sum(value for value, _ in penalties)))
    return round(score, 4), [reason for _, reason in penalties]

