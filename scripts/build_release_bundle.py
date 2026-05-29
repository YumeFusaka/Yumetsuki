from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from check_final_capabilities_match_build import capability_manifest_hash
except ImportError:
    from scripts.check_final_capabilities_match_build import capability_manifest_hash


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "apps" / "desktop" / "src-tauri" / "target" / "release" / "bundle"
TAURI_ROOT = ROOT / "apps" / "desktop" / "src-tauri"
FRONTEND_DIST = ROOT / "apps" / "desktop" / "frontend" / "dist"
CAPABILITY_DIR = TAURI_ROOT / "capabilities"
SIDECAR_EXE = TAURI_ROOT / "target" / "release" / "yumetsuki-desktop.exe"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def hash_directory(path: Path, pattern: str = "*") -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob(pattern) if item.is_file())
    if not files:
        raise SystemExit(f"目录没有可 hash 文件: {path}")
    for file_path in files:
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def size_tree(path: Path, exclude: Iterable[Path] = ()) -> int:
    excluded = {item.resolve() for item in exclude}
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file() and file_path.resolve() not in excluded:
            total += file_path.stat().st_size
    return total


def file_record(bundle: Path, path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(bundle).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def run_text(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def cargo_package_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^version\s*=\s*\"([^\"]+)\"", text)
    return match.group(1) if match else "0.0.0"


def cargo_lock_package_version(lock_path: Path, package_name: str) -> str:
    text = lock_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\[\[package\]\]\s+name\s*=\s*\"" + re.escape(package_name) + r"\"\s+version\s*=\s*\"([^\"]+)\"", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1) if match else "unknown"


def git_commit() -> str:
    value = run_text(["git", "rev-parse", "HEAD"])
    if re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    return "0" * 40


def source_tree_status() -> str:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "dirty"
    return "clean" if completed.stdout.strip() == "" else "dirty"


def rust_host_triple() -> str:
    output = run_text(["rustc", "-vV"])
    match = re.search(r"(?m)^host:\s*(\S+)", output)
    if match:
        return match.group(1)
    return f"{platform.machine().lower()}-pc-windows-msvc" if os.name == "nt" else platform.platform()


def read_budget_max(metric: str, fallback: int) -> int:
    path = ROOT / "apps" / "desktop" / "perf" / "budgets.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload["metrics"][metric]["max"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return fallback
    return int(value)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"{label} 缺失: {path}")


def require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SystemExit(f"{label} 缺失: {path}")


def reset_bundle(bundle: Path) -> None:
    release_root = (TAURI_ROOT / "target" / "release").resolve()
    resolved = bundle.resolve()
    if resolved == release_root or release_root not in resolved.parents:
        raise SystemExit(f"拒绝清理 release target 外的目录: {bundle}")
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True, exist_ok=True)


def copy_inputs(bundle: Path, sidecar_exe: Path, frontend_dist: Path, capability_dir: Path) -> dict[str, Path]:
    resources = bundle / "resources"
    defaults = resources / "defaults"
    frontend = bundle / "frontend"
    capabilities = bundle / "capabilities"
    defaults.mkdir(parents=True, exist_ok=True)
    frontend.mkdir(parents=True, exist_ok=True)

    sidecar_target = resources / "sidecar.exe"
    shutil.copy2(sidecar_exe, sidecar_target)
    shutil.copytree(frontend_dist, frontend, dirs_exist_ok=True)
    shutil.copytree(capability_dir, capabilities, dirs_exist_ok=True)

    (defaults / "api.example.yaml").write_text(
        "provider: openai\nbase_url: https://api.example.invalid/v1\napi_key: PLACEHOLDER\n",
        encoding="utf-8",
    )
    (defaults / "mcp.example.yaml").write_text(
        "\n".join(
            [
                "servers:",
                "  - name: example-stdio",
                "    transport: stdio",
                "    command: python path/to/mcp_server.py",
                "    url: \"\"",
                "    enabled: false",
                "    connect_timeout_seconds: 10",
                "    request_timeout_seconds: 10",
                "    retry_attempts: 0",
                "  - name: example-sse",
                "    transport: sse",
                "    command: \"\"",
                "    url: https://mcp.example.invalid/mcp",
                "    enabled: false",
                "    connect_timeout_seconds: 10",
                "    request_timeout_seconds: 10",
                "    retry_attempts: 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    shutil.copy2(ROOT / "requirements-sidecar.txt", bundle / "requirements-sidecar.txt")
    shutil.copy2(ROOT / "apps" / "desktop" / "frontend" / "package-lock.json", bundle / "package-lock.json")
    shutil.copy2(TAURI_ROOT / "Cargo.lock", bundle / "Cargo.lock")
    return {
        "sidecar": sidecar_target,
        "frontend": frontend,
        "frontend_marker": frontend / "index.html",
        "capabilities": capabilities,
        "resources": resources,
    }


def build_manifest(bundle: Path, paths: dict[str, Path]) -> dict[str, object]:
    schema_path = ROOT / "schemas" / "release_manifest.schema.json"
    capability_hash = capability_manifest_hash(
        paths["capabilities"],
        TAURI_ROOT / "tauri.conf.json",
        TAURI_ROOT / "src" / "command_catalog.rs",
        TAURI_ROOT / "src" / "lib.rs",
        TAURI_ROOT / "permissions",
    )
    lockfiles = [
        bundle / "requirements-sidecar.txt",
        bundle / "package-lock.json",
        bundle / "Cargo.lock",
    ]
    capability_files = sorted(path for path in paths["capabilities"].rglob("*.json") if path.is_file())
    frontend_files = sorted(path for path in paths["frontend"].rglob("*") if path.is_file())
    artifacts = [paths["sidecar"], *frontend_files, *capability_files]
    frontend_size = size_tree(paths["frontend"])
    sidecar_size = paths["sidecar"].stat().st_size
    resources_size = size_tree(paths["resources"])
    bundle_size = size_tree(bundle)
    return {
        "app_version": cargo_package_version(TAURI_ROOT / "Cargo.toml"),
        "schema_hash": sha256_file(schema_path),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "target_triple": rust_host_triple(),
        "build_profile": "release",
        "build_inputs": {
            "git_commit": git_commit(),
            "source_tree_status": source_tree_status(),
            "python_version": platform.python_version(),
            "node_version": run_text(["node", "--version"]),
            "rust_version": run_text(["cargo", "--version"]),
            "tauri_version": cargo_lock_package_version(TAURI_ROOT / "Cargo.lock", "tauri"),
            "requirements_sidecar_hash": sha256_file(bundle / "requirements-sidecar.txt"),
            "node_lock_hash": sha256_file(bundle / "package-lock.json"),
            "cargo_lock_hash": sha256_file(bundle / "Cargo.lock"),
            "capability_manifest_hash": capability_hash,
        },
        "lockfiles": [file_record(bundle, path) for path in lockfiles],
        "artifacts": [file_record(bundle, path) for path in artifacts],
        "artifact_hashes": {
            "sidecar": sha256_file(paths["sidecar"]),
            "frontend_dist": hash_directory(paths["frontend"]),
            "capability_manifest": capability_hash,
        },
        "size_bytes": {
            "bundle": bundle_size,
            "sidecar": sidecar_size,
            "frontend": frontend_size,
            "resources": resources_size,
            "installer": max(1, sidecar_size),
        },
        "budgets": {
            "bundle_size_bytes": read_budget_max("bundle_size_bytes", 250_000_000),
            "sidecar_size_bytes": read_budget_max("sidecar_artifact_size_bytes", 100_000_000),
            "frontend_size_bytes": read_budget_max("frontend_bundle_size_bytes", 10_000_000),
        },
        "approval_records": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成可扫描的 Yumetsuki release bundle 和 manifest")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--sidecar-exe", type=Path, default=SIDECAR_EXE)
    parser.add_argument("--frontend-dist", type=Path, default=FRONTEND_DIST)
    parser.add_argument("--capabilities", type=Path, default=CAPABILITY_DIR)
    args = parser.parse_args()

    bundle = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
    sidecar_exe = args.sidecar_exe if args.sidecar_exe.is_absolute() else ROOT / args.sidecar_exe
    frontend_dist = args.frontend_dist if args.frontend_dist.is_absolute() else ROOT / args.frontend_dist
    capability_dir = args.capabilities if args.capabilities.is_absolute() else ROOT / args.capabilities
    require_file(sidecar_exe, "release sidecar artifact")
    require_dir(frontend_dist, "frontend dist")
    require_dir(capability_dir, "capability manifest")
    reset_bundle(bundle)
    copied = copy_inputs(bundle, sidecar_exe, frontend_dist, capability_dir)
    require_file(copied["frontend_marker"], "frontend index.html")
    manifest = build_manifest(bundle, copied)
    (bundle / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"release bundle 已生成: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
