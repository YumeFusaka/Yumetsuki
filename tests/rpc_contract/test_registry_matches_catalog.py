from __future__ import annotations

from python_core.rpc.registry import REGISTRY, get_handler, registered_methods
from python_core.rpc.schema.schema_hash import load_catalog
from python_core.rpc.schema.validate import method_names


def test_registry_matches_catalog_exactly() -> None:
    catalog_methods = set(method_names(load_catalog()))
    assert registered_methods() == catalog_methods
    assert set(REGISTRY) == catalog_methods


def test_all_catalog_methods_have_stub_or_handler() -> None:
    for method in method_names(load_catalog()):
        assert get_handler(method) is not None


def test_non_catalog_method_is_not_registered() -> None:
    assert get_handler("unknown.method") is None


def test_unmigrated_stub_returns_sidecar_not_ready() -> None:
    response = REGISTRY["config.get_all"]({})
    assert response["ok"] is False
    assert response["error"]["code"] == "sidecar.not_ready"
