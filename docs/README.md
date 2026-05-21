# Yumetsuki 文档入口

> 最后更新：2026-05-21

## 项目定位

Yumetsuki（梦月）是一个 Python 桌宠 AI 伴侣项目，第三阶段进行中。

## 文档结构

### 入口文档

- `docs/README.md`
  作为文档导航入口

### 协作文档

- `CLAUDE.md`
  面向 AI / 协作者的最小工作上下文

### 专题文档

- [代码架构](./architecture.md)
  模块结构、主流程、工具系统边界
- [UI 规范](./ui-guidelines.md)
  主题、控件、反馈、交互约定
- [插件与 MCP](./plugin-mcp.md)
  插件 SDK、宿主、MCP 配置与 transport
- [开发流程](./development.md)
  环境、配置、测试、保存语义、Git 约定

## 当前进度

- 第二阶段：已完成（插件系统、LLM 工具调用、MCP 接入、统一工具目录）
- 第三阶段：已完成
  已完成：
  - 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
  - 记忆设置页 UI（向量模型选择、存储目录、检索条数）
  - 记忆异步加载（后台线程，不阻塞 UI 启动）
  - Agent 模块（planner + executor + reflector + manager）

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
