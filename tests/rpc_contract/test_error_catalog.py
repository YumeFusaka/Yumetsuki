from __future__ import annotations

import re
from pathlib import Path

from python_core.rpc.errors import ERROR_METADATA
from python_core.rpc.schema.schema_hash import load_catalog


ROOT = Path(__file__).resolve().parents[2]
TS_ERROR_CODES = ROOT / "apps" / "desktop" / "frontend" / "src" / "client" / "errorCodes.ts"
RUST_ERROR_CODES = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "error_codes.rs"


def test_catalog_errors_map_to_error_metadata() -> None:
    catalog = load_catalog()
    known_domains = {code.split(".", 1)[0] for code in ERROR_METADATA}
    for code in catalog["errors"]:
        if code.endswith(".*"):
            assert code[:-2] in known_domains
        else:
            assert code in ERROR_METADATA
    for method in catalog["methods"]:
        for code in method["errors"]:
            if code.endswith(".*"):
                assert code[:-2] in known_domains
            else:
                assert code in ERROR_METADATA


def test_error_metadata_is_complete() -> None:
    for metadata in ERROR_METADATA.values():
        assert set(metadata) >= {
            "message",
            "user_message",
            "retryable",
            "details_schema",
            "redaction_policy",
        }


def test_ts_and_rust_error_code_sets_match_python() -> None:
    expected = set(ERROR_METADATA)
    ts_codes = set(re.findall(r"'([^']+\.[^']+)'", TS_ERROR_CODES.read_text(encoding="utf-8")))
    rust_codes = set(re.findall(r'"([^"]+\.[^"]+)"', RUST_ERROR_CODES.read_text(encoding="utf-8")))
    assert ts_codes == expected
    assert rust_codes == expected
