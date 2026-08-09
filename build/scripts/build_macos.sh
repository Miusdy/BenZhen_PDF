#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"
TARGET="${1:-$(rustc -vV | awk '/host:/ {print $2}')}"
VENDOR_ROOT="build/vendor/tesseract/$TARGET"
export APPLE_SIGNING_IDENTITY="-"
"$PROJECT_ROOT/.venv/bin/python" build/scripts/build_sidecar.py --target "$TARGET" --require-ocr
mkdir -p frontend/src-tauri/resources/tesseract
cp -R "$VENDOR_ROOT/." frontend/src-tauri/resources/tesseract/
BUNDLE_CONFIG="$PROJECT_ROOT/frontend/src-tauri/target/benzhen-$TARGET.conf.json"
CONFIG_ARGS=(
  write
  --root "$VENDOR_ROOT"
  --root "$PROJECT_ROOT/frontend/src-tauri/binaries/pdf2word-sidecar-$TARGET"
  --pyinstaller-toc "$PROJECT_ROOT/build/pdf2word-sidecar/Analysis-00.toc"
  --output "$BUNDLE_CONFIG"
)
if [[ -n "${BENZHEN_MAXIMUM_MACOS:-}" ]]; then
  CONFIG_ARGS+=(--maximum-macos "$BENZHEN_MAXIMUM_MACOS")
fi
"$PROJECT_ROOT/.venv/bin/python" build/scripts/macos_bundle_config.py "${CONFIG_ARGS[@]}"
cd frontend
TAURI_ARGS=(build --target "$TARGET" --config "$BUNDLE_CONFIG")
pnpm tauri "${TAURI_ARGS[@]}"
