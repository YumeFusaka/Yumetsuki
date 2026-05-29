from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import tempfile
from typing import Any, Iterable, Literal


RuntimeMode = Literal["dev", "release"]


class RuntimePathError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
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

    @classmethod
    def from_json(
        cls,
        payload: dict[str, Any],
        mode: RuntimeMode = "dev",
        repo_root: Path | None = None,
        allowed_model_roots: Iterable[Path] | None = None,
    ) -> "RuntimePaths":
        required = {
            "app_data_dir",
            "config_dir",
            "log_dir",
            "memory_dir",
            "vision_dir",
            "browser_sessions_dir",
            "temp_dir",
            "resource_dir",
            "models_dir",
            "platform",
        }
        missing = required - set(payload)
        if missing:
            raise RuntimePathError(f"missing runtime path fields: {sorted(missing)}")
        unknown = set(payload) - required
        if unknown:
            raise RuntimePathError(f"unknown runtime path fields: {sorted(unknown)}")

        paths = {
            key: _resolve_injected_path(payload[key], key)
            for key in required
            if key != "platform"
        }
        platform = payload["platform"]
        if not isinstance(platform, str) or not platform:
            raise RuntimePathError("platform must be a non-empty string")

        app_data = paths["app_data_dir"]
        app_scoped_keys = (
            "config_dir",
            "log_dir",
            "memory_dir",
            "vision_dir",
            "browser_sessions_dir",
            "temp_dir",
        )
        for key in app_scoped_keys:
            assert_in_scope(paths[key], [app_data])

        models_dir = paths["models_dir"]
        if allowed_model_roots is not None:
            assert_in_scope(models_dir, [Path(root).resolve() for root in allowed_model_roots])
        elif not _is_relative_to(models_dir, app_data):
            raise RuntimePathError("models_dir must be in app_data_dir unless explicitly scoped")

        repo = (repo_root or _default_repo_root()).resolve()
        if mode == "release":
            for key, value in paths.items():
                if _is_relative_to(value, repo):
                    raise RuntimePathError(f"{key} cannot point into repo in release mode")
            for key in ("config_dir", "log_dir", "memory_dir"):
                if _has_repo_data_segment(value=paths[key]):
                    raise RuntimePathError(f"{key} cannot use repo data directory in release mode")

        return cls(platform=platform, **paths)

    @classmethod
    def temporary(cls, platform: str = "windows") -> "RuntimePaths":
        base = Path(tempfile.mkdtemp(prefix="yumetsuki-sidecar-")).resolve()
        resource = base / "resources"
        models = base / "models"
        payload = {
            "app_data_dir": str(base),
            "config_dir": str(base / "config"),
            "log_dir": str(base / "logs"),
            "memory_dir": str(base / "memory"),
            "vision_dir": str(base / "vision"),
            "browser_sessions_dir": str(base / "browser_sessions"),
            "temp_dir": str(base / "temp"),
            "resource_dir": str(resource),
            "models_dir": str(models),
            "platform": platform,
        }
        return cls.from_json(payload, mode="dev")

    def to_json(self) -> dict[str, str]:
        values = asdict(self)
        return {key: str(value) if isinstance(value, Path) else value for key, value in values.items()}

    @property
    def ready(self) -> bool:
        return True


def assert_in_scope(path: Path | str, allowed_roots: Iterable[Path | str]) -> Path:
    resolved_path = Path(path).resolve()
    resolved_roots = [Path(root).resolve() for root in allowed_roots]
    if not any(_is_relative_to(resolved_path, root) for root in resolved_roots):
        raise RuntimePathError(f"path is outside allowed scope: {resolved_path}")
    return resolved_path


def _resolve_injected_path(value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimePathError(f"{field_name} must be a non-empty path string")
    path = Path(value)
    if not path.is_absolute():
        raise RuntimePathError(f"{field_name} must be absolute")
    return path.resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _has_repo_data_segment(value: Path) -> bool:
    normalized = [part.lower() for part in value.parts]
    return "data" in normalized and any(part in normalized for part in ("config", "logs", "memory"))
