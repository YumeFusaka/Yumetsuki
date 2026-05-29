# OCR 与视觉输入

## 范围

Phase 6 第一版视觉能力只做屏幕 OCR 文本，不做复杂图像语义推理。

## 触发方式

默认仅在用户显式要求读屏时触发，例如“看看屏幕”“请看屏幕”“你能看到屏幕吗”“识别一下这个界面”“屏幕上写了什么”。

如果用户刚通过默认浏览器搜索或打开页面，随后说“看看你搜索的这个页面有什么内容”“总结当前网页”这类语义，系统应按当前页面阅读请求处理，先采集屏幕 OCR 作为上下文，而不是把整句话再次当作搜索词。

用户也可以在系统设置中显式开启“被动状态定时读屏”。该能力只在聊天窗已经进入被动状态后按配置间隔触发，用于补充最近屏幕观察，让后续主动发言更贴近当前桌面场景。该能力默认关闭，不改变普通聊天的显式读屏边界。

## 配置

`SystemConfig.vision` 字段：

- `enabled`：是否启用 OCR
- `ocr_engine`：默认 `rapidocr`，可选 `paddleocr`
- `language`：OCR 语言，RapidOCR/PaddleOCR 默认中文为 `ch`
- `screenshot_dir`：截图中间产物目录，默认 `data/vision`
- `max_text_chars`：进入会话态的最大文本长度
- `explicit_trigger_only`：显式触发策略，当前版本固定为 `true`
- `passive_observation_enabled`：是否允许被动状态下定时 OCR，默认 `false`
- `passive_observation_interval_seconds`：被动状态定时 OCR 间隔，默认 `10`
- `screenshot_retention_hours`：读屏截图保留时长，默认 `24`
- `screenshot_max_files`：读屏截图最多保留数量，默认 `200`
- `screenshot_cleanup_interval_minutes`：读屏截图清理间隔，默认 `30`

这些配置已暴露在设置中心的 `系统设置 -> 视觉 / OCR` 分组中。系统页仍采用“修改后点击保存”的语义；未保存时切换到其他页面会丢弃本次草稿。保存成功后，已打开的聊天窗口会同步更新视觉配置和截图清理计时器；保存失败时会回滚内存中的系统配置、设置页草稿和已打开聊天窗口的视觉配置。为避免默认后台自动采集屏幕，当前版本的普通触发方式固定为“仅在明确要求读屏时触发”，设置页不允许关闭该限制；被动状态定时 OCR 必须由用户单独显式开启。

## OCR 后端策略

- `rapidocr` 是默认方案，面向本地桌面截图、中文 UI 文本和轻量部署。
- `paddleocr` 是进阶可选方案，适合用户愿意安装较重依赖、追求更高复杂版面识别能力的场景。
- 项目不再使用 Tesseract 作为主方案；旧配置中的 `tesseract_cmd` / `psm` 不再参与运行。

## 数据流

```text
用户显式要求读屏
→ Vue 聊天页通过 typed client 提交读屏请求
→ Tauri command 在受控路径下采集屏幕截图并生成资源 handle
→ Python sidecar VisionService 通过 VisionManager.recognize_image_text() 调用 RapidOCRAdapter 或 PaddleOCRAdapter 识别截图文本
→ OCRResult
→ SessionContext.visual_observations
→ SessionPolicy 注入最近视觉信息
→ LLM 回复
```

被动状态定时读屏路径：

```text
聊天窗进入被动状态
→ 若 vision.enabled 与 passive_observation_enabled 同时为 true
→ Vue / Tauri 按 passive_observation_interval_seconds 节流采集截图
→ Python sidecar 后台任务执行 OCR
→ ProactiveService 写入 SessionContext.visual_observations
→ ProactiveScheduler 获得最近屏幕观察摘要，供后续主动发言参考
```

截图中间产物处理：

```text
聊天窗启动或截图前
→ VisionManager 按 screenshot_retention_hours 与 screenshot_max_files 清理 screenshot_dir 下的 screen_*.png
→ Tauri / sidecar 生命周期按 screenshot_cleanup_interval_minutes 定时执行强制清理
→ 非 screen_*.png 文件不参与清理
```

## 隐私边界

截图和 OCR 文本来自用户当前屏幕，属于本地敏感运行期数据。`data/vision/` 默认不应提交。截图原图只作为本地中间产物保留，并按配置定期清理。被动定时读屏默认关闭；开启后仍只保留截断后的视觉观察与脱敏日志，不应把截图原图或长 OCR 原文写入诊断包。
