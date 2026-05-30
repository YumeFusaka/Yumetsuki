from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from config.schema import ProactiveConfig, ProactiveEventConfig

logger = logging.getLogger(__name__)


# 主动消息生成 prompt
_PROACTIVE_SYSTEM_PROMPT = """你必须完全基于给定“角色”说话，像角色本人在桌面旁主动开口。生成一句有角色感的主动发言，不超过48字。
要求：
- 像真实陪伴里的自然插话，不要解释你在做什么。
- 避免连续使用“在吗”“好久不见”“要不要聊聊”这类泛泛问候。
- 不要固定成健康提醒，不要反复让用户喝水、休息或汇报状态。
- 可以带一点观察、关心、轻微自我暴露、撒娇、赌气或具体小提议。
- 情绪要随场景变化，允许温柔、不安、委屈、撒娇、赌气、生气，但不能脱离角色。
- 语气要贴合角色，不要像系统通知。"""


class ProactiveScheduler(QObject):
    """主动行为调度器。后台运行，定时检查或响应自定义事件。"""

    # 主动消息信号：(message, source_event_name)
    proactive_message = Signal(str, str)

    def __init__(
        self,
        config: ProactiveConfig | None = None,
        llm_helper=None,
        can_fire: Callable[[], bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config or ProactiveConfig()
        self._llm = llm_helper
        self._can_fire = can_fire
        self._last_interaction_time = time.time()
        self._last_proactive_time = 0.0
        # 每个事件的最后触发时间
        self._event_last_fired: dict[str, float] = {}
        # 自定义事件触发器 (event_name -> condition_callable)
        self._custom_triggers: dict[str, Callable[[], bool]] = {}
        self._worker: _SchedulerWorker | None = None
        self._character_context = ""
        self._visual_context = ""

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

    def set_character_context(self, context: str) -> None:
        """更新主动消息使用的角色上下文。"""
        self._character_context = (context or "").strip()

    def set_visual_context(self, context: str) -> None:
        """更新主动消息可参考的最近屏幕观察。"""
        self._visual_context = (context or "").strip()

    # --- 内部方法（供 worker 调用）---

    def _tick(self) -> None:
        """定时检查所有触发条件。worker 每秒调用一次。"""
        now = time.time()

        if self._can_fire is not None:
            try:
                if not self._can_fire():
                    return
            except Exception as exc:
                logger.warning(f"Proactive can_fire check failed: {exc}")
                return

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
        idle_minutes = max(1, int((time.time() - self._last_interaction_time) / 60))
        hour = datetime.now().hour
        if 5 <= hour < 11:
            period = "早上"
        elif 11 <= hour < 14:
            period = "中午"
        elif 14 <= hour < 18:
            period = "下午"
        elif 18 <= hour < 23:
            period = "晚上"
        else:
            period = "深夜"
        prompt = (
            f"用户已经约 {idle_minutes} 分钟没有互动，现在是{period}。"
            f"{self._idle_mood_guidance(idle_minutes)}"
            "任选一个具体角度生成一句主动陪伴发言："
            "注意到安静、想念用户、分享一个刚冒出来的小念头、撒娇地要一点回应、"
            "赌气地抱怨被冷落、轻轻试探用户是不是还在、说一句带角色口癖的小抱怨。"
            "不要总是打招呼，不要催促用户回复，不要每次都说同一种句式。"
            "本次不要提喝水、休息、活动身体、早点睡这类固定照顾模板。"
        )
        message = self._generate_message(prompt)
        if message:
            self._emit_message(message, "idle_chat")

    def _idle_mood_guidance(self, idle_minutes: int) -> str:
        if idle_minutes >= 180:
            return (
                "闲置程度：很久没被理。情绪可以更强烈：委屈、生气、赌气、需要被安抚，"
                "但仍要保留角色本来的表达方式。"
            )
        if idle_minutes >= 60:
            return (
                "闲置程度：已经有一阵子。情绪可以是不安、想念、撒娇、轻微赌气，"
                "像在试探用户还在不在。"
            )
        return (
            "闲置程度：刚安静一会儿。情绪以温柔、好奇、轻声关心或轻微撒娇为主，"
            "不要显得过度焦虑。"
        )

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
        system_prompt = _PROACTIVE_SYSTEM_PROMPT
        if self._character_context:
            system_prompt = (
                f"{self._character_context}\n\n"
                "---\n\n"
                f"{system_prompt}\n"
                "如果角色有可用情绪，输出必须以 `[emotion:情绪名]` 开头，情绪名必须来自角色可用情绪。"
            )
        if self._visual_context:
            prompt = f"最近屏幕观察:\n{self._visual_context}\n\n{prompt}"
        return self._llm.judge(system_prompt, prompt, max_tokens=120)

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
