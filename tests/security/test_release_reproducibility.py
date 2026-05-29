import json
import os
import subprocess
import sys
from pathlib import Path

from tests.security.test_release_manifest import create_fake_bundle


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_release_reproducibility.py"


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


def test_release_reproducibility_accepts_matching_locks_and_artifacts(tmp_path):
    bundle = create_fake_bundle(tmp_path)

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "可复现性检查通过" in result.stdout


def test_release_reproducibility_rejects_lockfile_hash_drift(tmp_path):
    bundle = create_fake_bundle(tmp_path)
    (bundle / "requirements-sidecar.txt").write_text("pydantic==2.1.0\n", encoding="utf-8")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "requirements-sidecar.txt hash 不匹配" in result.stderr


def test_release_reproducibility_rejects_missing_toolchain_version(tmp_path):
    bundle = create_fake_bundle(tmp_path)
    manifest_path = bundle / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["build_inputs"].pop("tauri_version")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "build_inputs.tauri_version 缺失" in result.stderr
