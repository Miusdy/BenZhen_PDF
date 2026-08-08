from pathlib import Path

from docx import Document
from pdf2word.docx_writer import write_docx
from pdf2word.models import (
    BoundingBox,
    ContentBlock,
    DocumentIR,
    DocumentMetadata,
    PageKind,
    PageResult,
)
from PIL import Image


def test_tall_image_is_fitted_to_page_without_inline_source_note(tmp_path: Path) -> None:
    image_path = tmp_path / "tall.png"
    Image.new("RGB", (600, 2400), "#dff7f6").save(image_path, dpi=(96, 96))
    block = ContentBlock(
        id="p1-image1",
        type="image",
        source_page=1,
        source_bbox=BoundingBox(x0=10, y0=10, x1=200, y1=700),
        image_path=str(image_path),
    )
    document_ir = DocumentIR(
        metadata=DocumentMetadata(
            input_path="fixture.pdf",
            input_name="fixture.pdf",
            file_sha256="0" * 64,
            total_pages=1,
        ),
        pages=[
            PageResult(
                page_number=1,
                width=595,
                height=842,
                kind=PageKind.MIXED,
                quality_score=1.0,
                blocks=[block],
                image_count=1,
            )
        ],
    )
    output = write_docx(document_ir, tmp_path / "fitted.docx")
    rendered = Document(output)

    assert len(rendered.inline_shapes) == 1
    assert rendered.inline_shapes[0].width.inches <= 5.8
    assert rendered.inline_shapes[0].height.inches <= 7.0
    assert "[来源：PDF" not in "\n".join(paragraph.text for paragraph in rendered.paragraphs)
