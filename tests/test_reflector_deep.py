from agent.reflector import AgentReflector, Reflection, MemoryEntry
from config.schema import ReflectorConfig


class FakeLLMHelper:
    def __init__(self, response: dict | None = None):
        self.response = response or {}
        self.calls = []

    def judge_json(self, system_prompt, user_prompt, max_tokens=300):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return self.response


def test_shallow_reflect_short_response():
    """短回复走浅层反思，不调用 LLM。"""
    helper = FakeLLMHelper()
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=30),
        llm_helper=helper,
    )
    result = reflector.reflect("你好", "你好呀", None)

    assert isinstance(result, Reflection)
    assert len(helper.calls) == 0  # 未调用 LLM
    assert result.memories_to_store == []


def test_deep_reflect_long_response():
    """长回复触发深度反思。"""
    helper = FakeLLMHelper(response={
        "memories": [
            {"type": "topic", "content": "讨论天气", "confidence": 0.9},
        ],
        "key_points": ["今天天气很好"],
    })
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=10),
        llm_helper=helper,
    )
    result = reflector.reflect(
        "今天天气怎么样",
        "今天天气很好，阳光明媚，适合出门散步。",
        None,
    )

    assert len(helper.calls) == 1
    assert len(result.memories_to_store) == 1
    assert result.memories_to_store[0].type == "topic"
    assert result.memories_to_store[0].content == "讨论天气"


def test_deep_reflect_on_tool_calls():
    """有工具调用时触发深度反思。"""
    helper = FakeLLMHelper(response={
        "memories": [],
        "key_points": ["查询了天气"],
    })
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=100),
        llm_helper=helper,
    )
    result = reflector.reflect(
        "查天气",
        "好的",
        [{"name": "weather__query"}],
    )

    assert len(helper.calls) == 1  # 有工具调用，触发深度反思


def test_deep_reflect_on_preference_keywords():
    """用户表达偏好时触发深度反思。"""
    helper = FakeLLMHelper(response={
        "memories": [
            {"type": "preference", "content": "喜欢樱花", "confidence": 0.95},
        ],
        "key_points": ["用户喜欢樱花"],
    })
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=100),
        llm_helper=helper,
    )
    result = reflector.reflect("我喜欢樱花", "好的", None)

    assert len(helper.calls) == 1
    assert result.memories_to_store[0].type == "preference"


def test_deep_reflect_filters_by_extract_types():
    """只提取配置中允许的记忆类型。"""
    helper = FakeLLMHelper(response={
        "memories": [
            {"type": "preference", "content": "喜欢猫", "confidence": 0.9},
            {"type": "emotion", "content": "开心", "confidence": 0.8},
            {"type": "fact", "content": "住在东京", "confidence": 0.95},
        ],
        "key_points": [],
    })
    reflector = AgentReflector(
        config=ReflectorConfig(
            enabled=True,
            deep_threshold=10,
            extract_types=["preference", "fact"],  # 不提取 emotion
        ),
        llm_helper=helper,
    )
    result = reflector.reflect("我喜欢猫，我住在东京", "好的，记住了！", None)

    assert len(result.memories_to_store) == 2
    types = [m.type for m in result.memories_to_store]
    assert "emotion" not in types


def test_reflector_disabled():
    """反思关闭时走浅层反思。"""
    helper = FakeLLMHelper()
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=False),
        llm_helper=helper,
    )
    result = reflector.reflect("我喜欢樱花", "好的" * 50, None)

    assert len(helper.calls) == 0  # 即使长回复也不调用 LLM


def test_reflector_no_llm_helper():
    """无 LLM helper 时走浅层反思。"""
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=10),
        llm_helper=None,
    )
    result = reflector.reflect("你好", "你好呀，今天过得怎么样？", None)

    assert result.memories_to_store == []


def test_deep_reflect_llm_failure():
    """LLM 返回空结果时降级为浅层反思的 key_points。"""
    helper = FakeLLMHelper(response={})
    reflector = AgentReflector(
        config=ReflectorConfig(enabled=True, deep_threshold=10),
        llm_helper=helper,
    )
    # 回复需要足够长（> 50 字符）才能触发 _extract_key_points 的规则提取
    long_response = "你好呀，今天天气很好，阳光明媚，适合出门散步。我建议你可以去附近的公园走走，呼吸一下新鲜空气。如果你喜欢的话，也可以带上一本书在树荫下阅读。"
    result = reflector.reflect("你好", long_response, None)

    assert len(helper.calls) == 1
    assert result.memories_to_store == []
    # 降级使用规则提取的 key_points
    assert len(result.key_points) > 0
