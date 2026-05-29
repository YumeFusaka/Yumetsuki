from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_final_capabilities_match_build import capability_manifest_hash


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_final_capabilities_match_build.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_array(values: list[str]) -> str:
    return ", ".join(f'"{value}"' for value in values)


def _catalog(registered: list[str], pet_allowed: list[str] | None = None, security: list[str] | None = None) -> str:
    security = security or registered
    classes = ",\n".join(f'    ("{command}", "test.class")' for command in security)
    return "\n".join(
        [
            f"pub const REGISTERED_COMMANDS: &[&str] = &[{_json_array(registered)}];",
            f"pub const PET_ALLOWED_COMMANDS: &[&str] = &[{_json_array(pet_allowed or [])}];",
            "pub const SECURITY_CLASSIFIED_COMMANDS: &[(&str, &str)] = &[",
            classes,
            "];",
            "",
        ]
    )


def _lib_rs(defined: list[str], handler: list[str]) -> str:
    functions = "\n".join(f"#[tauri::command]\nfn {command}() {{}}\n" for command in defined)
    handlers = ",\n            ".join(handler)
    return (
        functions
        + "\npub fn run() {\n"
        + "    tauri::Builder::default()\n"
        + "        .invoke_handler(tauri::generate_handler![\n"
        + f"            {handlers}\n"
        + "        ]);\n"
        + "}\n"
    )


def _make_fixture(
    tmp_path: Path,
    *,
    registered: list[str] | None = None,
    defined: list[str] | None = None,
    handler: list[str] | None = None,
    permission_allow: list[str] | None = None,
    security: list[str] | None = None,
) -> tuple[Path, Path]:
    registered = registered or ["sidecar_hello"]
    defined = defined or registered
    handler = handler or registered
    permission_allow = permission_allow or registered

    tauri_root = tmp_path / "src-tauri"
    capability = {
        "$schema": "../gen/schemas/desktop-schema.json",
        "identifier": "main",
        "windows": ["main"],
        "permissions": ["core:app:default", "sidecar-lifecycle"],
    }
    tauri_conf = {
        "build": {"frontendDist": "../frontend/dist"},
        "app": {
            "windows": [{"label": "main"}],
            "security": {"capabilities": ["main"], "csp": "default-src 'self'"},
        },
    }
    _write(tauri_root / "capabilities" / "main.json", json.dumps(capability, ensure_ascii=False))
    _write(tauri_root / "tauri.conf.json", json.dumps(tauri_conf, ensure_ascii=False))
    _write(tauri_root / "src" / "command_catalog.rs", _catalog(registered, security=security))
    _write(tauri_root / "src" / "lib.rs", _lib_rs(defined, handler))
    _write(
        tauri_root / "permissions" / "sidecar-lifecycle.toml",
        "\n".join(
            [
                '[[permission]]',
                'identifier = "sidecar-lifecycle"',
                'description = "test permission"',
                f"commands.allow = [{_json_array(permission_allow)}]",
                "",
            ]
        ),
    )

    bundle = tmp_path / "bundle"
    shutil.copytree(tauri_root / "capabilities", bundle / "capabilities")
    cap_hash = capability_manifest_hash(
        tauri_root / "capabilities",
        tauri_root / "tauri.conf.json",
        tauri_root / "src" / "command_catalog.rs",
        tauri_root / "src" / "lib.rs",
        tauri_root / "permissions",
    )
    manifest = {
        "artifact_hashes": {"capability_manifest": cap_hash},
        "build_inputs": {"capability_manifest_hash": cap_hash},
    }
    _write(bundle / "release_manifest.json", json.dumps(manifest, ensure_ascii=False))
    return tauri_root, bundle


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_final_capabilities_accepts_matching_source_and_bundle(tmp_path: Path) -> None:
    tauri_root, bundle = _make_fixture(tmp_path)

    result = _run("--bundle", str(bundle), "--tauri-root", str(tauri_root))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "capability 构建一致性检查通过" in result.stdout


def test_final_capabilities_rejects_hash_drift(tmp_path: Path) -> None:
    tauri_root, bundle = _make_fixture(tmp_path)
    manifest_path = bundle / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_hashes"]["capability_manifest"] = "sha256:" + "b" * 64
    manifest["build_inputs"]["capability_manifest_hash"] = "sha256:" + "b" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run("--bundle", str(bundle), "--tauri-root", str(tauri_root))

    assert result.returncode == 1
    assert "capability manifest hash 不匹配" in result.stderr


def test_final_capabilities_rejects_unregistered_permission_command(tmp_path: Path) -> None:
    tauri_root, bundle = _make_fixture(tmp_path, permission_allow=["sidecar_hello", "extra_command"])

    result = _run("--bundle", str(bundle), "--tauri-root", str(tauri_root))

    assert result.returncode == 1
    assert "未注册 command" in result.stderr


def test_final_capabilities_rejects_tauri_command_not_in_catalog(tmp_path: Path) -> None:
    tauri_root, bundle = _make_fixture(
        tmp_path,
        defined=["sidecar_hello", "extra_command"],
        handler=["sidecar_hello", "extra_command"],
    )

    result = _run("--bundle", str(bundle), "--tauri-root", str(tauri_root))

    assert result.returncode == 1
    assert "REGISTERED_COMMANDS 与 #[tauri::command] 定义不一致" in result.stderr
