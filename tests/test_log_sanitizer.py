from core.log_sanitizer import sanitize_details


def test_sanitize_details_masks_sensitive_fields():
    payload = {
        "api_key": "sk-live-secret",
        "headers": {
            "Authorization": "Bearer top-secret",
            "Cookie": "session=abc",
        },
        "text": "hello",
    }

    sanitized = sanitize_details(payload)

    assert sanitized["api_key"] == "***"
    assert sanitized["headers"]["Authorization"] == "***"
    assert sanitized["headers"]["Cookie"] == "***"
    assert sanitized["text"] == "hello"
