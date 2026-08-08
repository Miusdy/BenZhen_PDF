from __future__ import annotations

import html
import json
from pathlib import Path

from .models import ConversionSummary, DocumentIR, ReviewIssue


def report_payload(document: DocumentIR, summary: ConversionSummary) -> dict[str, object]:
    return {
        "schema_version": document.schema_version,
        "summary": summary.model_dump(mode="json"),
        "metadata": document.metadata.model_dump(mode="json"),
        "issues": [issue.model_dump(mode="json") for issue in document.issues],
        "pages": [page.model_dump(mode="json") for page in document.pages],
    }


def write_json_report(document: DocumentIR, summary: ConversionSummary, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_payload(document, summary), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _issue_row(issue: ReviewIssue) -> str:
    bbox = issue.bbox
    coordinate = (
        f"{bbox.x0:.1f}, {bbox.y0:.1f}, {bbox.x1:.1f}, {bbox.y1:.1f}" if bbox else "整页"
    )
    return (
        "<tr>"
        f"<td>{issue.page}</td>"
        f"<td>{html.escape(issue.issue_type)}</td>"
        f"<td>{html.escape(issue.severity)}</td>"
        f"<td>{html.escape(issue.message)}</td>"
        f"<td>{issue.confidence:.1%}</td>"
        f"<td>{html.escape(coordinate)}</td>"
        f"<td><pre>{html.escape(issue.current_text)}</pre></td>"
        f"<td><pre>{html.escape(issue.original_text)}</pre></td>"
        f"<td><pre>{html.escape(issue.ocr_text)}</pre></td>"
        "</tr>"
    )


def write_html_report(document: DocumentIR, summary: ConversionSummary, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(_issue_row(issue) for issue in document.issues) or (
        '<tr><td colspan="9" class="empty">没有发现需要人工核对的问题</td></tr>'
    )
    status = html.escape(summary.status.value if hasattr(summary.status, "value") else str(summary.status))
    html_document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PDF 转 Word 检查报告</title><style>
:root{{--ink:#152338;--muted:#667085;--line:#d9e0e8;--teal:#088c93;--amber:#b56d00;}}
body{{font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink);margin:0;background:#fff}}
main{{max-width:1180px;margin:0 auto;padding:42px 28px 72px}} h1{{font-size:28px;margin:0 0 6px}} .sub{{color:var(--muted)}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border-block:1px solid var(--line);margin:28px 0}}
.metric{{padding:18px 10px}} .metric strong{{display:block;font-size:24px}} .metric span{{color:var(--muted)}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}
th{{background:#f6f8fa;position:sticky;top:0}} pre{{white-space:pre-wrap;max-width:260px;margin:0;font:12px/1.45 ui-monospace,monospace}}
.warn{{color:var(--amber)}} .empty{{padding:36px;text-align:center;color:var(--muted)}}
</style></head><body><main><h1>PDF 转 Word 检查报告</h1>
<p class="sub">{html.escape(document.metadata.input_name)} · SHA-256 {document.metadata.file_sha256} · 状态 {status}</p>
<section class="summary">
<div class="metric"><strong>{summary.total_pages}</strong><span>总页数</span></div>
<div class="metric"><strong>{summary.ocr_pages}</strong><span>OCR 页数</span></div>
<div class="metric"><strong>{summary.review_issue_count}</strong><span>核对问题</span></div>
<div class="metric"><strong>{summary.critical_conflicts}</strong><span>关键内容冲突</span></div>
<div class="metric"><strong>{summary.overall_confidence:.1%}</strong><span>总体可信度</span></div>
<div class="metric"><strong>{summary.elapsed_seconds:.2f}s</strong><span>处理耗时</span></div>
</section><h2>问题清单</h2><table><thead><tr><th>页</th><th>类型</th><th>风险</th><th>说明</th><th>置信度</th><th>坐标</th><th>当前内容</th><th>原文字层</th><th>OCR</th></tr></thead>
<tbody>{rows}</tbody></table></main></body></html>"""
    path.write_text(html_document, encoding="utf-8")
    return path
