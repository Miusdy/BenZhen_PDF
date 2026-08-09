from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Literal

import pymupdf as fitz
from PIL import Image
from typing_extensions import Self

from .errors import EncryptedPdfError, Pdf2WordError
from .models import BoundingBox, Character, ContentBlock, ExtractionMethod, TextLine


class PdfReader:
    def __init__(self, path: Path, password: str | None = None) -> None:
        self.path = path
        try:
            self.document = fitz.open(path)
        except Exception as exc:
            raise Pdf2WordError(f"无法打开 PDF：{exc}") from exc
        if self.document.needs_pass and not (password and self.document.authenticate(password)):
            self.document.close()
            raise EncryptedPdfError("PDF 已加密，请提供正确密码")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.document.close()

    @property
    def page_count(self) -> int:
        return self.document.page_count

    @property
    def metadata(self) -> dict[str, Any]:
        return self.document.metadata or {}

    def page(self, index: int) -> fitz.Page:
        return self.document.load_page(index)

    def text_dict(self, index: int) -> dict[str, Any]:
        return self.page(index).get_text("rawdict", sort=False)

    def plain_text(self, index: int) -> str:
        return self.page(index).get_text("text", sort=True)

    def image_area_ratio(self, index: int) -> float:
        page = self.page(index)
        page_area = max(page.rect.width * page.rect.height, 1.0)
        area = 0.0
        for image in page.get_images(full=True):
            xref = image[0]
            for rect in page.get_image_rects(xref):
                area += max(rect.width, 0) * max(rect.height, 0)
        return min(1.0, area / page_area)

    def drawing_count(self, index: int) -> int:
        return len(self.page(index).get_drawings())

    def render(self, index: int, dpi: int) -> Image.Image:
        pixmap = self.page(index).get_pixmap(dpi=dpi, alpha=False, colorspace=fitz.csRGB)
        return Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")

    def extract_blocks(self, index: int) -> list[ContentBlock]:
        page = self.page(index)
        raw = page.get_text("rawdict", sort=False)
        block_results: list[ContentBlock] = []
        font_sizes: list[float] = []
        prepared: list[tuple[dict[str, Any], list[TextLine], float, bool, bool]] = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines: list[TextLine] = []
            sizes: list[float] = []
            bold = False
            italic = False
            for line in block.get("lines", []):
                chars: list[Character] = []
                parts: list[str] = []
                for span in line.get("spans", []):
                    sizes.append(float(span.get("size", 0)))
                    font = str(span.get("font", ""))
                    flags = int(span.get("flags", 0))
                    bold = bold or bool(flags & 16) or "bold" in font.lower()
                    italic = italic or bool(flags & 2) or "italic" in font.lower()
                    for char in span.get("chars", []):
                        value = str(char.get("c", ""))
                        parts.append(value)
                        chars.append(
                            Character(
                                text=value,
                                bbox=BoundingBox.from_sequence(char.get("bbox", [0, 0, 0, 0])),
                                font=font,
                                size=float(span.get("size", 0)),
                                flags=flags,
                            )
                        )
                line_text = "".join(parts).strip()
                if line_text:
                    lines.append(
                        TextLine(
                            text=line_text,
                            bbox=BoundingBox.from_sequence(line.get("bbox", block.get("bbox"))),
                            characters=chars,
                        )
                    )
            if not lines:
                continue
            avg_size = sum(sizes) / max(len(sizes), 1)
            font_sizes.append(avg_size)
            prepared.append((block, lines, avg_size, bold, italic))

        body_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 11.0
        for ordinal, (block, lines, avg_size, bold, italic) in enumerate(prepared):
            text = "\n".join(line.text for line in lines)
            block_type: Literal["paragraph", "heading", "list"] = "paragraph"
            heading_level = 0
            if avg_size >= body_size * 1.35 and len(text) <= 150:
                block_type = "heading"
                heading_level = 1 if avg_size >= body_size * 1.75 else 2
            elif text.lstrip().startswith(("•", "·", "-", "–")) or any(
                text.lstrip().startswith(f"{n}.") for n in range(1, 10)
            ):
                block_type = "list"
            bbox = BoundingBox.from_sequence(block.get("bbox", [0, 0, page.rect.width, 0]))
            block_results.append(
                ContentBlock(
                    id=f"p{index + 1}-b{ordinal + 1}",
                    type=block_type,
                    text=text,
                    source_page=index + 1,
                    source_bbox=bbox,
                    method=ExtractionMethod.PDF_TEXT,
                    confidence=1.0,
                    original_text=text,
                    lines=lines,
                    style={
                        "font_size": round(avg_size, 2),
                        "bold": bold,
                        "italic": italic,
                        "heading_level": heading_level,
                    },
                )
            )
        return block_results

    def extract_tables(self, index: int) -> list[ContentBlock]:
        page = self.page(index)
        if not hasattr(page, "find_tables"):
            return []
        try:
            finder = page.find_tables()
        except Exception:
            return []
        results: list[ContentBlock] = []
        for ordinal, table in enumerate(finder.tables):
            rows = [[cell or "" for cell in row] for row in table.extract()]
            if not rows:
                continue
            results.append(
                ContentBlock(
                    id=f"p{index + 1}-t{ordinal + 1}",
                    type="table",
                    text="\n".join("\t".join(row) for row in rows),
                    source_page=index + 1,
                    source_bbox=BoundingBox.from_sequence(table.bbox),
                    method=ExtractionMethod.PDF_TEXT,
                    confidence=0.92,
                    original_text="\n".join("\t".join(row) for row in rows),
                    table_rows=rows,
                    style={"detected_by": "pymupdf"},
                )
            )
        return results

    def extract_images(self, index: int, directory: Path) -> list[ContentBlock]:
        directory.mkdir(parents=True, exist_ok=True)
        page = self.page(index)
        results: list[ContentBlock] = []
        for ordinal, image in enumerate(page.get_images(full=True)):
            xref = image[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            try:
                payload = self.document.extract_image(xref)
                extension = payload.get("ext", "png")
                path = directory / f"page-{index + 1}-image-{ordinal + 1}.{extension}"
                path.write_bytes(payload["image"])
            except Exception:
                continue
            rect = rects[0]
            results.append(
                ContentBlock(
                    id=f"p{index + 1}-i{ordinal + 1}",
                    type="image",
                    source_page=index + 1,
                    source_bbox=BoundingBox.from_sequence((rect.x0, rect.y0, rect.x1, rect.y1)),
                    method=ExtractionMethod.PDF_TEXT,
                    confidence=1.0,
                    image_path=str(path),
                )
            )
        return results
