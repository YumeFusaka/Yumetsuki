from pathlib import Path

from PySide6.QtWidgets import QApplication

from config.schema import AgentConfig, APIConfig, MCPConfig, MemoryConfig, SystemConfig
from core.diagnostic_runner import DiagnosticCheckResult, DiagnosticStatus
from ui.settings.pages.diagnostics_page import DiagnosticsPage


def _app():
    app = QApplication.instance()
    return app or QApplication([])


class _FakeConfig:
    def __init__(self):
        self.api = APIConfig()
        self.system = SystemConfig()
        self.mcp = MCPConfig()
        self.memory = MemoryConfig()
        self.agent = AgentConfig()


class _FakeIssue:
    def __init__(self, level, area, code, message):
        self.level = level
        self.area = area
        self.code = code
        self.message = message


class _FakeLevel:
    value = "warn"


class _FakeLogService:
    log_root = Path(".")

    def export_diagnostic_bundle(self, path):
        self.exported_path = Path(path)
        return type("Result", (), {"path": Path(path), "event_count": 2})()


def test_diagnostics_page_renders_health_and_smoke_results(monkeypatch):
    _app()
    page = DiagnosticsPage(_FakeConfig(), _FakeLogService())
    monkeypatch.setattr(
        page,
        "_collect_health_issues",
        lambda: [_FakeIssue(_FakeLevel(), "api.tts", "tts_experimental_mode", "TTS 扩展模式")],
        raising=False,
    )
    monkeypatch.setattr(
        page,
        "_run_smoke_checks",
        lambda: [DiagnosticCheckResult("api", "API 连通", DiagnosticStatus.PASS, "通过", {}, "", 1)],
        raising=False,
    )

    page._refresh_health()
    page._run_checks()

    assert "TTS 扩展模式" in page._health_text.toPlainText()
    assert "API 连通" in page._result_text.toPlainText()
    assert "通过" in page._result_text.toPlainText()


def test_diagnostics_page_exports_bundle_without_file_dialog(monkeypatch, tmp_path):
    _app()
    log_service = _FakeLogService()
    page = DiagnosticsPage(_FakeConfig(), log_service)
    target = tmp_path / "diagnostic.zip"
    monkeypatch.setattr(page, "_choose_bundle_path", lambda: target, raising=False)

    page._export_bundle()

    assert log_service.exported_path == target
    assert str(target) in page._result_text.toPlainText()
    assert "事件数量：2" in page._result_text.toPlainText()
