import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_perf_budgets.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def test_perf_budgets_accepts_results_within_budget(tmp_path):
    budgets = tmp_path / "budgets.json"
    results = tmp_path / "results.json"
    metrics = {
        "cold_startup_ms": 1200,
        "warm_startup_ms": 800,
        "sidecar_hello_ms": 500,
        "idle_cpu_percent": 0.5,
        "sidecar_memory_mib": 120,
        "chat_first_token_ms": 90,
        "tts_first_segment_ms": 140,
        "logs_10k_fps": 55,
        "frontend_bundle_size_bytes": 4_000_000,
        "sidecar_artifact_size_bytes": 16_000_000,
        "resource_size_bytes": 1_000_000,
        "installer_size_bytes": 80_000_000,
        "bundle_size_bytes": 120_000_000,
    }
    _write_json(
        budgets,
        {
            "metrics": {
                "cold_startup_ms": {"max": 3000},
                "warm_startup_ms": {"max": 1500},
                "sidecar_hello_ms": {"max": 10000},
                "idle_cpu_percent": {"max": 2},
                "sidecar_memory_mib": {"max": 500},
                "chat_first_token_ms": {"max": 300},
                "tts_first_segment_ms": {"max": 500},
                "logs_10k_fps": {"min": 30},
                "frontend_bundle_size_bytes": {"max": 10_000_000},
                "sidecar_artifact_size_bytes": {"max": 100_000_000},
                "resource_size_bytes": {"max": 50_000_000},
                "installer_size_bytes": {"max": 200_000_000},
                "bundle_size_bytes": {"max": 250_000_000},
            }
        },
    )
    _write_json(
        results,
        {
            "generated_by": {
                "manual": False,
                "sources": ["e2e:startup", "e2e:stress", "diagnostics_perf", "release_scan"],
                "commands": ["npm run e2e:startup", "npm run e2e:stress", "python scripts/check_release_manifest.py"],
            },
            "metrics": metrics,
        },
    )

    result = run_script("--budgets", str(budgets), "--results", str(results))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "性能预算检查通过" in result.stdout


def test_perf_budgets_rejects_zero_budget(tmp_path):
    budgets = tmp_path / "budgets.json"
    results = tmp_path / "results.json"
    _write_json(budgets, {"metrics": {"cold_startup_ms": {"max": 0}}})
    _write_json(results, {"metrics": {"cold_startup_ms": 1}})

    result = run_script("--budgets", str(budgets), "--results", str(results))

    assert result.returncode == 1
    assert "cold_startup_ms.max 必须是正数" in result.stderr


def test_perf_budgets_rejects_over_budget_result(tmp_path):
    budgets = tmp_path / "budgets.json"
    results = tmp_path / "results.json"
    _write_json(budgets, {"metrics": {"cold_startup_ms": {"max": 3000}, "logs_10k_fps": {"min": 30}}})
    _write_json(results, {"metrics": {"cold_startup_ms": 3500, "logs_10k_fps": 25}})

    result = run_script("--budgets", str(budgets), "--results", str(results))

    assert result.returncode == 1
    assert "cold_startup_ms 超出预算" in result.stderr
    assert "logs_10k_fps 低于预算" in result.stderr


def test_perf_budgets_rejects_missing_result_sources(tmp_path):
    budgets = tmp_path / "budgets.json"
    results = tmp_path / "results.json"
    _write_json(
        budgets,
        {
            "metrics": {
                "cold_startup_ms": {"max": 3000},
                "warm_startup_ms": {"max": 1500},
                "sidecar_hello_ms": {"max": 10000},
                "idle_cpu_percent": {"max": 2},
                "sidecar_memory_mib": {"max": 500},
                "chat_first_token_ms": {"max": 300},
                "tts_first_segment_ms": {"max": 500},
                "logs_10k_fps": {"min": 30},
                "frontend_bundle_size_bytes": {"max": 10_000_000},
                "sidecar_artifact_size_bytes": {"max": 100_000_000},
                "resource_size_bytes": {"max": 50_000_000},
                "installer_size_bytes": {"max": 200_000_000},
                "bundle_size_bytes": {"max": 250_000_000},
            }
        },
    )
    _write_json(results, {"metrics": {metric: 1 for metric in [
        "cold_startup_ms",
        "warm_startup_ms",
        "sidecar_hello_ms",
        "idle_cpu_percent",
        "sidecar_memory_mib",
        "chat_first_token_ms",
        "tts_first_segment_ms",
        "logs_10k_fps",
        "frontend_bundle_size_bytes",
        "sidecar_artifact_size_bytes",
        "resource_size_bytes",
        "installer_size_bytes",
        "bundle_size_bytes",
    ]}})

    result = run_script("--budgets", str(budgets), "--results", str(results))

    assert result.returncode == 1
    assert "results.generated_by 必须记录性能结果来源" in result.stderr
