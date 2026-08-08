#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"
TARGET="${1:-$(rustc -vV | awk '/host:/ {print $2}')}"
"$PROJECT_ROOT/.venv/bin/python" build/scripts/build_sidecar.py --target "$TARGET" --require-ocr
mkdir -p frontend/src-tauri/resources/tesseract
cp -R "build/vendor/tesseract/$TARGET/." frontend/src-tauri/resources/tesseract/
cd frontend
pnpm tauri build --target "$TARGET"

