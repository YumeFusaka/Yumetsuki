from core.diagnostic_runner import (
    DiagnosticCheck,
    DiagnosticRunner,
    DiagnosticStatus,
)


def test_diagnostic_runner_returns_pass_for_successful_check():
    runner = DiagnosticRunner(
        [
            DiagnosticCheck(
                "logs",
                "日志目录",
                lambda: {"message": "可用", "path": "data/logs"},
            )
        ]
    )

    result = runner.run_all()[0]

    assert result.key == "logs"
    assert result.label == "日志目录"
    assert result.status == DiagnosticStatus.PASS
    assert result.message == "可用"
    assert result.details["path"] == "data/logs"
    assert result.error_type == ""
    assert result.elapsed_ms >= 0


def test_diagnostic_runner_returns_warn_when_details_warning_is_true():
    runner = DiagnosticRunner(
        [
            DiagnosticCheck(
                "config",
                "配置对象",
                lambda: {"warning": True, "message": "存在非阻塞问题"},
            )
        ]
    )

    result = runner.run_all()[0]

    assert result.status == DiagnosticStatus.WARN
    assert result.message == "存在非阻塞问题"


def test_diagnostic_runner_returns_fail_for_exception():
    def fail():
        raise RuntimeError("boom")

    runner = DiagnosticRunner([DiagnosticCheck("api", "API", fail)])

    result = runner.run_all()[0]

    assert result.status == DiagnosticStatus.FAIL
    assert result.message == "boom"
    assert result.error_type == "RuntimeError"
    assert result.elapsed_ms >= 0
