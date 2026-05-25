import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
)


SOURCE_GROUPS = {
    "全部": [],
    "记忆": ["session.manager", "memory.mem0"],
    "LLM": ["llm.manager"],
    "切句": ["chat.segmenter"],
    "TTS": ["chat.tts", "tts.gptsovits"],
    "工具": ["tool.registry"],
    "UI": ["chat.window", "ui.event_bridge"],
    "Agent": ["agent.manager"],
}

SCROLL_BOTTOM_THRESHOLD = 24


PAGE_STYLE = """
QWidget {
    background: transparent;
}
QTextEdit {
    background: rgba(255, 252, 254, 0.82);
    border: 1px solid rgba(220, 160, 180, 0.28);
    border-radius: 14px;
    padding: 12px;
    color: #4a3040;
    font-size: 12px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}
QLabel {
    color: #8c6b7a;
    font-size: 13px;
}
QLineEdit, QComboBox {
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 8px;
    padding: 8px 10px;
    color: #4a3040;
    min-height: 18px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #d4567a;
}
QComboBox::drop-down {
    border: none;
    border-left: 1px solid rgba(220, 160, 180, 0.28);
    width: 22px;
    background: transparent;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9b3060;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: rgba(255, 250, 252, 0.98);
    border: 1px solid rgba(220, 160, 180, 0.35);
    selection-background-color: rgba(255, 210, 224, 0.9);
    selection-color: #4a3040;
    color: #4a3040;
    padding: 4px;
}
QPushButton {
    background: rgba(255, 245, 250, 0.88);
    border: 1px solid rgba(212, 86, 122, 0.32);
    border-radius: 8px;
    padding: 8px 14px;
    color: #6b4a5a;
}
QPushButton:hover {
    background: rgba(255, 232, 240, 0.96);
    border-color: rgba(212, 86, 122, 0.48);
}
QCheckBox {
    color: #6b4a5a;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(212, 86, 122, 0.45);
    background: rgba(255,255,255,0.8);
}
QCheckBox::indicator:checked {
    background: #d4567a;
    border-color: #d4567a;
}
QListWidget {
    background: rgba(255, 252, 254, 0.82);
    border: 1px solid rgba(220, 160, 180, 0.28);
    border-radius: 14px;
    padding: 8px;
    color: #4a3040;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 10px;
    margin-bottom: 4px;
}
QListWidget::item:selected {
    background: rgba(255, 222, 232, 0.95);
    color: #4a3040;
    border: 1px solid rgba(212, 86, 122, 0.35);
}
QListWidget::item:hover {
    background: rgba(255, 238, 244, 0.95);
}
"""


class SystemLogPage(QWidget):
    def __init__(self, log_service, parent=None):
        super().__init__(parent)
        self._log_service = log_service
        self._selected_event: dict | None = None
        self._current_session_id: str | None = None
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("系统日志")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("查看 TTS、LLM、工具调用与运行期系统事件。")
        layout.addWidget(desc)

        controls = QHBoxLayout()
        self._source_group_filter = QComboBox()
        for group_name in SOURCE_GROUPS:
            self._source_group_filter.addItem(group_name, group_name)
        self._source_group_filter.currentIndexChanged.connect(self._on_source_group_changed)
        controls.addWidget(self._source_group_filter)

        self._source_filter = QComboBox()
        self._source_filter.currentIndexChanged.connect(self._refresh_view)
        controls.addWidget(self._source_filter, 1)
        self._rebuild_source_filter_options()

        self._level_filter = QComboBox()
        self._level_filter.addItem("全部级别", "")
        self._level_filter.addItem("INFO", "info")
        self._level_filter.addItem("WARN", "warn")
        self._level_filter.addItem("ERROR", "error")
        self._level_filter.currentIndexChanged.connect(self._refresh_view)
        controls.addWidget(self._level_filter)

        self._keyword_filter = QLineEdit()
        self._keyword_filter.setPlaceholderText("关键字")
        self._keyword_filter.editingFinished.connect(self._refresh_view)
        controls.addWidget(self._keyword_filter, 1)

        self._current_session_only = QCheckBox("仅当前会话")
        self._current_session_only.stateChanged.connect(lambda *_: self._refresh_view())
        controls.addWidget(self._current_session_only)

        self._view_mode = QComboBox()
        self._view_mode.addItem("结构化列表", "list")
        self._view_mode.addItem("连续文本", "text")
        self._view_mode.currentIndexChanged.connect(self._refresh_view)
        controls.addWidget(self._view_mode)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_view)
        controls.addWidget(refresh_btn)

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_current_view)
        controls.addWidget(export_btn)

        open_dir_btn = QPushButton("打开目录")
        open_dir_btn.clicked.connect(self._open_log_directory)
        controls.addWidget(open_dir_btn)

        copy_btn = QPushButton("复制详情")
        copy_btn.clicked.connect(self._copy_selected_event_json)
        controls.addWidget(copy_btn)
        layout.addLayout(controls)

        self._event_list = QListWidget()
        self._event_list.currentRowChanged.connect(self._on_event_selected)
        layout.addWidget(self._event_list, 7)

        self._continuous_text = QTextEdit()
        self._continuous_text.setReadOnly(True)
        self._continuous_text.setPlaceholderText("连续文本视图会在此展示筛选后的日志。")
        self._continuous_text.hide()
        layout.addWidget(self._continuous_text, 7)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setPlaceholderText("选择或刷新日志后可在此查看完整 JSON 详情。")
        self._detail_text.hide()
        layout.addWidget(self._detail_text, 3)

        self._empty_label = QLabel("暂无系统日志。")
        self._empty_label.setStyleSheet("color: #8c6b7a; padding: 8px 4px;")
        layout.insertWidget(layout.indexOf(self._event_list) + 1, self._empty_label)
        self._empty_label.hide()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_view)
        self._refresh_timer.start()

    def _set_selected_event(self, event: dict | None) -> None:
        if event == self._selected_event:
            return
        detail_scroll = self._capture_scroll_state(self._detail_text)
        self._selected_event = event
        if event is None:
            self._detail_text.clear()
            self._detail_text.hide()
            return
        self._detail_text.setPlainText(json.dumps(event, ensure_ascii=False, indent=2))
        self._detail_text.show()
        self._restore_scroll_state(self._detail_text, detail_scroll)

    def _copy_selected_event_json(self) -> None:
        if self._selected_event is None:
            return
        self._copy_text(json.dumps(self._selected_event, ensure_ascii=False, indent=2))

    def _copy_text(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _on_source_group_changed(self) -> None:
        self._rebuild_source_filter_options()
        self._refresh_view()

    def _rebuild_source_filter_options(self) -> None:
        group_name = self._source_group_filter.currentData() or "全部"
        current_source = self._source_filter.currentData()
        sources = SOURCE_GROUPS.get(group_name, [])
        self._source_filter.blockSignals(True)
        self._source_filter.clear()
        self._source_filter.addItem("全部", "")
        for source in sources:
            self._source_filter.addItem(source, source)
        if current_source:
            index = self._source_filter.findData(current_source)
            if index >= 0:
                self._source_filter.setCurrentIndex(index)
        self._source_filter.blockSignals(False)

    def _refresh_view(self) -> None:
        session_id = self._current_session_id if self._current_session_only.isChecked() else None
        selected_key = self._event_key(self._selected_event) if self._selected_event is not None else None
        list_scroll = self._capture_scroll_state(self._event_list)
        continuous_scroll = self._capture_scroll_state(self._continuous_text)
        events = self._current_filtered_events()
        self._apply_view_mode()
        self._event_list.clear()
        if not events:
            self._empty_label.show()
            self._continuous_text.clear()
            self._set_selected_event(None)
            return
        self._empty_label.hide()
        for event in events:
            item = QListWidgetItem(self._render_event_line_text(event))
            item.setData(256, event)
            self._event_list.addItem(item)
        self._continuous_text.setPlainText(self._render_continuous_text(events))
        self._restore_scroll_state(self._continuous_text, continuous_scroll)
        if selected_key is not None:
            for index in range(self._event_list.count()):
                item = self._event_list.item(index)
                event = item.data(256)
                if self._event_key(event) == selected_key:
                    self._event_list.setCurrentRow(index)
                    self._restore_scroll_state(self._event_list, list_scroll)
                    return
        self._restore_scroll_state(self._event_list, list_scroll)
        self._set_selected_event(None)

    def _choose_export_path(self) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出系统日志",
            str(self._log_service.log_root / "system-export.jsonl"),
            "JSON Lines (*.jsonl)",
        )
        return Path(path) if path else None

    def _export_current_view(self) -> None:
        path = self._choose_export_path()
        if path is None:
            return
        events = self._current_filtered_events()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _open_log_directory(self) -> None:
        self._open_path(self._log_service.log_root / "system")

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        import os

        os.startfile(str(path))

    def set_session_id(self, session_id: str | None) -> None:
        self._current_session_id = session_id or None
        self._current_session_only.setChecked(bool(self._current_session_id))
        self._refresh_view()

    def _filter_events(self, events: list[dict]) -> list[dict]:
        level = self._level_filter.currentData()
        keyword = self._keyword_filter.text().strip().lower()
        group_sources = set(self._selected_group_sources())
        source = (self._selected_source() or "").lower()
        filtered = events
        if group_sources:
            filtered = [
                event for event in filtered
                if str(event.get("source", "")) in group_sources
            ]
        if source:
            filtered = [
                event for event in filtered
                if str(event.get("source", "")).lower() == source
            ]
        if level:
            filtered = [event for event in filtered if event.get("level") == level]
        if keyword:
            filtered = [
                event for event in filtered
                if keyword in json.dumps(event, ensure_ascii=False).lower()
            ]
        return filtered

    def _current_filtered_events(self) -> list[dict]:
        session_id = self._current_session_id if self._current_session_only.isChecked() else None
        events = self._log_service.query_events(source=None, session_id=session_id)
        return self._filter_events(events)

    def _selected_group_sources(self) -> list[str]:
        return list(SOURCE_GROUPS.get(self._source_group_filter.currentData() or "全部", []))

    def _selected_source(self) -> str | None:
        return self._source_filter.currentData() or None

    def _apply_view_mode(self) -> None:
        is_text_mode = self._view_mode.currentData() == "text"
        self._event_list.setHidden(is_text_mode)
        self._continuous_text.setHidden(not is_text_mode)

    def _render_continuous_text(self, events: list[dict]) -> str:
        return "\n\n".join(self._render_event_line_text(event) for event in events)

    def _render_event_line_text(self, event: dict) -> str:
        timestamp = event.get("timestamp", "")[11:23]
        level = (event.get("level", "info") or "info").upper()
        source = event.get("source", "unknown")
        session_id = event.get("session_id", "")
        body = self._body_text(event)
        return f"{timestamp}  {level}  {source}  [{session_id}]\n{body}"

    def _body_text(self, event: dict) -> str:
        event_type = event.get("event_type", "")
        details = event.get("details", {}) or {}
        if event_type in {"conversation.user_input", "conversation.assistant_reply"}:
            return details.get("text", event.get("summary", ""))
        if details.get("text"):
            return f"{event.get('summary', '')} | {details.get('text')}"
        if details.get("result_preview"):
            return f"{event.get('summary', '')} | {details.get('result_preview')}"
        return event.get("summary", "")

    def _on_event_selected(self, index: int) -> None:
        if index < 0:
            self._set_selected_event(None)
            return
        item = self._event_list.item(index)
        self._set_selected_event(item.data(256))

    @staticmethod
    def _event_key(event: dict | None):
        if not event:
            return None
        return (
            event.get("id"),
            event.get("timestamp"),
            event.get("source"),
            event.get("event_type"),
            event.get("summary"),
        )

    @staticmethod
    def _capture_scroll_state(widget) -> tuple[bool, int]:
        scrollbar = widget.verticalScrollBar()
        distance_to_bottom = scrollbar.maximum() - scrollbar.value()
        is_near_bottom = distance_to_bottom <= SCROLL_BOTTOM_THRESHOLD
        return is_near_bottom, scrollbar.value()

    @staticmethod
    def _restore_scroll_state(widget, state: tuple[bool, int]) -> None:
        is_near_bottom, previous_value = state
        scrollbar = widget.verticalScrollBar()
        if is_near_bottom:
            scrollbar.setValue(scrollbar.maximum())
            return
        scrollbar.setValue(min(previous_value, scrollbar.maximum()))
