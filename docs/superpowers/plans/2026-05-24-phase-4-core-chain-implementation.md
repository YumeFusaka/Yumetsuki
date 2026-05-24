# Phase 4 核心链路实施计划

> **面向执行型代理：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项推进。所有步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 完成 Yumetsuki 的 Phase 4，建立真正的短期会话上下文层，缩短首字热路径压力，收紧 EventBus 线程边界，并把 TTS 从“可用但脆”提升为“长时间运行可恢复”。

**架构：** 在 `AgentManager` 与长期记忆之间新增 `SessionContext` 子系统，让每轮聊天优先依赖轻量短期会话上下文，而不是只依赖原始 `_history` 和长期检索；同时把 TTS 改造成有界、可超时、可失败推进的固定流水线。`mem0` 保留为长期记忆，易变的多轮状态迁入 `SessionContext`。

**技术栈：** Python、PySide6、pytest、sqlite3、dataclasses / Pydantic 风格模型、基于 `requests` 的 TTS 适配器、现有 OpenAI-compatible LLM 链路。

---

## 文件结构

### 新增文件

- `session/__init__.py`
  导出短期记忆子系统的公共符号。
- `session/context.py`
  定义 `SessionContext`、`SessionTurn`、`WorkingFact`、`ActiveTask`、`SessionSummary`。
- `session/store.py`
  提供内存态注册与 SQLite 快照持久化。
- `session/policy.py`
  负责 working facts 提取、recent turns 裁切、facts 衰减和长期记忆升格候选收集。
- `session/manager.py`
  提供给 `AgentManager` 使用的高层门面。
- `tests/test_session_context.py`
  覆盖数据演进、工作事实提取、裁切和 prompt 上下文构建。
- `tests/test_session_store.py`
  覆盖 SQLite 快照读写。
- `tests/test_event_bus.py`
  覆盖事件发布的线程安全语义。

### 需要修改的现有文件

- `config/schema.py`
  增加短期记忆、事件队列与 TTS 有界流水线所需的配置模型。
- `config/manager.py`
  持久化新增配置字段。
- `agent/manager.py`
  集成 `SessionContextManager`，把短期上下文接入聊天主链路。
- `llm/manager.py`
  支持“短期上下文优先，长期记忆次之”的消息组装。
- `core/event_bus.py`
  引入线程安全发布与 handler 快照语义。
- `ui/chat/window.py`
  把当前无上限句段 worker 扩散改成有界 TTS 流水线。
- `tts/adapters/gptsovits.py`
  增加读超时、句段总超时、明确重试 / 回退边界。
- `tests/test_agent_manager.py`
  覆盖 SessionContext 接线与热路径行为。
- `tests/test_chat_tts_flow.py`
  覆盖有界 TTS 流水线、失败推进、超时状态流转。
- `tests/test_config_agent.py`
  覆盖新增运行时配置默认值。

### 实施完成后需再次同步的文档

- `docs/architecture.md`
- `docs/development.md`

说明：

- 上述文档现在已经同步到路线图级别；
- 只有当 Phase 4 真实实现和当前设计发生偏离时，才需要再次补充实现级说明。

---

## 任务 0：先补齐 Phase 4 的配置模型

**文件：**
- 修改：`config/schema.py`
- 修改：`config/manager.py`
- 测试：`tests/test_config_agent.py`

- [ ] **步骤 1：先写失败测试，锁定“关键参数配置化”原则**

```python
from config.schema import AgentConfig


def test_agent_config_exposes_session_context_runtime_settings():
    cfg = AgentConfig()

    assert hasattr(cfg, "session_context")
    assert hasattr(cfg.session_context, "recent_turns_limit")
    assert hasattr(cfg.session_context, "constraint_ttl_turns")


def test_agent_config_exposes_tts_runtime_limits():
    cfg = AgentConfig()

    assert hasattr(cfg, "tts_runtime")
    assert hasattr(cfg.tts_runtime, "pcm_read_timeout_seconds")
    assert hasattr(cfg.tts_runtime, "max_translation_workers")
    assert hasattr(cfg.tts_runtime, "max_tts_workers")
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

`python -m pytest tests/test_config_agent.py -k "session_context_runtime_settings or tts_runtime_limits" -v`

预期：

- 失败，因为这些配置模型尚不存在。

- [ ] **步骤 3：写最小配置实现，让关键体验参数先进入配置层**

```python
# config/schema.py
class SessionContextConfig(BaseModel):
    recent_turns_limit: int = 8
    working_facts_limit: int = 12
    prompt_facts_limit: int = 3
    prompt_turns_limit: int = 2
    constraint_ttl_turns: int = 12
    mem0_promotion_importance: float = 0.9


class TTSRuntimeConfig(BaseModel):
    pcm_read_timeout_seconds: int = 15
    segment_total_timeout_seconds: int = 45
    max_translation_workers: int = 1
    max_tts_workers: int = 2
    tts_queue_limit: int = 16


class AgentConfig(BaseModel):
    ...
    session_context: SessionContextConfig = SessionContextConfig()
    tts_runtime: TTSRuntimeConfig = TTSRuntimeConfig()
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_config_agent.py -k "session_context_runtime_settings or tts_runtime_limits" -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add config/schema.py config/manager.py tests/test_config_agent.py
git commit -m "feat(config): add phase 4 runtime settings"
```

---

## 任务 1：建立 SessionContext 数据模型

**文件：**
- 新建：`session/__init__.py`
- 新建：`session/context.py`
- 测试：`tests/test_session_context.py`

- [ ] **步骤 1：先写失败测试，锁定 SessionContext 基础形态**

```python
from session.context import SessionContext, SessionTurn, WorkingFact, ActiveTask, SessionSummary


def test_session_context_starts_empty():
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    assert ctx.session_id == "s1"
    assert ctx.user_id == "u1"
    assert ctx.turn_counter == 0
    assert ctx.recent_turns == []
    assert ctx.working_facts == []
    assert ctx.active_tasks == []
    assert ctx.summary.current_topic == ""


def test_session_context_append_turn_increments_counter():
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    turn = SessionTurn.user(turn_id=1, text="先讨论方案")
    ctx.append_turn(turn)

    assert ctx.turn_counter == 1
    assert ctx.recent_turns[-1].text == "先讨论方案"
    assert ctx.recent_turns[-1].role == "user"
```

- [ ] **步骤 2：运行测试，确认当前确实失败**

运行：

`python -m pytest tests/test_session_context.py -k basics -v`

预期：

- 失败，报 `session.context` 不存在，或 `SessionContext.new` 未定义。

- [ ] **步骤 3：写最小实现，只满足测试通过**

```python
# session/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class SessionTurn:
    turn_id: int
    role: str
    text: str
    timestamp: float
    tokens_estimate: int = 0
    topic_tags: list[str] = field(default_factory=list)
    importance: float = 0.0

    @classmethod
    def user(cls, turn_id: int, text: str) -> "SessionTurn":
        return cls(turn_id=turn_id, role="user", text=text, timestamp=time())


@dataclass
class WorkingFact:
    fact_id: str
    content: str
    category: str
    importance: float
    created_turn_id: int
    last_seen_turn_id: int
    ttl_turns: int
    source: str
    sticky: bool = False


@dataclass
class ActiveTask:
    task_id: str
    goal: str
    status: str
    current_step: str
    tool_name: str | None
    last_result: str
    created_turn_id: int
    updated_turn_id: int
    importance: float


@dataclass
class SessionSummary:
    current_topic: str = ""
    summary_text: str = ""
    mood_state: str = ""
    relationship_state: str = ""
    updated_turn_id: int = 0


@dataclass
class SessionContext:
    session_id: str
    user_id: str
    turn_counter: int = 0
    recent_turns: list[SessionTurn] = field(default_factory=list)
    working_facts: list[WorkingFact] = field(default_factory=list)
    active_tasks: list[ActiveTask] = field(default_factory=list)
    summary: SessionSummary = field(default_factory=SessionSummary)

    @classmethod
    def new(cls, session_id: str, user_id: str) -> "SessionContext":
        return cls(session_id=session_id, user_id=user_id)

    def append_turn(self, turn: SessionTurn) -> None:
        self.recent_turns.append(turn)
        self.turn_counter = max(self.turn_counter, turn.turn_id)
```

- [ ] **步骤 4：再跑测试，确认转绿**

运行：

`python -m pytest tests/test_session_context.py -k basics -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/__init__.py session/context.py tests/test_session_context.py
git commit -m "feat(session): add session context data models"
```

## 任务 2：增加 SessionPolicy，建立热路径更新规则

**文件：**
- 新建：`session/policy.py`
- 修改：`session/context.py`
- 测试：`tests/test_session_context.py`

- [ ] **步骤 1：先写失败测试，锁定工作事实提取和热上下文格式**

```python
from session.context import SessionContext
from session.policy import SessionPolicy


def test_policy_extracts_high_priority_user_constraint():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    assert any(f.category == "constraint" for f in ctx.working_facts)
    assert any("只讨论方案" in f.content for f in ctx.working_facts)


def test_policy_build_prompt_context_contains_recent_turns_and_summary():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()
    policy.record_user_input(ctx, "先讨论性能问题")
    policy.record_assistant_reply(ctx, "好，我们先分析性能。")

    prompt_context = policy.build_prompt_context(ctx)

    assert "当前会话短期上下文" in prompt_context
    assert "先讨论性能问题" in prompt_context
    assert "好，我们先分析性能。" in prompt_context
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

`python -m pytest tests/test_session_context.py -k "constraint or prompt_context" -v`

预期：

- 失败，因为 `SessionPolicy` 及其方法尚不存在。

- [ ] **步骤 3：写最小实现，先用规则驱动，不引入额外外部 LLM**

```python
# session/policy.py
from __future__ import annotations

import uuid

from session.context import SessionContext, SessionTurn, WorkingFact


class SessionPolicy:
    def __init__(self, config):
        self._config = config

    def record_user_input(self, ctx: SessionContext, text: str) -> None:
        turn_id = ctx.turn_counter + 1
        ctx.append_turn(SessionTurn.user(turn_id=turn_id, text=text))
        if "先不要" in text or "只讨论" in text:
            ctx.working_facts.append(
                WorkingFact(
                    fact_id=uuid.uuid4().hex,
                    content=text,
                    category="constraint",
                    importance=0.95,
                    created_turn_id=turn_id,
                    last_seen_turn_id=turn_id,
                    ttl_turns=self._config.constraint_ttl_turns,
                    source="user",
                    sticky=True,
                )
            )
        if not ctx.summary.current_topic:
            ctx.summary.current_topic = text[:32]
            ctx.summary.updated_turn_id = turn_id

    def record_assistant_reply(self, ctx: SessionContext, text: str) -> None:
        turn_id = ctx.turn_counter + 1
        turn = SessionTurn(turn_id=turn_id, role="assistant", text=text, timestamp=ctx.recent_turns[-1].timestamp)
        ctx.append_turn(turn)

    def build_prompt_context(self, ctx: SessionContext) -> str:
        lines = ["当前会话短期上下文:"]
        lines.append(f"- 当前主题: {ctx.summary.current_topic}")
        if ctx.working_facts:
            lines.append("- 最近高优先级信息:")
            for fact in ctx.working_facts[-self._config.prompt_facts_limit:]:
                lines.append(f"  - {fact.content}")
        if ctx.recent_turns:
            lines.append("- 最近对话:")
            for turn in ctx.recent_turns[-self._config.prompt_turns_limit:]:
                lines.append(f"  - {turn.role}: {turn.text}")
        return "\n".join(lines)
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_session_context.py -k "constraint or prompt_context" -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/policy.py session/context.py tests/test_session_context.py
git commit -m "feat(session): add session policy for working facts"
```

## 任务 3：增加 SessionStore 与 SQLite 快照持久化

**文件：**
- 新建：`session/store.py`
- 测试：`tests/test_session_store.py`

- [ ] **步骤 1：先写失败测试，锁定最小快照能力**

```python
from pathlib import Path

from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore


def test_store_round_trips_context_to_sqlite(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()
    policy.record_user_input(ctx, "今天先讨论记忆系统")

    store.save(ctx)
    loaded = store.load("u1", "s1")

    assert loaded is not None
    assert loaded.session_id == "s1"
    assert loaded.recent_turns[-1].text == "今天先讨论记忆系统"


def test_store_returns_none_for_unknown_session(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    assert store.load("u1", "missing") is None
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_session_store.py -v`

预期：

- 失败，因为 `SessionContextStore` 尚不存在。

- [ ] **步骤 3：写最小 SQLite 实现**

```python
# session/store.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from session.context import SessionContext, SessionSummary, SessionTurn


class SessionContextStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS session_contexts (user_id TEXT, session_id TEXT, turn_counter INTEGER, summary_json TEXT, PRIMARY KEY(user_id, session_id))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS session_turns (user_id TEXT, session_id TEXT, turn_id INTEGER, role TEXT, text TEXT, PRIMARY KEY(user_id, session_id, turn_id, role))"
            )

    def save(self, ctx: SessionContext) -> None:
        with self._connect() as conn:
            conn.execute(
                "REPLACE INTO session_contexts(user_id, session_id, turn_counter, summary_json) VALUES (?, ?, ?, ?)",
                (ctx.user_id, ctx.session_id, ctx.turn_counter, json.dumps(ctx.summary.__dict__, ensure_ascii=False)),
            )
            conn.execute("DELETE FROM session_turns WHERE user_id=? AND session_id=?", (ctx.user_id, ctx.session_id))
            conn.executemany(
                "INSERT INTO session_turns(user_id, session_id, turn_id, role, text) VALUES (?, ?, ?, ?, ?)",
                [(ctx.user_id, ctx.session_id, t.turn_id, t.role, t.text) for t in ctx.recent_turns],
            )

    def load(self, user_id: str, session_id: str) -> SessionContext | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT turn_counter, summary_json FROM session_contexts WHERE user_id=? AND session_id=?",
                (user_id, session_id),
            ).fetchone()
            if row is None:
                return None
            ctx = SessionContext.new(session_id=session_id, user_id=user_id)
            ctx.turn_counter = row[0]
            summary = json.loads(row[1])
            ctx.summary = SessionSummary(**summary)
            turns = conn.execute(
                "SELECT turn_id, role, text FROM session_turns WHERE user_id=? AND session_id=? ORDER BY turn_id ASC",
                (user_id, session_id),
            ).fetchall()
            for turn_id, role, text in turns:
                ctx.recent_turns.append(SessionTurn(turn_id=turn_id, role=role, text=text, timestamp=0.0))
            return ctx
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_session_store.py -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/store.py tests/test_session_store.py
git commit -m "feat(session): add sqlite-backed session store"
```

## 任务 4：把 SessionContextManager 接到 AgentManager 与 LLM 热路径

**文件：**
- 新建：`session/manager.py`
- 修改：`agent/manager.py`
- 修改：`llm/manager.py`
- 修改：`tests/test_agent_manager.py`

- [ ] **步骤 1：先写失败测试，锁定短期上下文必须进入 LLM**

```python
from agent.manager import AgentManager


def test_agent_manager_injects_short_term_session_context_before_reply():
    llm = FakeLLMManager("[emotion:开心]我记得刚刚说的是先讨论方案")
    session_manager = FakeSessionManager(prompt_context="当前会话短期上下文:\n- 最近高优先级信息:\n  - 先不要改代码，只讨论方案。")
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(
            mode="chat",
            goal="reply",
        )),
        executor=FakeExecutor(""),
        memory_store=FakeMemoryStore(),
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        user_id="u1",
    )

    list(manager.chat_stream("继续"))

    assert "当前会话短期上下文" in llm.calls[0]["session_context"]
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_agent_manager.py -k short_term_session_context -v`

预期：

- 失败，因为 `session_manager` 参数尚未接入，或 `session_context` 未传给 LLM。

- [ ] **步骤 3：写最小接线实现**

```python
# session/manager.py
from __future__ import annotations

from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore


class SessionContextManager:
    def __init__(self, store: SessionContextStore | None = None, policy: SessionPolicy | None = None):
        self._store = store
        self._policy = policy or SessionPolicy()
        self._live: dict[tuple[str, str], SessionContext] = {}

    def get_or_create(self, user_id: str, session_id: str) -> SessionContext:
        key = (user_id, session_id)
        if key in self._live:
            return self._live[key]
        ctx = self._store.load(user_id, session_id) if self._store else None
        if ctx is None:
            ctx = SessionContext.new(session_id=session_id, user_id=user_id)
        self._live[key] = ctx
        return ctx

    def record_user_input(self, ctx: SessionContext, text: str) -> None:
        self._policy.record_user_input(ctx, text)

    def record_assistant_reply(self, ctx: SessionContext, text: str) -> None:
        self._policy.record_assistant_reply(ctx, text)

    def build_prompt_context(self, ctx: SessionContext) -> str:
        return self._policy.build_prompt_context(ctx)
```

```python
# agent/manager.py（概念性接线）
self._session_manager = session_manager
self._session_id = session_id or "default-session"
ctx = self._session_manager.get_or_create(self._user_id, self._session_id)
self._session_manager.record_user_input(ctx, user_input)
session_context = self._session_manager.build_prompt_context(ctx)
for result in self._llm_manager.chat_stream(
    user_input,
    session_context=session_context,
    extra_context=extra_context,
    allow_tools=allow_tools,
):
    ...
self._session_manager.record_assistant_reply(ctx, assistant_response)
```

```python
# llm/manager.py（概念性签名）
def chat_stream(self, user_input: str, session_context: str = "", extra_context: str = "", allow_tools: bool = True):
    messages = self._build_messages(user_input, session_context=session_context, extra_context=extra_context)
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_agent_manager.py -k short_term_session_context -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/manager.py agent/manager.py llm/manager.py tests/test_agent_manager.py
git commit -m "feat(agent): inject session context into chat flow"
```

## 任务 5：让 EventBus 线程安全并适配主线程友好发布

**文件：**
- 修改：`core/event_bus.py`
- 新建：`tests/test_event_bus.py`

- [ ] **步骤 1：先写失败测试，锁定发布时的 handler 快照语义**

```python
from core.event_bus import EventBus


def test_event_bus_publish_uses_snapshot_of_handlers():
    bus = EventBus()
    seen = []

    def first(data):
        seen.append(("first", data))
        bus.unsubscribe("x", first)

    def second(data):
        seen.append(("second", data))

    bus.subscribe("x", first)
    bus.subscribe("x", second)

    bus.publish("x", 1)

    assert seen == [("first", 1), ("second", 1)]
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_event_bus.py -v`

预期：

- 失败，因为当前遍历订阅者时修改列表会带来不安全行为。

- [ ] **步骤 3：写最小线程安全实现**

```python
# core/event_bus.py
from collections import defaultdict
from threading import RLock
from typing import Any, Callable


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            if handler in self._handlers[event]:
                self._handlers[event].remove(handler)

    def publish(self, event: str, data: Any = None) -> None:
        with self._lock:
            handlers = list(self._handlers[event])
        for handler in handlers:
            handler(data)
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_event_bus.py -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add core/event_bus.py tests/test_event_bus.py
git commit -m "fix(core): make event bus publish thread-safe"
```

## 任务 6：给 GPT-SoVITS 流式链路增加有限读超时与失败推进

**文件：**
- 修改：`tts/adapters/gptsovits.py`
- 修改：`tests/test_tts_adapter.py`
- 修改：`tests/test_chat_tts_flow.py`

- [ ] **步骤 1：先写失败测试，锁定 PCM 不能无限等**

```python
def test_pcm_stream_request_uses_finite_read_timeout(monkeypatch):
    captured = {}

    class FakeSession:
        def post(self, url, json, timeout, stream=False):
            captured["timeout"] = timeout
            captured["stream"] = stream
            raise RuntimeError("stop")

    adapter = GPTSoVITSAdapter(TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="pcm_stream"))
    adapter._session = FakeSession()

    list(adapter.stream_synthesize("你好"))

    assert captured["stream"] is True
    assert captured["timeout"][1] is not None
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_tts_adapter.py -k finite_read_timeout -v`

预期：

- 失败，因为当前超时仍然使用 `(30, None)`。

- [ ] **步骤 3：写最小实现，先把无限等待变成有限等待**

```python
# tts/adapters/gptsovits.py
def _request_audio(self, payload: dict[str, object], audio_mode: str):
    wants_stream = audio_mode == self.AUDIO_MODE_PCM_STREAM
    read_timeout = self._runtime_config.pcm_read_timeout_seconds
    timeout = (30, read_timeout) if wants_stream else 30
    ...
```

```python
# tests/test_chat_tts_flow.py（补充断言）
def test_pcm_timeout_marks_segment_failed_and_advances(chat_window):
    key = (chat_window._current_utterance_id, 0)
    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="error", message="read timeout"))
    assert chat_window._next_play_id == 1
```

- [ ] **步骤 4：运行定向测试，确认通过**

运行：

`python -m pytest tests/test_tts_adapter.py -k finite_read_timeout -v`

`python -m pytest tests/test_chat_tts_flow.py -k pcm_timeout -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add tts/adapters/gptsovits.py tests/test_tts_adapter.py tests/test_chat_tts_flow.py
git commit -m "fix(tts): add finite PCM read timeout and failure progression"
```

## 任务 7：把无上限 TTS worker 扩散改成有界流水线

**文件：**
- 修改：`ui/chat/window.py`
- 修改：`tests/test_chat_tts_flow.py`

- [ ] **步骤 1：先写失败测试，锁定 worker 数不能无限扩张**

```python
def test_tts_enqueue_respects_translation_and_tts_worker_limits(chat_window, monkeypatch):
    chat_window._tts_output_lang = "en"
    chat_window._active_translation_workers = ["busy"]
    queued = []
    monkeypatch.setattr(chat_window, "_queue_pending_tts_segment", lambda *args: queued.append(args), raising=False)

    chat_window._enqueue_tts_segment("你好。")

    assert queued != []
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_chat_tts_flow.py -k worker_limits -v`

预期：

- 失败，因为当前实现会立即起新 worker，没有队列与上限。

- [ ] **步骤 3：写有界调度的最小实现**

```python
# ui/chat/window.py（概念性新增）
self._pending_translation_segments: list[tuple[int, int, str, str]] = []
self._pending_tts_segments: list[tuple[int, int, str]] = []
self._max_translation_workers = agent_config.tts_runtime.max_translation_workers
self._max_tts_workers = agent_config.tts_runtime.max_tts_workers

def _enqueue_tts_segment(self, text: str) -> None:
    ...
    if not self._tts_text_matches_output_lang(text):
        if len(self._active_translation_workers) >= self._max_translation_workers:
            self._pending_translation_segments.append((self._current_utterance_id, segment_id, text, self._tts_output_lang))
            return
        self._start_translation_worker(...)
        return
    if len(self._active_tts_workers) >= self._max_tts_workers:
        self._pending_tts_segments.append((self._current_utterance_id, segment_id, text))
        return
    self._start_tts_worker(...)
```

- [ ] **步骤 4：运行定向测试，确认通过**

运行：

`python -m pytest tests/test_chat_tts_flow.py -k worker_limits -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add ui/chat/window.py tests/test_chat_tts_flow.py
git commit -m "refactor(tts): add bounded translation and synthesis queues"
```

## 任务 8：Phase 4 末尾回归验证与文档同步

**文件：**
- 修改：`docs/architecture.md`
- 修改：`docs/development.md`
- 测试：`tests/test_agent_manager.py`
- 测试：`tests/test_chat_tts_flow.py`
- 测试：`tests/test_session_context.py`
- 测试：`tests/test_session_store.py`
- 测试：`tests/test_tts_adapter.py`

- [ ] **步骤 1：运行聚焦回归套件**

运行：

```bash
python -m pytest tests/test_session_context.py -q
python -m pytest tests/test_session_store.py -q
python -m pytest tests/test_agent_manager.py -q
python -m pytest tests/test_chat_tts_flow.py -q
python -m pytest tests/test_tts_adapter.py -q
```

预期：

- 全部通过。

- [ ] **步骤 2：把实现结果同步回架构和开发文档**

```markdown
- `docs/architecture.md`
  补上真实落地后的 `session/` 模块、prompt 分层和有界 TTS 流水线。
- `docs/development.md`
  补上新增测试、关键配置项和 Phase 4 实现说明。
```

- [ ] **步骤 3：做最终文档级 sanity check**

运行：

```bash
python -m pytest tests/test_session_context.py tests/test_session_store.py tests/test_agent_manager.py -q
```

预期：

- 通过。

- [ ] **步骤 4：提交这一小步**

```bash
git add docs/architecture.md docs/development.md tests/test_session_context.py tests/test_session_store.py tests/test_agent_manager.py tests/test_chat_tts_flow.py tests/test_tts_adapter.py
git commit -m "docs: sync architecture after phase 4 implementation"
```

## 自检

- spec 覆盖检查：
  - `SessionContext` 短期记忆系统 → 任务 1-4
  - 长短期记忆分层 → 任务 3-4
  - 首字热路径与上下文优先级 → 任务 4
  - EventBus / 线程治理 → 任务 5
  - TTS 稳定性修复 → 任务 6-7
  - 文档同步 → 任务 8
- 占位词检查：
  - 文档中不应出现 `TODO`、`TBD`
  - 每个任务都给出明确文件、测试、命令和代码片段
- 命名一致性检查：
  - `SessionContext`、`SessionPolicy`、`SessionContextStore`、`SessionContextManager` 在全文中保持一致
