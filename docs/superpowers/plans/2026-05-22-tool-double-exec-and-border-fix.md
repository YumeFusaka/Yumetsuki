# Tool Double Execution And Border Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复聊天窗输入框与圆形按钮顶边主题色缺失的问题，并修复 `tool` 模式下副作用工具被执行两次的问题。

**Architecture:** 保持现有 Agent 分层架构不变，只给 `LLMManager.chat_stream()` 增加一个显式 `allow_tools` 开关，并在 `AgentManager` 已经执行过工具的路径上关闭后续 tools 暴露。聊天窗样式仅调整顶边高光颜色，不改动其他布局和透明度参数。

**Tech Stack:** Python 3.10+, PySide6, pytest, 当前 Agent/LLM 聊天链路

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `llm/manager.py` | 控制 LLM 流式对话时是否向模型暴露 tools |
| `agent/manager.py` | 在已执行工具的路径上关闭后续二次 tool-calling |
| `ui/chat/window.py` | 调整输入框和按钮顶边高光为浅粉主题色 |
| `tests/test_agent_manager.py` | 验证 `tool` 模式下 Agent 不再让 LLM 二次调用工具 |
| `tests/test_llm_manager_tools.py` | 验证 `LLMManager` 在 `allow_tools=False` 时不暴露 tools |
| `tests/test_chat_window_scale.py` | 验证输入框与按钮样式包含顶边主题色 |

---

### Task 1: 先补回归测试并确认失败

**Files:**
- Modify: `tests/test_agent_manager.py`
- Modify: `tests/test_llm_manager_tools.py`
- Modify: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 在 `tests/test_agent_manager.py` 增加 Agent 路径回归测试**

```python
def test_agent_manager_tool_mode_disables_followup_llm_tools():
    llm = FakeLLMManager("[emotion:开心]已经打开了")
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(
            mode="tool",
            goal="open browser",
            tool_name="system_control__open_browser",
            arguments={},
        )),
        executor=FakeExecutor("已打开浏览器"),
        memory_store=FakeMemoryStore(),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("打开浏览器"))

    assert results[-1].clean_text == "已经打开了"
    assert llm.calls[0]["allow_tools"] is False
    assert "已打开浏览器" in llm.calls[0]["extra_context"]
```

- [ ] **Step 2: 在 `tests/test_llm_manager_tools.py` 增加 `allow_tools=False` 回归测试**

```python
class NoToolAdapter(LLMAdapter):
    def __init__(self):
        self.calls: list[dict] = []

    def stream_chat(self, messages: list[dict], tools: list[dict] | None = None):
        self.calls.append({"messages": messages, "tools": tools})
        yield "普通回复"


def test_llm_manager_can_disable_tools_for_reply_only_phase():
    adapter = NoToolAdapter()
    manager = LLMManager(LLMConfig(api_key="test"), tool_registry=FakeMCPRegistry())
    manager._adapter = adapter

    results = list(manager.chat_stream("打开浏览器", allow_tools=False))

    assert results[-1].clean_text == "普通回复"
    assert adapter.calls[0]["tools"] is None
```

- [ ] **Step 3: 在 `tests/test_chat_window_scale.py` 增加顶边主题色断言**

```python
def test_rebuild_stylesheet_keeps_theme_tint_on_top_border():
    """输入框和按钮顶边应保留浅粉主题色，而不是纯白。"""
    import ui.chat.window as win_module

    source = inspect.getsource(win_module.ChatWindow._rebuild_stylesheet)
    assert "border-top: 1px solid rgba(255, 214, 224, 0.78);" in source
    assert "border-top: 1px solid rgba(255, 220, 228, 0.8);" in source
```

- [ ] **Step 4: 运行针对性测试，确认按预期失败**

Run: `E:/Tool/Miniconda/envs/ai/python.exe -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_chat_window_scale.py -v`

Expected:
- `KeyError: 'allow_tools'` 或 `TypeError`，因为 `FakeLLMManager` / `LLMManager.chat_stream()` 还没有该参数
- 顶边颜色断言失败，因为源码里仍是接近纯白的 `border-top`

- [ ] **Step 5: 提交测试改动**

```bash
git add tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_chat_window_scale.py
git commit -m "test: add regressions for tool double execution and border tint"
```

---

### Task 2: 修复 Agent/LLM 二次工具调用

**Files:**
- Modify: `llm/manager.py`
- Modify: `agent/manager.py`
- Test: `tests/test_agent_manager.py`
- Test: `tests/test_llm_manager_tools.py`

- [ ] **Step 1: 给 `LLMManager.chat_stream()` 增加 `allow_tools` 参数**

```python
def chat_stream(
    self,
    user_input: str,
    extra_context: str = "",
    allow_tools: bool = True,
) -> Generator[ProcessedText, None, None]:
    messages = self._build_messages(user_input, extra_context=extra_context)
    self._history.append({"role": "user", "content": user_input})

    full_response = ""
    tools = self._tool_registry.tool_specs() if self._tool_registry and allow_tools else None
    for _ in range(3):
        ...
```

- [ ] **Step 2: 在 `AgentManager` 的 `tool` 路径关闭后续 tools**

```python
def chat_stream(self, user_input: str) -> Generator[ProcessedText, None, None]:
    ...
    allow_tools = True
    if plan.needs_multi_step and self._config.multi_step.enabled:
        ...
    elif plan.mode == "tool":
        result = self._executor.execute(plan, self._tool_registry)
        tool_result = str(result)
        tool_calls = [{"name": plan.tool_name, "result": tool_result}]
        allow_tools = False
        self._event_bus.publish(AgentEvents.TOOL_EXECUTED, {
            "tool": plan.tool_name,
            "result": tool_result[:200],
        })
    else:
        self._event_bus.publish(AgentEvents.TOOL_SKIPPED, {"reason": "chat mode"})

    extra_context = self._build_extra_context(memories, tool_result)
    self._event_bus.publish(AgentEvents.LLM_STARTED, {})
    final_result: ProcessedText | None = None
    assistant_response = ""
    for result in self._llm_manager.chat_stream(
        user_input,
        extra_context=extra_context,
        allow_tools=allow_tools,
    ):
        ...
```

- [ ] **Step 3: 兼容测试中的 `FakeLLMManager` 调用记录**

```python
class FakeLLMManager:
    def __init__(self, final_text="[emotion:开心]好的"):
        self.final_text = final_text
        self.calls = []

    def chat_stream(self, user_input, extra_context="", allow_tools=True):
        self.calls.append({
            "user_input": user_input,
            "extra_context": extra_context,
            "allow_tools": allow_tools,
        })
        yield ProcessedText(clean_text=self.final_text.replace("[emotion:开心]", ""), emotion="开心")
```

- [ ] **Step 4: 运行相关测试确认通过**

Run: `E:/Tool/Miniconda/envs/ai/python.exe -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py -v`

Expected: PASS

- [ ] **Step 5: 提交二次工具调用修复**

```bash
git add agent/manager.py llm/manager.py tests/test_agent_manager.py tests/test_llm_manager_tools.py
git commit -m "fix: prevent duplicate tool execution in tool mode"
```

---

### Task 3: 修复聊天窗顶边主题色

**Files:**
- Modify: `ui/chat/window.py`
- Test: `tests/test_chat_window_scale.py`

- [ ] **Step 1: 把输入框顶边改为浅粉高光**

```python
self._input.setStyleSheet(f"""
    QLineEdit {{
        background: rgba(255, 255, 255, 0.64);
        border: 1px solid rgba(212, 86, 122, 0.32);
        border-top: 1px solid rgba(255, 214, 224, 0.78);
        border-bottom: 1px solid rgba(155, 48, 96, 0.18);
        border-radius: {radius}px; padding: {int(8*s)}px {padding}px;
        color: #4a3040; font-size: {input_font}px;
    }}
    ...
""")
```

- [ ] **Step 2: 把圆形按钮顶边改为浅粉高光**

```python
btn.setStyleSheet(f"""
    QPushButton {{
        background: rgba(255,255,255,0.68);
        border: 1px solid rgba(212, 86, 122, 0.32);
        border-top: 1px solid rgba(255, 220, 228, 0.8);
        border-bottom: 1px solid rgba(155, 48, 96, 0.18);
        border-radius: {btn_radius}px; color: #6b4a5a; font-size: {int(14*s)}px;
    }}
    ...
""")
```

- [ ] **Step 3: 运行聊天窗相关测试**

Run: `E:/Tool/Miniconda/envs/ai/python.exe -m pytest tests/test_chat_window_scale.py -v`

Expected: PASS

- [ ] **Step 4: 提交样式修复**

```bash
git add ui/chat/window.py tests/test_chat_window_scale.py
git commit -m "fix: restore themed top border tint in chat controls"
```

---

### Task 4: 集成验证与文档同步

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/ui-guidelines.md`
- Test: `tests/`

- [ ] **Step 1: 更新文档，记录本次修复点**

```markdown
# CLAUDE.md
- 聊天窗控件边框修正：输入框和按钮顶边恢复浅粉主题高光
- Agent 工具调用修正：tool 模式下禁止后续 LLM 二次调用同轮工具

# docs/README.md
- 第三阶段补充修复：
  - 修复聊天窗控件顶边主题色缺失
  - 修复副作用工具重复执行

# docs/ui-guidelines.md
### 输入框
- 顶边高光应使用同主题浅粉色，不得因纯白高光导致边缘消失

### 按钮
- 圆形按钮的高光边缘必须保持主题色层次，不得出现顶边发白丢失
```

- [ ] **Step 2: 运行自动化验证**

Run: `E:/Tool/Miniconda/envs/ai/python.exe -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_chat_window_scale.py -v`
Expected: PASS

Run: `E:/Tool/Miniconda/envs/ai/python.exe -m pytest tests/ -q`
Expected: PASS

Run: `C:\\Users\\j\\AppData\\Local\\Microsoft\\WindowsApps\\pwsh.exe -Command "E:/Tool/Miniconda/envs/ai/python.exe -m py_compile ui/chat/window.py agent/manager.py llm/manager.py"`
Expected: no output

- [ ] **Step 3: 手动验证**

Run: `E:/Tool/Miniconda/envs/ai/python.exe main.py`

验证清单：
1. 输入框和圆形按钮顶边可见浅粉主题高光
2. “打开浏览器”“打开文件”等副作用型操作只触发一次

- [ ] **Step 4: 提交最终改动**

```bash
git add CLAUDE.md docs/README.md docs/ui-guidelines.md ui/chat/window.py agent/manager.py llm/manager.py tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_chat_window_scale.py
git commit -m "fix: avoid duplicate tool calls and restore top border tint"
```
