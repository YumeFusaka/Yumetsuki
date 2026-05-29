from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_TAURI = ROOT / "apps" / "desktop" / "src-tauri"
CAPABILITIES_DIR = SRC_TAURI / "capabilities"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(_read_text(path))


def _capability_files() -> dict[str, dict]:
    return {path.stem: _read_json(path) for path in sorted(CAPABILITIES_DIR.glob("*.json"))}


def test_sidecar_supervisor_keeps_stateful_process_stdio_registry_traces() -> None:
    sidecar = _read_text(SRC_TAURI / "src" / "sidecar.rs")
    rpc = _read_text(SRC_TAURI / "src" / "rpc.rs")

    for token in [
        "pub struct SidecarSupervisor",
        "SidecarProcessSpec",
        "SidecarProcessState",
        "RequestRegistryEntry",
        "SidecarEventBridge",
        "python_core.sidecar_main",
        "--stdio",
        "request_registry: BTreeMap<String, RequestRegistryEntry>",
        "request_deadline_ms: u64",
        "shutdown_timeout_ms: u64",
        "process_spec: SidecarProcessSpec",
        "process_state: SidecarProcessState",
        "cancel_with_reason",
        "sidecar.restarted",
        "shared.request_registry.remove",
        "CommandResponse::accepted(",
        "sidecar_generation: self.generation",
    ]:
        assert token in sidecar, f"sidecar.rs 缺少结构痕迹: {token}"

    assert sidecar.count("CommandResponse::accepted(") >= 3, "sidecar.rs 应保留多个 accepted 分支"
    assert "todo!(" not in sidecar.lower()
    assert "unimplemented!" not in sidecar.lower()

    for token in [
        "pub struct RequestEnvelope<T>",
        "pub request_id: String",
        "pub method: String",
        "pub params: T",
        "pub deadline_ms: u64",
        "pub trace_id: String",
        "pub session_id: Option<String>",
        "pub struct CommandResponse<T>",
        "rpc.request_timeout",
    ]:
        assert token in rpc, f"rpc.rs 缺少结构痕迹: {token}"


def test_tauri_config_keeps_frontend_dist_csp_and_capabilities_closed() -> None:
    config = _read_json(SRC_TAURI / "tauri.conf.json")
    capabilities = _capability_files()

    assert config["build"]["frontendDist"] == "../frontend/dist"

    security = config["app"]["security"]
    assert set(security["capabilities"]) == set(capabilities)

    csp = security["csp"]
    assert isinstance(csp, str)
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "connect-src ipc: http://ipc.localhost" in csp
    assert "unsafe-eval" not in csp

    dangerous_prefixes = ("shell:", "fs:", "opener:", "http:", "clipboard:")
    for name, capability in capabilities.items():
        assert capability["identifier"] == name
        assert capability["windows"] == [name]
        assert capability["permissions"], f"{name} capability permissions 不能为空"
        for permission in capability["permissions"]:
            assert "*" not in permission, f"{name} capability 不得使用通配权限: {permission}"
            assert not permission.startswith(dangerous_prefixes), (
                f"{name} capability 不得宽开危险插件权限: {permission}"
            )
