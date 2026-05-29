from __future__ import annotations

from typing import Any

from python_core.rpc.envelope import validate_event_envelope, validate_request_envelope, validate_response_envelope
from python_core.rpc.registry import MethodRegistry, SidecarRuntime
from python_core.runtime_paths import RuntimePaths


class RpcHarness:
    def __init__(self) -> None:
        self.registry = MethodRegistry()
        self.runtime = SidecarRuntime.create(RuntimePaths.temporary())

    def dispatch(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        payload = {
            "kind": "request",
            "request_id": request_id or f"req_{method.replace('.', '_')}",
            "method": method,
            "params": params or {},
            "protocol_version": 1,
            "trace_id": "trace_speech_vision",
            "parent_trace_id": None,
            "session_id": "sess_speech_vision",
            "deadline_ms": 30000,
        }
        response = self.registry.dispatch(validate_request_envelope(payload), self.runtime)
        validate_response_envelope(response)
        events = self.runtime.task_registry.event_publisher.drain()
        for event in events:
            validate_event_envelope(event)
        if not response["ok"]:
            assert response["error"]["code"] != "sidecar.not_ready"
        return response, events


def _terminal_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["payload"].get("terminal_state") in {"done", "error", "cancelled"}]


def test_tts_synthesize_returns_accepted_and_audio_events() -> None:
    response, events = RpcHarness().dispatch(
        "tts.synthesize",
        {"text": "hello", "voice_config_ref": "default", "session_id": "sess_speech_vision"},
    )

    assert response["ok"] is True
    assert response["result"]["status"] == "accepted"
    assert [event["type"] for event in events] == ["tts.started", "tts.segment", "tts.done"]
    assert events[1]["payload"]["segment_handle"].startswith("handle:audio:")
    assert len(_terminal_events(events)) == 1


def test_stt_methods_return_safe_headless_audio_and_transcript() -> None:
    harness = RpcHarness()

    begin_response, begin_events = harness.dispatch("stt.begin_recording", {"timeout_ms": 1000})
    stop_response, stop_events = harness.dispatch(
        "stt.stop_recording",
        {"recording_request_id": begin_response["result"]["request_id"]},
    )
    transcribe_response, transcribe_events = harness.dispatch(
        "stt.transcribe",
        {"audio_handle": stop_response["result"]["audio_handle"], "language": "zh"},
    )

    assert begin_response["result"]["task_type"] == "stt.begin_recording"
    assert begin_events[0]["type"] == "stt.recording"
    assert len(_terminal_events(begin_events)) == 1
    assert stop_response["result"]["no_audio"] is False
    assert stop_events[-1]["type"] == "stt.recording_stopped"
    assert transcribe_response["result"]["status"] == "accepted"
    assert transcribe_events[-1]["type"] == "stt.done"


def test_ocr_capture_recognize_and_cleanup_use_headless_facades() -> None:
    harness = RpcHarness()

    capture_response, capture_events = harness.dispatch("ocr.capture", {"reason": "contract"})
    image_handle = capture_events[-1]["payload"]["image_handle"]
    recognize_response, recognize_events = harness.dispatch("ocr.recognize", {"image_handle": image_handle})
    cleanup_response, cleanup_events = harness.dispatch("ocr.cleanup", {})

    assert capture_response["result"]["task_type"] == "ocr.capture"
    assert capture_events[-1]["type"] == "ocr.capture_done"
    assert len(_terminal_events(capture_events)) == 1
    assert recognize_response["result"]["status"] == "accepted"
    assert recognize_events[-1]["type"] == "ocr.done"
    assert cleanup_response["result"]["cleanup_summary"]["released_handles"] == 0
    assert cleanup_events == []


def test_speech_and_vision_required_param_errors_are_invalid_params() -> None:
    harness = RpcHarness()

    tts_error, _tts_events = harness.dispatch("tts.synthesize", {"text": "hello", "session_id": "sess"})
    ocr_error, _ocr_events = harness.dispatch("ocr.recognize", {})

    assert tts_error["error"]["code"] == "rpc.invalid_params"
    assert ocr_error["error"]["code"] == "rpc.invalid_params"
