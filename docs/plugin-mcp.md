# 插件与 MCP

## 本地插件

### 目录结构

```text
plugins/
└── plugin_name/
    ├── plugin.py
    └── README.md
```

### 最小插件

```python
from sdk.base import BasePlugin, tool


class Plugin(BasePlugin):
    name = "example_echo"
    description = "Example plugin"

    @tool(description="Echo text")
    def echo(self, text: str) -> str:
        return text
```

### 规则

- 插件入口文件必须是 `plugin.py`
- 必须导出 `Plugin` 类
- `Plugin` 必须继承 `BasePlugin`
- 对外工具必须使用 `@tool`

## 插件宿主

`core/plugin_host.py` 负责：

- 扫描 `plugins/*/plugin.py`
- 加载插件
- 收集工具 schema
- 调用插件工具
- 记录加载失败信息
- 输出结构化加载状态：插件名称、路径、加载状态、工具数量、说明和错误消息

## MCP 配置

实际配置文件：

- `data/config/mcp.yaml`

示例模板：

- `data/config/mcp.example.yaml`

### 示例

```yaml
servers:
  - name: notes-local
    transport: stdio
    command: python path/to/mcp_server.py
    url: ""
    enabled: true
    connect_timeout_seconds: 10
    request_timeout_seconds: 10
    retry_attempts: 0
  - name: web-tools
    transport: sse
    command: ""
    url: http://127.0.0.1:8000/mcp
    enabled: false
    connect_timeout_seconds: 10
    request_timeout_seconds: 10
    retry_attempts: 0
```

## MCP transport

当前已支持：

- `stdio`
- `sse` / HTTP JSON-RPC

### stdio

- 启动子进程
- `initialize`
- `tools/list`
- `tools/call`

### sse / HTTP

- POST JSON-RPC 请求
- 支持 `application/json`
- 支持 `text/event-stream`
- 请求超时使用 `request_timeout_seconds`
- URL 路径取决于服务端实现，常见为 `/mcp` 或 `/sse`；设置页 placeholder 同时提示两种写法，实际以目标 MCP 服务端文档为准。

### 诊断配置

- `connect_timeout_seconds`：连接阶段超时配置候选，默认 `10`
- `request_timeout_seconds`：HTTP MCP 请求超时，默认 `10`
- `retry_attempts`：连接失败后的重试次数，默认 `0`

`MCPHost` 会记录每个 server 的连接状态、工具数量、工具名、错误类型、诊断消息和最后检查时间。

## 工具目录

`core/tool_registry.py` 统一聚合：

- 插件工具
- MCP 工具

负责：

- 输出统一 tool schema
- 提供 UI 展示条目
- 调用分发
- 刷新统计
- 记录工具来源类型和来源名称；qualified name 仍保持 `plugin__tool` / `server__tool`

## 设置页支持

插件页面当前支持：

- 导入本地插件
- 删除外部插件；内置插件不可删除
- 查看插件加载状态、工具数量、说明和错误消息
- 配置内置插件权限
- 读取用户提供的 JSON 插件索引并下载 / 导入外部插件；当前没有官方插件 marketplace

MCP 页面当前支持：

- 添加 MCP server
- 编辑 MCP server
- 启用 / 停用 MCP server
- 删除 MCP server
- 配置 transport、命令或 URL、连接超时、请求超时和失败重试
- 刷新 MCP 连接与 MCP 工具列表
- 查看 MCP 工具来源、描述、参数摘要
- 查看 MCP 连接状态、工具数量、工具名、错误类型、诊断消息和最后检查时间

## 当前限制

- 未做真实第三方 MCP 服务端兼容性回归
- 工具执行日志没有独立面板
- 暂无官方插件 marketplace；外部插件只支持用户提供 JSON 插件索引
- 不自动执行第三方 MCP 返回的命令或外部指令；MCP 返回内容仍按不可信输入处理
