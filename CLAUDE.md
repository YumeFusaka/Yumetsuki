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

## 下一步

- 句级增量 TTS 播报接入（GPT-SoVITS）
- 更多内置插件能力扩展（媒体控制、文件操作等）

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [开发流程](./docs/development.md)
