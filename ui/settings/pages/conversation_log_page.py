from PySide6.QtCore import Qt, QTimer
from html import escape as html_escape

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import SAKURA_COMBO_BOX_STYLE, SAKURA_TOOLTIP_STYLE, settings_font_tokens, settings_page_title


PAGE_STYLE = """
QWidget {
    background: transparent;
}
QTextEdit {
    background: rgba(255, 252, 254, 0.78);
    border: 1px solid rgba(220, 160, 180, 0.28);
    border-radius: 14px;
    padding: 14px;
    color: #4a3040;
    font-size: 13px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
}
QLabel {
    color: #8c6b7a;
    font-size: 13px;
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
""" + SAKURA_COMBO_BOX_STYLE + SAKURA_TOOLTIP_STYLE

SCROLL_BOTTOM_THRESHOLD = 2


class ConversationLogPage(QWidget):
    def __init__(self, log_service, parent=None):
        super().__init__(parent)
        self._log_service = log_service
        self._current_session_id: str | None = None
        self._last_timeline_html = ""
        self._last_timeline_plain = "暂无对话日志。"
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = settings_page_title(QLabel("对话日志"))
        layout.addWidget(title)

        desc = QLabel("查看用户输入、角色回复与会话级结构化日志。")
        layout.addWidget(desc)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("范围"))
        self._scope_selector = QComboBox()
        self._scope_selector.addItems(["当前会话", "全部会话"])
        self._scope_selector.currentTextChanged.connect(self._refresh_view)
        controls.addWidget(self._scope_selector)

        controls.addWidget(QLabel("最近会话"))
        self._session_selector = QComboBox()
        self._session_selector.currentIndexChanged.connect(self._apply_session_selection)
        controls.addWidget(self._session_selector, 1)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_sessions_and_view)
        controls.addWidget(refresh_btn)

        self._auto_refresh = QCheckBox("自动刷新")
        self._auto_refresh.setChecked(True)
        controls.addWidget(self._auto_refresh)
        layout.addLayout(controls)

        self._timeline = QTextEdit()
        self._timeline.setReadOnly(True)
        self._timeline.setPlainText("暂无对话日志。")
        layout.addWidget(self._timeline, 1)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_if_enabled)
        self._sync_refresh_timer()
        self._refresh_sessions()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_sessions_and_view()
        self._sync_refresh_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._sync_refresh_timer()

    def _sync_refresh_timer(self) -> None:
        if self.isVisible():
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
            return
        self._refresh_timer.stop()

    def _refresh_view(self) -> None:
        scroll_state = self._capture_scroll_state(self._timeline)
        session_id = self._current_session_id
        if self._scope_selector.currentText() == "全部会话":
            session_id = None
        events = self._log_service.query_events(
            channel="conversation",
            session_id=session_id,
        )
        if not events:
            text = "暂无对话日志。"
            if text != self._last_timeline_plain:
                self._timeline.setPlainText(text)
                self._last_timeline_plain = text
                self._last_timeline_html = ""
            self._restore_scroll_state(self._timeline, scroll_state)
            self._restore_scroll_state_later(self._timeline, scroll_state)
            return
        html = "".join(self._render_event_block(event) for event in events)
        if html != self._last_timeline_html:
            self._timeline.setHtml(html)
            self._last_timeline_html = html
            self._last_timeline_plain = ""
        self._restore_scroll_state(self._timeline, scroll_state)
        self._restore_scroll_state_later(self._timeline, scroll_state)

    def refresh_appearance(self) -> None:
        self._refresh_view()

    def set_session_id(self, session_id: str | None) -> None:
        self._current_session_id = session_id or None
        self._scope_selector.setCurrentText("当前会话" if self._current_session_id else "全部会话")
        self._refresh_sessions()
        self._refresh_view()

    def _apply_session_selection(self) -> None:
        self._current_session_id = self._session_selector.currentData() or None
        if self._current_session_id:
            self._scope_selector.setCurrentText("当前会话")
        self._refresh_view()

    def _refresh_sessions_and_view(self) -> None:
        self._refresh_sessions()
        self._refresh_view()

    def _refresh_sessions(self) -> None:
        list_sessions = getattr(self._log_service, "list_conversation_sessions", None)
        sessions = list_sessions(limit=20) if callable(list_sessions) else []
        selected_session_id = self._current_session_id
        self._session_selector.blockSignals(True)
        self._session_selector.clear()

        found_current = False
        for session in sessions:
            session_id = session.get("session_id")
            if not session_id:
                continue
            label = session.get("label") or str(session_id)
            self._session_selector.addItem(str(label), session_id)
            if session_id == selected_session_id:
                found_current = True

        if selected_session_id and not found_current:
            self._session_selector.insertItem(0, f"当前会话 {selected_session_id}", selected_session_id)

        if self._session_selector.count() > 0:
            index = self._session_selector.findData(selected_session_id)
            self._session_selector.setCurrentIndex(index if index >= 0 else 0)
            if selected_session_id:
                self._current_session_id = selected_session_id
            else:
                self._current_session_id = self._session_selector.currentData() or None
        self._session_selector.blockSignals(False)

    def _refresh_if_enabled(self) -> None:
        if self._auto_refresh.isChecked() and not self._is_user_selecting_text():
            self._refresh_view()

    def _render_event_block(self, event: dict) -> str:
        tokens = settings_font_tokens(self._config_for_fonts())
        event_type = event.get("event_type", "")
        details = event.get("details", {}) or {}
        timestamp = self._format_time(event.get("timestamp", ""))
        text = html_escape(details.get("text", event.get("summary", "")))

        emotion = details.get("emotion")
        inline_emotion = ""
        if emotion:
            inline_emotion = (
                f' <span style="display:inline-block; margin-left: 6px; padding: 4px 12px; '
                'background: rgba(255, 236, 242, 0.96); border: 1px solid rgba(212, 86, 122, 0.18); '
                f'border-radius: 999px; font-size: {tokens.html_small}px; color: #8b4d66; vertical-align: middle;">'
                f'{html_escape(str(emotion))}</span>'
            )

        if event_type == "conversation.user_input":
            return self._render_message_card(
                speaker="你",
                timestamp=timestamp,
                text=text,
                inline_suffix="",
                tags=[],
                title_color="#5f6fb2",
            )

        tags = []
        tool_names = details.get("tool_names") or []
        if tool_names:
            tags.append("工具 " + ", ".join(html_escape(str(name)) for name in tool_names))
        memory_count = details.get("memory_count")
        if memory_count:
            tags.append(f"关联记忆 {memory_count} 条")
        return self._render_message_card(
            speaker="梦月",
            timestamp=timestamp,
            text=text,
            inline_suffix=inline_emotion,
            tags=tags,
            title_color="#9b3060",
        )

    def _config_for_fonts(self):
        parent = self.parent()
        while parent is not None:
            config = getattr(parent, "_config", None)
            if config is not None and hasattr(config, "system"):
                return config.system
            parent = parent.parent()
        return None

    @staticmethod
    def _format_time(timestamp: str) -> str:
        if not timestamp:
            return ""
        return timestamp[11:16]

    def _render_message_card(
        self,
        speaker: str,
        timestamp: str,
        text: str,
        inline_suffix: str,
        tags: list[str],
        title_color: str,
    ) -> str:
        tokens = settings_font_tokens(self._config_for_fonts())
        tag_html = ""
        if tags:
            tag_html = (
                '<div style="margin-top: 10px; padding-top: 9px; '
                'border-top: 1px solid rgba(220, 160, 180, 0.18);">'
                + "".join(
                    f'<span style="display:inline-block; margin: 0 8px 8px 0; padding: 5px 10px; '
                    'background: rgba(255, 236, 242, 0.96); border: 1px solid rgba(212, 86, 122, 0.18); '
                    f'border-radius: 999px; font-size: {tokens.html_small}px; color: #8b4d66;">'
                    f'{html_escape(tag)}</span>'
                    for tag in tags
                )
                + "</div>"
            )
        return (
            '<div style="margin: 0 0 16px 0; padding: 16px 18px; background: rgba(255, 248, 251, 0.95); '
            'border: 1px solid rgba(220, 160, 180, 0.26); border-radius: 16px;">'
            f'<div style="font-size: {tokens.html_small}px; color: {title_color}; margin-bottom: 8px; font-weight: 600;">'
            f'{speaker} · {timestamp}</div>'
            f'<div style="font-size: {tokens.html_body}px; line-height: 1.7; color: #4a3040;">{text}{inline_suffix}</div>'
            f'{tag_html}'
            '</div>'
        )

    def _is_user_selecting_text(self) -> bool:
        if self._timeline.textCursor().hasSelection():
            return True
        if not QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            return False
        focus_widget = QApplication.focusWidget()
        return focus_widget is self._timeline or self._timeline.isAncestorOf(focus_widget)

    @staticmethod
    def _capture_scroll_state(widget) -> tuple[bool, int]:
        scrollbar = widget.verticalScrollBar()
        distance_to_bottom = scrollbar.maximum() - scrollbar.value()
        is_near_bottom = distance_to_bottom <= SCROLL_BOTTOM_THRESHOLD
        return is_near_bottom, scrollbar.value()

    @staticmethod
    def _restore_scroll_state(widget, state: tuple[bool, int]) -> None:
        is_near_bottom, previous_value = state
        try:
            scrollbar = widget.verticalScrollBar()
        except RuntimeError:
            return
        if is_near_bottom:
            scrollbar.setValue(scrollbar.maximum())
            return
        scrollbar.setValue(min(previous_value, scrollbar.maximum()))

    @staticmethod
    def _restore_scroll_state_later(widget, state: tuple[bool, int]) -> None:
        QTimer.singleShot(0, lambda: ConversationLogPage._restore_scroll_state(widget, state))
