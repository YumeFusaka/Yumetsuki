from datetime import datetime
from html import escape as html_escape

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from agent.manager import AgentEvents
from config.manager import ConfigManager
from config.schema import AgentConfig, ProactiveEventConfig
from core.event_bus import event_bus
from ui.widgets.rose_spin_box import RoseSpinBox


LOG_STYLE = """
QTextEdit {
    background: rgba(255, 250, 252, 0.95);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 8px; padding: 10px;
    color: #4a3040; font-size: 12px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}
"""

PAGE_STYLE = """
QPushButton {
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(220, 160, 180, 0.35);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 12px;
}
QPushButton:hover {
    background: rgba(255, 225, 232, 0.9);
    border-color: rgba(212, 86, 122, 0.45);
}
QPushButton:pressed {
    background: rgba(255, 200, 215, 0.8);
}
QCheckBox {
    color: #4a3040; font-size: 13px; spacing: 8px;
}
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid rgba(220, 160, 180, 0.45);
    background: rgba(255,255,255,0.8);
}
QCheckBox::indicator:checked {
    background: #d4567a; border-color: #d4567a;
}
QLineEdit {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
    min-height: 18px;
}
QLineEdit:focus {
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.85);
}
QLabel { color: #6b4a5a; font-size: 13px; }
QGroupBox {
    color: #7a4060; font-size: 14px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding: 18px 14px 12px 14px;
    background: rgba(255, 255, 255, 0.35);
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }
QTabWidget::pane {
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 8px;
    background: rgba(255, 252, 254, 0.4);
}
QTabBar::tab {
    background: rgba(255, 245, 250, 0.6);
    color: #7a4060;
    padding: 8px 18px;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 0.85);
    color: #d4567a;
    font-weight: bold;
}
QTabBar::tab:hover { background: rgba(255, 230, 238, 0.85); }
QListWidget {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px;
    padding: 4px;
    color: #4a3040;
}
QListWidget::item {
    padding: 6px 10px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: rgba(212, 86, 122, 0.18);
    color: #4a3040;
}
"""


class AgentLogHandler(QObject):
    log_entry = Signal(str)


class AgentPage(QWidget):
    def __init__(self, agent_config: AgentConfig | None = None, parent=None):
        super().__init__(parent)
        self._config = agent_config or AgentConfig()
        self._mgr = ConfigManager()
        self._loading = True  # 加载阶段不触发 save
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # 标题
        title = QLabel("Agent 设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("配置 Agent 的智能行为：意图路由、反思深度、多步推理、主动行为。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_log_tab(), "运行日志")
        self._tabs.addTab(self._build_planner_tab(), "规划")
        self._tabs.addTab(self._build_reflector_tab(), "反思")
        self._tabs.addTab(self._build_multistep_tab(), "多步推理")
        self._tabs.addTab(self._build_proactive_tab(), "主动行为")
        layout.addWidget(self._tabs, 1)

        self._setup_event_subscription()
        self._loading = False

    # ---------- 日志 tab ----------
    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setSpacing(10)

        self._log_handler = AgentLogHandler()
        self._log_entries: list[str] = []
        self._auto_scroll = True

        # 控制栏
        control_bar = QHBoxLayout()
        self._enabled_check = QCheckBox("启用日志记录")
        self._enabled_check.setChecked(True)
        self._enabled_check.stateChanged.connect(self._on_log_enabled_changed)
        control_bar.addWidget(self._enabled_check)
        control_bar.addStretch()

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        control_bar.addWidget(clear_btn)
        v.addLayout(control_bar)

        # 日志区
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(LOG_STYLE)
        self._log_text.setMinimumHeight(280)
        v.addWidget(self._log_text, 1)

        # 状态栏
        status_bar = QHBoxLayout()
        self._status_label = QLabel("状态: 监听中")
        self._status_label.setStyleSheet("color: #6b8a7a; font-size: 12px;")
        status_bar.addWidget(self._status_label)
        status_bar.addStretch()
        self._entry_count = QLabel("0 条日志")
        self._entry_count.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        status_bar.addWidget(self._entry_count)
        v.addLayout(status_bar)

        return tab

    # ---------- Planner tab ----------
    def _build_planner_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setSpacing(10)
        v.setContentsMargins(8, 12, 8, 12)

        hint = QLabel(
            "意图路由策略：默认走快速关键词匹配，复杂场景升级到 LLM 精判。"
            "关闭 LLM 精判可获得最低延迟。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8c6b7a; font-size: 12px; padding: 4px 8px;")
        v.addWidget(hint)

        group = QGroupBox("规划策略")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._planner_judge = QCheckBox("启用 LLM 精判（更准但增加一次 API 调用）")
        self._planner_judge.setChecked(self._config.planner.llm_judge_enabled)
        self._planner_judge.stateChanged.connect(self._save_live)
        form.addRow("", self._planner_judge)

        self._planner_threshold = RoseSpinBox()
        self._planner_threshold.setRange(0, 500)
        self._planner_threshold.setValue(self._config.planner.complexity_threshold)
        self._planner_threshold.setMinimumWidth(140)
        self._planner_threshold.valueChanged.connect(self._save_live)
        form.addRow("复杂度阈值（字符数）:", self._planner_threshold)

        self._planner_max_tokens = RoseSpinBox()
        self._planner_max_tokens.setRange(50, 1000)
        self._planner_max_tokens.setValue(self._config.planner.judge_max_tokens)
        self._planner_max_tokens.setMinimumWidth(140)
        self._planner_max_tokens.valueChanged.connect(self._save_live)
        form.addRow("精判 max_tokens:", self._planner_max_tokens)

        self._planner_keywords = QLineEdit(", ".join(self._config.planner.extra_trigger_keywords))
        self._planner_keywords.setPlaceholderText("用逗号分隔，例如：分析, 总结, 推理")
        self._planner_keywords.editingFinished.connect(self._save_live)
        form.addRow("自定义触发词:", self._planner_keywords)

        v.addWidget(group)
        v.addStretch()
        return tab

    # ---------- Reflector tab ----------
    def _build_reflector_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setSpacing(10)
        v.setContentsMargins(8, 12, 8, 12)

        hint = QLabel(
            "反思在每轮对话后异步运行，不影响响应速度。深度反思会调用 LLM 提取偏好/事实写入记忆。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8c6b7a; font-size: 12px; padding: 4px 8px;")
        v.addWidget(hint)

        group = QGroupBox("反思策略")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._reflector_enabled = QCheckBox("启用深度反思")
        self._reflector_enabled.setChecked(self._config.reflector.enabled)
        self._reflector_enabled.stateChanged.connect(self._save_live)
        form.addRow("", self._reflector_enabled)

        self._reflector_threshold = RoseSpinBox()
        self._reflector_threshold.setRange(0, 500)
        self._reflector_threshold.setValue(self._config.reflector.deep_threshold)
        self._reflector_threshold.setMinimumWidth(140)
        self._reflector_threshold.valueChanged.connect(self._save_live)
        form.addRow("深度阈值（回复字符数）:", self._reflector_threshold)

        self._reflector_max_tokens = RoseSpinBox()
        self._reflector_max_tokens.setRange(100, 2000)
        self._reflector_max_tokens.setValue(self._config.reflector.reflect_max_tokens)
        self._reflector_max_tokens.setMinimumWidth(140)
        self._reflector_max_tokens.valueChanged.connect(self._save_live)
        form.addRow("反思 max_tokens:", self._reflector_max_tokens)

        types_label = QLabel("提取记忆类型:")
        form.addRow("", types_label)

        self._reflector_types: dict[str, QCheckBox] = {}
        types_box = QHBoxLayout()
        for t, cn in [("preference", "偏好"), ("fact", "事实"), ("emotion", "情绪"), ("topic", "话题")]:
            cb = QCheckBox(cn)
            cb.setChecked(t in self._config.reflector.extract_types)
            cb.stateChanged.connect(self._save_live)
            self._reflector_types[t] = cb
            types_box.addWidget(cb)
        types_box.addStretch()
        form.addRow("", types_box)

        v.addWidget(group)
        v.addStretch()
        return tab

    # ---------- 多步推理 tab ----------
    def _build_multistep_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setSpacing(10)
        v.setContentsMargins(8, 12, 8, 12)

        hint = QLabel(
            "多步推理用于处理需要多次工具调用的任务（如先查天气再写提醒）。"
            "由 Planner 自动检测多动作模式触发。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8c6b7a; font-size: 12px; padding: 4px 8px;")
        v.addWidget(hint)

        group = QGroupBox("多步推理")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._ms_enabled = QCheckBox("启用多步推理")
        self._ms_enabled.setChecked(self._config.multi_step.enabled)
        self._ms_enabled.stateChanged.connect(self._save_live)
        form.addRow("", self._ms_enabled)

        self._ms_max_steps = RoseSpinBox()
        self._ms_max_steps.setRange(1, 10)
        self._ms_max_steps.setValue(self._config.multi_step.max_steps)
        self._ms_max_steps.setMinimumWidth(140)
        self._ms_max_steps.valueChanged.connect(self._save_live)
        form.addRow("最大步数:", self._ms_max_steps)

        self._ms_step_timeout = RoseSpinBox()
        self._ms_step_timeout.setRange(5, 600)
        self._ms_step_timeout.setValue(int(self._config.multi_step.step_timeout))
        self._ms_step_timeout.setMinimumWidth(140)
        self._ms_step_timeout.valueChanged.connect(self._save_live)
        form.addRow("单步超时（秒）:", self._ms_step_timeout)

        self._ms_total_timeout = RoseSpinBox()
        self._ms_total_timeout.setRange(10, 1800)
        self._ms_total_timeout.setValue(int(self._config.multi_step.total_timeout))
        self._ms_total_timeout.setMinimumWidth(140)
        self._ms_total_timeout.valueChanged.connect(self._save_live)
        form.addRow("总超时（秒）:", self._ms_total_timeout)

        v.addWidget(group)
        v.addStretch()
        return tab

    # ---------- 主动行为 tab ----------
    def _build_proactive_tab(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setSpacing(10)
        v.setContentsMargins(8, 12, 8, 12)

        hint = QLabel(
            "主动行为允许桌宠在闲置时或满足特定条件时主动开口。"
            "需要重启对话窗口生效。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8c6b7a; font-size: 12px; padding: 4px 8px;")
        v.addWidget(hint)

        group = QGroupBox("主动行为")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._pro_enabled = QCheckBox("启用主动行为（重启后生效）")
        self._pro_enabled.setChecked(self._config.proactive.enabled)
        self._pro_enabled.stateChanged.connect(self._save_live)
        form.addRow("", self._pro_enabled)

        self._pro_idle = RoseSpinBox()
        self._pro_idle.setRange(1, 1440)
        self._pro_idle.setValue(self._config.proactive.idle_interval_minutes)
        self._pro_idle.setMinimumWidth(140)
        self._pro_idle.valueChanged.connect(self._save_live)
        form.addRow("闲置触发（分钟）:", self._pro_idle)

        self._pro_min = RoseSpinBox()
        self._pro_min.setRange(0, 1440)
        self._pro_min.setValue(self._config.proactive.min_interval_minutes)
        self._pro_min.setMinimumWidth(140)
        self._pro_min.valueChanged.connect(self._save_live)
        form.addRow("最小间隔（分钟）:", self._pro_min)

        hours_row = QHBoxLayout()
        self._pro_start = RoseSpinBox()
        self._pro_start.setRange(0, 23)
        self._pro_start.setValue(self._config.proactive.active_hours_start)
        self._pro_start.setMinimumWidth(80)
        self._pro_start.valueChanged.connect(self._save_live)
        hours_row.addWidget(self._pro_start)
        hours_row.addWidget(QLabel("点 ~"))
        self._pro_end = RoseSpinBox()
        self._pro_end.setRange(0, 24)
        self._pro_end.setValue(self._config.proactive.active_hours_end)
        self._pro_end.setMinimumWidth(80)
        self._pro_end.valueChanged.connect(self._save_live)
        hours_row.addWidget(self._pro_end)
        hours_row.addWidget(QLabel("点"))
        hours_row.addStretch()
        form.addRow("活跃时段:", hours_row)

        v.addWidget(group)

        # 事件列表
        events_group = QGroupBox("自定义事件（高级，预留扩展）")
        events_layout = QVBoxLayout(events_group)
        self._events_list = QListWidget()
        self._refresh_events_list()
        events_layout.addWidget(self._events_list)

        events_hint = QLabel("事件配置目前通过 data/config/agent.yaml 直接编辑")
        events_hint.setStyleSheet("color: #a08090; font-size: 11px;")
        events_layout.addWidget(events_hint)

        v.addWidget(events_group)
        v.addStretch()
        return tab

    def _refresh_events_list(self):
        self._events_list.clear()
        if not self._config.proactive.events:
            item = QListWidgetItem("（无自定义事件）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._events_list.addItem(item)
            return
        for ev in self._config.proactive.events:
            label = f"{ev.name} [{ev.type}] - 冷却 {ev.cooldown_minutes}分钟"
            self._events_list.addItem(label)

    # ---------- 实时保存 ----------
    def _save_live(self) -> None:
        if self._loading:
            return
        self.apply()
        self._mgr.agent = self._config
        self._mgr.save_agent()

    def apply(self) -> None:
        # Planner
        self._config.planner.llm_judge_enabled = self._planner_judge.isChecked()
        self._config.planner.complexity_threshold = self._planner_threshold.value()
        self._config.planner.judge_max_tokens = self._planner_max_tokens.value()
        kw_text = self._planner_keywords.text().strip()
        self._config.planner.extra_trigger_keywords = (
            [k.strip() for k in kw_text.split(",") if k.strip()] if kw_text else []
        )

        # Reflector
        self._config.reflector.enabled = self._reflector_enabled.isChecked()
        self._config.reflector.deep_threshold = self._reflector_threshold.value()
        self._config.reflector.reflect_max_tokens = self._reflector_max_tokens.value()
        self._config.reflector.extract_types = [
            t for t, cb in self._reflector_types.items() if cb.isChecked()
        ]

        # Multi-step
        self._config.multi_step.enabled = self._ms_enabled.isChecked()
        self._config.multi_step.max_steps = self._ms_max_steps.value()
        self._config.multi_step.step_timeout = float(self._ms_step_timeout.value())
        self._config.multi_step.total_timeout = float(self._ms_total_timeout.value())

        # Proactive
        self._config.proactive.enabled = self._pro_enabled.isChecked()
        self._config.proactive.idle_interval_minutes = self._pro_idle.value()
        self._config.proactive.min_interval_minutes = self._pro_min.value()
        self._config.proactive.active_hours_start = self._pro_start.value()
        self._config.proactive.active_hours_end = self._pro_end.value()

    # ---------- 日志事件订阅 ----------
    def _setup_event_subscription(self):
        self._log_handler.log_entry.connect(self._append_log)
        event_bus.subscribe(AgentEvents.PLANNER_DECIDED, self._on_planner_decided)
        event_bus.subscribe(AgentEvents.MEMORY_RETRIEVED, self._on_memory_retrieved)
        event_bus.subscribe(AgentEvents.TOOL_EXECUTED, self._on_tool_executed)
        event_bus.subscribe(AgentEvents.TOOL_SKIPPED, self._on_tool_skipped)
        event_bus.subscribe(AgentEvents.LLM_STARTED, self._on_llm_started)
        event_bus.subscribe(AgentEvents.LLM_COMPLETE, self._on_llm_complete)
        event_bus.subscribe(AgentEvents.REFLECTION_COMPLETE, self._on_reflection)
        event_bus.subscribe(AgentEvents.MULTI_STEP_PROGRESS, self._on_multi_step_progress)
        event_bus.subscribe(AgentEvents.USER_INPUT, self._on_user_input)
        event_bus.subscribe(AgentEvents.ASSISTANT_REPLY, self._on_assistant_reply)
        event_bus.subscribe(AgentEvents.THINKING, self._on_thinking)

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _escape(self, text: str) -> str:
        return html_escape(text).replace("\n", "<br>")

    def _on_log_enabled_changed(self, state):
        on = state != 0
        self._status_label.setText("状态: 监听中" if on else "状态: 已暂停")
        self._status_label.setStyleSheet(
            "color: #6b8a7a; font-size: 12px;" if on else "color: #8a6a6a; font-size: 12px;"
        )

    def _clear_log(self):
        self._log_entries.clear()
        self._log_text.clear()
        self._update_count()

    def _append_log(self, text: str):
        if not self._enabled_check.isChecked():
            return
        self._log_entries.append(text)
        if len(self._log_entries) > 200:
            self._log_entries.pop(0)
        self._log_text.insertHtml(text + "<br>")
        if self._auto_scroll:
            scrollbar = self._log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        self._update_count()

    def _update_count(self):
        self._entry_count.setText(f"{len(self._log_entries)} 条日志")

    def _on_planner_decided(self, data):
        mode = data.get("mode", "unknown")
        tool = data.get("tool_name")
        multi = data.get("needs_multi_step", False)
        if multi:
            msg = "路由到多步推理模式"
        elif mode == "tool" and tool:
            msg = f"路由到工具: {tool}"
        else:
            msg = "路由到对话模式"
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#6b8a7a;">[Planner]</span> {msg}'
        )

    def _on_memory_retrieved(self, data):
        count = data.get("count", 0)
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#8a7ab0;">[Memory]</span> 检索到 {count} 条相关记忆'
        )

    def _on_tool_executed(self, data):
        tool = data.get("tool", "unknown")
        result_preview = data.get("result", "")[:100]
        msg = f"执行: {tool}"
        if result_preview:
            msg += f" → {self._escape(result_preview)}..."
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#b08a40;">[Tool]</span> {msg}'
        )

    def _on_tool_skipped(self, data):
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#b08a40;">[Tool]</span> 跳过 (对话模式)'
        )

    def _on_llm_started(self, data):
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#5a8a9a;">[LLM]</span> 开始生成回复...'
        )

    def _on_llm_complete(self, data):
        length = data.get("response_length", 0)
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#5a8a9a;">[LLM]</span> 回复完成 ({length} 字符)'
        )

    def _on_reflection(self, data):
        memories = data.get("memories_extracted", 0)
        points = data.get("key_points", [])
        msg = "反思完成"
        if memories:
            msg += f" | 提取记忆: {memories} 条"
        if points:
            msg += f" | {self._escape(points[0][:50])}..."
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#7a6a9a;">[Reflector]</span> {msg}'
        )

    def _on_multi_step_progress(self, data):
        idx = data.get("step_index", 0)
        desc = data.get("description", "")
        ok = data.get("success", True)
        status = "✓" if ok else "✗"
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#6b8a7a;">[MultiStep]</span> 步骤{idx + 1} {status} {desc}'
        )

    def _on_user_input(self, data):
        text = data.get("text", "")
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#5f6fb2;font-weight:bold;">[User]</span> {self._escape(text)}'
        )

    def _on_assistant_reply(self, data):
        text = data.get("text", "")
        name = data.get("character_name", "") or "Assistant"
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#9b3060;font-weight:bold;">[{self._escape(name)}]</span> {self._escape(text)}'
        )

    def _on_thinking(self, data):
        text = data.get("text", "")
        preview = text[:80]
        suffix = "..." if len(text) > 80 else ""
        self._log_handler.log_entry.emit(
            f'<span style="color:#888;font-size:11px;">[{self._timestamp()}]</span> '
            f'<span style="color:#888;font-style:italic;">[Thinking]</span> '
            f'<span style="color:#888;font-style:italic;">{self._escape(preview)}{suffix}</span>'
        )
