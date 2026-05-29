from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_TAURI = ROOT / "apps" / "desktop" / "src-tauri"
CAPABILITIES_DIR = SRC_TAURI / "capabilities"
PERMISSIONS_DIR = SRC_TAURI / "permissions"
COMMAND_CATALOG = SRC_TAURI / "src" / "command_catalog.rs"
LIB_RS = SRC_TAURI / "src" / "lib.rs"

DANGEROUS_PERMISSION_PREFIXES = ("shell:", "fs:", "opener:", "http:", "clipboard:")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registered_commands() -> set[str]:
    text = COMMAND_CATALOG.read_text(encoding="utf-8")
    match = re.search(r"REGISTERED_COMMANDS:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];", text, re.S)
    assert match, "REGISTERED_COMMANDS 常量必须存在"
    return set(re.findall(r'"([a-zA-Z0-9_]+)"', match.group("body")))


def _tauri_commands() -> set[str]:
    text = LIB_RS.read_text(encoding="utf-8")
    return set(re.findall(r"#\[tauri::command\]\s*(?:pub\s+)?fn\s+([a-zA-Z0-9_]+)", text))


def _permission_commands() -> dict[str, set[str]]:
    permissions: dict[str, set[str]] = {}
    for path in PERMISSIONS_DIR.glob("*.toml"):
        text = path.read_text(encoding="utf-8")
        identifiers = re.findall(r'identifier\s*=\s*"([^"]+)"', text)
        allow_blocks = re.findall(r"commands\.allow\s*=\s*\[(.*?)\]", text, re.S)
        assert len(identifiers) == len(allow_blocks) == 1, f"{path} 必须只声明一个 permission 和 commands.allow"
        commands = set(re.findall(r'"([a-zA-Z0-9_]+)"', allow_blocks[0]))
        assert commands, f"{path} 的 commands.allow 不能为空"
        assert "commands.deny" not in text, f"{path} 不应声明额外 deny 占位"
        permissions[identifiers[0]] = commands
    return permissions


def _capabilities() -> dict[str, dict]:
    return {path.stem: _read_json(path) for path in CAPABILITIES_DIR.glob("*.json")}


def test_capability_files_exist_and_match_tauri_config() -> None:
    expected = {"main", "pet", "settings", "diagnostics"}
    capabilities = _capabilities()
    assert set(capabilities) == expected

    config = _read_json(SRC_TAURI / "tauri.conf.json")
    configured = set(config["app"]["security"]["capabilities"])
    assert configured == expected


def test_tauri_build_uses_frontend_dist_outside_src_tauri() -> None:
    config = _read_json(SRC_TAURI / "tauri.conf.json")
    frontend_dist = config["build"]["frontendDist"]
    assert frontend_dist == "../frontend/dist"
    assert not frontend_dist.startswith("dist")


def test_registered_commands_match_tauri_command_functions_and_permissions() -> None:
    registered = _registered_commands()
    assert registered, "REGISTERED_COMMANDS 不能为空"
    assert registered == _tauri_commands()

    permissions = _permission_commands()
    allowed = set().union(*permissions.values())
    assert allowed == registered


def test_capability_permissions_are_minimal_and_not_dangerous() -> None:
    capabilities = _capabilities()
    permissions = _permission_commands()

    for name, capability in capabilities.items():
        assert capability["identifier"] == name
        assert capability["windows"] == [name]
        assert capability["permissions"], f"{name} capability permissions 不能为空"
        for permission in capability["permissions"]:
            assert not permission.startswith(DANGEROUS_PERMISSION_PREFIXES), (
                f"{name} 不得宽开危险插件权限: {permission}"
            )
            assert "*" not in permission, f"{name} capability 不得使用通配权限: {permission}"

    pet_commands = set()
    for permission in capabilities["pet"]["permissions"]:
        pet_commands.update(permissions.get(permission, set()))
    assert pet_commands == {"sidecar_cancel", "chat_send"}

    forbidden_for_pet = {"config_get_all", "logs_query", "sidecar_shutdown", "sidecar_hello", "sidecar_health"}
    assert pet_commands.isdisjoint(forbidden_for_pet)


def test_security_classification_covers_every_command() -> None:
    text = COMMAND_CATALOG.read_text(encoding="utf-8")
    classified_match = re.search(
        r"SECURITY_CLASSIFIED_COMMANDS:\s*&\[\(&str,\s*&str\)\]\s*=\s*&\[(?P<body>.*?)\];",
        text,
        re.S,
    )
    assert classified_match, "SECURITY_CLASSIFIED_COMMANDS 常量必须存在"
    classified = set(re.findall(r'\("([a-zA-Z0-9_]+)",\s*"[^"]+"\)', classified_match.group("body")))
    assert classified == _registered_commands()


def test_no_shell_or_file_plugin_dependency_is_enabled() -> None:
    config = _read_json(SRC_TAURI / "tauri.conf.json")
    text = json.dumps(config, ensure_ascii=False)
    assert "tauri-plugin-shell" not in text
    assert "tauri-plugin-fs" not in text
    assert "tauri-plugin-opener" not in text
    assert "tauri-plugin-http" not in text
    assert "tauri-plugin-clipboard" not in text


def test_tauri_csp_is_not_disabled() -> None:
    config = _read_json(SRC_TAURI / "tauri.conf.json")
    csp = config["app"]["security"].get("csp")
    assert isinstance(csp, str)
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
