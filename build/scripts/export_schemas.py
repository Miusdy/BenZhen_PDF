#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from pdf2word.models import DocumentIR, PreflightResult, ProgressEvent

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "shared" / "schema"


def main() -> None:
    SCHEMA.mkdir(parents=True, exist_ok=True)
    for name, model in {
        "document-ir.schema.json": DocumentIR,
        "preflight.schema.json": PreflightResult,
        "progress-event.schema.json": ProgressEvent,
    }.items():
        (SCHEMA / name).write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

