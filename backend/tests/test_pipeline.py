from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document
from pdf2word.config import ConversionConfig, OcrMode
from pdf2word.errors import EncryptedPdfError
from pdf2word.models import JobStatus
from pdf2word.pipeline import ConversionPipeline, JobControl, preflight_pdf

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def generate_fixtures() -> None:
    subprocess.run([sys.executable, str(ROOT / "build/scripts/generate_fixtures.py")], check=True)


def test_preflight_text_and_scan() -> None:
    text = preflight_pdf(FIXTURES / "中文 路径-文字与表格.pdf")
    scan = preflight_pdf(FIXTURES / "scanned-invoice.pdf")
    assert text.total_pages == 3 and text.has_text_layer
    assert scan.total_pages == 1 and scan.estimated_ocr_pages == 1


def test_text_pdf_to_docx(tmp_path: Path) -> None:
    output = tmp_path / "中文 输出.docx"
    config = ConversionConfig(ocr=OcrMode.NEVER, keep_intermediate=True)
    summary = ConversionPipeline(config).convert(
        FIXTURES / "中文 路径-文字与表格.pdf", output
    )
    assert summary.status == JobStatus.SUCCESS
    assert summary.processed_pages == summary.total_pages == 3
    assert output.exists()
    document = Document(output)
    all_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "TEST-2026-0808" in all_text
    assert "12,345.67" in all_text
    assert "原 PDF 第" not in all_text
    assert "[来源：PDF" not in all_text


def test_scan_without_ocr_is_flagged_not_silently_lost(tmp_path: Path) -> None:
    output = tmp_path / "scan.docx"
    summary = ConversionPipeline(ConversionConfig(ocr=OcrMode.AUTO)).convert(
        FIXTURES / "scanned-invoice.pdf", output
    )
    assert summary.status == JobStatus.SUCCESS
    assert summary.review_issue_count >= 1


def test_encrypted_pdf_requires_password() -> None:
    with pytest.raises(EncryptedPdfError):
        preflight_pdf(FIXTURES / "encrypted.pdf")
    result = preflight_pdf(FIXTURES / "encrypted.pdf", "test-password")
    assert result.total_pages == 3


def test_cancel_does_not_create_success_docx(tmp_path: Path) -> None:
    control = JobControl()
    control.cancel()
    output = tmp_path / "cancelled.docx"
    summary = ConversionPipeline(ConversionConfig(ocr=OcrMode.NEVER), control=control).convert(
        FIXTURES / "中文 路径-文字与表格.pdf", output
    )
    assert summary.status == JobStatus.CANCELLED
    assert not output.exists()
