# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

project_root = Path(SPECPATH).parents[1]
vendor_target = os.environ.get("PDF2WORD_VENDOR_TARGET", "")
vendor_root = project_root / "build" / "vendor" / "tesseract" / vendor_target
signing_identity = os.environ.get("APPLE_SIGNING_IDENTITY")
if signing_identity in {None, "", "-"}:
    signing_identity = None
datas = []
binaries = []

if vendor_root.exists():
    for item in vendor_root.rglob("*"):
        if item.is_file():
            relative = item.relative_to(vendor_root)
            destination = str(Path("tesseract") / relative.parent)
            if "bin" in relative.parts or "lib" in relative.parts:
                binaries.append((str(item), destination))
            else:
                datas.append((str(item), destination))

analysis = Analysis(
    [str(project_root / "build" / "pyinstaller" / "sidecar_entry.py")],
    pathex=[str(project_root / "backend" / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pytesseract", "cv2", "rapidfuzz", "docx", "pymupdf"],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="pdf2word-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    codesign_identity=signing_identity,
)
