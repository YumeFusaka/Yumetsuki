from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = Path("data/models")
STT_MODELS_DIR = MODELS_ROOT / "stt"
EMBEDDING_MODELS_DIR = MODELS_ROOT / "embedding"


def is_stt_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "config.json").exists() and (
        (path / "model.bin").exists() or any(path.glob("*.bin"))
    )


def is_embedding_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "modules.json").exists() or (path / "sentence_bert_config.json").exists()


def model_path_key(path: str | Path) -> str:
    normalized = Path(path)
    if not normalized.is_absolute():
        normalized = PROJECT_ROOT / normalized
    return os.path.normcase(os.path.normpath(str(normalized.resolve(strict=False))))


def scan_model_dirs(category_dir: Path, validator, *, include_legacy: bool = True) -> list[str]:
    paths: list[Path] = []
    if category_dir.exists():
        paths.extend(p for p in sorted(category_dir.iterdir()) if validator(p))
    if include_legacy and MODELS_ROOT.exists():
        paths.extend(
            p for p in sorted(MODELS_ROOT.iterdir())
            if p.parent == MODELS_ROOT and p != category_dir and validator(p)
        )

    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        key = model_path_key(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(str(path))
    return result


def resolve_model_path(path_text: str, category_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute() or path.exists():
        return path
    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return project_path
    legacy_path = PROJECT_ROOT / MODELS_ROOT / path.name
    if legacy_path.exists():
        return legacy_path
    categorized_path = PROJECT_ROOT / category_dir / path.name
    if categorized_path.exists():
        return categorized_path
    return project_path
