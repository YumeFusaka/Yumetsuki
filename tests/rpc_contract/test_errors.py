from __future__ import annotations

from python_core.rpc.errors import ERROR_CATALOG, error_catalog_with_policies, make_error


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
    "sidecar.busy",
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
    assert REQUIRED_CODES <= set(ERROR_CATALOG)


def test_errors_include_ui_and_redaction_metadata() -> None:
    catalog = error_catalog_with_policies()
    for code in REQUIRED_CODES:
        spec = catalog[code]
        assert spec["message"]
        assert spec["user_message"]
        assert isinstance(spec["retryable"], bool)
        assert spec["details_schema"]
        assert spec["redaction_policy"]


def test_make_error_redacts_sensitive_details() -> None:
    error = make_error(
        "rpc.invalid_params",
        details={
            "api_key": "sk-secret-token-value",
            "path": "C:/Users/alice/private/model.bin",
            "url": "http://127.0.0.1:8080/secret?q=1",
        },
    )
    assert error.details["api_key"] == "<redacted>"
    assert "<user-path>" in error.details["path"]
    assert error.details["url"] == "<private-url>"
