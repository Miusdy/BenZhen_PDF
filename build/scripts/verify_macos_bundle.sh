#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <app-path> <dmg-path>" >&2
  exit 2
fi

APP_PATH="$1"
DMG_PATH="$2"

test -d "$APP_PATH"
test -f "$DMG_PATH"

verify_app() {
  local candidate="$1"
  local tesseract_root="$candidate/Contents/Resources/resources/tesseract"
  local main_binary="$candidate/Contents/MacOS/benzhen-pdf"
  local sidecar_binary="$candidate/Contents/MacOS/pdf2word-sidecar"
  test -x "$main_binary"
  test -x "$sidecar_binary"
  test -x "$tesseract_root/bin/tesseract"
  test -f "$tesseract_root/tessdata/chi_sim.traineddata"
  test -f "$tesseract_root/tessdata/eng.traineddata"
  codesign --verify --deep --strict --verbose=4 "$candidate"
  python3 build/scripts/macos_bundle_config.py verify --app "$candidate"
  local expected_architecture
  expected_architecture="$(uname -m)"
  for binary in "$main_binary" "$sidecar_binary" "$tesseract_root/bin/tesseract"; do
    local architectures
    architectures="$(lipo -archs "$binary")"
    grep -qw "$expected_architecture" <<<"$architectures"
  done
  local bundle_version
  bundle_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$candidate/Contents/Info.plist")"
  test -n "$bundle_version"
  local languages
  languages="$("$tesseract_root/bin/tesseract" --tessdata-dir "$tesseract_root/tessdata" --list-langs 2>&1)"
  grep -qx "chi_sim" <<<"$languages"
  grep -qx "eng" <<<"$languages"
}

verify_app "$APP_PATH"
hdiutil verify "$DMG_PATH"

MOUNT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/benzhen-dmg-verify.XXXXXX")"
cleanup() {
  hdiutil detach "$MOUNT_ROOT" >/dev/null 2>&1 || true
  rmdir "$MOUNT_ROOT" >/dev/null 2>&1 || true
}
trap cleanup EXIT
hdiutil attach -readonly -nobrowse -mountpoint "$MOUNT_ROOT" "$DMG_PATH" >/dev/null
MOUNTED_APP="$(find "$MOUNT_ROOT" -maxdepth 1 -name '*.app' -print -quit)"
test -n "$MOUNTED_APP"
verify_app "$MOUNTED_APP"

echo "Verified app, DMG, code signature, architecture-native executables, and OCR runtime."
