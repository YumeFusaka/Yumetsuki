# CLAUDE.md — 协作上下文

## 作用

本文件只保留给 AI / 协作者的最小工作上下文。
详细内容不要继续堆在这里，统一查看 `docs/` 下的专题文档。

## 项目一句话

Yumetsuki 是一个 Python 桌宠 AI 伴侣项目，当前第三阶段进行中。

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
- 完成的功能同步更新文档

## 当前阶段

- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：进行中
  已完成：
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI（向量模型选择、存储目录、检索条数）
  - 记忆异步加载（不阻塞 UI 启动）
  待完成：
  - `agent/planner.py`
  - `agent/executor.py`
  - `agent/reflector.py`

## 文档入口

- [文档入口](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [开发流程](./docs/development.md)
