from pdf2word.models import ExtractionMethod
from pdf2word.text_reconciliation import critical_conflicts, reconcile


def test_critical_amount_and_date_conflict() -> None:
    fields = critical_conflicts(
        "合同 TEST-2026-0808，金额 12,345.67 元，日期 2026-08-08",
        "合同 TEST-2026-0808，金额 12,345.87 元，日期 2026-08-09",
    )
    assert "amount" in fields
    assert "date" in fields


def test_high_quality_original_is_preserved_without_rewrite() -> None:
    result = reconcile("原文不得改写", "识别内容不同", 0.95, 0.99, 0.72, 0.72, 0.82, 0.8)
    assert result.text == "原文不得改写"
    assert result.method == ExtractionMethod.PDF_TEXT
    assert result.needs_review


def test_ocr_replaces_bad_text_layer_with_reason() -> None:
    result = reconcile("���", "可靠 OCR 结果", 0.1, 0.94, 0.72, 0.72, 0.82, 0.8)
    assert result.text == "可靠 OCR 结果"
    assert result.method == ExtractionMethod.OCR
    assert any("切换为 OCR" in reason for reason in result.reasons)
