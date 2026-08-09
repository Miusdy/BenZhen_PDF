#!/usr/bin/env python3
"""Derive and verify the macOS deployment target from bundled Mach-O files."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

MINOS_PATTERN = re.compile(r"^\s*minos\s+([0-9]+(?:\.[0-9]+){1,2})\s*$", re.MULTILINE)


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def is_mach_o(path: Path) -> bool:
    if not path.is_file():
        return False
    result = subprocess.run(["file", "-b", str(path)], check=True, text=True, capture_output=True)
    return "Mach-O" in result.stdout


def minimum_versions(path: Path) -> list[str]:
    result = subprocess.run(
        ["vtool", "-show-build", str(path)], check=True, text=True, capture_output=True
    )
    return MINOS_PATTERN.findall(result.stdout)


def toc_files(path: Path) -> list[Path]:
    contents = ast.literal_eval(path.read_text(encoding="utf-8"))
    files: list[Path] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            candidate = Path(value)
            if candidate.is_absolute() and candidate.is_file():
                files.append(candidate)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.items():
                visit(item)

    visit(contents)
    return files


def required_minimum(roots: list[Path], tocs: list[Path] | None = None) -> tuple[str, Path]:
    requirements: list[tuple[tuple[int, ...], str, Path]] = []
    candidates: list[Path] = []
    for root in roots:
        candidates.extend([root] if root.is_file() else sorted(root.rglob("*")))
    for toc in tocs or []:
        candidates.extend(toc_files(toc))
    for candidate in candidates:
        if not is_mach_o(candidate):
            continue
        for version in minimum_versions(candidate):
            requirements.append((version_tuple(version), version, candidate))
    if not requirements:
        raise SystemExit("No Mach-O files found in the supplied roots or PyInstaller TOCs")
    _, version, path = max(requirements, key=lambda item: item[0])
    return version, path


def write_config(
    roots: list[Path],
    tocs: list[Path],
    output: Path,
    hardened_runtime: bool,
    maximum: str | None,
) -> None:
    required, source = required_minimum(roots, tocs)
    if maximum and version_tuple(required) > version_tuple(maximum):
        raise SystemExit(
            f"Bundled code requires macOS {required} ({source}), exceeding release maximum {maximum}"
        )
    config = {
        "bundle": {
            "macOS": {
                "minimumSystemVersion": required,
                "hardenedRuntime": hardened_runtime,
            }
        }
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"macOS minimum system version: {required} (from {source.name})")


def verify_app(app: Path) -> None:
    plist = app / "Contents" / "Info.plist"
    result = subprocess.run(
        ["/usr/libexec/PlistBuddy", "-c", "Print :LSMinimumSystemVersion", str(plist)],
        check=True,
        text=True,
        capture_output=True,
    )
    declared = result.stdout.strip()
    required, source = required_minimum([app])
    if version_tuple(required) > version_tuple(declared):
        raise SystemExit(
            f"Bundle declares macOS {declared}, but {source} requires macOS {required}"
        )
    print(f"Verified deployment target: declared {declared}, bundled code requires {required}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    write_parser = subparsers.add_parser("write")
    write_parser.add_argument("--root", type=Path, action="append", required=True)
    write_parser.add_argument("--pyinstaller-toc", type=Path, action="append", default=[])
    write_parser.add_argument("--output", type=Path, required=True)
    write_parser.add_argument("--hardened-runtime", action="store_true")
    write_parser.add_argument("--maximum-macos")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--app", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "write":
        write_config(
            [path.resolve() for path in args.root],
            [path.resolve() for path in args.pyinstaller_toc],
            args.output.resolve(),
            args.hardened_runtime,
            args.maximum_macos,
        )
    else:
        verify_app(args.app.resolve())


if __name__ == "__main__":
    main()
