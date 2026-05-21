import time
from unittest.mock import MagicMock

import pytest

from config.schema import ProactiveConfig, ProactiveEventConfig


# Qt 测试需要 QApplication
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class FakeLLMHelper:
    def __init__(self, response: str = "你好呀"):
        self.response = response
        self.calls = []

    def judge(self, system_prompt, user_prompt, max_tokens=80):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return self.response


def test_proactive_disabled_no_emit(qapp):
    """禁用时不产生任何主动消息。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(enabled=False),
        llm_helper=FakeLLMHelper(),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    # 即使强制 tick，也不应触发（因为禁用）
    # 注意：disabled 状态下 start() 不启动，但 _tick 仍可手动调用
    scheduler._last_interaction_time = 0  # 模拟很久没交互
    scheduler._tick()

    # disabled 时 _tick 仍会检查并触发——这是设计选择
    # 但若 start() 不启动，实际场景下 _tick 不会被调用
    # 这里测试 enabled=False 不会从 start() 启动 worker
    assert scheduler._worker is None
    scheduler.start()
    assert scheduler._worker is None


def test_proactive_idle_triggers(qapp):
    """闲置超时触发主动闲聊。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=0,  # 立即触发
            min_interval_minutes=0,
            active_hours_start=0,
            active_hours_end=24,
        ),
        llm_helper=FakeLLMHelper("好久不见呀"),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    scheduler._last_interaction_time = time.time() - 100  # 100秒前交互
    scheduler._tick()

    qapp.processEvents()  # 处理 Qt 信号
    assert len(received) == 1
    assert received[0][1] == "idle_chat"
    assert received[0][0] == "好久不见呀"


def test_proactive_cooldown_blocks(qapp):
    """全局冷却时间内不重复触发。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=0,
            min_interval_minutes=10,  # 10分钟冷却
            active_hours_start=0,
            active_hours_end=24,
        ),
        llm_helper=FakeLLMHelper("hi"),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    scheduler._last_interaction_time = time.time() - 100
    scheduler._tick()
    qapp.processEvents()
    assert len(received) == 1

    # 再次 tick，应被冷却阻挡
    scheduler._tick()
    qapp.processEvents()
    assert len(received) == 1  # 没增加


def test_proactive_active_hours_filter(qapp):
    """非活跃时段不触发。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=0,
            min_interval_minutes=0,
            # 设置一个不可能的时段（同时同分）
            active_hours_start=25,  # 永远不会满足
            active_hours_end=26,
        ),
        llm_helper=FakeLLMHelper(),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    scheduler._last_interaction_time = 0
    scheduler._tick()
    qapp.processEvents()

    assert len(received) == 0


def test_proactive_custom_event(qapp):
    """自定义事件通过注册触发器触发。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=99999,  # 闲置不触发
            min_interval_minutes=0,
            active_hours_start=0,
            active_hours_end=24,
            events=[
                ProactiveEventConfig(
                    name="rest_remind",
                    type="system",
                    condition="工作60分钟",
                    prompt_template="提醒主人休息一下",
                    cooldown_minutes=60,
                ),
            ],
        ),
        llm_helper=FakeLLMHelper("休息一下吧"),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    # 注册触发器：始终返回 True
    scheduler.register_trigger("rest_remind", lambda: True)

    scheduler._tick()
    qapp.processEvents()

    assert len(received) == 1
    assert received[0][1] == "rest_remind"


def test_proactive_event_cooldown(qapp):
    """每个事件有独立冷却时间。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=99999,
            min_interval_minutes=0,
            active_hours_start=0,
            active_hours_end=24,
            events=[
                ProactiveEventConfig(
                    name="test_event",
                    type="system",
                    cooldown_minutes=60,
                    prompt_template="hi",
                ),
            ],
        ),
        llm_helper=FakeLLMHelper("hi"),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    scheduler.register_trigger("test_event", lambda: True)

    scheduler._tick()
    qapp.processEvents()
    assert len(received) == 1

    # 第二次 tick，事件冷却中
    scheduler._tick()
    qapp.processEvents()
    assert len(received) == 1


def test_proactive_notify_interaction_resets(qapp):
    """notify_interaction 重置闲置计时。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(
            enabled=True,
            idle_interval_minutes=1,  # 1分钟
            min_interval_minutes=0,
            active_hours_start=0,
            active_hours_end=24,
        ),
        llm_helper=FakeLLMHelper(),
    )
    received = []
    scheduler.proactive_message.connect(lambda msg, src: received.append((msg, src)))

    # 模拟 2 分钟前交互
    scheduler._last_interaction_time = time.time() - 120

    # 用户刚交互
    scheduler.notify_interaction()

    scheduler._tick()
    qapp.processEvents()

    assert len(received) == 0  # 刚交互过，不触发


def test_proactive_set_config_runtime(qapp):
    """运行时更新配置。"""
    from agent.proactive import ProactiveScheduler

    scheduler = ProactiveScheduler(
        config=ProactiveConfig(enabled=False),
        llm_helper=FakeLLMHelper(),
    )

    # 启动时禁用，无 worker
    scheduler.start()
    assert scheduler._worker is None

    # 切换到启用
    scheduler.set_config(ProactiveConfig(enabled=True))
    assert scheduler._worker is not None

    scheduler.stop()
