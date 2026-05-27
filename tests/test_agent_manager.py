from dataclasses import dataclass
import threading
import time
from types import SimpleNamespace

from agent.manager import AgentManager
from core.log_types import LogLevel
from llm.text_processor import ProcessedText
from session.context import WorkingFact
from session.manager import SessionContextManager
from vision.types import OCRResult


@dataclass
class FakePlan:
    mode: str
    goal: str
    tool_name: str | None = None
    arguments: dict | None = None
    needs_multi_step: bool = False
    steps: list = None


class FakePlanner:
    def __init__(self, plan: FakePlan):
        self.plan_value = plan
        self.calls = []

    def plan(self, user_input, tools):
        self.calls.append({"user_input": user_input, "tools": tools})
        return self.plan_value


class FakeExecutor:
    def __init__(self, result: str):
        self.result = result
        self.calls = []

    def execute(self, plan, tool_registry):
        self.calls.append({"plan": plan, "tool_registry": tool_registry})
        return self.result


class FakeMemoryStore:
    def __init__(self, memories=None):
        self.memories = memories or []
        self.search_calls = []
        self.add_calls = []
        self.add_memory_calls = []

    def search_relevant(self, query, user_id):
        self.search_calls.append({"query": query, "user_id": user_id})
        return self.memories

    def add_conversation(self, user_text, assistant_text, user_id):
        self.add_calls.append({
            "user_text": user_text,
            "assistant_text": assistant_text,
            "user_id": user_id,
        })

    def add_memory(self, content, memory_type, user_id):
        self.add_memory_calls.append({
            "content": content,
            "memory_type": memory_type,
            "user_id": user_id,
        })


class SlowMemoryStore(FakeMemoryStore):
    def __init__(self):
        super().__init__([])
        self.started = threading.Event()
        self.release = threading.Event()

    def add_conversation(self, user_text, assistant_text, user_id):
        self.started.set()
        self.release.wait(timeout=1.0)
        super().add_conversation(user_text, assistant_text, user_id)


class FakeToolRegistry:
    def tool_specs(self):
        return [{"function": {"name": "notes__search"}}]

    def entries(self):
        return []


class FakeSessionManager:
    def __init__(self, prompt_context: str, mem0_candidates=None):
        self.prompt_context = prompt_context
        self.context = object()
        self.calls = []
        self.mem0_candidates = mem0_candidates or []

    def get_or_create(self, user_id: str, session_id: str):
        self.calls.append(("get_or_create", user_id, session_id))
        return self.context

    def record_user_input(self, ctx, text: str) -> None:
        self.calls.append(("record_user_input", ctx, text))

    def record_assistant_reply(self, ctx, text: str) -> None:
        self.calls.append(("record_assistant_reply", ctx, text))

    def build_prompt_context(self, ctx) -> str:
        self.calls.append(("build_prompt_context", ctx))
        return self.prompt_context

    def collect_mem0_candidates(self, ctx):
        self.calls.append(("collect_mem0_candidates", ctx))
        return [
            candidate
            for candidate in self.mem0_candidates
            if not getattr(candidate, "promoted_to_mem0", False)
        ]


class FakeLLMManager:
    def __init__(self, final_text="[emotion:开心]好的"):
        self.final_text = final_text
        self.calls = []

    def chat_stream(self, user_input, session_context="", extra_context="", allow_tools=True):
        self.calls.append({
            "user_input": user_input,
            "session_context": session_context,
            "extra_context": extra_context,
            "allow_tools": allow_tools,
        })
        yield ProcessedText(clean_text=self.final_text.replace("[emotion:开心]", ""), emotion="开心")


class FakeVisionManager:
    def __init__(self):
        self.called = False

    def capture_screen_text(self):
        self.called = True
        return OCRResult(ok=True, text="屏幕上显示保存成功", image_path="data/vision/a.png")

    def recognize_image_text(self, image_path):
        self.called = True
        return OCRResult(ok=True, text=f"识别 {image_path}", image_path=str(image_path))


def test_agent_manager_injects_memories_into_chat():
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]我记得你喜欢樱花"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=FakeMemoryStore(["用户喜欢樱花主题"]),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("我喜欢什么主题？"))

    assert results[-1].clean_text == "我记得你喜欢樱花"
    assert "用户喜欢樱花主题" in manager._llm_manager.calls[0]["extra_context"]
    assert manager._memory_store.add_calls[0]["assistant_text"] == "我记得你喜欢樱花"


def test_agent_manager_flags_explicit_screen_request():
    session_manager = SessionContextManager()
    vision = FakeVisionManager()
    manager = AgentManager(
        llm_manager=FakeLLMManager("知道了"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        session_id="s1",
        vision_manager=vision,
    )

    list(manager.chat_stream("帮我看看屏幕上写了什么"))

    ctx = session_manager.get_or_create("default-user", "s1")
    assert manager.should_capture_screen("帮我看看屏幕上写了什么") is True
    assert vision.called is False
    assert ctx.visual_observations == []


def test_agent_manager_uses_pre_captured_screen_image():
    session_manager = SessionContextManager()
    vision = FakeVisionManager()
    manager = AgentManager(
        llm_manager=FakeLLMManager("知道了"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        session_id="s1",
        vision_manager=vision,
    )

    list(manager.chat_stream("帮我看看屏幕", visual_capture=OCRResult(ok=True, image_path="data/vision/a.png")))

    ctx = session_manager.get_or_create("default-user", "s1")
    assert vision.called is True
    assert ctx.visual_observations[0].text == "识别 data/vision/a.png"


def test_agent_manager_adds_ocr_failure_to_extra_context():
    events = []
    manager = AgentManager(
        llm_manager=FakeLLMManager("没看到"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        vision_manager=FakeVisionManager(),
        log_service=SimpleNamespace(record=lambda event: events.append(event)),
    )

    list(manager.chat_stream("帮我看看屏幕", visual_capture=OCRResult(ok=False, error="missing rapidocr")))

    assert "视觉 OCR 未完成：missing rapidocr" in manager._llm_manager.calls[0]["extra_context"]
    ocr_events = [event for event in events if event.event_type == "vision.ocr_failed"]
    assert len(ocr_events) == 1
    assert ocr_events[0].level == LogLevel.WARN
    assert ocr_events[0].source == "agent.vision"
    assert ocr_events[0].summary == "OCR 未完成: missing rapidocr"
    assert ocr_events[0].details == {"error": "missing rapidocr", "image_path": ""}


def test_agent_manager_treats_empty_ocr_text_as_failure():
    events = []

    class EmptyVisionManager(FakeVisionManager):
        def recognize_image_text(self, image_path):
            return OCRResult(ok=True, text="  ", image_path=str(image_path))

    manager = AgentManager(
        llm_manager=FakeLLMManager("没看到"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        vision_manager=EmptyVisionManager(),
        log_service=SimpleNamespace(record=lambda event: events.append(event)),
    )

    list(manager.chat_stream("帮我看看屏幕", visual_capture=OCRResult(ok=True, image_path="data/vision/a.png")))

    assert "视觉 OCR 未完成：未识别到屏幕文字" in manager._llm_manager.calls[0]["extra_context"]
    ocr_events = [event for event in events if event.event_type == "vision.ocr_failed"]
    assert ocr_events[0].details == {"error": "未识别到屏幕文字", "image_path": "data/vision/a.png"}


def test_agent_manager_does_not_capture_screen_for_normal_chat():
    vision = FakeVisionManager()
    manager = AgentManager(
        llm_manager=FakeLLMManager("你好"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        vision_manager=vision,
    )

    list(manager.chat_stream("你好呀"))

    assert vision.called is False


def test_agent_manager_does_not_capture_for_broad_window_phrase():
    vision = FakeVisionManager()
    manager = AgentManager(
        llm_manager=FakeLLMManager("你好"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        tool_registry=FakeToolRegistry(),
        vision_manager=vision,
    )

    list(manager.chat_stream("这个窗口真可爱"))

    assert manager.should_capture_screen("这个窗口真可爱") is False
    assert manager.should_capture_screen("不要显示在屏幕上") is False
    assert manager.should_capture_screen("不要在屏幕上显示提示") is False
    assert manager.should_capture_screen("优化屏幕内容布局") is False
    assert manager.should_capture_screen("帮我看看屏幕上写了什么") is True
    assert vision.called is False


def test_agent_manager_executes_tool_then_calls_llm():
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]我帮你查到了"),
        planner=FakePlanner(FakePlan(
            mode="tool",
            goal="search notes",
            tool_name="notes__search",
            arguments={"query": "待办"},
        )),
        executor=FakeExecutor("找到 3 条待办"),
        memory_store=FakeMemoryStore(),
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    results = list(manager.chat_stream("帮我看看待办"))

    assert results[-1].clean_text == "我帮你查到了"
    assert "找到 3 条待办" in manager._llm_manager.calls[0]["extra_context"]


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


def test_agent_manager_marks_tool_success_in_followup_context():
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

    list(manager.chat_stream("打开浏览器"))

    extra_context = llm.calls[0]["extra_context"]
    assert "工具调用已成功执行" in extra_context
    assert "不要再说自己做不到" in extra_context


def test_agent_manager_does_not_block_on_add_conversation():
    memory_store = SlowMemoryStore()
    manager = AgentManager(
        llm_manager=FakeLLMManager("[emotion:开心]马上完成"),
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=FakeToolRegistry(),
        user_id="u1",
    )

    start = time.perf_counter()
    results = list(manager.chat_stream("测试一下"))
    elapsed = time.perf_counter() - start

    assert results[-1].clean_text == "马上完成"
    assert memory_store.started.is_set()
    assert elapsed < 0.5
    memory_store.release.set()


def test_agent_manager_injects_short_term_session_context_before_reply():
    llm = FakeLLMManager("[emotion:开心]我记得刚刚说的是先讨论方案")
    session_manager = FakeSessionManager(
        prompt_context="当前会话短期上下文:\n- 最近高优先级信息:\n  - 先不要改代码，只讨论方案。"
    )
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


def test_agent_manager_promotes_session_candidates_into_mem0():
    llm = FakeLLMManager("[emotion:开心]记住了")
    memory_store = FakeMemoryStore()
    candidate = WorkingFact(
        fact_id="f1",
        content="以后别写长篇回答",
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
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        user_id="u1",
    )

    list(manager.chat_stream("记住，我以后都不想看长篇回答。"))
    time.sleep(0.05)

    assert memory_store.add_memory_calls == [{
        "content": "以后别写长篇回答",
        "memory_type": "preference",
        "user_id": "u1",
    }]


def test_agent_manager_does_not_promote_same_session_candidate_twice():
    llm = FakeLLMManager("[emotion:开心]记住了")
    memory_store = FakeMemoryStore()
    candidate = WorkingFact(
        fact_id="f1",
        content="以后别写长篇回答",
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
        llm_manager=llm,
        planner=FakePlanner(FakePlan(mode="chat", goal="reply")),
        executor=FakeExecutor(""),
        memory_store=memory_store,
        tool_registry=FakeToolRegistry(),
        session_manager=session_manager,
        user_id="u1",
    )

    list(manager.chat_stream("记住，我以后都不想看长篇回答。"))
    time.sleep(0.05)
    list(manager.chat_stream("继续"))
    time.sleep(0.05)

    assert memory_store.add_memory_calls == [{
        "content": "以后别写长篇回答",
        "memory_type": "preference",
        "user_id": "u1",
    }]
