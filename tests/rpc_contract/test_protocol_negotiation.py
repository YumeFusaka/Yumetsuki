from __future__ import annotations

import copy

import pytest

from python_core.rpc.protocol import ProtocolNegotiationError, build_hello_result, negotiate_protocol
from python_core.rpc.schema.schema_hash import compute_schema_hash, load_catalog


def test_schema_hash_is_stable() -> None:
    catalog = load_catalog()
    assert compute_schema_hash(catalog) == compute_schema_hash(copy.deepcopy(catalog))


def test_schema_hash_changes_when_catalog_changes() -> None:
    catalog = load_catalog()
    changed = copy.deepcopy(catalog)
    changed["schema_version"] = 999
    assert compute_schema_hash(catalog) != compute_schema_hash(changed)


def test_protocol_negotiation_selects_highest_common_version() -> None:
    assert negotiate_protocol([0, 1]) == 1


def test_protocol_negotiation_rejects_no_common_version() -> None:
    with pytest.raises(ProtocolNegotiationError) as exc_info:
        negotiate_protocol([0])
    assert exc_info.value.code == "rpc.protocol_unsupported"


def test_hello_result_contains_required_contract_fields() -> None:
    result = build_hello_result([1], runtime_paths_ready=True)
    assert set(result) >= {
        "selected_protocol_version",
        "min_compatible_protocol_version",
        "sidecar_version",
        "capabilities",
        "runtime_paths_ready",
        "schema_hash",
    }
    assert result["selected_protocol_version"] == 1
    assert result["runtime_paths_ready"] is True
