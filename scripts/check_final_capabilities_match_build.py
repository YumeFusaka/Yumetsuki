from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


class CapabilityCheckError(ValueError):
    pass


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAURI_ROOT = ROOT / "apps" / "desktop" / "src-tauri"
DANGEROUS_PERMISSION_PREFIXES = ("shell:", "fs:", "opener:", "http:", "clipboard:")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise CapabilityCheckError(f"{label} 缺失: {path}")


def _require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise CapabilityCheckError(f"{label} 缺失: {path}")


def _hash_files(files: list[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for label, path in sorted(files, key=lambda item: item[0]):
        _require_file(path, label)
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _hash_capability_dir(capability_dir: Path) -> str:
    _require_dir(capability_dir, "capability 目录")
    files = [
        (path.relative_to(capability_dir).as_posix(), path)
        for path in capability_dir.rglob("*.json")
        if path.is_file()
    ]
    if not files:
        raise CapabilityCheckError(f"capability 文件缺失: {capability_dir}")
    return _hash_files(files)


def capability_manifest_hash(
    capability_dir: Path,
    tauri_conf: Path | None = None,
    command_catalog: Path | None = None,
    lib_rs: Path | None = None,
    permissions_dir: Path | None = None,
) -> str:
    """Hash the exact inputs that define Tauri command exposure."""
    tauri_root = DEFAULT_TAURI_ROOT
    tauri_conf = tauri_conf or tauri_root / "tauri.conf.json"
    command_catalog = command_catalog or tauri_root / "src" / "command_catalog.rs"
    lib_rs = lib_rs or tauri_root / "src" / "lib.rs"
    permissions_dir = permissions_dir or tauri_root / "permissions"

    _require_dir(capability_dir, "capability 目录")
    _require_dir(permissions_dir, "permission 目录")

    files: list[tuple[str, Path]] = [
        ("tauri.conf.json", tauri_conf),
        ("src/command_catalog.rs", command_catalog),
        ("src/lib.rs", lib_rs),
    ]
    capability_files = sorted(path for path in capability_dir.rglob("*.json") if path.is_file())
    if not capability_files:
        raise CapabilityCheckError(f"capability 文件缺失: {capability_dir}")
    files.extend(
        (f"capabilities/{path.relative_to(capability_dir).as_posix()}", path)
        for path in capability_files
    )
    permission_files = sorted(path for path in permissions_dir.rglob("*.toml") if path.is_file())
    if not permission_files:
        raise CapabilityCheckError(f"permission 文件缺失: {permissions_dir}")
    files.extend(
        (f"permissions/{path.relative_to(permissions_dir).as_posix()}", path)
        for path in permission_files
    )
    return _hash_files(files)


def _load_manifest(bundle: Path) -> dict:
    path = bundle / "release_manifest.json"
    if not path.is_file():
        raise CapabilityCheckError(f"release_manifest.json 缺失: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapabilityCheckError(f"release_manifest.json 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CapabilityCheckError("release_manifest.json 根对象必须是 object")
    return payload


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    _require_file(path, label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapabilityCheckError(f"{label} 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CapabilityCheckError(f"{label} 根对象必须是 object")
    return payload


def _extract_string_array(text: str, name: str) -> set[str]:
    match = re.search(rf"{re.escape(name)}:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];", text, re.S)
    if not match:
        raise CapabilityCheckError(f"{name} 常量缺失")
    return set(re.findall(r'"([a-zA-Z0-9_]+)"', match.group("body")))


def _extract_security_classified(text: str) -> set[str]:
    match = re.search(
        r"SECURITY_CLASSIFIED_COMMANDS:\s*&\[\(&str,\s*&str\)\]\s*=\s*&\[(?P<body>.*?)\];",
        text,
        re.S,
    )
    if not match:
        raise CapabilityCheckError("SECURITY_CLASSIFIED_COMMANDS 常量缺失")
    return set(re.findall(r'\("([a-zA-Z0-9_]+)",\s*"[^"]+"\)', match.group("body")))


def _tauri_command_defs(text: str) -> set[str]:
    return set(re.findall(r"#\[tauri::command\]\s*(?:pub\s+)?fn\s+([a-zA-Z0-9_]+)", text))


def _invoke_handler_commands(text: str) -> set[str]:
    match = re.search(r"invoke_handler\s*\(\s*tauri::generate_handler!\s*\[(?P<body>.*?)\]\s*\)", text, re.S)
    if not match:
        raise CapabilityCheckError("invoke_handler(generate_handler![...]) 缺失")
    return set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", match.group("body")))


def _load_capabilities(capability_dir: Path) -> dict[str, dict[str, Any]]:
    _require_dir(capability_dir, "capability 目录")
    capabilities: dict[str, dict[str, Any]] = {}
    for path in sorted(capability_dir.glob("*.json")):
        capabilities[path.stem] = _read_json_object(path, f"capability {path.name}")
    if not capabilities:
        raise CapabilityCheckError(f"capability 文件缺失: {capability_dir}")
    return capabilities


def _load_permissions(permissions_dir: Path) -> dict[str, dict[str, Any]]:
    _require_dir(permissions_dir, "permission 目录")
    permissions: dict[str, dict[str, Any]] = {}
    for path in sorted(permissions_dir.rglob("*.toml")):
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^\s*\[\[permission\]\]\s*$", text)
        blocks = [part for part in parts[1:] if part.strip()]
        if not blocks:
            raise CapabilityCheckError(f"{path} 必须包含 [[permission]]")
        for block in blocks:
            identifier_match = re.search(r'(?m)^\s*identifier\s*=\s*"([^"]+)"\s*$', block)
            if identifier_match is None:
                raise CapabilityCheckError(f"{path} permission.identifier 缺失")
            identifier = identifier_match.group(1)
            if identifier in permissions:
                raise CapabilityCheckError(f"permission identifier 重复: {identifier}")
            allow_match = re.search(r"(?ms)^\s*commands\.allow\s*=\s*\[(.*?)\]\s*$", block)
            deny_match = re.search(r"(?ms)^\s*commands\.deny\s*=\s*\[(.*?)\]\s*$", block)
            allow = re.findall(r'"([a-zA-Z0-9_]+)"', allow_match.group(1)) if allow_match else []
            deny = re.findall(r'"([a-zA-Z0-9_]+)"', deny_match.group(1)) if deny_match else []
            permissions[identifier] = {
                "allow": set(allow),
                "deny": set(deny),
                "source": path,
            }
    if not permissions:
        raise CapabilityCheckError(f"permission 文件缺失: {permissions_dir}")
    return permissions


def _format_set(values: set[str]) -> str:
    return ", ".join(sorted(values)) if values else "<empty>"


def validate_capability_semantics(
    capability_dir: Path,
    tauri_conf: Path,
    command_catalog: Path,
    lib_rs: Path,
    permissions_dir: Path,
) -> None:
    errors: list[str] = []
    config = _read_json_object(tauri_conf, "tauri.conf.json")
    catalog_text = command_catalog.read_text(encoding="utf-8")
    lib_text = lib_rs.read_text(encoding="utf-8")

    registered = _extract_string_array(catalog_text, "REGISTERED_COMMANDS")
    pet_allowed = _extract_string_array(catalog_text, "PET_ALLOWED_COMMANDS")
    security_classified = _extract_security_classified(catalog_text)
    command_defs = _tauri_command_defs(lib_text)
    invoke_commands = _invoke_handler_commands(lib_text)
    capabilities = _load_capabilities(capability_dir)
    permissions = _load_permissions(permissions_dir)

    app = config.get("app")
    security = app.get("security") if isinstance(app, dict) else None
    configured_capabilities = security.get("capabilities") if isinstance(security, dict) else None
    if not isinstance(configured_capabilities, list) or not all(isinstance(item, str) for item in configured_capabilities):
        errors.append("tauri.conf.json app.security.capabilities 必须是字符串数组")
        configured_set: set[str] = set()
    else:
        configured_set = set(configured_capabilities)

    windows = app.get("windows") if isinstance(app, dict) else None
    window_labels = {window.get("label") for window in windows if isinstance(window, dict)} if isinstance(windows, list) else set()
    window_labels = {label for label in window_labels if isinstance(label, str)}

    if registered != command_defs:
        errors.append(
            "REGISTERED_COMMANDS 与 #[tauri::command] 定义不一致: "
            f"missing_defs={_format_set(registered - command_defs)} extra_defs={_format_set(command_defs - registered)}"
        )
    if registered != invoke_commands:
        errors.append(
            "REGISTERED_COMMANDS 与 invoke_handler 注册不一致: "
            f"missing_handler={_format_set(registered - invoke_commands)} extra_handler={_format_set(invoke_commands - registered)}"
        )
    if registered != security_classified:
        errors.append(
            "SECURITY_CLASSIFIED_COMMANDS 未覆盖全部注册命令: "
            f"missing={_format_set(registered - security_classified)} extra={_format_set(security_classified - registered)}"
        )

    if set(capabilities) != configured_set:
        errors.append(
            "capability 文件集合与 tauri.conf.json app.security.capabilities 不一致: "
            f"files={_format_set(set(capabilities))} config={_format_set(configured_set)}"
        )

    permission_command_union: set[str] = set()
    pet_commands: set[str] = set()
    for name, capability in capabilities.items():
        if capability.get("identifier") != name:
            errors.append(f"{name}.json identifier 必须等于文件名")
        cap_windows = capability.get("windows")
        if not isinstance(cap_windows, list) or not all(isinstance(item, str) for item in cap_windows):
            errors.append(f"{name}.json windows 必须是字符串数组")
            cap_windows = []
        for window in cap_windows:
            if window not in window_labels:
                errors.append(f"{name}.json 引用了未配置窗口: {window}")
        cap_permissions = capability.get("permissions")
        if not isinstance(cap_permissions, list) or not cap_permissions:
            errors.append(f"{name}.json permissions 必须是非空数组")
            continue
        for permission in cap_permissions:
            if not isinstance(permission, str):
                errors.append(f"{name}.json permissions 只能包含字符串")
                continue
            if "*" in permission:
                errors.append(f"{name}.json 不得使用通配 permission: {permission}")
            if permission.startswith(DANGEROUS_PERMISSION_PREFIXES):
                errors.append(f"{name}.json 不得宽开危险插件 permission: {permission}")
            if permission.startswith("core:"):
                continue
            if permission.startswith(("allow-", "deny-")):
                errors.append(f"{name}.json 不得直接引用 autogenerated permission: {permission}")
            permission_record = permissions.get(permission)
            if permission_record is None:
                errors.append(f"{name}.json 引用了不存在的 permission: {permission}")
                continue
            allowed_commands = set(permission_record["allow"])
            denied_commands = set(permission_record["deny"])
            if denied_commands:
                errors.append(f"{permission} 被 capability 引用时不得声明 commands.deny")
            if not allowed_commands:
                errors.append(f"{permission} 被 capability 引用时 commands.allow 不能为空")
            unknown = allowed_commands - registered
            if unknown:
                errors.append(f"{permission} capability allowlist 包含未注册 command: {_format_set(unknown)}")
            permission_command_union.update(allowed_commands)
            if name == "pet":
                pet_commands.update(allowed_commands)

    for identifier, record in permissions.items():
        unknown_allowed = set(record["allow"]) - registered
        unknown_denied = set(record["deny"]) - registered
        if unknown_allowed:
            errors.append(f"{identifier}.commands.allow 包含未注册 command: {_format_set(unknown_allowed)}")
        if unknown_denied:
            errors.append(f"{identifier}.commands.deny 包含未注册 command: {_format_set(unknown_denied)}")

    if permission_command_union != registered:
        errors.append(
            "capability permission allowlist 未覆盖注册命令或包含多余命令: "
            f"missing={_format_set(registered - permission_command_union)} "
            f"extra={_format_set(permission_command_union - registered)}"
        )
    if "pet" in capabilities and pet_commands != pet_allowed:
        errors.append(
            "pet capability 命令与 PET_ALLOWED_COMMANDS 不一致: "
            f"pet={_format_set(pet_commands)} catalog={_format_set(pet_allowed)}"
        )

    if errors:
        raise CapabilityCheckError("\n".join(errors))


def _resolve_source_paths(
    tauri_root: Path,
    capabilities: Path | None,
    tauri_conf: Path | None,
    command_catalog: Path | None,
    lib_rs: Path | None,
    permissions: Path | None,
) -> tuple[Path, Path, Path, Path, Path]:
    return (
        capabilities or tauri_root / "capabilities",
        tauri_conf or tauri_root / "tauri.conf.json",
        command_catalog or tauri_root / "src" / "command_catalog.rs",
        lib_rs or tauri_root / "src" / "lib.rs",
        permissions or tauri_root / "permissions",
    )


def check_capabilities(
    bundle: Path,
    capability_dir: Path | None,
    tauri_root: Path,
    tauri_conf: Path | None,
    command_catalog: Path | None,
    lib_rs: Path | None,
    permissions: Path | None,
) -> None:
    manifest = _load_manifest(bundle)
    expected = manifest.get("artifact_hashes", {}).get("capability_manifest")
    if not expected:
        raise CapabilityCheckError("artifact_hashes.capability_manifest 缺失")

    build_input_hash = manifest.get("build_inputs", {}).get("capability_manifest_hash")
    if build_input_hash and build_input_hash != expected:
        raise CapabilityCheckError("build_inputs.capability_manifest_hash 与 artifact_hashes.capability_manifest 不一致")

    source_capabilities, source_tauri_conf, source_command_catalog, source_lib_rs, source_permissions = _resolve_source_paths(
        tauri_root,
        capability_dir,
        tauri_conf,
        command_catalog,
        lib_rs,
        permissions,
    )

    source_hash = capability_manifest_hash(
        source_capabilities,
        source_tauri_conf,
        source_command_catalog,
        source_lib_rs,
        source_permissions,
    )
    if source_hash != expected:
        raise CapabilityCheckError(f"capability manifest hash 不匹配: {source_hash} != {expected}")

    bundle_capabilities = bundle / "capabilities"
    if bundle_capabilities.is_dir():
        source_capability_files_hash = _hash_capability_dir(source_capabilities)
        bundle_capability_files_hash = _hash_capability_dir(bundle_capabilities)
        if source_capability_files_hash != bundle_capability_files_hash:
            raise CapabilityCheckError("bundle/capabilities 与最终审核 capability 文件不一致")
        bundle_hash = capability_manifest_hash(
            bundle_capabilities,
            source_tauri_conf,
            source_command_catalog,
            source_lib_rs,
            source_permissions,
        )
        if bundle_hash != expected:
            raise CapabilityCheckError(f"bundle capability manifest hash 不匹配: {bundle_hash} != {expected}")

    validate_capability_semantics(
        source_capabilities,
        source_tauri_conf,
        source_command_catalog,
        source_lib_rs,
        source_permissions,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验最终构建 capability 与 manifest 一致")
    parser.add_argument("--bundle", type=Path, default=Path("apps/desktop/src-tauri/target/release/bundle"))
    parser.add_argument("--capabilities", type=Path)
    parser.add_argument("--tauri-root", type=Path, default=DEFAULT_TAURI_ROOT)
    parser.add_argument("--tauri-conf", type=Path)
    parser.add_argument("--command-catalog", type=Path)
    parser.add_argument("--lib-rs", type=Path)
    parser.add_argument("--permissions", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    if not args.bundle.exists():
        if args.allow_missing:
            print(f"bundle 不存在，按 --allow-missing 跳过: {args.bundle}")
            return 0
        print(f"bundle 不存在: {args.bundle}", file=sys.stderr)
        return 1

    try:
        check_capabilities(
            args.bundle,
            args.capabilities,
            args.tauri_root,
            args.tauri_conf,
            args.command_catalog,
            args.lib_rs,
            args.permissions,
        )
    except CapabilityCheckError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("capability 构建一致性检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
