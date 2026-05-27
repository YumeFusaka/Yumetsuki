# OCR 与视觉输入

## 范围

Phase 6 第一版视觉能力只做屏幕 OCR 文本，不做复杂图像语义推理。

## 触发方式

默认仅在用户显式要求读屏时触发，例如“看看屏幕”“识别屏幕”“屏幕上写了什么”。

## 配置

`SystemConfig.vision` 字段：

- `enabled`：是否启用 OCR
- `ocr_engine`：默认 `rapidocr`，可选 `paddleocr`
- `language`：OCR 语言，RapidOCR/PaddleOCR 默认中文为 `ch`
- `screenshot_dir`：截图中间产物目录，默认 `data/vision`
- `max_text_chars`：进入会话态的最大文本长度
- `explicit_trigger_only`：显式触发策略，当前版本固定为 `true`

这些配置已暴露在设置中心的 `系统设置 -> 视觉 / OCR` 分组中。系统页仍采用“修改后点击保存”的语义；未保存时切换到其他页面会丢弃本次草稿。保存成功后，已打开的聊天窗口会同步更新视觉配置；保存失败时会回滚内存中的系统配置、设置页草稿和已打开聊天窗口的视觉配置。为避免后台自动采集屏幕，当前版本的触发方式固定为“仅在明确要求读屏时触发”，设置页不允许关闭该限制。

## OCR 后端策略

- `rapidocr` 是默认方案，面向本地桌面截图、中文 UI 文本和轻量部署。
- `paddleocr` 是进阶可选方案，适合用户愿意安装较重依赖、追求更高复杂版面识别能力的场景。
- 项目不再使用 Tesseract 作为主方案；旧配置中的 `tesseract_cmd` / `psm` 不再参与运行。

## 数据流

```text
用户显式要求读屏
→ ChatWindow 询问 AgentManager.should_capture_screen()
→ ChatWindow 在 Qt 主线程通过 VisionManager.capture_screen_image() 预采集截图
→ LLMWorker 后台线程通过 VisionManager.recognize_image_text() 调用 RapidOCRAdapter 或 PaddleOCRAdapter 识别截图文本
→ OCRResult
→ SessionContext.visual_observations
→ SessionPolicy 注入最近视觉信息
→ LLM 回复
```

## 隐私边界

截图和 OCR 文本来自用户当前屏幕，属于本地敏感运行期数据。`data/vision/` 默认不应提交。
