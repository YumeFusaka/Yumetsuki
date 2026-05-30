from __future__ import annotations

import sys
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from python_core.rpc.errors import ERROR_CODES
from python_core.rpc.registry import registered_methods
from python_core.rpc.schema.schema_hash import compute_schema_hash, load_catalog
from python_core.rpc.schema.validate import event_names, method_names, validate_catalog


TS_PROJECTION = ROOT / "apps" / "desktop" / "frontend" / "src" / "client" / "types" / "rpc.ts"
RUST_PROJECTION = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "rpc_schema.rs"


def _extract_single_quoted_constants(path: Path, name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"{name}\s*=\s*\[(.*?)\]", text, re.S)
    if not match:
        return set()
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _extract_rust_constants(path: Path, name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"{name}:\s*&\[\&str\]\s*=\s*&\[(.*?)\];", text, re.S)
    if not match:
        return set()
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _extract_text_constant(path: Path, name: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    patterns = [
        rf"{name}\s*=\s*'([^']+)'",
        rf"{name}:\s*&str\s*=\s*\"([^\"]+)\"",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def main() -> int:
    catalog = load_catalog()
    errors = validate_catalog(catalog, ERROR_CODES)
    catalog_methods = set(method_names(catalog))
    catalog_events = set(event_names(catalog))
    if registered_methods() != catalog_methods:
        errors.append("Python registry 与 catalog method 集合不一致")
    if "security.confirm_required" in catalog_methods:
        errors.append("security.confirm_required 不能是 method")
    if "security.confirm_required" not in set(event_names(catalog)):
        errors.append("security.confirm_required 必须是 event")
    schema_hash = compute_schema_hash(catalog)
    if len(schema_hash) != 64:
        errors.append("schema hash 必须是 sha256 hex")
    if TS_PROJECTION.exists():
        if _extract_text_constant(TS_PROJECTION, "SCHEMA_HASH") != schema_hash:
            errors.append("TS SCHEMA_HASH 与 catalog 不一致")
        if _extract_single_quoted_constants(TS_PROJECTION, "RPC_METHODS") != catalog_methods:
            errors.append("TS RPC_METHODS 与 catalog 不一致")
        if _extract_single_quoted_constants(TS_PROJECTION, "RPC_EVENTS") != catalog_events:
            errors.append("TS RPC_EVENTS 与 catalog 不一致")
    if RUST_PROJECTION.exists():
        if _extract_text_constant(RUST_PROJECTION, "SCHEMA_HASH") != schema_hash:
            errors.append("Rust SCHEMA_HASH 与 catalog 不一致")
        if _extract_rust_constants(RUST_PROJECTION, "RPC_METHODS") != catalog_methods:
            errors.append("Rust RPC_METHODS 与 catalog 不一致")
        if _extract_rust_constants(RUST_PROJECTION, "RPC_EVENTS") != catalog_events:
            errors.append("Rust RPC_EVENTS 与 catalog 不一致")

    if errors:
        print("rpc schema contract failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"rpc schema contract ok ({len(catalog_methods)} methods, schema_hash={schema_hash})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
