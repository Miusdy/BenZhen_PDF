from __future__ import annotations

from statistics import median

from .models import ContentBlock


def order_blocks(blocks: list[ContentBlock], page_width: float) -> list[ContentBlock]:
    text_blocks = [block for block in blocks if block.type != "image"]
    if len(text_blocks) < 3:
        return sorted(blocks, key=lambda block: (block.source_bbox.y0, block.source_bbox.x0))

    centers = [(block.source_bbox.x0 + block.source_bbox.x1) / 2 for block in text_blocks]
    left = [value for value in centers if value < page_width / 2]
    right = [value for value in centers if value >= page_width / 2]
    narrow = [block for block in text_blocks if (block.source_bbox.x1 - block.source_bbox.x0) < page_width * 0.62]
    two_columns = len(left) >= 2 and len(right) >= 2 and len(narrow) / len(text_blocks) >= 0.6
    if not two_columns:
        return sorted(blocks, key=lambda block: (block.source_bbox.y0, block.source_bbox.x0))

    split = median(centers)
    spanning = [block for block in blocks if (block.source_bbox.x1 - block.source_bbox.x0) >= page_width * 0.62]
    columns = [block for block in blocks if block not in spanning]
    ordered_spanning = sorted(spanning, key=lambda block: block.source_bbox.y0)
    top_spanning = [block for block in ordered_spanning if block.source_bbox.y0 < min(b.source_bbox.y0 for b in columns)]
    bottom_spanning = [block for block in ordered_spanning if block not in top_spanning]
    left_blocks = sorted(
        [block for block in columns if (block.source_bbox.x0 + block.source_bbox.x1) / 2 <= split],
        key=lambda block: block.source_bbox.y0,
    )
    right_blocks = sorted(
        [block for block in columns if (block.source_bbox.x0 + block.source_bbox.x1) / 2 > split],
        key=lambda block: block.source_bbox.y0,
    )
    return top_spanning + left_blocks + right_blocks + bottom_spanning


def mark_repeating_headers_and_footers(pages: list[list[ContentBlock]], page_heights: list[float]) -> None:
    if len(pages) < 3:
        return
    candidates: dict[str, list[ContentBlock]] = {}
    for blocks, height in zip(pages, page_heights, strict=True):
        for block in blocks:
            normalized = " ".join(block.text.split())
            if normalized and (block.source_bbox.y0 < height * 0.10 or block.source_bbox.y1 > height * 0.90):
                candidates.setdefault(normalized, []).append(block)
    threshold = max(2, round(len(pages) * 0.5))
    for repeated in candidates.values():
        if len({block.source_page for block in repeated}) >= threshold:
            for block in repeated:
                block.type = "header" if block.source_bbox.y0 < page_heights[block.source_page - 1] * 0.10 else "footer"
