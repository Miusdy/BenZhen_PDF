from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from .config import ConversionConfig, OcrMode
from .docx_writer import write_docx
from .errors import ConversionCancelled, OcrUnavailableError
from .models import (
    BoundingBox,
    ContentBlock,
    ConversionSummary,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    JobStatus,
    PageKind,
    PageResult,
    PreflightResult,
    ProgressEvent,
    ReviewIssue,
)
from .ocr_engine import TesseractOcrEngine
from .page_classifier import classify_page
from .pdf_reader import PdfReader
from .reading_order import mark_repeating_headers_and_footers, order_blocks
from .structure_detection import refine_structure
from .text_quality import score_text
from .text_reconciliation import reconcile
from .utils import sha256_file

LOGGER = logging.getLogger("pdf2word")
ProgressCallback = Callable[[ProgressEvent], None]


class JobControl:
    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._running = threading.Event()
        self._running.set()

    def cancel(self) -> None:
        self._cancelled.set()
        self._running.set()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def checkpoint(self) -> None:
        if self._cancelled.is_set():
            raise ConversionCancelled("任务已取消")
        self._running.wait()
        if self._cancelled.is_set():
            raise ConversionCancelled("任务已取消")


def preflight_pdf(path: Path, password: str | None = None) -> PreflightResult:
    path = path.expanduser().resolve()
    with PdfReader(path, password) as reader:
        sampled = range(min(reader.page_count, 20))
        scan_count = 0
        text_count = 0
        for index in sampled:
            text = reader.plain_text(index)
            quality, _ = score_text(text, reader.image_area_ratio(index))
            if text.strip() and quality >= 0.72:
                text_count += 1
            else:
                scan_count += 1
        factor = reader.page_count / max(len(list(sampled)), 1)
        estimated_scan = min(reader.page_count, round(scan_count * factor))
        has_text = text_count > 0
        size = path.stat().st_size
        return PreflightResult(
            input_path=str(path),
            input_name=path.name,
            file_size=size,
            total_pages=reader.page_count,
            encrypted=reader.document.needs_pass,
            has_text_layer=has_text,
            estimated_scan_pages=estimated_scan,
            estimated_ocr_pages=estimated_scan,
            estimated_seconds=max(1, estimated_scan * 4 + reader.page_count),
            estimated_temp_bytes=max(size * 3, estimated_scan * 4_000_000),
        )


class ConversionPipeline:
    def __init__(
        self,
        config: ConversionConfig | None = None,
        progress: ProgressCallback | None = None,
        control: JobControl | None = None,
        job_id: str | None = None,
    ) -> None:
        self.config = config or ConversionConfig()
        self.progress = progress
        self.control = control or JobControl()
        self.job_id = job_id or str(uuid.uuid4())
        self.ocr = TesseractOcrEngine(self.config.language)

    def _emit(
        self,
        event_type: str,
        stage: str,
        current: int,
        total: int,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.progress:
            self.progress(
                ProgressEvent(
                    type=event_type,  # type: ignore[arg-type]
                    job_id=self.job_id,
                    stage=stage,
                    current_page=current,
                    total_pages=total,
                    progress=current / max(total, 1),
                    message=message,
                    payload=payload or {},
                )
            )

    def _state_directory(self, output: Path, digest: str) -> Path:
        if self.config.temp_dir:
            root = self.config.temp_dir.expanduser().resolve()
        else:
            root = output.parent / ".pdf2word-state"
        return root / digest[:16]

    def _config_fingerprint(self) -> dict[str, object]:
        return self.config.model_dump(mode="json", exclude={"password", "temp_dir"})

    def _load_cached_page(self, state_dir: Path, digest: str, page_number: int) -> PageResult | None:
        manifest_path = state_dir / "manifest.json"
        page_path = state_dir / f"page-{page_number}.json"
        if not manifest_path.exists() or not page_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("file_sha256") != digest or manifest.get("config") != self._config_fingerprint():
                return None
            return PageResult.model_validate_json(page_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def _save_state(self, state_dir: Path, digest: str, page: PageResult, total: int) -> None:
        state_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "1.0.0",
            "file_sha256": digest,
            "config": self._config_fingerprint(),
            "total_pages": total,
            "last_completed_page": page.page_number,
            "status": "running",
        }
        (state_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (state_dir / f"page-{page.page_number}.json").write_text(
            page.model_dump_json(indent=2), encoding="utf-8"
        )

    def _issue_for_block(
        self,
        block: ContentBlock,
        issue_type: str,
        message: str,
        severity: str = "medium",
        critical_fields: list[str] | None = None,
    ) -> ReviewIssue:
        return ReviewIssue(
            issue_type=issue_type,
            severity=severity,  # type: ignore[arg-type]
            page=block.source_page,
            bbox=block.source_bbox,
            message=message,
            current_text=block.text,
            original_text=block.original_text,
            ocr_text=block.ocr_text,
            confidence=block.confidence,
            critical_fields=critical_fields or [],
        )

    def _process_page(self, reader: PdfReader, index: int, state_dir: Path) -> PageResult:
        page = reader.page(index)
        original = reader.plain_text(index)
        image_ratio = reader.image_area_ratio(index)
        quality, reasons = score_text(original, image_ratio)
        kind = classify_page(original, quality, image_ratio, reader.drawing_count(index), self.config)
        use_ocr = self.config.ocr == OcrMode.ALWAYS or (
            self.config.ocr == OcrMode.AUTO
            and kind in {PageKind.SCANNED, PageKind.GARBLED}
        )
        ocr_text = ""
        ocr_confidence = 0.0
        issues: list[ReviewIssue] = []
        if use_ocr:
            self._emit("progress", "ocr", index + 1, reader.page_count, f"正在识别第 {index + 1} 页")
            try:
                rendered = reader.render(index, self.config.dpi)
                ocr_result = self.ocr.recognize(rendered)
                rendered.close()
                ocr_text, ocr_confidence = ocr_result.text, ocr_result.confidence
            except OcrUnavailableError as exc:
                if not original.strip():
                    block = ContentBlock(
                        id=f"p{index + 1}-ocr-unavailable",
                        type="paragraph",
                        text="",
                        source_page=index + 1,
                        source_bbox=BoundingBox(x0=0, y0=0, x1=page.rect.width, y1=page.rect.height),
                        method=ExtractionMethod.NONE,
                        confidence=0,
                        needs_review=True,
                        review_reasons=[str(exc)],
                        original_text=original,
                    )
                    issues.append(self._issue_for_block(block, "ocr_unavailable", str(exc), "high"))
                use_ocr = False

        blocks: list[ContentBlock]
        if use_ocr:
            reconciled = reconcile(
                original,
                ocr_text,
                quality,
                ocr_confidence,
                self.config.text_quality_threshold,
                self.config.ocr_confidence_threshold,
                self.config.disagreement_threshold,
                self.config.review_threshold,
            )
            block = ContentBlock(
                id=f"p{index + 1}-reconciled",
                type="paragraph",
                text=reconciled.text,
                source_page=index + 1,
                source_bbox=BoundingBox(x0=0, y0=0, x1=page.rect.width, y1=page.rect.height),
                method=reconciled.method,
                confidence=reconciled.confidence,
                needs_review=reconciled.needs_review,
                review_reasons=reconciled.reasons,
                original_text=original,
                ocr_text=ocr_text,
            )
            blocks = [block] if block.text else []
            if block.needs_review:
                severity = "critical" if reconciled.critical_fields else "high"
                issue_type = "critical_content_conflict" if reconciled.critical_fields else "text_disagreement"
                issues.append(
                    self._issue_for_block(
                        block,
                        issue_type,
                        "；".join(reconciled.reasons),
                        severity,
                        reconciled.critical_fields,
                    )
                )
        else:
            blocks = reader.extract_blocks(index)
            for block in blocks:
                block.confidence = quality
                block.needs_review = quality < self.config.review_threshold
                block.review_reasons = reasons.copy()
                if block.needs_review:
                    issues.append(
                        self._issue_for_block(
                            block, "low_text_quality", "；".join(reasons) or "文字层质量低", "high"
                        )
                    )

        if self.config.detect_tables and not use_ocr:
            tables = reader.extract_tables(index)
            if tables:
                table_boxes = [table.source_bbox for table in tables]
                blocks = [
                    block
                    for block in blocks
                    if not any(
                        block.source_bbox.x0 >= box.x0
                        and block.source_bbox.y0 >= box.y0
                        and block.source_bbox.x1 <= box.x1
                        and block.source_bbox.y1 <= box.y1
                        for box in table_boxes
                    )
                ] + tables

        if self.config.preserve_images and kind in {PageKind.TEXT, PageKind.MIXED}:
            blocks.extend(reader.extract_images(index, state_dir / "images"))
        blocks = refine_structure(order_blocks(blocks, page.rect.width), page.rect.height)
        if kind == PageKind.BLANK:
            blocks = []
        if not blocks and kind != PageKind.BLANK:
            issue = ReviewIssue(
                issue_type="missing_page_content",
                severity="critical",
                page=index + 1,
                bbox=BoundingBox(x0=0, y0=0, x1=page.rect.width, y1=page.rect.height),
                message="页面存在可见内容但未获得可用文字，未静默忽略",
                confidence=0,
            )
            issues.append(issue)
        return PageResult(
            page_number=index + 1,
            width=page.rect.width,
            height=page.rect.height,
            kind=kind,
            quality_score=quality,
            quality_reasons=reasons,
            blocks=blocks,
            issues=issues,
            used_ocr=use_ocr,
            text_character_count=len(original),
            image_count=len(page.get_images(full=True)),
        )

    def convert(
        self,
        input_path: Path,
        output_docx: Path,
    ) -> ConversionSummary:
        started = time.monotonic()
        input_path = input_path.expanduser().resolve()
        output_docx = output_docx.expanduser().resolve()
        digest = sha256_file(input_path)
        state_dir = self._state_directory(output_docx, digest)
        status = JobStatus.RUNNING
        document: DocumentIR | None = None
        error: str | None = None
        try:
            with PdfReader(input_path, self.config.password) as reader:
                metadata = reader.metadata
                document = DocumentIR(
                    metadata=DocumentMetadata(
                        input_path=str(input_path),
                        input_name=input_path.name,
                        file_sha256=digest,
                        total_pages=reader.page_count,
                        encrypted=reader.document.needs_pass,
                        title=str(metadata.get("title") or ""),
                        author=str(metadata.get("author") or ""),
                    )
                )
                for index in range(reader.page_count):
                    self.control.checkpoint()
                    cached = self._load_cached_page(state_dir, digest, index + 1)
                    page = cached or self._process_page(reader, index, state_dir)
                    self.control.checkpoint()
                    document.pages.append(page)
                    document.issues.extend(page.issues)
                    if cached is None:
                        self._save_state(state_dir, digest, page, reader.page_count)
                    self._emit(
                        "page_complete",
                        "page_complete",
                        index + 1,
                        reader.page_count,
                        f"第 {index + 1} 页处理完成",
                        {"issues": len(page.issues), "kind": page.kind.value},
                    )
                mark_repeating_headers_and_footers(
                    [page.blocks for page in document.pages], [page.height for page in document.pages]
                )
                self.control.checkpoint()
                write_docx(document, output_docx, self.config.mark_review_in_docx)
                status = JobStatus.SUCCESS
        except ConversionCancelled as exc:
            status, error = JobStatus.CANCELLED, str(exc)
        except Exception as exc:
            LOGGER.exception("Conversion failed for %s", input_path.name)
            status, error = JobStatus.FAILED, str(exc)

        if document is None:
            document = DocumentIR(
                metadata=DocumentMetadata(
                    input_path=str(input_path),
                    input_name=input_path.name,
                    file_sha256=digest,
                    total_pages=0,
                )
            )
        elapsed = time.monotonic() - started
        confidences = [block.confidence for page in document.pages for block in page.blocks if block.type != "image"]
        summary = ConversionSummary(
            input_file=input_path.name,
            file_sha256=digest,
            total_pages=document.metadata.total_pages,
            processed_pages=len(document.pages),
            text_pages=sum(page.kind == PageKind.TEXT for page in document.pages),
            ocr_pages=sum(page.used_ocr for page in document.pages),
            mixed_pages=sum(page.kind == PageKind.MIXED for page in document.pages),
            blank_pages=sum(page.kind == PageKind.BLANK for page in document.pages),
            low_confidence_blocks=sum(
                block.confidence < self.config.review_threshold
                for page in document.pages
                for block in page.blocks
                if block.type != "image"
            ),
            garbled_pages=sum(page.kind == PageKind.GARBLED for page in document.pages),
            critical_conflicts=sum(issue.severity == "critical" for issue in document.issues),
            table_count=sum(block.type == "table" for page in document.pages for block in page.blocks),
            image_count=sum(page.image_count for page in document.pages),
            review_issue_count=len(document.issues),
            overall_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            elapsed_seconds=round(elapsed, 3),
            status=status,
            quality_gate_passed=status == JobStatus.SUCCESS
            and not any(issue.severity == "critical" for issue in document.issues),
            output_docx=str(output_docx) if status == JobStatus.SUCCESS else None,
            intermediate_path=str(state_dir) if state_dir.exists() else None,
            error=error,
        )
        final_event_type = {
            JobStatus.SUCCESS: "complete",
            JobStatus.CANCELLED: "cancelled",
        }.get(status, "error")
        self._emit(
            final_event_type,
            "complete",
            len(document.pages),
            document.metadata.total_pages,
            "转换完成" if status == JobStatus.SUCCESS else (error or "转换未完成"),
            summary.model_dump(mode="json"),
        )
        if status == JobStatus.SUCCESS and not self.config.keep_intermediate:
            shutil.rmtree(state_dir, ignore_errors=True)
            summary.intermediate_path = None
        return summary


def convert_pdf(
    input_path: Path,
    output_docx: Path,
    config: ConversionConfig | None = None,
) -> ConversionSummary:
    return ConversionPipeline(config=config).convert(input_path, output_docx)
