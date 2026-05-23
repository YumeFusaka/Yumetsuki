# CLAUDE.md — 协作上下文

## 作用

本文件只保留给 AI / 协作者的最小工作上下文。
详细内容不要继续堆在这里，统一查看 `docs/` 下的专题文档。

## 项目一句话

Yumetsuki 是一个 Python 桌宠 AI 伴侣项目，第三阶段已完成。

## 运行环境

- Python:
  `E:/Tool/Miniconda/envs/ai/python.exe`
- 运行：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 关键约束

- 不提交真实 API key
- `data/config/api.yaml` 和 `data/config/memory.yaml` 默认视为本地敏感配置
- 优先沿用现有 UI 风格和提交信息格式
- 当前不引入 LangChain / LangGraph，继续走自定义架构
- 原版兼容优先：涉及第三方服务、协议或接口时，必须先保证原版行为与默认语义不被破坏；对魔改或桌宠端的支持只能通过显式扩展实现，不能靠改写原版默认值、原版必填项或原版返回格式达成
- 完成的功能同步更新文档：每次提交的改动必须同步更新 CLAUDE.md 和 docs/ 目录中的相关文档；已完成的 specs 和 plan 文件应及时删除或更新
- 所有文档必须使用中文
- 每个插件必须在 `docs/` 下有对应的说明文档（如 `docs/plugin-system-control.md`）

## 当前阶段

- 第一阶段：已完成（基础 UI、角色系统、LLM 对话）
- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI + 异步加载
  - Agent 分层智能架构（分层路由、异步反思、多步推理、主动行为）
  - Agent 设置页（多 Tab 配置 + 实时日志）
  - Agent 日志混合时间线：用户输入、角色回复、Thinking 预览与内部事件统一显示
  - 系统控制插件（`plugins/system_control/`）：打开应用、系统默认浏览器、默认浏览器搜索、文件管理器、文件、URL、执行命令；三级权限控制
  - Web 自动化插件（`plugins/web_automation/`）：后台搜索、可见自动化搜索、提取文本、截图；Playwright + Edge；三级权限控制
  - 桌宠聊天窗优化：面板体感更宽、面板高度收紧、立绘落点下移、长文本内部滚动、整体缩放驱动字体/按钮/边框同步变化、文本压缩多余段间空白
  - 聊天窗边框修正：默认对话框 3px、输入框和圆形按钮 2px 纯玫瑰色边框；整体缩放时边框厚度同步按比例变化，并设最小值；hover/focus 使用更深玫瑰色
  - Agent 工具调用修正：tool 模式下禁止后续 LLM 二次调用同轮工具
  - 句级增量 TTS 播报与服务端兼容能力已接入：支持句级合成、输出语言约束、参考模式 / 预热与兼容回退，以及 `audio_mode=auto/pcm_stream/wav`
  - ChatWindow 在窗口生命周期内生成 TTS `session_id`，仅用于显式扩展路径下的 GPT-SoVITS speaker 会话化
  - `auto` 模式优先请求 PCM 流式，若流式失败则在当前聊天会话内锁定为 WAV；原版默认 `/tts` 语义与无扩展字段请求保持不变
  - `audio_mode=wav + reference_mode=inline` 被定义为桌宠端保底原版模式：不调用 `set_refer_audio`、不透传 `session_id`、不发送 PCM/流式扩展参数；其余组合才进入扩展模式
  - 当前已确认的剩余 TTS 异常（如服务端 warmup 文本语言选择错误、`、。` 之类切分异常）归因服务端；在桌宠端已正确传递 `session_id`、`prompt_lang`、`prompt_text` 的前提下，不再视为本仓库当前已知根因

## 下一步

- 更多内置插件能力扩展（媒体控制、文件操作等）

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [开发流程](./docs/development.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)
