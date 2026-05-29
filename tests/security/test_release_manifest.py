import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_release_manifest.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _schema_hash() -> str:
    return _sha256(REPO_ROOT / "schemas" / "release_manifest.schema.json")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bundle_size(bundle: Path) -> int:
    return sum(
        path.stat().st_size
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "release_manifest.json"
    )


def create_fake_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    _write(bundle / "resources" / "sidecar.exe", "sidecar-binary")
    _write(bundle / "frontend" / "assets" / "app.js", "console.log('ok');")
    _write(bundle / "resources" / "defaults" / "api.example.yaml", "api_key: PLACEHOLDER\n")
    _write(bundle / "capabilities" / "main.json", '{"identifier":"main","permissions":[]}\n')
    _write(bundle / "requirements-sidecar.txt", "pydantic==2.0.0\n")
    _write(bundle / "package-lock.json", '{"lockfileVersion":3}\n')
    _write(bundle / "Cargo.lock", "# cargo lock\n")

    lockfiles = [
        bundle / "requirements-sidecar.txt",
        bundle / "package-lock.json",
        bundle / "Cargo.lock",
    ]
    artifacts = [
        bundle / "resources" / "sidecar.exe",
        bundle / "frontend" / "assets" / "app.js",
        bundle / "capabilities" / "main.json",
    ]
    manifest = {
        "app_version": "0.1.0",
        "schema_hash": _schema_hash(),
        "generated_at": "2026-05-29T00:00:00Z",
        "target_triple": "x86_64-pc-windows-msvc",
        "build_profile": "release",
        "build_inputs": {
            "git_commit": "0" * 40,
            "source_tree_status": "clean",
            "python_version": "3.11.9",
            "node_version": "20.11.1",
            "rust_version": "1.78.0",
            "tauri_version": "2.0.0",
            "requirements_sidecar_hash": _sha256(bundle / "requirements-sidecar.txt"),
            "node_lock_hash": _sha256(bundle / "package-lock.json"),
            "cargo_lock_hash": _sha256(bundle / "Cargo.lock"),
            "capability_manifest_hash": _sha256(bundle / "capabilities" / "main.json"),
        },
        "lockfiles": [
            {
                "path": str(path.relative_to(bundle)).replace("\\", "/"),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in lockfiles
        ],
        "artifacts": [
            {
                "path": str(path.relative_to(bundle)).replace("\\", "/"),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in artifacts
        ],
        "artifact_hashes": {
            "sidecar": _sha256(bundle / "resources" / "sidecar.exe"),
            "frontend_dist": _sha256(bundle / "frontend" / "assets" / "app.js"),
            "capability_manifest": _sha256(bundle / "capabilities" / "main.json"),
        },
        "size_bytes": {
            "bundle": _bundle_size(bundle),
            "sidecar": (bundle / "resources" / "sidecar.exe").stat().st_size,
            "frontend": (bundle / "frontend" / "assets" / "app.js").stat().st_size,
            "resources": (bundle / "resources" / "defaults" / "api.example.yaml").stat().st_size,
            "installer": 1,
        },
        "budgets": {
            "bundle_size_bytes": _bundle_size(bundle) + 1024,
            "sidecar_size_bytes": 1024 * 1024,
            "frontend_size_bytes": 1024 * 1024,
        },
        "approval_records": [],
    }
    (bundle / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return bundle


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
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


def test_release_manifest_accepts_valid_fake_bundle(tmp_path):
    bundle = create_fake_bundle(tmp_path)

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "release manifest 检查通过" in result.stdout


def test_release_manifest_fails_when_bundle_missing(tmp_path):
    missing = tmp_path / "missing-bundle"

    result = run_script("--bundle", str(missing))

    assert result.returncode == 1
    assert "bundle 不存在" in result.stderr


def test_release_manifest_allows_missing_bundle_when_requested(tmp_path):
    missing = tmp_path / "missing-bundle"

    result = run_script("--bundle", str(missing), "--allow-missing")

    assert result.returncode == 0
    assert "跳过" in result.stdout


def test_release_manifest_rejects_zero_size_budget(tmp_path):
    bundle = create_fake_bundle(tmp_path)
    manifest_path = bundle / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["budgets"]["bundle_size_bytes"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "budgets.bundle_size_bytes 必须是正数" in result.stderr


def test_release_manifest_schema_rejects_extra_top_level_field(tmp_path):
    bundle = create_fake_bundle(tmp_path)
    manifest_path = bundle / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unexpected"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "未声明字段" in result.stderr
