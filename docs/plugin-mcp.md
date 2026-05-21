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
  - name: web-tools
    transport: sse
    command: ""
    url: http://127.0.0.1:8000/mcp
    enabled: false
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

## 工具目录

`core/tool_registry.py` 统一聚合：

- 插件工具
- MCP 工具

负责：

- 输出统一 tool schema
- 提供 UI 展示条目
- 调用分发
- 刷新统计

## 设置页支持

插件 / MCP 页面当前支持：

- 导入本地插件
- 删除本地插件
- 添加 MCP server
- 启用 / 停用 MCP server
- 删除 MCP server
- 刷新统一工具目录
- 查看工具来源、描述、参数摘要

## 当前限制

- 未做真实第三方 MCP 服务端兼容性回归
- 工具执行日志没有独立面板
- 暂无插件 marketplace / 安装源
