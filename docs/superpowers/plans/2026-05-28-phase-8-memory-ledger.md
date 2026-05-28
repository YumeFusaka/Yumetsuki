# Phase 8-A Memory Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. 用户已要求后续不要开多 agent，本计划执行时默认使用单会话 inline execution。
>
> 状态：已实现，本地自动化验证通过；真实 Mem0 本地向量库写入联调待补。

**Goal:** 建立第一版记忆质量治理与可回溯记忆账本，让长期记忆写入、跳过、失败和冲突标记都能通过平台日志追踪。

**Architecture:** 新增独立的记忆候选评估模块，继续复用现有 `SessionContext`、`SessionPolicy`、`AgentManager` 和 `LogService`。第一版不新增数据库表和设置页，只把可追溯账本落在结构化平台日志中，并保持 Mem0 写入接口向后兼容。

**Tech Stack:** Python dataclass、现有 pytest、现有 `LogService` / `LogEvent`、现有 Mem0 包装层、PySide6 日志页面。

---

## 实施结果

- 已新增 `memory/ledger.py`，显式建模记忆候选、账本决策、归一化内容、跳过原因和冲突标记。
- 已在 `AgentManager` 后台记忆写入链路接入 `memory.ledger` 平台日志事件。
- 已收紧 `SessionPolicy.collect_mem0_candidates()`，短期约束不再直接升格为长期记忆候选。
- 已让 `Mem0MemoryStore.add_memory()` 接受可选 metadata，同时保持旧 Mem0 调用行为不变。
- 已把 `memory.ledger` 归入平台日志“记忆”链路。
- 已补实机验收待补记录：`docs/superpowers/smoke/2026-05-28-phase-8-memory-ledger-smoke.md`。
- 本地验证：
  - `python -m pytest tests/test_memory_ledger.py tests/test_session_context.py tests/test_mem0_store.py -q`：`18 passed`
  - `python -m pytest tests/test_agent_manager.py tests/test_logging_integration.py tests/test_system_log_page.py -q`：`56 passed`
  - `python -m py_compile memory/ledger.py memory/mem0_store.py session/policy.py agent/manager.py ui/settings/pages/system_log_page.py`：通过
  - `python -m pytest tests/ -q`：`528 passed`

## 范围

本计划只覆盖 Phase 8 的工作流 A：记忆质量治理与可回溯记忆账本。

做：

- 把“可写入 Mem0 的内容”显式建模为记忆候选。
- 对候选做确定性评估：升格、跳过、冲突标记、失败记录。
- 记录候选来源、类型、置信度、升格原因、跳过原因、关联 session / turn / trace。
- 保持记忆写入后台执行，不阻塞聊天首字和主回复链路。
- 在平台日志中形成可筛选的记忆账本事件。

不做：

- 不做长期记忆管理 UI。
- 不自动删除或覆盖旧记忆。
- 不把低置信模型反思结果直接写入 Mem0。
- 不改 Mem0 底层存储结构。
- 不实现 Phase 8 的会话画像、语音状态机、聊天窗完整微交互或主动行为 2.0。

## 文件结构

- Create: `memory/ledger.py`
  - 负责记忆候选、评估决策、内容归一化和确定性治理规则。
- Modify: `memory/mem0_store.py`
  - 保持 `add_memory()` 旧调用兼容，允许未来传入可选 metadata，但第一版不依赖 Mem0 metadata 能力。
- Modify: `agent/manager.py`
  - 在后台持久化链路中接入记忆账本评估和日志记录。
- Modify: `session/policy.py`
  - 收紧 `collect_mem0_candidates()`，避免短期约束被默认升格为长期记忆。
- Modify: `ui/settings/pages/system_log_page.py`
  - 确认 `memory.ledger` 归入“记忆”业务链路并有稳定颜色。
- Modify: `docs/README.md`
  - 增加 Phase 8-A 计划入口和当前阶段说明。
- Modify: `docs/development.md`
  - 增加 Phase 8-A 聚焦回归入口。
- Modify: `CLAUDE.md`
  - 增加 Phase 8-A 当前执行入口。
- Test: `tests/test_memory_ledger.py`
  - 覆盖候选评估的确定性规则。
- Test: `tests/test_agent_manager.py`
  - 覆盖后台记忆写入接入账本后的升格、跳过、失败日志。
- Test: `tests/test_mem0_store.py`
  - 覆盖 `add_memory()` 可选 metadata 的兼容性。
- Test: `tests/test_system_log_page.py`
  - 覆盖 `memory.ledger` 来源归类。

## 任务

### Task 1: 记忆候选与评估器

**Files:**
- Create: `memory/ledger.py`
- Test: `tests/test_memory_ledger.py`

- [x] **Step 1: 写候选评估失败测试**

在 `tests/test_memory_ledger.py` 新增：

```python
from memory.ledger import MemoryCandidate, MemoryLedgerEvaluator


def test_memory_ledger_promotes_explicit_preference():
    evaluator = MemoryLedgerEvaluator()
    candidate = MemoryCandidate(
        candidate_id="c1",
        content="记住，我以后都不想看长篇回答。",
        memory_type="preference",
        source="working_fact",
        confidence=0.95,
        session_id="s1",
        turn_id=1,
    )

    decisions = evaluator.evaluate([candidate])

    assert decisions[0].action == "promote"
    assert decisions[0].reason == "explicit_memory"
    assert decisions[0].normalized_content == "记住，我以后都不想看长篇回答"


def test_memory_ledger_skips_short_term_constraint():
    evaluator = MemoryLedgerEvaluator()
    candidate = MemoryCandidate(
        candidate_id="c1",
        content="先不要改代码，只讨论方案。",
        memory_type="constraint",
        source="working_fact",
        confidence=0.95,
        session_id="s1",
        turn_id=1,
    )

    decisions = evaluator.evaluate([candidate])

    assert decisions[0].action == "skip"
    assert decisions[0].reason == "short_term_constraint"


def test_memory_ledger_skips_duplicate_candidates():
    evaluator = MemoryLedgerEvaluator()
    candidates = [
        MemoryCandidate(
            candidate_id="c1",
            content="记住，我喜欢樱花主题。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=1,
        ),
        MemoryCandidate(
            candidate_id="c2",
            content="记住，我喜欢樱花主题",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=2,
        ),
    ]

    decisions = evaluator.evaluate(candidates)

    assert [item.action for item in decisions] == ["promote", "skip"]
    assert decisions[1].reason == "duplicate_candidate"


def test_memory_ledger_marks_possible_conflict_without_deleting_old_memory():
    evaluator = MemoryLedgerEvaluator()
    candidates = [
        MemoryCandidate(
            candidate_id="c1",
            content="记住，我喜欢长篇解释。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=1,
        ),
        MemoryCandidate(
            candidate_id="c2",
            content="记住，我不喜欢长篇解释。",
            memory_type="preference",
            source="working_fact",
            confidence=0.95,
            session_id="s1",
            turn_id=2,
        ),
    ]

    decisions = evaluator.evaluate(candidates)

    assert decisions[1].action == "promote"
    assert decisions[1].conflict is True
    assert decisions[1].reason == "possible_conflict"
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_memory_ledger.py -q`

Expected: FAIL，提示 `ModuleNotFoundError: No module named 'memory.ledger'`。

- [x] **Step 3: 实现最小评估器**

创建 `memory/ledger.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re


@dataclass(frozen=True)
class MemoryCandidate:
    candidate_id: str
    content: str
    memory_type: str
    source: str
    confidence: float
    session_id: str
    turn_id: int
    trace_id: str = ""
    request_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryLedgerDecision:
    candidate: MemoryCandidate
    action: str
    reason: str
    normalized_content: str
    conflict: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_log_details(self) -> dict:
        return {
            "candidate_id": self.candidate.candidate_id,
            "source": self.candidate.source,
            "memory_type": self.candidate.memory_type,
            "confidence": self.candidate.confidence,
            "action": self.action,
            "reason": self.reason,
            "conflict": self.conflict,
            "turn_id": self.candidate.turn_id,
            "content_preview": self.candidate.content[:120],
            "normalized_preview": self.normalized_content[:120],
        }


class MemoryLedgerEvaluator:
    _SHORT_TERM_MARKERS = ("先不要", "只讨论", "这次", "临时", "暂时")
    _EXPLICIT_MARKERS = ("记住", "以后", "长期", "一直", "永远")

    def evaluate(self, candidates: list[MemoryCandidate]) -> list[MemoryLedgerDecision]:
        decisions: list[MemoryLedgerDecision] = []
        seen: set[tuple[str, str]] = set()
        promoted_by_type: dict[str, list[str]] = {}
        for candidate in candidates:
            normalized = normalize_memory_content(candidate.content)
            key = (candidate.memory_type, normalized)
            if key in seen:
                decision = MemoryLedgerDecision(candidate, "skip", "duplicate_candidate", normalized)
            elif self._is_short_term_constraint(candidate):
                decision = MemoryLedgerDecision(candidate, "skip", "short_term_constraint", normalized)
            elif candidate.confidence < 0.8:
                decision = MemoryLedgerDecision(candidate, "skip", "low_confidence", normalized)
            else:
                conflict = self._has_possible_conflict(normalized, promoted_by_type.get(candidate.memory_type, []))
                reason = "possible_conflict" if conflict else self._promotion_reason(candidate)
                decision = MemoryLedgerDecision(candidate, "promote", reason, normalized, conflict=conflict)
                seen.add(key)
                promoted_by_type.setdefault(candidate.memory_type, []).append(normalized)
            decisions.append(decision)
        return decisions

    def _is_short_term_constraint(self, candidate: MemoryCandidate) -> bool:
        text = candidate.content
        return candidate.memory_type == "constraint" and any(marker in text for marker in self._SHORT_TERM_MARKERS)

    def _promotion_reason(self, candidate: MemoryCandidate) -> str:
        if any(marker in candidate.content for marker in self._EXPLICIT_MARKERS):
            return "explicit_memory"
        return "stable_candidate"

    def _has_possible_conflict(self, normalized: str, previous_items: list[str]) -> bool:
        if "不喜欢" not in normalized:
            return False
        positive = normalized.replace("不喜欢", "喜欢")
        return positive in previous_items


def normalize_memory_content(content: str) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    return text.rstrip("。.!！?？；;，, ")
```

- [x] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_memory_ledger.py -q`

Expected: PASS。

### Task 2: SessionPolicy 候选边界收紧

**Files:**
- Modify: `session/policy.py`
- Test: `tests/test_session_context.py`

- [x] **Step 1: 写短期约束不进入 Mem0 候选的失败测试**

在 `tests/test_session_context.py` 增加：

```python
def test_policy_does_not_collect_short_term_constraint_as_mem0_candidate():
    ctx = SessionContext.new(session_id="s1", user_id="u1")
    policy = SessionPolicy()

    policy.record_user_input(ctx, "先不要改代码，只讨论方案。")

    assert policy.collect_mem0_candidates(ctx) == []
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_session_context.py::test_policy_does_not_collect_short_term_constraint_as_mem0_candidate -q`

Expected: FAIL，当前 `constraint` 会被收集。

- [x] **Step 3: 修改候选筛选**

在 `session/policy.py` 中把 `collect_mem0_candidates()` 改为：

```python
    def collect_mem0_candidates(self, ctx: SessionContext) -> list[WorkingFact]:
        return [
            fact
            for fact in ctx.working_facts
            if fact.importance >= self._config.mem0_promotion_importance
            and fact.category in {"preference", "intent"}
            and not fact.promoted_to_mem0
        ]
```

- [x] **Step 4: 运行 session 测试**

Run: `python -m pytest tests/test_session_context.py -q`

Expected: PASS。

### Task 3: AgentManager 接入账本日志

**Files:**
- Modify: `agent/manager.py`
- Test: `tests/test_agent_manager.py`
- Test: `tests/test_logging_integration.py`

- [x] **Step 1: 写升格与跳过日志测试**

在 `tests/test_agent_manager.py` 增加：

```python
class RecordingLogService:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def test_agent_manager_records_memory_ledger_promote_and_skip_events():
    llm = FakeLLMManager("[emotion:开心]记住了")
    memory_store = FakeMemoryStore()
    log_service = RecordingLogService()
    candidates = [
        WorkingFact(
            fact_id="f1",
            content="记住，我喜欢樱花主题。",
            category="preference",
            importance=0.95,
            created_turn_id=1,
            last_seen_turn_id=1,
            ttl_turns=12,
            source="user",
            sticky=True,
        ),
        WorkingFact(
            fact_id="f2",
            content="记住，我喜欢樱花主题",
            category="preference",
            importance=0.95,
            created_turn_id=2,
            last_seen_turn_id=2,
            ttl_turns=12,
            source="user",
            sticky=True,
        ),
    ]
    session_manager = FakeSessionManager(
        prompt_context="当前会话短期上下文:\n- 当前主题: 偏好",
        mem0_candidates=candidates,
    )
    manager = AgentManager(
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        user_id="u1",
        session_id="s1",
        log_service=log_service,
    )

    list(manager.chat_stream("记住，我喜欢樱花主题。"))
    time.sleep(0.05)

    ledger_events = [event for event in log_service.events if event.source == "memory.ledger"]
    assert [event.event_type for event in ledger_events] == [
        "memory.candidate_promoted",
        "memory.candidate_skipped",
    ]
    assert memory_store.add_memory_calls == [{
        "content": "记住，我喜欢樱花主题。",
        "memory_type": "preference",
        "user_id": "u1",
    }]
```

- [x] **Step 2: 写失败日志测试**

在 `tests/test_agent_manager.py` 增加：

```python
class FailingMemoryStore(FakeMemoryStore):
    def add_memory(self, content, memory_type, user_id):
        raise RuntimeError("mem0 write failed")


def test_agent_manager_records_memory_ledger_failed_event():
    log_service = RecordingLogService()
    candidate = WorkingFact(
        fact_id="f1",
        content="记住，我喜欢樱花主题。",
        category="preference",
        importance=0.95,
        created_turn_id=1,
        last_seen_turn_id=1,
        ttl_turns=12,
        source="user",
        sticky=True,
    )
    session_manager = FakeSessionManager(
        prompt_context="当前会话短期上下文:\n- 当前主题: 偏好",
        mem0_candidates=[candidate],
    )
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]记住了"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=FailingMemoryStore(),
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        user_id="u1",
        session_id="s1",
        log_service=log_service,
    )

    list(manager.chat_stream("记住，我喜欢樱花主题。"))
    time.sleep(0.05)

    failed = next(event for event in log_service.events if event.event_type == "memory.candidate_failed")
    assert failed.level == LogLevel.ERROR
    assert failed.details["error_type"] == "RuntimeError"
    assert candidate.promoted_to_mem0 is False
```

- [x] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_manager.py::test_agent_manager_records_memory_ledger_promote_and_skip_events tests/test_agent_manager.py::test_agent_manager_records_memory_ledger_failed_event -q`

Expected: FAIL，当前没有 `memory.ledger` 事件。

- [x] **Step 4: 修改 AgentManager**

在 `agent/manager.py` 顶部增加：

```python
from memory.ledger import MemoryCandidate, MemoryLedgerEvaluator
```

在 `AgentManager.__init__()` 中增加：

```python
        self._memory_ledger = MemoryLedgerEvaluator()
```

在 `_async_persist_and_reflect()` 中，把 session candidate 写入部分替换为：

```python
            if self._memory_store and hasattr(self._memory_store, "add_memory"):
                candidates = [
                    MemoryCandidate(
                        candidate_id=getattr(candidate, "fact_id", ""),
                        content=candidate.content,
                        memory_type=candidate.category,
                        source=getattr(candidate, "source", "session"),
                        confidence=float(getattr(candidate, "importance", 0.0)),
                        session_id=getattr(session_ctx, "session_id", self._session_id),
                        turn_id=int(getattr(candidate, "last_seen_turn_id", 0)),
                    )
                    for candidate in self._session_manager.collect_mem0_candidates(session_ctx)
                ]
                decisions = self._memory_ledger.evaluate(candidates)
                candidate_by_id = {
                    getattr(candidate, "fact_id", ""): candidate
                    for candidate in self._session_manager.collect_mem0_candidates(session_ctx)
                }
                for decision in decisions:
                    if decision.action != "promote":
                        self._record_memory_ledger_event(decision, "memory.candidate_skipped")
                        continue
                    original = candidate_by_id.get(decision.candidate.candidate_id)
                    try:
                        self._memory_store.add_memory(
                            content=decision.candidate.content,
                            memory_type=decision.candidate.memory_type,
                            user_id=self._user_id,
                        )
                        if original is not None and hasattr(original, "promoted_to_mem0"):
                            original.promoted_to_mem0 = True
                        self._record_memory_ledger_event(decision, "memory.candidate_promoted")
                    except Exception as exc:
                        self._record_memory_ledger_event(
                            decision,
                            "memory.candidate_failed",
                            level=LogLevel.ERROR,
                            extra={"error_type": type(exc).__name__, "error": str(exc)[:200]},
                        )
```

在 `AgentManager` 中增加：

```python
    def _record_memory_ledger_event(
        self,
        decision,
        event_type: str,
        level: LogLevel = LogLevel.INFO,
        extra: dict | None = None,
    ) -> None:
        details = decision.to_log_details()
        if extra:
            details.update(extra)
        self._record_log_event(
            channel=LogChannel.SYSTEM,
            level=level,
            source="memory.ledger",
            event_type=event_type,
            session_id=decision.candidate.session_id,
            summary=f"Memory candidate {decision.action}: {decision.reason}",
            details=details,
            trace_id=decision.candidate.trace_id,
            request_id=decision.candidate.request_id,
            stage="memory_ledger",
        )
```

实现时把 `collect_mem0_candidates()` 的结果保存到局部变量，避免重复调用：

```python
                raw_candidates = list(self._session_manager.collect_mem0_candidates(session_ctx))
```

- [x] **Step 5: 运行聚焦测试**

Run: `python -m pytest tests/test_agent_manager.py tests/test_logging_integration.py -q`

Expected: PASS。

### Task 4: Mem0 写入接口兼容性

**Files:**
- Modify: `memory/mem0_store.py`
- Test: `tests/test_mem0_store.py`

- [x] **Step 1: 写 metadata 兼容测试**

在 `tests/test_mem0_store.py` 增加：

```python
def test_mem0_store_add_memory_accepts_optional_metadata_without_changing_default_call():
    client = FakeMemoryClient()
    store = Mem0MemoryStore(memory_client=client)

    store.add_memory(
        "以后别写长篇回答",
        memory_type="preference",
        user_id="u1",
        metadata={"candidate_id": "c1"},
    )

    assert client.add_calls == [{
        "messages": [
            {"role": "assistant", "content": "以后别写长篇回答"},
        ],
        "user_id": "u1",
    }]
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_mem0_store.py::test_mem0_store_add_memory_accepts_optional_metadata_without_changing_default_call -q`

Expected: FAIL，当前 `add_memory()` 不接受 `metadata`。

- [x] **Step 3: 扩展签名但不改变 Mem0 调用**

在 `memory/mem0_store.py` 中改为：

```python
    def add_memory(
        self,
        content: str,
        memory_type: str,
        user_id: str,
        metadata: dict | None = None,
    ) -> None:
        messages = [{"role": "assistant", "content": content}]
        self._memory_client.add(messages, user_id=user_id)
```

- [x] **Step 4: 运行 Mem0 测试**

Run: `python -m pytest tests/test_mem0_store.py -q`

Expected: PASS。

### Task 5: 平台日志页面来源归类

**Files:**
- Modify: `ui/settings/pages/system_log_page.py`
- Test: `tests/test_system_log_page.py`

- [x] **Step 1: 写来源归类测试**

在 `tests/test_system_log_page.py` 中增加或扩展已有来源归类测试：

```python
def test_system_log_page_groups_memory_ledger_source_with_memory_chain():
    assert "memory.ledger" in system_log_page_module.BUSINESS_SOURCE_GROUPS["记忆"]
```

如果当前测试文件未以该模块名导入，使用：

```python
import ui.settings.pages.system_log_page as system_log_page_module
```

- [x] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_system_log_page.py::test_system_log_page_groups_memory_ledger_source_with_memory_chain -q`

Expected: FAIL，当前来源组只包含 `session.manager`、`memory.mem0` 等。

- [x] **Step 3: 更新来源分组**

在 `ui/settings/pages/system_log_page.py` 的记忆分组中加入：

```python
"memory.ledger"
```

如存在来源颜色表，也加入稳定颜色：

```python
"memory.ledger": "#6d8f3f"
```

- [x] **Step 4: 运行页面测试**

Run: `python -m pytest tests/test_system_log_page.py -q`

Expected: PASS。

### Task 6: 文档与回归入口

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/development.md`
- Modify: `CLAUDE.md`

- [x] **Step 1: 更新文档入口**

在 `docs/README.md` 的协作文档列表中加入：

```markdown
- [Phase 8-A 记忆质量治理实施计划](./superpowers/plans/2026-05-28-phase-8-memory-ledger.md)
  将 Phase 8 第一项拆成可执行任务；已完成记忆候选、升格 / 跳过决策和平台日志账本，本地自动化验证通过
```

- [x] **Step 2: 更新开发流程回归入口**

在 `docs/development.md` 增加：

```markdown
### Phase 8-A 实现后新增回归入口

- 记忆质量治理与账本：
  - `python -m pytest tests/test_memory_ledger.py tests/test_session_context.py tests/test_mem0_store.py -q`
  - `python -m pytest tests/test_agent_manager.py tests/test_logging_integration.py tests/test_system_log_page.py -q`
  - 第一版账本落在平台日志，不新增长期记忆管理 UI；真实 Mem0 本地向量库写入仍按本地配置手工联调。
```

- [x] **Step 3: 更新协作上下文**

在 `CLAUDE.md` 的“下一步”中加入：

```markdown
- Phase 8-A 记忆质量治理与可回溯记忆账本已完成，本地自动化验证通过；真实 Mem0 本地向量库写入联调待补。执行记录：`docs/superpowers/plans/2026-05-28-phase-8-memory-ledger.md`。
```

- [x] **Step 4: 运行文档检索确认入口**

Run: `rg -n "Phase 8-A|memory-ledger|记忆质量治理" CLAUDE.md docs`

Expected: 能看到 `CLAUDE.md`、`docs/README.md`、`docs/development.md` 和本计划。

### Task 7: 最终验证

**Files:**
- No code changes.

- [x] **Step 1: 运行 Phase 8-A 聚焦回归**

Run:

```powershell
python -m pytest tests/test_memory_ledger.py tests/test_session_context.py tests/test_mem0_store.py -q
python -m pytest tests/test_agent_manager.py tests/test_logging_integration.py tests/test_system_log_page.py -q
```

Expected: PASS。

- [x] **Step 2: 运行触达模块语法检查**

Run:

```powershell
python -m py_compile memory/ledger.py memory/mem0_store.py session/policy.py agent/manager.py ui/settings/pages/system_log_page.py
```

Expected: 无输出，退出码为 0。

- [x] **Step 3: 运行全量测试**

Run: `python -m pytest tests/ -q`

Expected: 全量 PASS。

- [x] **Step 4: 检查工作树**

Run: `git status --short`

Expected: 只包含 Phase 7 已完成改动、Phase 7 smoke 文档、Phase 8-A 计划和 Phase 8-A 实现相关文件；不包含 `data/config/api.yaml`、`data/config/memory.yaml`、`data/logs/`、`data/memory/`、`data/browser_sessions/` 或 `data/vision/` 运行期产物。

## 自检

- Spec coverage:
  - 显式记忆优先：Task 1 覆盖 `explicit_memory`。
  - 重复内容跳过：Task 1 覆盖 `duplicate_candidate`。
  - 短期约束不升格：Task 1 和 Task 2 覆盖 `short_term_constraint`。
  - 冲突只标记不删除：Task 1 覆盖 `possible_conflict`。
  - 写入、跳过、失败可回溯：Task 3 覆盖平台日志事件。
  - 诊断底座复用：Task 3 使用 `LogService` / `LogEvent` trace 字段。
- Placeholder scan:
  - 本计划没有未落实的占位符表述。
  - 每个代码修改步骤都给出目标代码或精确命令。
- Type consistency:
  - `MemoryCandidate`、`MemoryLedgerDecision`、`MemoryLedgerEvaluator` 在 Task 1 定义，Task 3 复用相同名称。
  - 日志 source 固定为 `memory.ledger`，Task 3 和 Task 5 一致。
