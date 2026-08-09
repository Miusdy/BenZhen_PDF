param(
    [string]$Target = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$Sidecar = Join-Path $ProjectRoot "frontend\src-tauri\binaries\pdf2word-sidecar-$Target.exe"
$TesseractRoot = Join-Path $ProjectRoot "frontend\src-tauri\resources\tesseract"
$Tesseract = Join-Path $TesseractRoot "bin\tesseract.exe"
$Tessdata = Join-Path $TesseractRoot "tessdata"
$BundleRoot = Join-Path $ProjectRoot "frontend\src-tauri\target\$Target\release\bundle"

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required bundle file is missing: $Path"
    }
}

function Assert-X64Pe([string]$Path) {
    $Bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($Bytes.Length -lt 64) { throw "Invalid PE executable: $Path" }
    $PeOffset = [BitConverter]::ToInt32($Bytes, 0x3C)
    if ($PeOffset -lt 0 -or $PeOffset + 6 -gt $Bytes.Length) {
        throw "Invalid PE header offset: $Path"
    }
    $Signature = [Text.Encoding]::ASCII.GetString($Bytes, $PeOffset, 4)
    $Machine = [BitConverter]::ToUInt16($Bytes, $PeOffset + 4)
    if ($Signature -ne "PE`0`0" -or $Machine -ne 0x8664) {
        throw "Expected an x64 PE executable: $Path"
    }
}

Assert-File $Sidecar
Assert-File $Tesseract
Assert-File (Join-Path $Tessdata "chi_sim.traineddata")
Assert-File (Join-Path $Tessdata "eng.traineddata")
Assert-X64Pe $Sidecar
Assert-X64Pe $Tesseract

$Languages = & $Tesseract --tessdata-dir $Tessdata --list-langs 2>&1
if ($LASTEXITCODE -ne 0) { throw "Packaged Tesseract failed to list languages" }
foreach ($Language in @("chi_sim", "eng")) {
    if ($Languages -notcontains $Language) {
        throw "Packaged Tesseract cannot load language: $Language"
    }
}

$Msi = @(Get-ChildItem -LiteralPath (Join-Path $BundleRoot "msi") -Filter *.msi -File -ErrorAction SilentlyContinue)
$Nsis = @(Get-ChildItem -LiteralPath (Join-Path $BundleRoot "nsis") -Filter *.exe -File -ErrorAction SilentlyContinue)
if ($Msi.Count -eq 0) { throw "Tauri did not produce an MSI installer" }
if ($Nsis.Count -eq 0) { throw "Tauri did not produce an NSIS installer" }

Write-Output "Verified Windows x64 sidecar, OCR runtime, language models, MSI, and NSIS installers."
