from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.replace("\u00a0", " "))
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def safe_stem(path: Path) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", path.stem).strip() or "document"


def redact_for_log(text: str, limit: int = 0) -> str:
    if not text:
        return ""
    return f"<{len(text)} characters>" if limit <= 0 else text[:limit]

