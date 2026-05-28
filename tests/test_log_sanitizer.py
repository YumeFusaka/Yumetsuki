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


def test_sanitize_details_masks_private_urls_and_long_paths():
    payload = {
        "api_url": "http://user:pass@127.0.0.1:9880/tts",
        "model_path": "E:/private/models/faster-whisper-large-v3-turbo",
        "screenshot_path": "data/vision/screen.png",
        "text": "短文本",
    }

    sanitized = sanitize_details(payload)

    assert sanitized["api_url"] == "http://***@127.0.0.1:9880/tts"
    assert sanitized["model_path"].endswith("faster-whisper-large-v3-turbo")
    assert sanitized["model_path"].startswith("***")
    assert sanitized["screenshot_path"].endswith("screen.png")
    assert sanitized["text"] == "短文本"


def test_sanitize_details_truncates_large_text_fields():
    payload = {"ocr_text": "屏幕文字" * 500}

    sanitized = sanitize_details(payload)

    assert len(sanitized["ocr_text"]) < len(payload["ocr_text"])
    assert sanitized["ocr_text"].endswith("...<truncated>")
