from __future__ import annotations

from python_core.rpc.registry import build_default_registry
from python_core.rpc.schema.validate import method_names


def test_registry_registers_every_catalog_method() -> None:
    registry = build_default_registry()
    assert registry.registered_methods == registry.catalog_methods
    assert registry.catalog_methods == method_names()


def test_default_registry_has_real_handlers_for_final_smoke_methods() -> None:
    registry = build_default_registry()
    required = {
        "sidecar.hello",
        "sidecar.health",
        "sidecar.shutdown",
        "sidecar.cancel",
        "config.get_all",
        "logs.query",
        "chat.send",
    }
    assert required <= registry.registered_methods
