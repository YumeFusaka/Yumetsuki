# OCR 与视觉输入

## 范围

Phase 6 第一版视觉能力只做屏幕 OCR 文本，不做复杂图像语义推理。

## 触发方式

默认仅在用户显式要求读屏时触发，例如“看看屏幕”“识别屏幕”“屏幕上写了什么”。

## 配置

`SystemConfig.vision` 字段：

- `enabled`：是否启用 OCR
- `ocr_engine`：当前为 `tesseract`
- `tesseract_cmd`：Tesseract 命令路径
- `language`：OCR 语言，如 `chi_sim+eng`
- `psm`：Tesseract page segmentation mode
- `screenshot_dir`：截图中间产物目录，默认 `data/vision`
- `max_text_chars`：进入会话态的最大文本长度
- `explicit_trigger_only`：是否只允许显式触发

## 数据流

```text
用户显式要求读屏
→ AgentManager 判断触发词
→ VisionManager 截屏
→ TesseractOCRAdapter 调用本地 tesseract
→ OCRResult
→ SessionContext.visual_observations
→ SessionPolicy 注入最近视觉信息
→ LLM 回复
```

## 隐私边界

截图和 OCR 文本来自用户当前屏幕，属于本地敏感运行期数据。`data/vision/` 默认不应提交。
