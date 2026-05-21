from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from config.schema import ProactiveConfig, ProactiveEventConfig

logger = logging.getLogger(__name__)


# 主动消息生成 prompt
_PROACTIVE_SYSTEM_PROMPT = """你是这个桌宠角色。根据下面的场景描述，生成一句简短自然的主动发言（不超过30字），不要解释你在做什么，直接说话即可。"""


class ProactiveScheduler(QObject):
    """主动行为调度器。后台运行，定时检查或响应自定义事件。"""

    # 主动消息信号：(message, source_event_name)
    proactive_message = Signal(str, str)

    def __init__(
        self,
        config: ProactiveConfig | None = None,
        llm_helper=None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config or ProactiveConfig()
        self._llm = llm_helper
        self._last_interaction_time = time.time()
        self._last_proactive_time = 0.0
        # 每个事件的最后触发时间
        self._event_last_fired: dict[str, float] = {}
        # 自定义事件触发器 (event_name -> condition_callable)
        self._custom_triggers: dict[str, Callable[[], bool]] = {}
        self._worker: _SchedulerWorker | None = None

    def start(self) -> None:
        """启动调度器后台线程。"""
        if not self._config.enabled:
            logger.info("ProactiveScheduler disabled, not starting")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = _SchedulerWorker(self)
        self._worker.start()

    def stop(self) -> None:
        """停止调度器。"""
        if self._worker is not None:
            self._worker.request_stop()
            self._worker.wait(2000)
            self._worker = None

    def notify_interaction(self) -> None:
        """通知调度器：用户刚刚交互过（重置闲置计时）。"""
        self._last_interaction_time = time.time()

    def register_trigger(self, event_name: str, condition: Callable[[], bool]) -> None:
        """注册自定义事件触发器。"""
        self._custom_triggers[event_name] = condition

    def set_config(self, config: ProactiveConfig) -> None:
        """更新配置（无需重启）。"""
        was_enabled = self._config.enabled
        self._config = config
        if config.enabled and not was_enabled:
            self.start()
        elif not config.enabled and was_enabled:
            self.stop()

    # --- 内部方法（供 worker 调用）---

    def _tick(self) -> None:
        """定时检查所有触发条件。worker 每秒调用一次。"""
        now = time.time()

        # 全局冷却检查
        if now - self._last_proactive_time < self._config.min_interval_minutes * 60:
            return

        # 活跃时段检查
        if not self._is_in_active_hours():
            return

        # 检查闲置定时器
        idle_seconds = now - self._last_interaction_time
        if idle_seconds >= self._config.idle_interval_minutes * 60:
            self._fire_idle_chat()
            return

        # 检查每个自定义事件
        for event in self._config.events:
            if self._should_fire_event(event, now):
                self._fire_event(event)
                return  # 一次只触发一个

    def _is_in_active_hours(self) -> bool:
        hour = datetime.now().hour
        start = self._config.active_hours_start
        end = self._config.active_hours_end
        if start <= end:
            return start <= hour < end
        # 跨天（如 22-6）
        return hour >= start or hour < end

    def _should_fire_event(self, event: ProactiveEventConfig, now: float) -> bool:
        # 冷却检查
        last_fired = self._event_last_fired.get(event.name, 0)
        if now - last_fired < event.cooldown_minutes * 60:
            return False

        # 自定义触发器
        trigger = self._custom_triggers.get(event.name)
        if trigger is not None:
            try:
                return trigger()
            except Exception as exc:
                logger.warning(f"Trigger {event.name} failed: {exc}")
                return False

        # 默认行为：timer 类型每隔 cooldown 触发
        if event.type == "timer":
            return last_fired == 0 or (now - last_fired >= event.cooldown_minutes * 60)

        return False

    def _fire_idle_chat(self) -> None:
        """触发闲置主动闲聊。"""
        prompt = "用户已经一段时间没和你说话了。用一句温柔自然的话主动打个招呼或分享一个小想法。"
        message = self._generate_message(prompt)
        if message:
            self._emit_message(message, "idle_chat")

    def _fire_event(self, event: ProactiveEventConfig) -> None:
        """触发自定义事件。"""
        message = self._generate_message(event.prompt_template)
        if message:
            self._event_last_fired[event.name] = time.time()
            self._emit_message(message, event.name)

    def _generate_message(self, prompt: str) -> str:
        """调用 LLM 生成主动消息。失败返回空字符串。"""
        if not self._llm:
            return ""
        return self._llm.judge(_PROACTIVE_SYSTEM_PROMPT, prompt, max_tokens=80)

    def _emit_message(self, message: str, source: str) -> None:
        self._last_proactive_time = time.time()
        self.proactive_message.emit(message, source)
        logger.info(f"Proactive message fired ({source}): {message[:40]}")


class _SchedulerWorker(QThread):
    """后台线程，每秒调用 scheduler._tick()。"""

    def __init__(self, scheduler: ProactiveScheduler):
        super().__init__()
        self._scheduler = scheduler
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        while not self._stop_requested:
            try:
                self._scheduler._tick()
            except Exception as exc:
                logger.warning(f"Scheduler tick failed: {exc}")
            # 每 5 秒检查一次（足够细的精度，开销可忽略）
            for _ in range(5):
                if self._stop_requested:
                    return
                self.msleep(1000)
