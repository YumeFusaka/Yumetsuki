# Yumetsuki 文档入口

> 最后更新：2026-05-23

## 项目定位

Yumetsuki（梦月）是一个 Python 桌宠 AI 伴侣项目，第三阶段已完成。

## 文档结构

### 入口文档

- `docs/README.md`
  作为文档导航入口

### 协作文档

- `CLAUDE.md`
  面向 AI / 协作者的最小工作上下文

### 专题文档

- [代码架构](./architecture.md)
  模块结构、主流程、工具系统、Agent 系统、记忆系统
- [UI 规范](./ui-guidelines.md)
  主题、控件、反馈、交互约定
- [插件与 MCP](./plugin-mcp.md)
  插件 SDK、宿主、MCP 配置与 transport
- [开发流程](./development.md)
  环境、配置、测试、保存语义、Git 约定

### 插件文档

- [系统控制插件](./plugin-system-control.md)
  打开应用、浏览器、文件、执行命令；三级权限
- [Web 自动化插件](./plugin-web-automation.md)
  搜索、提取文本、截图；Playwright + Edge；三级权限

## 当前进度

- 第一阶段：已完成（基础 UI、角色系统、LLM 对话）
- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI + 异步加载
  - Agent 分层智能架构（路由、反思、多步推理、主动行为）
  - Agent 设置页（多 Tab：日志/规划/反思/多步推理/主动行为）
  - Agent 日志混合时间线（用户输入、角色回复、Thinking 预览、内部事件）
  - 系统控制插件（打开应用、浏览器、文件、执行命令；三级权限）
  - Web 自动化插件（搜索、提取文本、截图；Playwright + Edge；三级权限）
  - 桌宠聊天窗视觉与排版优化（更宽面板、更轻毛玻璃、更紧凑多段文本、长文本内部滚动、整体等比缩放）
  - 聊天窗边框统一为纯玫瑰色实边，并按窗口缩放动态调整厚度
  - 副作用工具重复执行修复
  - 句级增量 TTS 播报接入（GPT-SoVITS，句级切分、后台合成、顺序播放、失败跳过）
  - TTS 输出语言强约束（参考语言/输出语言分离，逐句翻译后播报，保证播报语言与设置一致）

## 下一步方向

- 更多内置插件能力扩展（媒体控制、文件操作等）

## 快速开始

- 安装依赖：
  `pip install -r requirements.txt`
- 启动：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 推荐阅读顺序

1. `docs/README.md`
2. `docs/architecture.md`
3. `docs/ui-guidelines.md`
4. `docs/plugin-mcp.md`
5. `docs/development.md`
