from __future__ import annotations

from typing import Any

from test_sidecar_smoke import request, run_sidecar


def assert_all_stdout_lines_are_protocol_frames(frames: list[dict[str, Any]]) -> None:
    for frame in frames:
        assert frame["kind"] == "response"


def test_noisy_handlers_cannot_pollute_sidecar_stdout() -> None:
    frames, stderr = run_sidecar(
        [
            request("sidecar.hello", {"supported_versions": [1]}, "hello"),
            request("config.get_all", request_id="config"),
            request("tts.synthesize", {"text": "hello"}, "tts"),
            request("plugins.refresh", request_id="plugins"),
            request("mcp.list_servers", request_id="mcp"),
        ],
        env={
            "YUMETSUKI_SIDECAR_TEST_PRINT": "debug from handler",
            "YUMETSUKI_SIDECAR_TEST_FLOOD": "1",
        },
    )

    assert_all_stdout_lines_are_protocol_frames(frames)
    assert [frame["request_id"] for frame in frames] == ["hello", "config", "tts", "plugins", "mcp"]
    assert "debug from handler" in stderr
    assert "flood-line-" in stderr


def test_stderr_diagnostics_are_redacted() -> None:
    _frames, stderr = run_sidecar(
        [request("sidecar.hello", {"supported_versions": [1]})],
        env={"YUMETSUKI_SIDECAR_TEST_SENSITIVE_LOG": "1"},
    )

    assert "[redacted]" in stderr
    assert "sk-test-token" not in stderr
    assert "Authorization:" not in stderr
    assert "C:\\Users\\Alice" not in stderr
    assert "http://10.0.0.1" not in stderr
