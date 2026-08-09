# 本真 PDF（Benzhen PDF）

一款内容保真优先、隐私友好的本地 PDF 转 Word 工具。

本真 PDF 将文字型、扫描型和混合型 PDF 转换为可编辑的 DOCX，并尽量保留标题、段落、列表、表格、图片和阅读顺序。文件、OCR 文字及转换结果只在当前设备处理，不会上传到服务器。

## 项目简介

常见的 PDF 转 Word 工具要么依赖云端上传，要么在扫描件、复杂排版和大图片场景中产生明显失真。本真 PDF 提供 Python 转换核心、命令行工具与 Tauri 桌面应用，在“可编辑”和“忠于原文”之间采取保守策略：不猜测、不润色、不静默丢失内容，转换完成后在前端直接给出完成提示。

## 功能特点

- **全程本地处理**：PDF、密码、图片、OCR 结果和 Word 文件不离开设备。
- **多类型 PDF 支持**：自动识别文字页、扫描页、混合页、空白页和加密文件。
- **内容保真优先**：保留标题、正文、列表、表格、图片与多栏阅读顺序。
- **干净的 Word 正文**：不在正文后追加 PDF 页码或坐标等来源标记，转换结果即为可直接编辑的正文。
- **图片尺寸保护**：图片只会等比缩小到页面可用区域，不会因错误放大产生大量额外页面。
- **大文件状态反馈**：读取期间提供动画、进度提示和取消操作，避免界面无响应感。
- **OCR 与质量门禁**：支持 Tesseract 中英文识别，并对低置信度、乱码和冲突内容标记人工核对。
- **失败安全**：转换完成后才原子写入 DOCX，失败或取消不会留下伪成功结果。

## 下载与安装

在 GitHub 的 [Releases](https://github.com/Miusdy/BenZhen_PDF/releases) 页面下载对应平台安装包。

当前发布状态：

- **v1.0.2**：项目采用免费的开源发布方案；macOS 安装包经过完整 ad-hoc 签名，但没有付费 Developer ID 证书和 Apple 公证；
- macOS 发行包要求 macOS 15；构建会根据内嵌 OCR runtime 自动写入精确的小版本要求，不能在更旧系统安装；
- macOS Intel、Windows：已提供构建配置，等待对应平台实机验证；
- OCR 发行包需要按[打包说明](docs/PACKAGING.md)准备 Tesseract 与 `chi_sim`、`eng` 模型。

### macOS 首次打开

由于维护者不使用付费 Apple Developer Program，macOS 会将从 GitHub 下载的应用显示为“无法验证开发者”或阻止首次打开。这不代表安装包损坏。请只从本项目官方 Releases 下载，并按以下步骤操作：

1. 打开 DMG，将“本真 PDF”拖入“应用程序”。
2. 尝试打开一次应用；被系统阻止后，进入“系统设置 → 隐私与安全性”。
3. 在安全性区域找到“本真 PDF”，点击“仍要打开”，再次确认“打开”。此后可以正常双击启动。

如果系统仍提示“应用已损坏”，确认下载来源后执行：

```bash
xattr -dr com.apple.quarantine "/Applications/本真 PDF.app"
open "/Applications/本真 PDF.app"
```

该命令会移除 macOS 的下载隔离标记，不要对来源不明的应用使用。每个 macOS 构建产物同时包含 `SHA256SUMS.txt`；将它与 DMG 放在同一目录后可校验下载内容：

```bash
shasum -a 256 -c SHA256SUMS.txt
```

ad-hoc 签名用于保证应用 bundle 内部代码结构完整，但不能替代 Apple 对付费开发者身份的认证和公证。因此免费版本无法消除上述首次打开确认。

## 命令行快速开始

要求 Python 3.10 或更高版本。

```bash
git clone git@github.com:Miusdy/BenZhen_PDF.git
cd BenZhen_PDF
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

转换 PDF：

```bash
pdf2word convert "输入文件.pdf" -o "输出文件.docx"
```

快速预检：

```bash
pdf2word preflight "输入文件.pdf"
```

常用参数：

```text
--language chi_sim+eng
--mode content-first
--ocr auto|always|never
--dpi 300
--review-threshold 0.80
--keep-intermediate
--password
```

## 桌面端开发

要求 Node.js 20+、pnpm 9+、Rust stable 和当前平台所需的 Tauri 系统依赖。

```bash
cd frontend
pnpm install
pnpm tauri dev
```

桌面端通过标准输入输出 JSON Lines 协议调用 Python sidecar，不开放本地 HTTP 服务。

## OCR 说明

源码开发环境需要安装 Tesseract 5，以及简体中文 `chi_sim` 和英文 `eng` 语言模型。

OCR 不可用时：

- 文字型 PDF 仍可正常转换；
- 必须 OCR 的页面会在 Word 中标记为需要人工核对，不会被静默忽略；
- `--ocr always` 不会伪造成功识别内容。

## 项目结构

```text
backend/src/pdf2word/   Python 转换核心、CLI 与 sidecar
backend/tests/          后端单元测试与集成测试
frontend/               React、Vite 与 Tauri 桌面端
shared/schema/          IR 与 IPC JSON Schema
build/                  PyInstaller 和跨平台打包脚本
fixtures/               无隐私测试夹具
output/examples/        示例转换结果
docs/                   架构、隐私、打包和限制说明
```

## 测试

后端：

```bash
python build/scripts/generate_fixtures.py
ruff check backend
mypy backend/src/pdf2word
pytest
```

前端：

```bash
cd frontend
pnpm test
pnpm build
cargo check --manifest-path src-tauri/Cargo.toml
```

详细验收记录见 [docs/VERIFICATION.md](docs/VERIFICATION.md)。

## 已知限制

复杂无边框表格、嵌套表格、数学公式、竖排文字、任意多栏版式及跨页段落仍可能需要人工核对。完整说明见 [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)。

## 隐私与安全

本项目不会主动进行网络请求或上传文档。请勿在 Issue、日志或测试夹具中提交真实用户文件、密码或敏感信息。安全问题请参阅 [SECURITY.md](SECURITY.md)，隐私边界见 [docs/PRIVACY.md](docs/PRIVACY.md)。

## 参与贡献

欢迎提交 Issue 与 Pull Request。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，运行测试，并确认没有提交依赖缓存、构建产物、真实用户文档或超过 100 MB 的文本文件。

## 开源许可

本项目采用 [Apache License 2.0](LICENSE) 开源。
