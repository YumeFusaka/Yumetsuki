from __future__ import annotations


SENSITIVE_KEYS = {"api_key", "token", "password", "authorization", "cookie"}


def sanitize_details(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***"
                continue
            result[key] = sanitize_details(item)
        return result
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    return value
