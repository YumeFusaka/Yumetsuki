from __future__ import annotations

from dataclasses import dataclass

from python_core import __version__

from .schema.schema_hash import SCHEMA_HASH, load_catalog


SUPPORTED_PROTOCOL_VERSIONS = {1}
CAPABILITIES = ["runtime_paths.v1", "events.v1", "catalog.v1"]


@dataclass(frozen=True)
class ProtocolNegotiationError(Exception):
    code: str
    message: str


def negotiate_protocol(client_versions: list[int]) -> int:
    catalog = load_catalog()
    min_version = int(catalog["min_compatible_protocol_version"])
    server_versions = {version for version in SUPPORTED_PROTOCOL_VERSIONS if version >= min_version}
    shared = sorted(server_versions & set(client_versions))
    if not shared:
        raise ProtocolNegotiationError(
            "rpc.protocol_unsupported",
            "no compatible protocol version",
        )
    return shared[-1]


def build_hello_result(client_versions: list[int], runtime_paths_ready: bool) -> dict[str, object]:
    selected = negotiate_protocol(client_versions)
    catalog = load_catalog()
    return {
        "selected_protocol_version": selected,
        "min_compatible_protocol_version": catalog["min_compatible_protocol_version"],
        "sidecar_version": __version__,
        "capabilities": CAPABILITIES,
        "runtime_paths_ready": runtime_paths_ready,
        "schema_hash": SCHEMA_HASH,
    }
