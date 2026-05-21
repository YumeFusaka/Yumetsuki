from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
   QVBoxLayout,
    QWidget,
)
from agent.manager import AgentEvents
from core.event_bus import event_bus


LOG_STYLE = """
QTextEdit {
    background: rgba(255, 250, 252, 0.95);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 8px; padding: 10px;
    color: #4a3040; font-size: 12px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}
"""

CONTROL_STYLE = """
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
"""


class AgentLogHandler(QObject):
    log_entry = Signal(str)


class AgentPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_handler = AgentLogHandler()
        self._log_entries: list[str] = []
        self._auto_scroll = True
        self.setStyleSheet(CONTROL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Agent 调试")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("查看 Agent 的内部决策流程：Planner 路由、记忆检索、工具调用、反思结果。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        # Control bar
        control_bar = QHBoxLayout()
        control_bar.setSpacing(12)

        self._enabled_check = QCheckBox("启用日志记录")
        self._enabled_check.setChecked(True)
        self._enabled_check.stateChanged.connect(self._on_enabled_changed)
        control_bar.addWidget(self._enabled_check)

        control_bar.addStretch()

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self._clear_log)
        control_bar.addWidget(clear_btn)

        layout.addLayout(control_bar)

        # Log area
        group = QGroupBox("实时日志")
        group_layout = QVBoxLayout(group)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(LOG_STYLE)
        self._log_text.setMinimumHeight(300)
        group_layout.addWidget(self._log_text)

        layout.addWidget(group, 1)

        # Status bar
        status_bar = QHBoxLayout()
        self._status_label = QLabel("状态: 监听中")
        self._status_label.setStyleSheet("color: #6b8a7a; font-size: 12px;")
        status_bar.addWidget(self._status_label)
        status_bar.addStretch()
        self._entry_count = QLabel("0 条日志")
        self._entry_count.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        status_bar.addWidget(self._entry_count)
        layout.addLayout(status_bar)

        self._setup_event_subscription()

    def _setup_event_subscription(self):
        self._log_handler.log_entry.connect(self._append_log)
        event_bus.subscribe(AgentEvents.PLANNER_DECIDED, self._on_planner_decided)
        event_bus.subscribe(AgentEvents.MEMORY_RETRIEVED, self._on_memory_retrieved)
        event_bus.subscribe(AgentEvents.TOOL_EXECUTED, self._on_tool_executed)
        event_bus.subscribe(AgentEvents.TOOL_SKIPPED, self._on_tool_skipped)
        event_bus.subscribe(AgentEvents.LLM_STARTED, self._on_llm_started)
        event_bus.subscribe(AgentEvents.LLM_COMPLETE, self._on_llm_complete)
        event_bus.subscribe(AgentEvents.REFLECTION_COMPLETE, self._on_reflection)

    def _on_enabled_changed(self, state):
        self._status_label.setText("状态: 已暂停" if not state else "状态: 监听中")
        self._status_label.setStyleSheet(
            "color: #8a6a6a; font-size: 12px;" if not state else "color: #6b8a7a; font-size: 12px;"
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
        self._log_text.append(text)
        if self._auto_scroll:
            scrollbar = self._log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        self._update_count()

    def _update_count(self):
        self._entry_count.setText(f"{len(self._log_entries)} 条日志")

    def _on_planner_decided(self, data):
        mode = data.get("mode", "unknown")
        tool = data.get("tool_name")
        if mode == "tool" and tool:
            self._log_handler.log_entry.emit(f"[Planner] 路由到工具: {tool}")
        else:
            self._log_handler.log_entry.emit(f"[Planner] 路由到对话模式")

    def _on_memory_retrieved(self, data):
        count = data.get("count", 0)
        self._log_handler.log_entry.emit(f"[Memory] 检索到 {count} 条相关记忆")

    def _on_tool_executed(self, data):
        tool = data.get("tool", "unknown")
        result_preview = data.get("result", "")[:100]
        msg = f"[Tool] 执行: {tool}"
        if result_preview:
            msg += f"\n    结果: {result_preview}..."
        self._log_handler.log_entry.emit(msg)

    def _on_tool_skipped(self, data):
        self._log_handler.log_entry.emit(f"[Tool] 跳过 (对话模式)")

    def _on_llm_started(self, data):
        self._log_handler.log_entry.emit("[LLM] 开始生成回复...")

    def _on_llm_complete(self, data):
        length = data.get("response_length", 0)
        self._log_handler.log_entry.emit(f"[LLM] 回复完成 ({length} 字符)")

    def _on_reflection(self, data):
        points = data.get("key_points", [])
        needs = data.get("needs_continue", False)
        msg = f"[Reflector] 反思完成"
        if points:
            msg += f"\n    关键点 ({len(points)}): {points[0][:50]}..."
        if needs:
            msg += "\n    建议: 可能需要继续"
        self._log_handler.log_entry.emit(msg)
