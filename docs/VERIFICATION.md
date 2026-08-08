# 构建与验证记录

验证日期：2026-08-08；环境：macOS Apple Silicon。

## 已实现并验证

- 后端：12 个 pytest 单元/集成测试全部通过，覆盖文字质量、关键字段冲突、阅读顺序、中文及空格路径、表格、空白页、加密、混合/扫描页降级、取消与恢复状态。
- 代码质量：Python `ruff` 通过；React TypeScript 编译、2 个 Vitest 测试和 Vite release 构建通过；Rust `cargo check` 通过。
- 实际转换：3 页中文/中英混排文字夹具生成 DOCX、JSON 与 HTML；DOCX 在 LibreOffice 渲染为 3 页并逐页目检，标题、列表、表格和双栏顺序可读，正文没有坐标来源尾注。
- 图片回归：600×2400 像素纵向图片被等比限制在 5.8×7.0 英寸页面区域内，渲染后保持单页且不发生放大。
- 前端回归：预检读取动画、取消及迟到响应隔离通过自动化测试；1440×900 与 960×800 视口无横向溢出。
- sidecar：PyInstaller Apple Silicon 可执行文件构建成功，并用中文路径 PDF 完成 JSON Lines `preflight` 烟测。
- 桌面端：1440×900 与 960×800 浏览器视口验证拖放、预检、开始、暂停、继续/取消状态及响应式布局；控制台无错误且无横向溢出。
- 原生包：Tauri release 编译成功，生成未签名 `.app` 与 `.dmg`；`.app` 已原生启动，主界面与全部核心控件可见，包内存在目标 sidecar。
- 大文件：仓库文本文件 100 MiB 上限检查通过；构建物、依赖、OCR vendor 和 97 MiB sidecar 均由 `.gitignore` 排除。

## 已实现但尚未完成目标环境验证

- OCR 接口、图像预处理、语言诊断、原文字层/OCR 仲裁和随包运行时定位均已实现。
- 本机安装 Tesseract 与中文模型时，Homebrew 被未接受的 Xcode 许可阻止。接受法律协议必须由设备所有者完成，因此未做真实中文扫描 OCR 端到端验收。
- macOS Intel 与 Windows 构建脚本、Tauri 配置和手动 GitHub Actions 工作流已提供，尚未在相应目标系统运行。

## 构建产物边界

本地生成的 Apple Silicon DMG 是未签名测试包，包含 Python 转换核心，但不包含第三方 OCR runtime。正式发布必须先按 `docs/PACKAGING.md` 准备并审核 `chi_sim`、`eng`、Tesseract 及动态库；`--require-ocr` 会阻止缺少模型的正式 sidecar 构建。

项目已初始化本地 `main` 分支，但未提交、未设置远程、未上传、未推送，也未创建 GitHub 发布。
