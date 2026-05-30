from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from core.config_health import ConfigHealthChecker
from core.diagnostic_runner import DiagnosticCheck, DiagnosticRunner, DiagnosticStatus
from ui.theme import SAKURA_COMBO_BOX_STYLE, set_settings_font_role, settings_page_title


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
QPushButton#diagnosticsActionButton {
    background: rgba(255, 245, 250, 0.88);
    border: 1px solid rgba(212, 86, 122, 0.32);
    border-radius: 8px;
    padding: 6px 12px;
    color: #6b4a5a;
    font-size: 12px;
    min-height: 22px;
}
QPushButton#diagnosticsActionButton:hover {
    background: rgba(255, 232, 240, 0.96);
    border-color: rgba(212, 86, 122, 0.48);
}
""" + SAKURA_COMBO_BOX_STYLE


class DiagnosticsPage(QWidget):
    def __init__(self, config, log_service, parent=None):
        super().__init__(parent)
        self._config = config
        self._log_service = log_service
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        layout.addWidget(settings_page_title(QLabel("诊断")))

        desc = QLabel("查看配置健康检查、手动本机诊断结果，并导出脱敏诊断包。")
        layout.addWidget(desc)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self._refresh_btn = self._action_button("刷新配置健康")
        self._refresh_btn.clicked.connect(self._refresh_health)
        button_row.addWidget(self._refresh_btn)

        self._run_btn = self._action_button("运行本机诊断")
        self._run_btn.clicked.connect(self._run_checks)
        button_row.addWidget(self._run_btn)

        self._export_btn = self._action_button("导出诊断包")
        self._export_btn.clicked.connect(self._export_bundle)
        button_row.addWidget(self._export_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        layout.addWidget(QLabel("配置健康检查"))
        self._health_text = QTextEdit()
        self._health_text.setReadOnly(True)
        self._health_text.setPlaceholderText("点击刷新后显示配置健康检查结果。")
        layout.addWidget(self._health_text, 2)

        layout.addWidget(QLabel("手动诊断与导出结果"))
        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setPlaceholderText("点击运行本机诊断或导出诊断包后显示结果。")
        layout.addWidget(self._result_text, 3)

        self._refresh_health()

    def _action_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("diagnosticsActionButton")
        set_settings_font_role(button, "small")
        return button

    def _collect_health_issues(self) -> list[Any]:
        return ConfigHealthChecker().check_all(
            self._config.api,
            self._config.system,
            self._config.mcp,
            self._config.memory,
            self._config.agent,
        )

    def _run_smoke_checks(self):
        checks = [
            DiagnosticCheck("logs", "平台日志目录", self._check_log_root),
            DiagnosticCheck("config", "配置对象加载", self._check_config_loaded),
        ]
        return DiagnosticRunner(checks).run_all()

    def _check_log_root(self) -> dict[str, Any]:
        log_root = Path(getattr(self._log_service, "log_root", "data/logs"))
        return {"message": str(log_root), "exists": log_root.exists()}

    def _check_config_loaded(self) -> dict[str, Any]:
        missing = [
            name
            for name in ("api", "system", "mcp", "memory", "agent")
            if not hasattr(self._config, name)
        ]
        if missing:
            return {
                "warning": True,
                "message": "配置对象缺少字段：" + "、".join(missing),
                "missing": missing,
            }
        return {"message": "配置对象加载完成"}

    def _refresh_health(self) -> None:
        try:
            issues = self._collect_health_issues()
        except Exception as exc:
            self._health_text.setPlainText(f"[FAIL] 配置健康检查运行失败：{type(exc).__name__}: {exc}")
            return
        if not issues:
            self._health_text.setPlainText("配置健康检查未发现阻塞问题。")
            return
        lines = []
        for issue in issues:
            level = self._issue_level(issue)
            area = getattr(issue, "area", "config")
            code = getattr(issue, "code", "")
            message = getattr(issue, "message", str(issue))
            lines.append(f"[{level.upper()}] {area} {code}: {message}")
        self._health_text.setPlainText("\n".join(lines))

    def _run_checks(self) -> None:
        results = self._run_smoke_checks()
        lines = []
        for result in results:
            suffix = f" ({result.elapsed_ms}ms)"
            if result.status == DiagnosticStatus.FAIL and result.error_type:
                suffix = f" [{result.error_type}]{suffix}"
            lines.append(f"[{result.status.value.upper()}] {result.label}: {result.message}{suffix}")
        self._result_text.setPlainText("\n".join(lines) if lines else "没有可运行的诊断检查。")

    def _choose_bundle_path(self) -> Path | None:
        log_root = Path(getattr(self._log_service, "log_root", "data/logs"))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出诊断包",
            str(log_root / "yumetsuki-diagnostic.zip"),
            "Zip (*.zip)",
        )
        return Path(path) if path else None

    def _export_bundle(self) -> None:
        path = self._choose_bundle_path()
        if path is None:
            return
        export = getattr(self._log_service, "export_diagnostic_bundle", None)
        if not callable(export):
            self._result_text.setPlainText("诊断包导出入口尚未整合，暂时无法导出诊断包。")
            return
        try:
            result = export(path)
        except Exception as exc:
            self._result_text.setPlainText(f"诊断包导出失败：{type(exc).__name__}: {exc}")
            return
        self._result_text.setPlainText(f"诊断包已导出：{result.path}\n事件数量：{result.event_count}")

    @staticmethod
    def _issue_level(issue) -> str:
        level = getattr(issue, "level", "warn")
        return str(getattr(level, "value", level) or "warn")
