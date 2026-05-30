from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAPS = ROOT / "apps" / "desktop" / "src-tauri" / "capabilities"


def test_capability_files_exist() -> None:
    for name in ["main.json", "pet.json", "settings.json", "diagnostics.json"]:
        assert (CAPS / name).exists()


def test_pet_does_not_get_settings_or_diagnostics() -> None:
    text = (CAPS / "pet.json").read_text(encoding="utf-8")
    assert "settings" not in text
    assert "diagnostics" not in text


def test_forbidden_permissions_are_not_wide_open() -> None:
    for name in ["main.json", "pet.json", "settings.json", "diagnostics.json"]:
        text = (CAPS / name).read_text(encoding="utf-8")
        for token in ['"shell"', '"clipboard"', '"opener"', '"http"', '"file"']:
            assert token not in text
