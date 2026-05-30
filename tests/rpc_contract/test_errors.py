from __future__ import annotations

from python_core.rpc.errors import ERROR_METADATA, RpcErrorCode, make_error


REQUIRED_CODES = {
    "rpc.protocol_unsupported",
    "rpc.method_not_found",
    "rpc.invalid_params",
    "rpc.invalid_frame",
    "rpc.request_timeout",
    "rpc.duplicate_terminal",
    "rpc.event_out_of_order",
    "rpc.payload_too_large",
    "sidecar.not_ready",
    "sidecar.restarted",
    "sidecar.task_not_found",
    "sidecar.shutdown_timeout",
    "security.confirm_token_invalid",
    "filesystem.path_out_of_scope",
    "config.version_conflict",
    "config.validation_failed",
    "plugin.worker_crashed",
    "mcp.server_unavailable",
}


def test_required_error_codes_exist() -> None:
    assert REQUIRED_CODES <= set(ERROR_METADATA)


def test_each_error_has_user_visible_and_redaction_metadata() -> None:
    for code, metadata in ERROR_METADATA.items():
        assert metadata["message"]
        assert metadata["user_message"]
        assert isinstance(metadata["retryable"], bool)
        assert metadata["details_schema"]
        assert metadata["redaction_policy"]


def test_make_error_redacts_sensitive_details() -> None:
    error = make_error(
        RpcErrorCode.RPC_INVALID_PARAMS,
        details={"api_key": "sk-secret", "nested": {"cookie": "session=abc"}, "safe": "ok"},
    )
    assert error.details["api_key"] == "[redacted]"
    assert error.details["nested"]["cookie"] == "[redacted]"
    assert error.details["safe"] == "ok"
