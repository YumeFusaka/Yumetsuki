from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import sys
from typing import Any, Iterable, Literal


@dataclass(frozen=True)
class RuntimePaths:
    mode: str
    app_data_dir: Path
    config_dir: Path
    log_dir: Path
    memory_dir: Path
    vision_dir: Path
    browser_sessions_dir: Path
    temp_dir: Path
    resource_dir: Path
    models_dir: Path
    platform: str
    repo_root: Path | None = None

    @classmethod
    def field_names(cls) -> set[str]:
        return {field.name for field in fields(cls)}

    @classmethod
    def from_json(
        cls,
        data: dict[str, Any],
        mode: Literal["dev", "release"] | None = None,
        model_scope_roots: Iterable[str | Path] = (),
    ) -> "RuntimePaths":
        normalized = _normalize_fields(data)
        if mode is not None:
            payload_mode = normalized.get("mode")
            if payload_mode not in (None, mode):
                raise ValueError("RuntimePaths.mode 与调用模式不一致")
            normalized["mode"] = mode
        expected = cls.field_names()
        has_legacy_fields = any(key != "repo_root" and (key.endswith("_root") or key == "resources_root") for key in data)
        if data and has_legacy_fields:
            legacy_expected = set(LEGACY_FIELD_MAP) | {"mode", "repo_root"}
            legacy_actual = set(data)
            missing = legacy_expected - legacy_actual
            extra = legacy_actual - legacy_expected
            if missing:
                raise ValueError(f"RuntimePaths 缺少字段：{', '.join(sorted(missing))}")
            if extra:
                raise ValueError(f"RuntimePaths 存在未知字段：{', '.join(sorted(extra))}")
        actual = set(data)
        if not has_legacy_fields:
            actual = set(normalized)
            missing = expected - actual
            extra = actual - expected
            if missing:
                raise ValueError(f"RuntimePaths 缺少字段：{', '.join(sorted(missing))}")
            if extra:
                raise ValueError(f"RuntimePaths 存在未知字段：{', '.join(sorted(extra))}")
        normalized["platform"] = str(normalized.get("platform") or sys.platform)
        normalized["repo_root"] = _resolve_optional(normalized.get("repo_root"))
        for name in expected - {"mode", "platform", "repo_root"}:
            normalized[name] = _resolve_path(normalized[name])
        paths = cls(**normalized)
        paths.validate(model_scope_roots=model_scope_roots)
        return paths

    def validate(self, model_scope_roots: Iterable[str | Path] = ()) -> None:
        if self.mode not in {"dev", "release"}:
            raise ValueError("RuntimePaths.mode 必须是 dev 或 release")
        for name in (
            "app_data_dir",
            "config_dir",
            "log_dir",
            "memory_dir",
            "vision_dir",
            "browser_sessions_dir",
            "temp_dir",
            "resource_dir",
            "models_dir",
        ):
            _reject_unc(getattr(self, name), name)
        for name in ("config_dir", "log_dir", "memory_dir", "vision_dir", "browser_sessions_dir"):
            assert_in_scope(getattr(self, name), [self.app_data_dir], name)
        model_roots = [self.app_data_dir, *[_resolve_path(root) for root in model_scope_roots]]
        try:
            assert_in_scope(self.models_dir, model_roots, "models_dir")
        except ValueError as exc:
            raise ValueError("models_dir 不在 Tauri 授权范围内") from exc
        if self.mode == "release" and self.repo_root:
            for name in (
                "app_data_dir",
                "config_dir",
                "log_dir",
                "memory_dir",
                "vision_dir",
                "browser_sessions_dir",
                "temp_dir",
            ):
                value = getattr(self, name)
                if _is_relative_to(value, self.repo_root):
                    raise ValueError(f"release 模式运行期路径不得位于仓库内：{name}")

    @property
    def app_data_root(self) -> str:
        return str(self.app_data_dir)

    @property
    def resources_root(self) -> str:
        return str(self.resource_dir)

    @property
    def config_root(self) -> str:
        return str(self.config_dir)

    @property
    def logs_root(self) -> str:
        return str(self.log_dir)

    @property
    def memory_root(self) -> str:
        return str(self.memory_dir)

    @property
    def vision_root(self) -> str:
        return str(self.vision_dir)

    @property
    def browser_sessions_root(self) -> str:
        return str(self.browser_sessions_dir)

    @property
    def models_root(self) -> str:
        return str(self.models_dir)

    @property
    def temp_root(self) -> str:
        return str(self.temp_dir)


LEGACY_FIELD_MAP = {
    "app_data_root": "app_data_dir",
    "resources_root": "resource_dir",
    "config_root": "config_dir",
    "logs_root": "log_dir",
    "memory_root": "memory_dir",
    "vision_root": "vision_dir",
    "browser_sessions_root": "browser_sessions_dir",
    "models_root": "models_dir",
    "temp_root": "temp_dir",
}


def _normalize_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in data.items():
        normalized[LEGACY_FIELD_MAP.get(key, key)] = value
    return normalized


def _resolve_path(value: Any) -> Path:
    return Path(str(value)).expanduser().resolve(strict=False)


def _resolve_optional(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return _resolve_path(value)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def assert_in_scope(path: str | Path, allowed_roots: Iterable[str | Path], label: str = "path") -> Path:
    resolved = _resolve_path(path)
    roots = [_resolve_path(root) for root in allowed_roots]
    for root in roots:
        if _is_relative_to(resolved, root):
            return resolved
    raise ValueError(f"{label} 不在允许范围内")


def assert_default_resource_copy(paths: RuntimePaths, source: str | Path, destination: str | Path) -> None:
    resolved_source = assert_in_scope(source, [paths.resource_dir / "defaults"], "source")
    resolved_destination = _resolve_path(destination)
    if _is_relative_to(resolved_destination, paths.resource_dir):
        raise ValueError("默认资源不得原地写入 resource_dir")
    assert_in_scope(resolved_destination, [paths.app_data_dir], "destination")
    if resolved_source == resolved_destination:
        raise ValueError("默认资源不得原地写入")


def _reject_unc(path: Path, label: str) -> None:
    anchor = path.anchor.replace("/", "\\")
    if anchor.startswith("\\\\"):
        raise ValueError(f"{label} UNC 路径不允许")
