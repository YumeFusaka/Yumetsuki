from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable


class DiagnosticStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class DiagnosticCheckResult:
    key: str
    label: str
    status: DiagnosticStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    error_type: str = ""
    elapsed_ms: int = 0


@dataclass(frozen=True)
class DiagnosticCheck:
    key: str
    label: str
    run: Callable[[], dict[str, Any] | None]


class DiagnosticRunner:
    def __init__(self, checks: list[DiagnosticCheck]):
        self._checks = list(checks)

    def run_all(self) -> list[DiagnosticCheckResult]:
        return [self._run_check(check) for check in self._checks]

    def _run_check(self, check: DiagnosticCheck) -> DiagnosticCheckResult:
        started = time.perf_counter()
        try:
            details = check.run() or {}
            status = DiagnosticStatus.WARN if details.get("warning") else DiagnosticStatus.PASS
            message = str(details.get("message") or "通过")
            return DiagnosticCheckResult(
                key=check.key,
                label=check.label,
                status=status,
                message=message,
                details=details,
                elapsed_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return DiagnosticCheckResult(
                key=check.key,
                label=check.label,
                status=DiagnosticStatus.FAIL,
                message=str(exc),
                error_type=type(exc).__name__,
                elapsed_ms=self._elapsed_ms(started),
            )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
