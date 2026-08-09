#!/usr/bin/env python3
"""Stage a relocatable Tesseract runtime for an installer build.

The script intentionally consumes an already installed, platform-native Tesseract
distribution. It never downloads unpinned binaries by itself. On macOS it copies
and rewrites non-system dylib dependencies so the staged executable does not
depend on Homebrew paths on the destination Mac.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ("chi_sim", "eng")


def run(*command: str) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def copy_licenses(source: Path, destination: Path, label: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    patterns = ("LICENSE*", "COPYING*", "NOTICE*")
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in source.glob(pattern) if path.is_file())
    for path in sorted(set(found)):
        shutil.copy2(path, destination / f"{label}-{path.name}")


def cellar_root(path: Path) -> tuple[Path, str] | None:
    parts = path.resolve().parts
    try:
        index = parts.index("Cellar")
        formula = parts[index + 1]
        version_root = Path(*parts[: index + 3])
    except (ValueError, IndexError):
        return None
    return version_root, formula


def mac_dependency_entries(binary: Path) -> list[tuple[str, Path]]:
    output = run("otool", "-L", str(binary))
    dependencies: list[tuple[str, Path]] = []
    for line in output.splitlines()[1:]:
        value = line.strip().split(" (compatibility", 1)[0]
        if not value or value.startswith(("/usr/lib/", "/System/")):
            continue
        if value.startswith("@rpath/"):
            path = binary.resolve().parent / value.removeprefix("@rpath/")
        elif value.startswith("@loader_path/"):
            path = binary.resolve().parent / value.removeprefix("@loader_path/")
        elif value.startswith("@executable_path/"):
            path = binary.resolve().parent / value.removeprefix("@executable_path/")
        else:
            path = Path(value)
        if path.is_file():
            dependencies.append((value, path.resolve()))
    return dependencies


def mac_dependencies(binary: Path) -> list[Path]:
    return [resolved for _, resolved in mac_dependency_entries(binary)]


def sign_macos_binary(binary: Path) -> None:
    identity = os.environ.get("APPLE_SIGNING_IDENTITY") or "-"
    command = ["codesign", "--force", "--sign", identity]
    if identity != "-":
        command.extend(["--options", "runtime", "--timestamp"])
    command.append(str(binary))
    subprocess.run(command, check=True)


def stage_macos(executable: Path, destination: Path) -> None:
    bin_dir = destination / "bin"
    lib_dir = destination / "lib"
    license_dir = destination / "LICENSES"
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    staged_executable = bin_dir / "tesseract"
    shutil.copy2(executable, staged_executable)

    queue = [executable.resolve()]
    dependencies: dict[Path, Path] = {}
    while queue:
        current = queue.pop()
        for dependency in mac_dependencies(current):
            if dependency in dependencies:
                continue
            target = lib_dir / dependency.name
            if target.exists() and not target.samefile(dependency):
                raise SystemExit(f"Conflicting dylib basename: {dependency.name}")
            shutil.copy2(dependency, target)
            dependencies[dependency] = target
            queue.append(dependency)

    originals_by_name = {source.name: source for source in dependencies}
    for source, target in dependencies.items():
        target.chmod(target.stat().st_mode | 0o200)
        subprocess.run(
            ["install_name_tool", "-id", f"@loader_path/{target.name}", str(target)],
            check=True,
        )
        for old_load_path, old_dependency in mac_dependency_entries(source):
            if old_dependency.name in originals_by_name:
                subprocess.run(
                    [
                        "install_name_tool",
                        "-change",
                        old_load_path,
                        f"@loader_path/{old_dependency.name}",
                        str(target),
                    ],
                    check=True,
                )
        sign_macos_binary(target)

    staged_executable.chmod(staged_executable.stat().st_mode | 0o200)
    for old_load_path, dependency in mac_dependency_entries(executable):
        if dependency.name in originals_by_name:
            subprocess.run(
                [
                    "install_name_tool",
                    "-change",
                    old_load_path,
                    f"@executable_path/../lib/{dependency.name}",
                    str(staged_executable),
                ],
                check=True,
            )
    sign_macos_binary(staged_executable)

    roots: set[tuple[Path, str]] = set()
    for path in [executable, *dependencies]:
        root = cellar_root(path)
        if root:
            roots.add(root)
    for root, formula in sorted(roots, key=lambda item: item[1]):
        copy_licenses(root, license_dir, formula)


def stage_windows(executable: Path, destination: Path) -> None:
    bin_dir = destination / "bin"
    license_dir = destination / "LICENSES"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, bin_dir / executable.name)
    for path in executable.parent.glob("*.dll"):
        shutil.copy2(path, bin_dir / path.name)
    copy_licenses(executable.parent, license_dir, "tesseract")


def find_tesseract(explicit: Path | None) -> Path:
    if explicit:
        candidate = explicit.expanduser().resolve()
        if candidate.is_file():
            return candidate
        raise SystemExit(f"Tesseract executable not found: {candidate}")
    located = shutil.which("tesseract")
    if located:
        return Path(located).resolve()
    if os.name == "nt":
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(variable)
            if base:
                candidate = Path(base) / "Tesseract-OCR" / "tesseract.exe"
                if candidate.is_file():
                    return candidate.resolve()
    raise SystemExit("Tesseract executable not found; pass --tesseract explicitly")


def find_models(directories: list[Path]) -> dict[str, Path]:
    models: dict[str, Path] = {}
    for directory in directories:
        directory = directory.expanduser().resolve()
        for language in LANGUAGES:
            candidate = directory / f"{language}.traineddata"
            if candidate.is_file():
                models[language] = candidate
    missing = sorted(set(LANGUAGES) - models.keys())
    if missing:
        raise SystemExit("Missing OCR language models: " + ", ".join(missing))
    return models


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--tesseract", type=Path)
    parser.add_argument("--tessdata-dir", type=Path, action="append", default=[])
    args = parser.parse_args()

    executable = find_tesseract(args.tesseract)
    inferred_tessdata = executable.parent.parent / "share" / "tessdata"
    search_directories = [*args.tessdata_dir]
    if inferred_tessdata.is_dir():
        search_directories.append(inferred_tessdata)
    if os.name == "nt" and (executable.parent / "tessdata").is_dir():
        search_directories.append(executable.parent / "tessdata")
    models = find_models(search_directories)

    destination = ROOT / "build" / "vendor" / "tesseract" / args.target
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    if sys.platform == "darwin":
        stage_macos(executable, destination)
    elif os.name == "nt":
        stage_windows(executable, destination)
    else:
        raise SystemExit(f"Unsupported platform for installer OCR staging: {sys.platform}")

    tessdata = destination / "tessdata"
    tessdata.mkdir()
    for source in models.values():
        shutil.copy2(source, tessdata / source.name)

    staged_executable = destination / "bin" / ("tesseract.exe" if os.name == "nt" else "tesseract")
    language_output = run(
        str(staged_executable),
        "--tessdata-dir",
        str(tessdata),
        "--list-langs",
    )
    for language in LANGUAGES:
        if language not in language_output.splitlines():
            raise SystemExit(f"Staged OCR runtime cannot load language: {language}")
    print(destination)


if __name__ == "__main__":
    main()
