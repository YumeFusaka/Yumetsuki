# SessionContext 与热路径实施计划

> **面向执行型代理：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项推进。所有步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 实现专门的 `SessionContext` 短期记忆层，并把它接入首字热路径，让 Yumetsuki 在不把长期记忆、深规划和外部整理逻辑强行塞进首字前的前提下，稳定保持多轮连续性。

**架构：** 新增 `session/` 包，承载会话工作记忆、SQLite 快照、热上下文构建与 `mem0` 升格边界；由 `AgentManager` 驱动更新，`LLMManager` 负责注入 prompt。热路径只读取轻量同步状态，摘要压缩与长期记忆升格后置异步处理。

**技术栈：** Python、sqlite3、dataclasses、pytest、现有 AgentManager / LLMManager / Mem0 体系。

---

## 文件结构

### 新增文件

- `session/__init__.py`
- `session/context.py`
- `session/policy.py`
- `session/store.py`
- `session/manager.py`
- `tests/test_session_context.py`
- `tests/test_session_store.py`

### 需要修改的现有文件

- `config/schema.py`
- `config/manager.py`
- `agent/manager.py`
- `llm/manager.py`
- `memory/mem0_store.py`
- `tests/test_agent_manager.py`
- `docs/architecture.md`
- `docs/development.md`

---

## 任务 0：先补齐 SessionContext 的配置模型

**文件：**
- 修改：`config/schema.py`
- 修改：`config/manager.py`
- 测试：`tests/test_config_agent.py`

- [ ] **步骤 1：先写失败测试，锁定短期记忆关键参数必须进入配置层**

```python
from config.schema import AgentConfig


def test_agent_config_exposes_session_context_config():
    cfg = AgentConfig()

    assert hasattr(cfg, "session_context")
    assert hasattr(cfg.session_context, "recent_turns_limit")
    assert hasattr(cfg.session_context, "constraint_ttl_turns")
    assert hasattr(cfg.session_context, "mem0_promotion_importance")
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

`python -m pytest tests/test_config_agent.py -k session_context_config -v`

预期：

- 失败，因为相关配置模型尚不存在。

- [ ] **步骤 3：写最小配置实现**

```python
# config/schema.py
class SessionContextConfig(BaseModel):
    recent_turns_limit: int = 8
    working_facts_limit: int = 12
    prompt_facts_limit: int = 3
    prompt_turns_limit: int = 2
    constraint_ttl_turns: int = 12
    mem0_promotion_importance: float = 0.9


class AgentConfig(BaseModel):
    ...
    session_context: SessionContextConfig = SessionContextConfig()
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_config_agent.py -k session_context_config -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add config/schema.py config/manager.py tests/test_config_agent.py
git commit -m "feat(config): add session context settings"
```

---

## 任务 1：建立 SessionContext 数据模型

**文件：**
- 新建：`session/__init__.py`
- 新建：`session/context.py`
- 测试：`tests/test_session_context.py`

- [ ] **步骤 1：先写失败测试，锁定 SessionContext 的最小结构**

```python
from session.context import SessionContext, SessionTurn, SessionSummary


def test_session_context_new_has_empty_runtime_state():
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    assert ctx.session_id == "s1"
    assert ctx.user_id == "u1"
    assert ctx.turn_counter == 0
    assert ctx.recent_turns == []
    assert ctx.working_facts == []
    assert ctx.active_tasks == []
    assert isinstance(ctx.summary, SessionSummary)


def test_session_turn_helpers_assign_expected_role():
    turn = SessionTurn.user(turn_id=1, text="先不要改代码")

    assert turn.role == "user"
    assert turn.text == "先不要改代码"
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

`python -m pytest tests/test_session_context.py -k "new_has_empty_runtime_state or turn_helpers" -v`

预期：

- 失败，因为 `session.context` 尚不存在。

- [ ] **步骤 3：写最小实现**

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

    @classmethod
    def assistant(cls, turn_id: int, text: str) -> "SessionTurn":
        return cls(turn_id=turn_id, role="assistant", text=text, timestamp=time())


@dataclass
class SessionSummary:
    current_topic: str = ""
    summary_text: str = ""
    mood_state: str = ""
    relationship_state: str = ""
    updated_turn_id: int = 0


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
```

- [ ] **步骤 4：再跑测试，确认通过**

运行：

`python -m pytest tests/test_session_context.py -k "new_has_empty_runtime_state or turn_helpers" -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/__init__.py session/context.py tests/test_session_context.py
git commit -m "feat(session): add session context models"
```

## 任务 2：增加 SessionPolicy，建立热路径更新规则

**文件：**
- 新建：`session/policy.py`
- 修改：`session/context.py`
- 测试：`tests/test_session_context.py`

- [ ] **步骤 1：先写失败测试，锁定约束提取和热上下文输出**

```python
from session.context import SessionContext
from session.policy import SessionPolicy


def test_record_user_input_extracts_constraint_fact():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    assert ctx.turn_counter == 1
    assert ctx.recent_turns[-1].text == "先不要改代码，只讨论方案。"
    assert any(f.category == "constraint" for f in ctx.working_facts)


def test_build_prompt_context_emphasizes_topic_and_recent_facts():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先讨论短期记忆架构")
    prompt_context = policy.build_prompt_context(ctx)

    assert "当前会话短期上下文" in prompt_context
    assert "当前主题" in prompt_context
    assert "先讨论短期记忆架构" in prompt_context
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_session_context.py -k "constraint_fact or prompt_context_emphasizes" -v`

预期：

- 失败，因为 `SessionPolicy` 尚不存在。

- [ ] **步骤 3：写最小规则实现**

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
        ctx.turn_counter = turn_id
        ctx.recent_turns.append(SessionTurn.user(turn_id=turn_id, text=text))
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
        ctx.turn_counter = turn_id
        ctx.recent_turns.append(SessionTurn.assistant(turn_id=turn_id, text=text))

    def build_prompt_context(self, ctx: SessionContext) -> str:
        lines = ["当前会话短期上下文:"]
        lines.append(f"- 当前主题: {ctx.summary.current_topic}")
        if ctx.working_facts:
            lines.append("- 当前会话关键点:")
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

`python -m pytest tests/test_session_context.py -k "constraint_fact or prompt_context_emphasizes" -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/policy.py session/context.py tests/test_session_context.py
git commit -m "feat(session): add hot-path session policy"
```

## 任务 3：增加 SQLite 快照存储

**文件：**
- 新建：`session/store.py`
- 测试：`tests/test_session_store.py`

- [ ] **步骤 1：先写失败测试，锁定最小快照读写**

```python
from pathlib import Path

from session.context import SessionContext
from session.policy import SessionPolicy
from session.store import SessionContextStore


def test_session_store_round_trips_recent_turns(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    policy = SessionPolicy()
    ctx = SessionContext.new(session_id="s1", user_id="u1")

    policy.record_user_input(ctx, "先讨论方案")
    store.save(ctx)
    loaded = store.load(user_id="u1", session_id="s1")

    assert loaded is not None
    assert loaded.recent_turns[-1].text == "先讨论方案"


def test_session_store_returns_none_for_unknown_session(tmp_path: Path):
    store = SessionContextStore(tmp_path / "session.db")
    assert store.load(user_id="u1", session_id="missing") is None
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
            ctx.summary = SessionSummary(**json.loads(row[1]))
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
git commit -m "feat(session): add sqlite session snapshots"
```

## 任务 4：增加 SessionContextManager 并接入 Agent 与 LLM 热路径

**文件：**
- 新建：`session/manager.py`
- 修改：`agent/manager.py`
- 修改：`llm/manager.py`
- 修改：`tests/test_agent_manager.py`

- [ ] **步骤 1：先写失败测试，锁定短期上下文必须进入 LLM**

```python
def test_agent_manager_passes_session_context_into_llm():
    llm = FakeLLMManager("[emotion:开心]我们继续讨论方案")
    session_manager = FakeSessionManager("当前会话短期上下文:\n- 当前主题: 讨论方案")
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
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

`python -m pytest tests/test_agent_manager.py -k session_context_into_llm -v`

预期：

- 失败，因为 `session_manager` 和 `session_context` 尚未接线。

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
# llm/manager.py（概念性改动）
def _build_messages(self, user_input: str, session_context: str = "", extra_context: str = "") -> list[dict]:
    messages = []
    if self._character_prompt:
        messages.append({"role": "system", "content": self._character_prompt})
    if session_context:
        messages.append({"role": "system", "content": session_context})
    if extra_context:
        messages.append({"role": "system", "content": f"补充上下文：\n{extra_context}"})
    ...
```

```python
# agent/manager.py（概念性改动）
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

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_agent_manager.py -k session_context_into_llm -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/manager.py agent/manager.py llm/manager.py tests/test_agent_manager.py
git commit -m "feat(agent): wire session context into hot path"
```

## 任务 5：建立 mem0 保守升格边界

**文件：**
- 修改：`session/policy.py`
- 修改：`memory/mem0_store.py`
- 测试：`tests/test_session_context.py`

- [ ] **步骤 1：先写失败测试，锁定保守升格默认策略**

```python
def test_policy_collects_only_stable_mem0_candidates():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "记住，我以后都不想看长篇回答。")
    candidates = policy.collect_mem0_candidates(ctx)

    assert len(candidates) == 1
    assert "不想看长篇回答" in candidates[0].content
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

`python -m pytest tests/test_session_context.py -k stable_mem0_candidates -v`

预期：

- 失败，因为 `collect_mem0_candidates` 尚未定义。

- [ ] **步骤 3：写最小实现，先只保留稳定候选**

```python
# session/policy.py
def collect_mem0_candidates(self, ctx: SessionContext) -> list[WorkingFact]:
    return [
        fact for fact in ctx.working_facts
        if fact.importance >= self._config.mem0_promotion_importance
        and fact.category in {"constraint", "preference", "intent"}
    ]
```

```python
# memory/mem0_store.py
def add_memory(self, content: str, memory_type: str, user_id: str) -> None:
    self._memory_client.add(
        [{"role": "assistant", "content": content}],
        user_id=user_id,
        metadata={"type": memory_type},
    )
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

`python -m pytest tests/test_session_context.py -k stable_mem0_candidates -v`

预期：

- 通过。

- [ ] **步骤 5：提交这一小步**

```bash
git add session/policy.py memory/mem0_store.py tests/test_session_context.py
git commit -m "feat(memory): add mem0 promotion boundary"
```

## 任务 6：同步文档到 SessionContext 详细设计

**文件：**
- 修改：`docs/README.md`
- 修改：`docs/architecture.md`
- 修改：`docs/development.md`

- [ ] **步骤 1：同步总览文档入口与短期记忆职责边界**

```markdown
- `docs/README.md`
  增加 SessionContext / 热路径 spec 与 plan 入口。
- `docs/architecture.md`
  把 `session/` 提升为一等模块，并补充 prompt 分层顺序。
- `docs/development.md`
  明确 SessionContext 负责短期记忆，`mem0` 只负责长期记忆。
```

- [ ] **步骤 2：运行轻量 sanity check**

运行：

`python -m pytest tests/test_session_context.py tests/test_session_store.py tests/test_agent_manager.py -q`

预期：

- 通过。

- [ ] **步骤 3：提交这一小步**

```bash
git add docs/README.md docs/architecture.md docs/development.md
git commit -m "docs: sync session context design references"
```

## 自检

- spec 覆盖检查：
  - `SessionContext` 数据结构 → 任务 1-2
  - SQLite 快照 → 任务 3
  - 首字热路径接线 → 任务 4
  - 长短期记忆边界 → 任务 5
  - 文档同步 → 任务 6
- 占位词检查：
  - 文档中不应出现 `TODO`、`TBD`
  - 每个任务都必须给出明确文件、测试、命令和代码片段
- 命名一致性检查：
  - `SessionContext`、`SessionPolicy`、`SessionContextStore`、`SessionContextManager` 在全文中保持一致
