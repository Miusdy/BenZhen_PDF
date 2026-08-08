$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $ProjectRoot
$Target = "x86_64-pc-windows-msvc"
& "$ProjectRoot\.venv\Scripts\python.exe" build\scripts\build_sidecar.py --target $Target --require-ocr
New-Item -ItemType Directory -Force frontend\src-tauri\resources\tesseract | Out-Null
Copy-Item -Recurse -Force "build\vendor\tesseract\$Target\*" frontend\src-tauri\resources\tesseract\
Set-Location frontend
pnpm tauri build --target $Target

