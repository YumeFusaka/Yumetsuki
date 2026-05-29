import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_release_forbidden_content.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def test_release_forbidden_content_accepts_clean_fake_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    _write(bundle / "resources" / "sidecar.txt", "sidecar")
    _write(bundle / "frontend" / "assets" / "app.js", "console.log('ok');")
    _write(bundle / "resources" / "defaults" / "api.example.yaml", "api_key: PLACEHOLDER\n")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "未发现禁止内容" in result.stdout


def test_release_forbidden_content_rejects_pyside6_and_legacy_ui(tmp_path):
    bundle = tmp_path / "bundle"
    _write(bundle / "PySide6" / "QtCore.pyd", "binary")
    _write(bundle / "ui" / "main.py", "from PySide6.QtWidgets import QApplication\n")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "pyside6" in result.stderr.lower()
    assert "legacy_ui" in result.stderr


def test_release_forbidden_content_rejects_runtime_data(tmp_path):
    bundle = tmp_path / "bundle"
    _write(bundle / "data" / "config" / "api.yaml", "api_key: sk-live-secret\n")
    _write(bundle / "data" / "logs" / "system" / "2026-05-29.jsonl", "{}\n")
    _write(bundle / "data" / "vision" / "screen_1.png", "fake image")
    _write(bundle / "data" / "models" / "stt" / "model.bin", "model")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "runtime_config" in result.stderr
    assert "runtime_log" in result.stderr
    assert "screenshot" in result.stderr
    assert "model_cache" in result.stderr


def test_release_forbidden_content_redacts_sensitive_snippet(tmp_path):
    bundle = tmp_path / "bundle"
    secret = "Bearer abcdefghijklmnopqrstuvwxyz123456"
    _write(bundle / "resources" / "diagnostic.txt", f"Authorization: {secret}\n")

    result = run_script("--bundle", str(bundle))

    assert result.returncode == 1
    assert "authorization_secret" in result.stderr
    assert secret not in result.stderr
    assert "<redacted>" in result.stderr
