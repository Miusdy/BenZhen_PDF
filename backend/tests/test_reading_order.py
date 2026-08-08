from pdf2word.models import BoundingBox, ContentBlock
from pdf2word.reading_order import order_blocks


def block(block_id: str, text: str, x: float, y: float) -> ContentBlock:
    return ContentBlock(
        id=block_id,
        type="paragraph",
        text=text,
        source_page=1,
        source_bbox=BoundingBox(x0=x, y0=y, x1=x + 180, y1=y + 20),
    )


def test_two_columns_are_read_top_to_bottom_left_then_right() -> None:
    blocks = [
        block("r2", "右二", 330, 160),
        block("l2", "左二", 50, 160),
        block("r1", "右一", 330, 100),
        block("l1", "左一", 50, 100),
    ]
    assert [item.text for item in order_blocks(blocks, 595)] == ["左一", "左二", "右一", "右二"]

