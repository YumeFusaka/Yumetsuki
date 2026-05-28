import json
import zipfile

from core.diagnostic_bundle import DiagnosticBundleExporter
from core.log_service import LogService


def test_diagnostic_bundle_exports_sanitized_logs_and_metadata(tmp_path):
    service = LogService(tmp_path / "logs", system_flush_interval_ms=0)
    service.record_system(
        "llm.manager",
        "llm.request_failed",
        "请求失败",
        {
            "api_key": "fake-api-key",
            "api_url": "http://user:pass@127.0.0.1:8000/v1",
            "text": "错误摘要",
        },
        session_id="session-1",
    )
    bundle_path = tmp_path / "diagnostic.zip"

    result = DiagnosticBundleExporter(service).export(bundle_path)

    assert result.path == bundle_path
    assert result.event_count == 1
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert names == {"metadata.json", "events.jsonl"}
        metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
        events_text = archive.read("events.jsonl").decode("utf-8")

    assert metadata["format_version"] == 1
    assert "python_version" in metadata
    assert metadata["event_count"] == 1
    assert "fake-api-key" not in events_text
    assert "user:pass" not in events_text
    assert "llm.request_failed" in events_text
