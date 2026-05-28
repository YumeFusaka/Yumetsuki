from __future__ import annotations

from dataclasses import dataclass
import json
import platform
from pathlib import Path
import sys
import zipfile

from core.log_service import LogService
from core.log_sanitizer import sanitize_details


@dataclass(frozen=True)
class DiagnosticBundleResult:
    path: Path
    event_count: int


class DiagnosticBundleExporter:
    def __init__(self, log_service: LogService):
        self._log_service = log_service

    def export(self, path: Path | str) -> DiagnosticBundleResult:
        bundle_path = Path(path)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        events = [sanitize_details(event) for event in self._log_service.query_events()]
        metadata = {
            "format_version": 1,
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "event_count": len(events),
        }

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            lines = [json.dumps(event, ensure_ascii=False) for event in events]
            archive.writestr("events.jsonl", "\n".join(lines) + ("\n" if lines else ""))

        return DiagnosticBundleResult(path=bundle_path, event_count=len(events))
