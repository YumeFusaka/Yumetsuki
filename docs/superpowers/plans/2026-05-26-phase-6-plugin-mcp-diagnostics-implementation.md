# Phase 6 Plugin MCP Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 增强插件 / MCP 管理页的状态可视化、错误诊断、工具目录说明和 MCP 连接重试配置。

**Architecture:** 保持现有 `PluginHost -> MCPHost -> ToolRegistry -> PluginPage` 链路，先在宿主层产出结构化诊断数据，再让 UI 展示这些数据。MCP 超时与重试进入配置模型，默认值保持向后兼容；插件导入、删除和 MCP 启停语义不改变。

**Tech Stack:** Python 3、PySide6、pytest、Pydantic、requests、现有 YAML 配置系统。

---

## 文件结构

- 修改 `config/schema.py`
  - 在 `MCPServerConfig` 增加 `connect_timeout_seconds`、`request_timeout_seconds`、`retry_attempts`。
- 修改 `core/plugin_host.py`
  - 新增 `PluginStatus`，记录插件加载状态、路径、工具数量、说明和错误。
  - `PluginHost.load()` 同步维护 `statuses`。
- 修改 `core/mcp_host.py`
  - 扩展 `MCPServerStatus`，增加 `error_type`、`last_checked_at` 和 `tool_names`。
  - `MCPHttpSession` 使用 server 级请求超时。
  - `MCPHost.connect_all()` 按 `retry_attempts` 重试连接。
- 修改 `core/tool_registry.py`
  - `ToolEntry` 增加 `source_name`，UI 可显示工具来自哪个插件或 MCP server。
- 修改 `ui/settings/pages/plugin_page.py`
  - 插件 / MCP 页面增加状态列表、详情区和诊断刷新结果。
  - 保留导入插件、删除插件、添加 MCP、启停 MCP、删除 MCP、刷新工具目录的现有入口。
- 修改测试：
  - `tests/test_config.py`
  - `tests/test_plugin_import.py`
  - `tests/test_mcp_host.py`
  - `tests/test_tool_registry.py`
  - `tests/test_settings_window.py`
- 修改文档：
  - `docs/plugin-mcp.md`
  - `docs/development.md`
  - `CLAUDE.md`

---

### Task 1: MCP 配置增加超时与重试

**Files:**
- Modify: `config/schema.py`
- Test: `tests/test_config.py`

- [x] **Step 1: Write the failing config tests**

Add to `tests/test_config.py`:

```python
def test_mcp_server_config_has_runtime_diagnostics_defaults():
    cfg = MCPServerConfig(name="tools")

    assert cfg.connect_timeout_seconds == 10
    assert cfg.request_timeout_seconds == 10
    assert cfg.retry_attempts == 0


def test_load_mcp_runtime_options_from_yaml(tmp_path):
    mcp_yaml = tmp_path / "mcp.yaml"
    mcp_yaml.write_text(
        """
servers:
  - name: remote-tools
    transport: sse
    url: http://127.0.0.1:8000/mcp
    enabled: true
    connect_timeout_seconds: 3
    request_timeout_seconds: 5
    retry_attempts: 2
""",
        encoding="utf-8",
    )

    mgr = ConfigManager(tmp_path)

    server = mgr.mcp.servers[0]
    assert server.connect_timeout_seconds == 3
    assert server.request_timeout_seconds == 5
    assert server.retry_attempts == 2
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_config.py::test_mcp_server_config_has_runtime_diagnostics_defaults tests/test_config.py::test_load_mcp_runtime_options_from_yaml -q
```

Expected: FAIL because `MCPServerConfig` does not expose these fields.

- [x] **Step 3: Implement config fields**

Update `config/schema.py`:

```python
class MCPServerConfig(BaseModel):
    name: str = ""
    transport: str = "stdio"
    command: str = ""
    url: str = ""
    enabled: bool = True
    connect_timeout_seconds: int = 10
    request_timeout_seconds: int = 10
    retry_attempts: int = 0
```

- [x] **Step 4: Run config tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_config.py::test_mcp_server_config_has_runtime_diagnostics_defaults tests/test_config.py::test_load_mcp_runtime_options_from_yaml -q
```

Expected: PASS.

---

### Task 2: PluginHost 输出结构化插件状态

**Files:**
- Modify: `core/plugin_host.py`
- Test: `tests/test_plugin_import.py`

- [x] **Step 1: Write the failing PluginHost status tests**

Add to `tests/test_plugin_import.py`:

```python
def test_plugin_host_records_loaded_plugin_status(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        """
from sdk.base import BasePlugin, tool

class Plugin(BasePlugin):
    name = "demo"
    description = "Demo plugin"

    @tool(description="Echo text")
    def echo(self, text: str) -> str:
        return text
""",
        encoding="utf-8",
    )

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert len(host.statuses) == 1
    status = host.statuses[0]
    assert status.name == "demo"
    assert status.loaded is True
    assert status.tools_count == 1
    assert status.description == "Demo plugin"
    assert status.message == "loaded"


def test_plugin_host_records_failed_plugin_status(tmp_path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("raise RuntimeError('boom')", encoding="utf-8")

    host = PluginHost(tmp_path / "plugins")
    host.load()

    assert host.statuses[0].name == "broken"
    assert host.statuses[0].loaded is False
    assert "boom" in host.statuses[0].message
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_plugin_import.py::test_plugin_host_records_loaded_plugin_status tests/test_plugin_import.py::test_plugin_host_records_failed_plugin_status -q
```

Expected: FAIL because `PluginHost.statuses` does not exist.

- [x] **Step 3: Implement PluginStatus**

Update `core/plugin_host.py`:

```python
@dataclass(frozen=True)
class PluginStatus:
    name: str
    path: str
    loaded: bool
    tools_count: int = 0
    description: str = ""
    message: str = ""
```

Update `PluginHost.__init__()`:

```python
self.statuses: list[PluginStatus] = []
```

Update `PluginHost.load()`:

```python
self.plugins.clear()
self.errors.clear()
self.statuses.clear()
if not self._plugins_dir.is_dir():
    return

for plugin_dir in sorted(path for path in self._plugins_dir.iterdir() if path.is_dir()):
    plugin_file = plugin_dir / "plugin.py"
    if not plugin_file.exists():
        continue
    try:
        module = self._load_module(plugin_dir.name, plugin_file)
        plugin_cls = getattr(module, "Plugin")
        plugin = plugin_cls()
        if not isinstance(plugin, BasePlugin):
            raise TypeError("Plugin must inherit sdk.base.BasePlugin")
        self.plugins.append(plugin)
        self.statuses.append(PluginStatus(
            name=plugin.name,
            path=str(plugin_dir.resolve()),
            loaded=True,
            tools_count=len(plugin.tools()),
            description=plugin.description,
            message="loaded",
        ))
    except Exception as exc:
        message = str(exc)
        self.errors.append(PluginLoadError(plugin=plugin_dir.name, message=message))
        self.statuses.append(PluginStatus(
            name=plugin_dir.name,
            path=str(plugin_dir.resolve()),
            loaded=False,
            message=message,
        ))
```

- [x] **Step 4: Run PluginHost tests**

Run:

```bash
python -m pytest tests/test_plugin_import.py -q
```

Expected: PASS.

---

### Task 3: MCPHost 状态增加错误类型、工具名与重试

**Files:**
- Modify: `core/mcp_host.py`
- Test: `tests/test_mcp_host.py`

- [x] **Step 1: Write failing MCP diagnostics tests**

Add to `tests/test_mcp_host.py`:

```python
def test_mcp_host_status_includes_tool_names_and_checked_time():
    host = MCPHost(
        [MCPServerConfig(name="notes", transport="stdio", command="python server.py")],
        session_factory=FakeSession,
    )

    host.connect_all()

    status = host.statuses[0]
    assert status.connected is True
    assert status.tool_names == ["search"]
    assert status.error_type == ""
    assert status.last_checked_at > 0


def test_mcp_host_retries_connection_failures():
    attempts = {"count": 0}

    class FlakySession(FakeSession):
        def __init__(self, server: MCPServerConfig):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary")
            super().__init__(server)

    host = MCPHost(
        [MCPServerConfig(name="notes", transport="stdio", command="python server.py", retry_attempts=1)],
        session_factory=FlakySession,
    )

    host.connect_all()

    assert attempts["count"] == 2
    assert host.statuses[0].connected is True
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_mcp_host.py::test_mcp_host_status_includes_tool_names_and_checked_time tests/test_mcp_host.py::test_mcp_host_retries_connection_failures -q
```

Expected: FAIL because `MCPServerStatus` lacks these fields and `connect_all()` does not retry.

- [x] **Step 3: Extend MCPServerStatus**

Update `core/mcp_host.py`:

```python
import time


@dataclass(frozen=True)
class MCPServerStatus:
    server: str
    transport: str
    connected: bool
    tools_count: int = 0
    message: str = ""
    error_type: str = ""
    last_checked_at: float = 0.0
    tool_names: list[str] | None = None
```

- [x] **Step 4: Use request timeout in MCPHttpSession**

Update `MCPHttpSession.__init__()`:

```python
self._timeout = max(1, int(server.request_timeout_seconds or 10))
```

Replace both `timeout=10` arguments in `_request()` and `_notify()`:

```python
timeout=self._timeout,
```

- [x] **Step 5: Implement retry loop in MCPHost.connect_all()**

Replace enabled-server connection block with:

```python
attempts = max(0, int(server.retry_attempts)) + 1
last_error: Exception | None = None
for _ in range(attempts):
    try:
        session = self._create_session(server)
        tools = session.list_tools()
        self._sessions[server.name] = session
        self._tools[server.name] = tools
        self.statuses.append(MCPServerStatus(
            server=server.name,
            transport=server.transport,
            connected=True,
            tools_count=len(tools),
            message="connected",
            last_checked_at=time.time(),
            tool_names=[tool.name for tool in tools],
        ))
        last_error = None
        break
    except Exception as exc:
        last_error = exc

if last_error is not None:
    self.statuses.append(MCPServerStatus(
        server=server.name,
        transport=server.transport,
        connected=False,
        message=str(last_error),
        error_type=last_error.__class__.__name__,
        last_checked_at=time.time(),
        tool_names=[],
    ))
```

For disabled servers, set:

```python
last_checked_at=time.time(),
tool_names=[],
```

- [x] **Step 6: Run MCP tests**

Run:

```bash
python -m pytest tests/test_mcp_host.py -q
```

Expected: PASS.

---

### Task 4: ToolRegistry 标记工具来源名称

**Files:**
- Modify: `core/tool_registry.py`
- Test: `tests/test_tool_registry.py`

- [x] **Step 1: Write failing ToolRegistry source-name test**

Update assertions in `tests/test_tool_registry.py::test_tool_registry_combines_plugin_and_mcp_tools`:

```python
assert registry.entries()[0].source_name == "demo"
assert registry.entries()[1].source_name == "notes"
```

- [x] **Step 2: Run test and verify RED**

Run:

```bash
python -m pytest tests/test_tool_registry.py::test_tool_registry_combines_plugin_and_mcp_tools -q
```

Expected: FAIL because `ToolEntry.source_name` does not exist.

- [x] **Step 3: Add source_name to ToolEntry**

Update `core/tool_registry.py`:

```python
@dataclass(frozen=True)
class ToolEntry:
    name: str
    source: str
    source_name: str
    qualified_name: str
    schema: dict[str, Any]
```

When adding plugin entries:

```python
qualified_name = function["name"]
self._entries.append(ToolEntry(
    name=qualified_name.split("__", 1)[-1],
    source="plugin",
    source_name=qualified_name.split("__", 1)[0],
    qualified_name=qualified_name,
    schema={
        "description": function.get("description", ""),
        "parameters": function["parameters"],
    },
))
```

When adding MCP entries, use the same `qualified_name.split("__", 1)[0]` source-name logic.

- [x] **Step 4: Run ToolRegistry tests**

Run:

```bash
python -m pytest tests/test_tool_registry.py -q
```

Expected: PASS.

---

### Task 5: 插件 / MCP 页面增加诊断详情

**Files:**
- Modify: `ui/settings/pages/plugin_page.py`
- Test: `tests/test_settings_window.py`

- [x] **Step 1: Write failing formatting tests**

Add to `tests/test_settings_window.py`:

```python
def test_plugin_page_formats_plugin_status_detail():
    status = PluginStatus(
        name="demo",
        path="E:/Project/Yumetsuki/plugins/demo",
        loaded=True,
        tools_count=2,
        description="Demo plugin",
        message="loaded",
    )

    text = _format_plugin_status_detail(status)

    assert "名称：demo" in text
    assert "状态：已加载" in text
    assert "工具数量：2" in text
    assert "路径：E:/Project/Yumetsuki/plugins/demo" in text


def test_plugin_page_formats_mcp_status_detail():
    status = MCPServerStatus(
        server="notes",
        transport="sse",
        connected=False,
        message="boom",
        error_type="RuntimeError",
        last_checked_at=1.0,
        tool_names=[],
    )

    text = _format_mcp_status_detail(status)

    assert "名称：notes" in text
    assert "状态：未连接" in text
    assert "错误类型：RuntimeError" in text
    assert "boom" in text
```

Add imports:

```python
from core.mcp_host import MCPServerStatus
from core.plugin_host import PluginStatus
from ui.settings.pages.plugin_page import _format_mcp_status_detail, _format_plugin_status_detail
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_settings_window.py::test_plugin_page_formats_plugin_status_detail tests/test_settings_window.py::test_plugin_page_formats_mcp_status_detail -q
```

Expected: FAIL because formatting helpers do not exist.

- [x] **Step 3: Add formatting helpers**

Add to `ui/settings/pages/plugin_page.py`:

```python
def _format_plugin_status_detail(status) -> str:
    state = "已加载" if status.loaded else "加载失败"
    return "\n".join([
        f"名称：{status.name}",
        f"状态：{state}",
        f"工具数量：{status.tools_count}",
        f"说明：{status.description or '无'}",
        f"路径：{status.path}",
        f"消息：{status.message or '无'}",
    ])


def _format_mcp_status_detail(status) -> str:
    state = "已连接" if status.connected else "未连接"
    tools = "、".join(status.tool_names or []) or "无"
    return "\n".join([
        f"名称：{status.server}",
        f"状态：{state}",
        f"传输：{status.transport}",
        f"工具数量：{status.tools_count}",
        f"工具：{tools}",
        f"错误类型：{status.error_type or '无'}",
        f"消息：{status.message or '无'}",
    ])
```

- [x] **Step 4: Add details panel to PluginPage**

In `PluginPage.__init__()`, after creating `self._list`, add:

```python
self._detail = QLabel("选择插件、MCP 服务器或工具查看诊断详情。")
self._detail.setWordWrap(True)
self._detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
self._detail.setStyleSheet("""
    QLabel {
        background: rgba(255,255,255,0.5);
        border: 1px solid rgba(220, 160, 180, 0.25);
        border-radius: 8px;
        padding: 10px 12px;
        color: #4a3040;
        font-size: 12px;
    }
""")
layout.addWidget(self._detail)
self._list.currentItemChanged.connect(self._sync_detail)
```

Set item data during refresh:

```python
item.setData(Qt.ItemDataRole.UserRole, {"kind": "plugin_status", "detail": _format_plugin_status_detail(status)})
item.setData(Qt.ItemDataRole.UserRole, {"kind": "mcp_status", "index": index, "detail": _format_mcp_status_detail(status)})
item.setData(Qt.ItemDataRole.UserRole, {"kind": "tool", "detail": detail_text})
```

Add:

```python
def _sync_detail(self) -> None:
    data = self._selected_data()
    if data and data.get("detail"):
        self._detail.setText(data["detail"])
    else:
        self._detail.setText("选择插件、MCP 服务器或工具查看诊断详情。")
```

- [x] **Step 5: Preserve existing delete/toggle behavior**

In `_remove_selected_item()`, accept both old and new plugin data:

```python
if data.get("kind") in {"plugin", "plugin_status"} and data.get("path"):
    plugins_root = Path(__file__).parent.parent.parent.parent / "plugins"
    plugin_name = Path(data["path"]).name
    if not confirm_action(self, "确认删除", f"确定删除插件 '{plugin_name}' 吗？"):
        return
    if _remove_plugin_dir(Path(data["path"]), plugins_root):
        self._refresh_plugins()
        show_feedback(self, "删除成功", f"插件 '{plugin_name}' 已删除。")
        return
```

In `_toggle_selected_mcp()`, accept `"mcp_status"`:

```python
if not data or data.get("kind") not in {"mcp", "mcp_status"}:
    self._show_error("请选择一个 MCP 服务器条目。")
    return
```

- [x] **Step 6: Run settings tests**

Run:

```bash
python -m pytest tests/test_settings_window.py tests/test_plugin_import.py -q
```

Expected: PASS.

---

### Task 6: 文档同步

**Files:**
- Modify: `docs/plugin-mcp.md`
- Modify: `docs/development.md`
- Modify: `CLAUDE.md`

- [x] **Step 1: Update docs**

Document these facts:

- 插件 / MCP 页显示插件加载状态、MCP 连接状态、工具数量、错误类型和诊断消息。
- `MCPServerConfig` 支持 `connect_timeout_seconds`、`request_timeout_seconds`、`retry_attempts`。
- 工具目录可显示工具来源名称，不改变 tool calling 的 qualified name。
- 本阶段不实现 marketplace，也不自动执行第三方 MCP 返回的命令。

- [x] **Step 2: Run docs scan**

Run:

```bash
rg -n "connect_timeout_seconds|request_timeout_seconds|retry_attempts|插件 / MCP|诊断" CLAUDE.md docs
```

Expected: matches in updated docs.

---

### Task 7: Final verification

**Files:**
- All changed files

- [x] **Step 1: Focused tests**

Run:

```bash
python -m pytest tests/test_config.py tests/test_plugin_import.py tests/test_mcp_host.py tests/test_tool_registry.py tests/test_settings_window.py -q
```

Expected: PASS.

- [x] **Step 2: Syntax check**

Run:

```bash
python -m py_compile config/schema.py core/plugin_host.py core/mcp_host.py core/tool_registry.py ui/settings/pages/plugin_page.py
```

Expected: exit code 0.

- [x] **Step 3: Full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: PASS.

- [x] **Step 4: Diff check**

Run:

```bash
git diff --check
```

Expected: exit code 0.
