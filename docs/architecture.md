# Yumetsuki 代码架构

## 总览

Yumetsuki 当前采用轻量本地架构，核心目标是：

- 角色演出优先
- 工具调用可扩展
- 本地配置与数据可控
- 不依赖 LangChain / LangGraph 等外部 Agent 框架

## 目录结构

```text
yumetsuki/
├── main.py
├── core/
├── config/
├── llm/
├── tts/
├── ui/
├── data/
├── plugins/
└── tests/
```

## 核心模块

### `main.py`

- 应用入口
- 初始化 Qt 应用和全局样式
- 打开设置中心

### `ui/`

负责桌面 UI。

- `ui/settings/window.py`
  设置中心主窗口
- `ui/settings/pages/api_page.py`
  API 配置页面
- `ui/settings/pages/system_page.py`
  系统设置页面
- `ui/settings/pages/character_page.py`
  角色管理页面
- `ui/settings/pages/plugin_page.py`
  插件与 MCP 管理页面
- `ui/chat/window.py`
  桌宠聊天窗
- `ui/chat/sprite.py`
  立绘加载、缩放、情绪切换

### `config/`

负责配置模型和持久化。

- `config/schema.py`
  Pydantic 配置模型
- `config/manager.py`
  YAML 读写，当前支持：
  - `api.yaml`
  - `system_config.yaml`
  - `mcp.yaml`

### `llm/`

负责对话和工具调用。

- `llm/adapter.py`
  LLM 适配器抽象
- `llm/adapters/openai_compat.py`
  OpenAI-compatible 接口实现
- `llm/manager.py`
  对话历史、流式输出、工具调用循环
- `llm/text_processor.py`
  解析 `[emotion:xxx]`

### `core/`

负责非 UI 的基础能力。

- `core/event_bus.py`
  发布 / 订阅事件总线
- `core/character.py`
  角色目录加载
- `core/plugin_host.py`
  本地插件发现与调用
- `core/mcp_host.py`
  MCP server 会话、tools/list、tools/call
- `core/tool_registry.py`
  统一聚合本地插件工具和 MCP 工具

### `sdk/`

负责插件开发接口。

- `sdk/base.py`
  `BasePlugin`
  `@tool`
  工具 schema 生成

### `plugins/`

本地插件目录。

- 每个插件一个目录
- 至少包含 `plugin.py`
- 示例插件：`plugins/example_echo/`

### `data/`

项目数据目录。

- `data/config/`
  配置文件
- `data/characters/`
  角色包

## 对话主流程

```text
用户输入
→ LLMManager 组装 messages
→ ToolRegistry 注入 tool schemas
→ OpenAI-compatible API 流式返回
→ TextProcessor 解析 emotion
→ 如有 tool call，则通过 ToolRegistry 分发执行
→ tool result 回填给模型
→ UI 显示文本并切换立绘
```

## 工具系统

当前工具来源有两类：

- 本地插件工具
- MCP 工具

两者统一进入 `ToolRegistry`，由它负责：

- 汇总工具 schema
- 统一刷新
- 调用分发
- 提供 UI 展示数据

## 当前边界

第二阶段完成后，项目已经具备：

- 插件 SDK
- 插件宿主
- OpenAI-compatible tool calling
- MCP stdio / HTTP(SSE) transport
- 统一工具目录

第三阶段将新增：

- `agent/planner.py`
- `agent/executor.py`
- `agent/reflector.py`

Agent 层仍计划维持自定义实现，不引入大型外部框架。
