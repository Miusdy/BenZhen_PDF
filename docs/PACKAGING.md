# 跨平台打包

## 发行物边界

每个目标平台分别构建，不能复用 sidecar 二进制：

- macOS Apple Silicon：`aarch64-apple-darwin` → DMG；
- macOS Intel：`x86_64-apple-darwin` → DMG；
- Windows 10/11 x64：`x86_64-pc-windows-msvc` → MSI/NSIS EXE。

当前仓库不包含第三方 OCR 二进制和语言模型，以避免提交大文件及未经审核的再分发内容。发布维护者必须准备：

```text
build/vendor/tesseract/<target>/
  bin/tesseract[.exe]
  lib/... target-specific dynamic libraries ...
  tessdata/chi_sim.traineddata
  tessdata/eng.traineddata
  LICENSES/... upstream notices ...
```

`build_sidecar.py --require-ocr` 会拒绝缺少中英文模型的正式构建。发布前还应在干净系统检查 Tesseract 能从应用资源目录找到动态库与 `TESSDATA_PREFIX`；第一版脚本不自动下载未固定哈希的第三方二进制。

## Python sidecar

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[packaging]'
python build/scripts/build_sidecar.py --target aarch64-apple-darwin --require-ocr
```

Windows 使用 `.venv\\Scripts\\python.exe`。脚本将目标命名的 sidecar 复制至 `frontend/src-tauri/binaries/`，符合 Tauri externalBin 规则。

## macOS

```bash
bash build/scripts/build_macos.sh aarch64-apple-darwin
bash build/scripts/build_macos.sh x86_64-apple-darwin
```

必须在对应架构或正确的交叉编译环境构建和测试。没有 Apple Developer ID 时只生成未签名本地测试包，不执行签名或公证。

## Windows

在 Windows PowerShell 中：

```powershell
build\scripts\build_windows.ps1
```

需要 Visual Studio Build Tools、WebView2、Rust stable、Node 20+、pnpm 和 Python 3.10+。未配置代码签名证书时只生成未签名包。

## 干净系统验收

1. 系统没有 Python 和 Tesseract。
2. 安装、启动、中文文件与路径。
3. 文字、扫描、混合、加密和取消/恢复。
4. OCR 中界面响应，异常时保留日志与状态。
5. DOCX 可由 Word/LibreOffice 打开，报告可查看。
6. 网络抓包确认无文档上传。
7. 卸载后用户输出仍存在。

GitHub Actions 的安装包工作流是显式手动触发，并在 OCR vendor 内容缺失时失败。这样不会产出缺少 OCR 却看似完整的安装包。

