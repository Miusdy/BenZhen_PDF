#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def default_target() -> str:
    machine = platform.machine().lower()
    if platform.system() == "Darwin":
        return "aarch64-apple-darwin" if machine in {"arm64", "aarch64"} else "x86_64-apple-darwin"
    if platform.system() == "Windows":
        return "x86_64-pc-windows-msvc"
    return "x86_64-unknown-linux-gnu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=default_target())
    parser.add_argument("--require-ocr", action="store_true")
    args = parser.parse_args()
    vendor = ROOT / "build" / "vendor" / "tesseract" / args.target
    if args.require_ocr:
        tessdata = vendor / "tessdata"
        executable = vendor / "bin" / ("tesseract.exe" if "windows" in args.target else "tesseract")
        expected = [executable, tessdata / "chi_sim.traineddata", tessdata / "eng.traineddata"]
        if not all(path.exists() for path in expected):
            missing = ", ".join(str(path) for path in expected if not path.exists())
            raise SystemExit(f"Missing OCR runtime files: {missing}")
    build_environment = dict(os.environ)
    build_environment["PDF2WORD_VENDOR_TARGET"] = args.target
    build_environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / ".pyinstaller-cache")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(ROOT / "build/pyinstaller/pdf2word-sidecar.spec"),
        ],
        cwd=ROOT,
        env=build_environment,
        check=True,
    )
    suffix = ".exe" if "windows" in args.target else ""
    source = ROOT / "dist" / f"pdf2word-sidecar{suffix}"
    destination = ROOT / "frontend" / "src-tauri" / "binaries" / f"pdf2word-sidecar-{args.target}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(destination)


if __name__ == "__main__":
    main()
