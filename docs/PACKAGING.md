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

`build_sidecar.py --require-ocr` 会拒绝缺少 Tesseract 程序或中英文模型的正式构建。`prepare_ocr_vendor.py` 从当前平台已安装的 Tesseract 创建 vendor 目录；macOS 构建会递归复制非系统动态库并改写加载路径，避免目标机器依赖 Homebrew。

macOS 示例：

```bash
brew install tesseract tesseract-lang
python build/scripts/prepare_ocr_vendor.py \
  --target aarch64-apple-darwin \
  --tesseract "$(brew --prefix tesseract)/bin/tesseract" \
  --tessdata-dir "$(brew --prefix tesseract)/share/tessdata" \
  --tessdata-dir "$(brew --prefix tesseract-lang)/share/tessdata"
```

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

必须在对应架构或正确的交叉编译环境构建和测试。项目采用免费发布策略，构建脚本固定使用 Tauri 的 `-` identity 对整个应用 bundle 进行 ad-hoc 签名，并关闭只适用于可信 Developer ID 的 hardened runtime；这样 PyInstaller one-file sidecar 解压出的 Python 动态库可以正常加载。构建和发布不需要任何 Apple Secrets。

ad-hoc 签名只能验证 bundle 内部代码结构，不能向 Gatekeeper 证明开发者身份，也不能提交 Apple 公证。从 GitHub 下载后，用户必须按 README 在“隐私与安全性”中选择“仍要打开”。发布者不得把该产物描述为 Apple 已认证或已公证。

`macos_bundle_config.py` 会扫描 OCR runtime、sidecar 及 PyInstaller 收集清单中的 Mach-O deployment target，生成实际的 `minimumSystemVersion` 配置。正式 GitHub 构建只接受 macOS 15.x 依赖；任何依赖要求 macOS 16 或更高版本都会阻止上传，避免应用在旧系统安装后才于 OCR 阶段崩溃。

构建后执行以下验收：

```bash
bash build/scripts/verify_macos_bundle.sh \
  "frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/本真 PDF.app" \
  "frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/本真 PDF_1.0.2_aarch64.dmg"
```

## Windows

在 Windows PowerShell 中：

```powershell
build\scripts\build_windows.ps1
build\scripts\verify_windows_bundle.ps1
```

需要 Visual Studio Build Tools、WebView2、Rust stable、Node 20+、pnpm 和 Python 3.10+。验收脚本会检查 x64 sidecar、Tesseract、中英文模型以及 MSI/NSIS 产物。未配置代码签名证书时只生成未签名包。

## 干净系统验收

1. 系统没有 Python 和 Tesseract。
2. 安装、启动、中文文件与路径。
3. 文字、扫描、混合、加密和取消/恢复。
4. OCR 中界面响应，异常时保留日志与状态。
5. DOCX 可由 Word/LibreOffice 打开。
6. 网络抓包确认无文档上传。
7. 卸载后用户输出仍存在。

GitHub Actions 的安装包工作流是显式手动触发。它在 runner 上安装 OCR runtime、创建可重定位 vendor、构建 sidecar，并在上传前验证 DMG、ad-hoc bundle 签名、中英文模型和 Windows 安装器。macOS 产物名称明确带有 `ad-hoc`，并附带 `SHA256SUMS.txt`；它就是免费 Release 使用的正式产物，但没有 Apple 身份认证或公证。
