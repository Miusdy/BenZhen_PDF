# 构建与验证记录

验证日期：2026-08-09；环境：macOS 26.6.1 Apple Silicon。

## 已实现并验证

- 后端：Python 3.10 与 3.12 环境中的 19 个 pytest 单元/集成测试全部通过，覆盖文字质量、关键字段冲突、阅读顺序、中文及空格路径、表格、空白页、加密、混合/扫描页降级、页面处理中取消与恢复状态、单任务并发保护、Windows OCR staging 及 macOS deployment target 阻断。
- 代码质量：Python `ruff`、严格 `mypy` 通过；React TypeScript 编译、6 个 Vitest 测试和 Vite release 构建通过；Rust `cargo test --locked` 通过。
- 实际转换：3 页中文/中英混排文字夹具生成 DOCX；正文没有坐标来源尾注。
- 图片回归：600×2400 像素纵向图片被等比限制在 5.8×7.0 英寸页面区域内，渲染后保持单页且不发生放大。
- 前端回归：预检读取动画、取消及迟到响应隔离通过自动化测试；1440×900 与 960×800 视口无横向溢出。
- sidecar：PyInstaller Apple Silicon 可执行文件构建成功；打包后的 sidecar 通过 JSON Lines 对扫描夹具执行 `chi_sim+eng` OCR，输出置信度 0.9187 的有效 DOCX，识别出 `Invoice TEST-2026-0808` 与金额。
- 桌面端：1440×900 与 960×800 浏览器视口验证拖放、预检、开始、暂停、继续/取消状态及响应式布局；控制台无错误且无横向溢出。
- 原生包：Tauri release 编译成功，生成完整 ad-hoc 签名的 `.app` 与 `.dmg`；`codesign --verify --deep --strict` 与 `hdiutil verify` 通过，挂载 DMG 后对镜像内 `.app` 重复签名、deployment target 和 OCR 资源验收也通过。
- OCR runtime：Homebrew Tesseract 5.5.3 及中英文模型已重定位到包内，所有非系统 dylib 均改为相对加载路径，包内二进制可独立列出 `chi_sim`、`eng`。
- 大文件：构建物、依赖、OCR vendor 和 sidecar 均由 `.gitignore` 排除；最终本机测试 DMG SHA-256 为 `57cb4dfd29360b6f213bdca50b6038cea541227d05191a403e51408839211ee8`。

## 已实现但尚未完成目标环境验证

- macOS Intel 与 Windows 构建脚本、Tauri 配置和手动 GitHub Actions 工作流已提供，尚未在相应目标系统运行。
- macOS Intel 与 Windows 安装包尚未在对应目标实机完成首次安装和转换验收。

## 构建产物边界

本地生成的 Apple Silicon DMG 是免费 Release 使用的完整 ad-hoc 签名包，包含 Python 转换核心、Tesseract、所需动态库及中英文模型。它没有 Apple Developer ID 身份和公证票据，用户首次打开时必须按 README 在 macOS 安全设置中明确确认。

当前本机 Homebrew Tahoe OCR bottle 的最高 deployment target 为 macOS 26.4，因此本地测试 DMG 会如实声明需要 macOS 26.4；正式 CI 会拒绝高于 macOS 15.0 的依赖。
