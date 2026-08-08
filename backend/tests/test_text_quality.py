from pdf2word.text_quality import score_text


def test_normal_multilingual_text_scores_high() -> None:
    score, reasons = score_text("项目 TEST-2026 金额 12,345.67 元")
    assert score >= 0.8
    assert reasons == []


def test_replacement_and_private_use_are_reported() -> None:
    score, reasons = score_text("正常文字���\ue000\ue001\ue002")
    assert score < 0.8
    assert "包含 Unicode 替换字符" in reasons
    assert "私用区字符比例异常" in reasons


def test_empty_visible_page_is_not_silent() -> None:
    score, reasons = score_text("", visible_area_ratio=0.8)
    assert score == 0
    assert "页面可见内容较多但文字层为空" in reasons

