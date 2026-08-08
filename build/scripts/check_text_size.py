#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".pyi", ".json", ".toml", ".yaml", ".yml", ".ts", ".tsx", ".js",
    ".jsx", ".css", ".html", ".rs", ".sh", ".ps1", ".xml", ".csv", ".svg", ".lock",
}
IGNORED = {".git", ".venv", "node_modules", "dist", "target", ".pytest_cache", "tmp"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--limit-mb", type=int, default=100)
    args = parser.parse_args()
    limit = args.limit_mb * 1024 * 1024
    oversized: list[tuple[Path, int]] = []
    for path in Path(args.root).resolve().rglob("*"):
        if not path.is_file() or any(part in IGNORED for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size > limit:
            oversized.append((path, path.stat().st_size))
    if oversized:
        for path, size in oversized:
            print(f"{size / 1024 / 1024:.2f} MB\t{path}")
        raise SystemExit(1)
    print(f"OK: no text file exceeds {args.limit_mb} MB")


if __name__ == "__main__":
    main()

