from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).with_name("catalog.json")


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or CATALOG_PATH
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_schema_hash(catalog: dict[str, Any] | None = None) -> str:
    payload = catalog if catalog is not None else load_catalog()
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
