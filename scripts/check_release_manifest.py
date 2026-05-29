from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from check_release_forbidden_content import scan_bundle
except ImportError:
    from scripts.check_release_forbidden_content import scan_bundle


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SCHEMA_PATH = Path("schemas/release_manifest.schema.json")
REQUIRED_TOP_LEVEL = [
    "app_version",
    "schema_hash",
    "generated_at",
    "target_triple",
    "build_profile",
    "build_inputs",
    "lockfiles",
    "artifacts",
    "artifact_hashes",
    "size_bytes",
    "budgets",
    "approval_records",
]
REQUIRED_BUILD_INPUTS = [
    "git_commit",
    "source_tree_status",
    "python_version",
    "node_version",
    "rust_version",
    "tauri_version",
    "requirements_sidecar_hash",
    "node_lock_hash",
    "cargo_lock_hash",
    "capability_manifest_hash",
]
REQUIRED_SIZES = ["bundle", "sidecar", "frontend", "resources", "installer"]
REQUIRED_BUDGETS = ["bundle_size_bytes", "sidecar_size_bytes", "frontend_size_bytes"]
REQUIRED_ARTIFACT_HASHES = ["sidecar", "frontend_dist", "capability_manifest"]


class ManifestError(ValueError):
    pass


def load_release_schema(path: Path | None = None) -> dict:
    schema_path = (path or SCHEMA_PATH)
    if not schema_path.is_absolute():
        schema_path = Path(__file__).resolve().parents[1] / schema_path
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"release manifest schema 不是合法 JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise ManifestError("release manifest schema 根对象必须是 object")
    return schema


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def bundle_size(bundle: Path) -> int:
    return sum(
        path.stat().st_size
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "release_manifest.json"
    )


def load_manifest(bundle: Path) -> dict:
    manifest_path = bundle / "release_manifest.json"
    if not manifest_path.is_file():
        raise ManifestError(f"release_manifest.json 缺失: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"release_manifest.json 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("release_manifest.json 根对象必须是 object")
    return payload


def _require_keys(payload: dict, keys: list[str], prefix: str) -> None:
    for key in keys:
        if key not in payload:
            raise ManifestError(f"{prefix}.{key} 缺失" if prefix else f"{key} 缺失")


def _require_hash(value: object, field: str) -> None:
    if not isinstance(value, str) or not HASH_RE.match(value):
        raise ManifestError(f"{field} 必须是 sha256:<64 hex>")


def _require_positive_int(value: object, field: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{field} 必须是正数")


def _validate_file_records(records: object, field: str) -> None:
    if not isinstance(records, list):
        raise ManifestError(f"{field} 必须是数组")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ManifestError(f"{field}[{index}] 必须是 object")
        _require_keys(record, ["path", "sha256", "size_bytes"], f"{field}[{index}]")
        if not isinstance(record["path"], str) or not record["path"]:
            raise ManifestError(f"{field}[{index}].path 必须是非空字符串")
        if Path(record["path"]).is_absolute() or ".." in Path(record["path"]).parts:
            raise ManifestError(f"{field}[{index}].path 必须是 bundle 相对路径")
        _require_hash(record["sha256"], f"{field}[{index}].sha256")
        _require_positive_int(record["size_bytes"], f"{field}[{index}].size_bytes")


def validate_manifest_schema(manifest: dict) -> None:
    validate_json_schema(manifest, load_release_schema())
    _require_keys(manifest, REQUIRED_TOP_LEVEL, "")
    if manifest["build_profile"] != "release":
        raise ManifestError("build_profile 必须是 release")
    _require_hash(manifest["schema_hash"], "schema_hash")
    actual_schema_hash = sha256_file((Path(__file__).resolve().parents[1] / SCHEMA_PATH))
    if manifest["schema_hash"] != actual_schema_hash:
        raise ManifestError("schema_hash 与 release manifest schema 不一致")

    build_inputs = manifest["build_inputs"]
    if not isinstance(build_inputs, dict):
        raise ManifestError("build_inputs 必须是 object")
    _require_keys(build_inputs, REQUIRED_BUILD_INPUTS, "build_inputs")
    for key in [
        "requirements_sidecar_hash",
        "node_lock_hash",
        "cargo_lock_hash",
        "capability_manifest_hash",
    ]:
        _require_hash(build_inputs[key], f"build_inputs.{key}")

    _validate_file_records(manifest["lockfiles"], "lockfiles")
    _validate_file_records(manifest["artifacts"], "artifacts")

    artifact_hashes = manifest["artifact_hashes"]
    if not isinstance(artifact_hashes, dict):
        raise ManifestError("artifact_hashes 必须是 object")
    _require_keys(artifact_hashes, REQUIRED_ARTIFACT_HASHES, "artifact_hashes")
    for key, value in artifact_hashes.items():
        _require_hash(value, f"artifact_hashes.{key}")

    size_bytes = manifest["size_bytes"]
    if not isinstance(size_bytes, dict):
        raise ManifestError("size_bytes 必须是 object")
    _require_keys(size_bytes, REQUIRED_SIZES, "size_bytes")
    for key, value in size_bytes.items():
        _require_positive_int(value, f"size_bytes.{key}")

    budgets = manifest["budgets"]
    if not isinstance(budgets, dict):
        raise ManifestError("budgets 必须是 object")
    _require_keys(budgets, REQUIRED_BUDGETS, "budgets")
    for key, value in budgets.items():
        _require_positive_int(value, f"budgets.{key}")

    approvals = manifest["approval_records"]
    if not isinstance(approvals, list):
        raise ManifestError("approval_records 必须是数组")
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            raise ManifestError(f"approval_records[{index}] 必须是 object")
        _require_keys(approval, ["scope", "reason", "approved_by", "approved_at"], f"approval_records[{index}]")
        combined = " ".join(str(approval[key]) for key in ["approved_by", "reason"])
        if re.search(r"(?i)(token|secret|cookie|authorization|api[_-]?key)", combined):
            raise ManifestError(f"approval_records[{index}] 包含疑似敏感字段")


def validate_json_schema(value: object, schema: dict, path: str = "") -> None:
    """Small local JSON schema subset used to keep the script tied to the checked-in schema."""
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref != "#/$defs/file_record":
            raise ManifestError(f"{path or '<root>'} 使用了未支持的 schema ref: {ref}")
        root_schema = load_release_schema()
        validate_json_schema(value, root_schema["$defs"]["file_record"], path)
        return

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ManifestError(f"{path or '<root>'} 必须是 object")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ManifestError(f"{path + '.' if path else ''}{key} 缺失")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise ManifestError(f"{path or '<root>'} 包含未声明字段: {sorted(extra)}")
        for key, item in value.items():
            child_schema = properties.get(key)
            additional = schema.get("additionalProperties")
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                validate_json_schema(item, child_schema, f"{path + '.' if path else ''}{key}")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise ManifestError(f"{path or '<root>'} 必须是数组")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_json_schema(item, item_schema, f"{path}[{index}]")
    elif expected_type == "string":
        if not isinstance(value, str):
            raise ManifestError(f"{path or '<root>'} 必须是字符串")
        if schema.get("minLength") and len(value) < int(schema["minLength"]):
            raise ManifestError(f"{path or '<root>'} 必须是非空字符串")
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, value):
            raise ManifestError(f"{path or '<root>'} 格式不匹配")
        if "enum" in schema and value not in schema["enum"]:
            raise ManifestError(f"{path or '<root>'} 取值不在允许范围")
        if "const" in schema and value != schema["const"]:
            raise ManifestError(f"{path or '<root>'} 必须是 {schema['const']}")
        if "not" in schema and isinstance(schema["not"], dict):
            blocked = schema["not"].get("pattern")
            if blocked and re.search(blocked, value):
                raise ManifestError(f"{path or '<root>'} 包含禁止内容")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ManifestError(f"{path or '<root>'} 必须是整数")
        minimum = schema.get("minimum")
        if minimum is not None and value < int(minimum):
            raise ManifestError(f"{path or '<root>'} 必须是正数")
    elif "const" in schema:
        if value != schema["const"]:
            raise ManifestError(f"{path or '<root>'} 必须是 {schema['const']}")


def validate_record_hashes(bundle: Path, records: list[dict], field: str) -> None:
    for record in records:
        path = bundle / record["path"]
        if not path.is_file():
            raise ManifestError(f"{field}.{record['path']} 缺失")
        actual_hash = sha256_file(path)
        if actual_hash != record["sha256"]:
            raise ManifestError(f"{record['path']} hash 不匹配")
        actual_size = path.stat().st_size
        if actual_size != record["size_bytes"]:
            raise ManifestError(f"{record['path']} size_bytes 不匹配")


def validate_budget(manifest: dict, bundle: Path) -> None:
    actual_bundle_size = bundle_size(bundle)
    declared = manifest["size_bytes"]
    if declared["bundle"] != actual_bundle_size:
        raise ManifestError("size_bytes.bundle 与 bundle 重算结果不一致")
    checks = [
        ("bundle", "bundle_size_bytes"),
        ("sidecar", "sidecar_size_bytes"),
        ("frontend", "frontend_size_bytes"),
    ]
    approved_scopes = {
        str(record.get("scope", ""))
        for record in manifest.get("approval_records", [])
        if isinstance(record, dict)
    }
    for size_key, budget_key in checks:
        actual = declared[size_key]
        budget = manifest["budgets"][budget_key]
        if actual > budget and budget_key not in approved_scopes:
            raise ManifestError(f"{size_key} 体积超出预算: {actual} > {budget}")


def validate_release_manifest(bundle: Path) -> dict:
    manifest = load_manifest(bundle)
    validate_manifest_schema(manifest)
    validate_record_hashes(bundle, manifest["lockfiles"], "lockfiles")
    validate_record_hashes(bundle, manifest["artifacts"], "artifacts")
    validate_budget(manifest, bundle)
    findings = scan_bundle(bundle)
    if findings:
        first = findings[0]
        raise ManifestError(f"发布包命中禁止内容: {first.rule_id} {first.path}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Yumetsuki release manifest")
    parser.add_argument("--bundle", type=Path, default=Path("apps/desktop/src-tauri/target/release/bundle"))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    bundle = args.bundle
    if not bundle.exists():
        if args.allow_missing:
            print(f"bundle 不存在，按 --allow-missing 跳过: {bundle}")
            return 0
        print(f"bundle 不存在: {bundle}", file=sys.stderr)
        return 1
    if not bundle.is_dir():
        print(f"bundle 不是目录: {bundle}", file=sys.stderr)
        return 1

    try:
        validate_release_manifest(bundle)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("release manifest 检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
