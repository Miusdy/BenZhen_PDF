# 架构

## 数据流

```text
React/Tauri UI
  └─ JSON Lines over sidecar stdin/stdout
      └─ Python ConversionPipeline
          ├─ PyMuPDF reader and coordinates
          ├─ page classifier + text quality score
          ├─ OpenCV preprocessing + Tesseract fallback
          ├─ deterministic reconciliation and critical-field checks
          ├─ reading order + structure detection
          ├─ versioned DocumentIR
          └─ DOCX + JSON + HTML writers
```

没有本地 HTTP 服务。前端只传路径、配置和小型进度事件，不传未压缩页面图像。

## 内容选择

1. 原文字层质量达到阈值时保留原文。
2. 原文字层不足且 OCR 达标时采用 OCR，并记录切换原因。
3. 两路均不足时保留分数较高者并标记核对。
4. 两路文本相似度低或数字、日期、金额、百分比、账号、合同/条款编号、型号、URL、邮箱不同时标记高风险或严重风险。
5. 仅做 NFC Unicode 规范化和无歧义的行内空白清理，不做语言模型改写。

## 中间表示

`DocumentIR` 是 DOCX 与报告的唯一输入。页面、块、行和字符均保留 1-based 页码与 PDF 坐标。Schema 位于 `shared/schema/`，通过 `build/scripts/export_schemas.py` 从 Pydantic 模型生成。

## 任务状态与恢复

每页完成后写入 `.pdf2word-state/<input-hash>/page-N.json` 和 manifest。恢复前同时校验输入 SHA-256 和不含密码的配置指纹。成功任务默认清理状态；`keep_intermediate` 保留。取消时不会写出 DOCX，已完成页是否保留取决于配置。

## 进程隔离

Tauri 主进程启动打包后的 Python sidecar。后端异常不会直接终止 UI；标准错误被转换为诊断事件，标准输出只用于 JSON 协议。密码仅存在于内存中的单次命令和 Python 配置，不写入 manifest 或日志。

