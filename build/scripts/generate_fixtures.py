#!/usr/bin/env python3
"""Generate synthetic, privacy-safe PDF fixtures used by tests and examples."""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def add_text(page: fitz.Page, point: tuple[float, float], text: str, size: float = 11) -> None:
    page.insert_text(point, text, fontsize=size, fontname="china-s")


def add_common(page: fitz.Page, number: int) -> None:
    add_text(page, (50, 28), "本真 PDF 无隐私测试夹具", 8)
    add_text(page, (280, 815), f"第 {number} 页", 8)


def create_text_document(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    add_common(page, 1)
    add_text(page, (60, 90), "项目验收说明", 22)
    add_text(page, (60, 135), "本文件仅用于自动化测试，不包含任何真实个人或业务信息。", 12)
    add_text(page, (60, 170), "合同编号：TEST-2026-0808", 11)
    add_text(page, (60, 195), "金额：人民币 12,345.67 元", 11)
    add_text(page, (60, 220), "日期：2026-08-08，完成率：98.5%", 11)
    add_text(page, (60, 260), "1. 所有内容必须来源于原 PDF。", 11)
    add_text(page, (60, 285), "2. 无法确认时必须标记需要人工核对。", 11)

    page = doc.new_page(width=595, height=842)
    add_common(page, 2)
    add_text(page, (60, 85), "测试数据表", 18)
    x_positions = [60, 250, 410, 535]
    y_positions = [120, 155, 190, 225]
    for x in x_positions:
        page.draw_line((x, y_positions[0]), (x, y_positions[-1]), color=(0, 0, 0), width=0.7)
    for y in y_positions:
        page.draw_line((x_positions[0], y), (x_positions[-1], y), color=(0, 0, 0), width=0.7)
    cells = [
        (70, 144, "项目"), (260, 144, "数量"), (420, 144, "状态"),
        (70, 179, "文字页"), (260, 179, "2"), (420, 179, "通过"),
        (70, 214, "扫描页"), (260, 214, "1"), (420, 214, "需 OCR"),
    ]
    for x, y, text in cells:
        add_text(page, (x, y), text, 10)

    page = doc.new_page(width=595, height=842)
    add_common(page, 3)
    add_text(page, (60, 85), "双栏阅读顺序", 18)
    for row, text in enumerate(["左栏第一段。", "左栏第二段。", "左栏第三段。"]):
        add_text(page, (60, 135 + row * 46), text, 11)
    for row, text in enumerate(["右栏第一段。", "右栏第二段。", "右栏第三段。"]):
        add_text(page, (330, 135 + row * 46), text, 11)
    doc.save(path)
    doc.close()


def create_scanned_document(path: Path) -> None:
    source = fitz.open()
    page = source.new_page(width=595, height=842)
    add_text(page, (70, 110), "扫描页测试", 24)
    add_text(page, (70, 165), "Invoice TEST-2026-0808", 14)
    add_text(page, (70, 200), "Amount: 999.50 CNY", 14)
    pixmap = page.get_pixmap(dpi=180, alpha=False)
    png = pixmap.tobytes("png")
    source.close()
    scanned = fitz.open()
    target = scanned.new_page(width=595, height=842)
    target.insert_image(target.rect, stream=png)
    scanned.save(path)
    scanned.close()


def create_mixed_document(path: Path, scan_path: Path) -> None:
    text_doc = fitz.open()
    page = text_doc.new_page(width=595, height=842)
    add_text(page, (60, 100), "混合文档文字页", 20)
    add_text(page, (60, 150), "Page one text layer is available.", 12)
    scan_doc = fitz.open(scan_path)
    image_page = scan_doc[0].get_pixmap(dpi=150, alpha=False).tobytes("png")
    second = text_doc.new_page(width=595, height=842)
    second.insert_image(second.rect, stream=image_page)
    text_doc.save(path)
    scan_doc.close()
    text_doc.close()


def create_blank(path: Path) -> None:
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    doc.close()


def create_encrypted(source: Path, path: Path) -> None:
    reader = PdfReader(source)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.encrypt("test-password")
    with path.open("wb") as stream:
        writer.write(stream)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    text = FIXTURES / "中文 路径-文字与表格.pdf"
    scan = FIXTURES / "scanned-invoice.pdf"
    create_text_document(text)
    create_scanned_document(scan)
    create_mixed_document(FIXTURES / "mixed-text-scan.pdf", scan)
    create_blank(FIXTURES / "blank-page.pdf")
    create_encrypted(text, FIXTURES / "encrypted.pdf")
    print(f"Generated fixtures in {FIXTURES}")


if __name__ == "__main__":
    main()
