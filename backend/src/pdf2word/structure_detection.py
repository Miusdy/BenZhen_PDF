from __future__ import annotations

import re

from .models import ContentBlock


def refine_structure(blocks: list[ContentBlock], page_height: float) -> list[ContentBlock]:
    for block in blocks:
        text = block.text.strip()
        if block.source_bbox.y1 > page_height * 0.90 and re.fullmatch(r"第?\s*\d+\s*页?", text):
            block.type = "footer"
            continue
        if block.type == "paragraph" and re.match(r"^(?:[一二三四五六七八九十]+、|\d+[.)、])", text):
            block.type = "list"
        if block.type == "paragraph" and block.source_bbox.y1 > page_height * 0.88:
            font_size = float(block.style.get("font_size", 11.0))
            if font_size <= 9.5:
                block.type = "footnote"
    return blocks
