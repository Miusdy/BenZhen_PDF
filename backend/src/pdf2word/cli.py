from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .config import ConversionConfig, ConversionMode, OcrMode
from .models import JobStatus, ProgressEvent
from .pipeline import ConversionPipeline, preflight_pdf

app = typer.Typer(
    name="pdf2word",
    help="内容保真优先、全程本地处理的 PDF 转 Word 工具。",
    add_completion=False,
    no_args_is_help=True,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="显示版本号"),
    ] = False,
) -> None:
    del version


@app.command("convert")
def convert(
    input_pdf: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("-o", "--output", help="输出 DOCX 路径")],
    language: Annotated[str, typer.Option("--language")] = "chi_sim+eng",
    mode: Annotated[ConversionMode, typer.Option("--mode")] = ConversionMode.CONTENT_FIRST,
    ocr: Annotated[OcrMode, typer.Option("--ocr")] = OcrMode.AUTO,
    dpi: Annotated[int, typer.Option("--dpi", min=150, max=600)] = 300,
    review_threshold: Annotated[
        float, typer.Option("--review-threshold", min=0.0, max=1.0)
    ] = 0.80,
    keep_intermediate: Annotated[bool, typer.Option("--keep-intermediate")] = False,
    password: Annotated[
        str | None, typer.Option("--password", prompt=False, hide_input=True, help="PDF 密码")
    ] = None,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
) -> None:
    """将 INPUT_PDF 转换为可编辑 DOCX。"""
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO)

    def progress(event: ProgressEvent) -> None:
        if not quiet and event.type in {"progress", "page_complete"}:
            typer.echo(f"[{event.current_page}/{event.total_pages}] {event.message}", err=True)

    config = ConversionConfig(
        language=language,
        mode=mode,
        ocr=ocr,
        dpi=dpi,
        review_threshold=review_threshold,
        keep_intermediate=keep_intermediate,
        password=password,
    )
    summary = ConversionPipeline(config=config, progress=progress).convert(
        input_pdf, output
    )
    typer.echo(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if summary.status != JobStatus.SUCCESS:
        raise typer.Exit(code=2 if summary.status == JobStatus.CANCELLED else 1)


@app.command("preflight")
def preflight(
    input_pdf: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
    password: Annotated[str | None, typer.Option("--password", hide_input=True)] = None,
) -> None:
    """快速检查 PDF 页数、文字层与预计 OCR 开销。"""
    typer.echo(preflight_pdf(input_pdf, password).model_dump_json(indent=2))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] not in {"convert", "preflight", "--help", "-h", "--version"}:
        sys.argv.insert(1, "convert")
    app()


if __name__ == "__main__":
    main()
