from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from check_release_manifest import ManifestError, load_manifest, sha256_file, validate_manifest_schema
except ImportError:
    from scripts.check_release_manifest import ManifestError, load_manifest, sha256_file, validate_manifest_schema


LOCK_HASH_FIELDS = {
    "requirements-sidecar.txt": "requirements_sidecar_hash",
    "pnpm-lock.yaml": "node_lock_hash",
    "Cargo.lock": "cargo_lock_hash",
}
REQUIRED_LOCKFILES = set(LOCK_HASH_FIELDS)
REQUIRED_TOOLCHAIN_FIELDS = ["python_version", "node_version", "rust_version", "tauri_version"]


def _lock_records(manifest: dict) -> dict[str, dict]:
    return {record["path"].replace("\\", "/"): record for record in manifest.get("lockfiles", [])}


def check_reproducibility(bundle: Path) -> None:
    manifest = load_manifest(bundle)
    validate_manifest_schema(manifest)
    build_inputs = manifest["build_inputs"]
    for field in REQUIRED_TOOLCHAIN_FIELDS:
        if not build_inputs.get(field):
            raise ManifestError(f"build_inputs.{field} 缺失")

    records = _lock_records(manifest)
    for lock_path, field in LOCK_HASH_FIELDS.items():
        if lock_path not in records:
            raise ManifestError(f"{lock_path} 缺少 lockfile 记录")
        path = bundle / lock_path
        if not path.is_file():
            raise ManifestError(f"{lock_path} 缺失")
        actual = sha256_file(path)
        expected = build_inputs[field]
        if actual != expected or actual != records[lock_path]["sha256"]:
            raise ManifestError(f"{lock_path} hash 不匹配")

    for record in manifest.get("artifacts", []):
        path = bundle / record["path"]
        if not path.is_file():
            raise ManifestError(f"{record['path']} artifact 缺失")
        if sha256_file(path) != record["sha256"]:
            raise ManifestError(f"{record['path']} artifact hash 不匹配")

    capability_hash = manifest["artifact_hashes"]["capability_manifest"]
    if capability_hash != build_inputs["capability_manifest_hash"]:
        raise ManifestError("capability manifest hash 与 build_inputs 不一致")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验发布 artifact 可复现性")
    parser.add_argument("--bundle", type=Path, default=Path("apps/desktop/src-tauri/target/release/bundle"))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    if not args.bundle.exists():
        if args.allow_missing:
            print(f"bundle 不存在，按 --allow-missing 跳过: {args.bundle}")
            return 0
        print(f"bundle 不存在: {args.bundle}", file=sys.stderr)
        return 1
    try:
        check_reproducibility(args.bundle)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("可复现性检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
