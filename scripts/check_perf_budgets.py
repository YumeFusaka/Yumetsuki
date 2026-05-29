from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_BUDGETS = Path("apps/desktop/perf/budgets.json")
DEFAULT_RESULTS = Path("apps/desktop/perf/results.json")
REQUIRED_METRICS = {
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
}
REQUIRED_RESULT_SOURCES = {
    "e2e:startup",
    "e2e:stress",
    "diagnostics_perf",
    "release_scan",
}


class PerfBudgetError(ValueError):
    pass


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise PerfBudgetError(f"{label} 缺失: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PerfBudgetError(f"{label} 不是合法 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PerfBudgetError(f"{label} 根对象必须是 object")
    return payload


def check_perf_budgets(budgets_path: Path, results_path: Path) -> None:
    budgets = _load_json(budgets_path, "budgets")
    results = _load_json(results_path, "results")
    budget_metrics = budgets.get("metrics")
    result_metrics = results.get("metrics")
    if not isinstance(budget_metrics, dict) or not budget_metrics:
        raise PerfBudgetError("budgets.metrics 必须是非空 object")
    if not isinstance(result_metrics, dict):
        raise PerfBudgetError("results.metrics 必须是 object")

    errors: list[str] = []
    missing_budget_metrics = REQUIRED_METRICS - set(budget_metrics)
    if missing_budget_metrics:
        errors.append(f"budgets.metrics 缺少必需指标: {', '.join(sorted(missing_budget_metrics))}")
    missing_result_metrics = REQUIRED_METRICS - set(result_metrics)
    if missing_result_metrics:
        errors.append(f"results.metrics 缺少必需指标: {', '.join(sorted(missing_result_metrics))}")
    sources = results.get("generated_by")
    if not isinstance(sources, dict):
        errors.append("results.generated_by 必须记录性能结果来源")
    else:
        source_names = set(sources.get("sources", [])) if isinstance(sources.get("sources"), list) else set()
        missing_sources = REQUIRED_RESULT_SOURCES - source_names
        if missing_sources:
            errors.append(f"results.generated_by.sources 缺少来源: {', '.join(sorted(missing_sources))}")
        commands = sources.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("results.generated_by.commands 必须是非空数组")
        if sources.get("manual") is True:
            errors.append("results.generated_by.manual 不得为 true")
    for metric, rule in budget_metrics.items():
        if not isinstance(rule, dict):
            errors.append(f"{metric} 预算规则必须是 object")
            continue
        if metric not in result_metrics:
            errors.append(f"{metric} 结果缺失")
            continue
        value = result_metrics[metric]
        if not isinstance(value, (int, float)):
            errors.append(f"{metric} 结果必须是数字")
            continue
        if "max" in rule:
            max_value = rule["max"]
            if not isinstance(max_value, (int, float)) or max_value <= 0:
                errors.append(f"{metric}.max 必须是正数")
            elif value > max_value:
                errors.append(f"{metric} 超出预算: {value} > {max_value}")
        if "min" in rule:
            min_value = rule["min"]
            if not isinstance(min_value, (int, float)) or min_value <= 0:
                errors.append(f"{metric}.min 必须是正数")
            elif value < min_value:
                errors.append(f"{metric} 低于预算: {value} < {min_value}")
        if "max" not in rule and "min" not in rule:
            errors.append(f"{metric} 必须配置 max 或 min")

    if errors:
        raise PerfBudgetError("\n".join(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Tauri 迁移性能预算")
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    if args.allow_missing and (not args.budgets.exists() or not args.results.exists()):
        print("性能预算输入缺失，按 --allow-missing 跳过")
        return 0
    try:
        check_perf_budgets(args.budgets, args.results)
    except PerfBudgetError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("性能预算检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
