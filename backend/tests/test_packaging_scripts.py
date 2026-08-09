from pathlib import Path

import pytest

from build.scripts import macos_bundle_config
from build.scripts.prepare_ocr_vendor import find_models, stage_windows


def test_windows_ocr_staging_copies_runtime_and_license(tmp_path: Path) -> None:
    source = tmp_path / "Tesseract-OCR"
    source.mkdir()
    (source / "tesseract.exe").write_bytes(b"exe")
    (source / "libtesseract.dll").write_bytes(b"dll")
    (source / "uninstall.exe").write_bytes(b"uninstaller")
    (source / "README.txt").write_text("not part of runtime", encoding="utf-8")
    (source / "LICENSE").write_text("Apache-2.0", encoding="utf-8")

    destination = tmp_path / "vendor"
    stage_windows(source / "tesseract.exe", destination)

    assert (destination / "bin" / "tesseract.exe").read_bytes() == b"exe"
    assert (destination / "bin" / "libtesseract.dll").read_bytes() == b"dll"
    assert not (destination / "bin" / "uninstall.exe").exists()
    assert not (destination / "bin" / "README.txt").exists()
    assert (destination / "LICENSES" / "tesseract-LICENSE").read_text() == "Apache-2.0"


def test_ocr_model_discovery_requires_both_languages(tmp_path: Path) -> None:
    (tmp_path / "chi_sim.traineddata").write_bytes(b"chi_sim")
    with pytest.raises(SystemExit, match="eng"):
        find_models([tmp_path])

    (tmp_path / "eng.traineddata").write_bytes(b"eng")
    models = find_models([tmp_path])
    assert set(models) == {"chi_sim", "eng"}


def test_macos_release_rejects_a_runtime_above_supported_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"mach-o")
    output = tmp_path / "bundle-config.json"
    monkeypatch.setattr(
        macos_bundle_config,
        "required_minimum",
        lambda roots, tocs: ("16.0", runtime),
    )

    with pytest.raises(SystemExit, match="exceeding release maximum 15.0"):
        macos_bundle_config.write_config([runtime], [], output, False, "15.0")

    macos_bundle_config.write_config([runtime], [], output, True, "16.0")
    assert '"minimumSystemVersion": "16.0"' in output.read_text(encoding="utf-8")
    assert '"hardenedRuntime": true' in output.read_text(encoding="utf-8")
