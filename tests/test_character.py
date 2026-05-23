from pathlib import Path

from core.character import build_system_prompt, load_character


def test_load_character_keeps_skill_body_and_builds_into_system_prompt(tmp_path: Path):
    char_dir = tmp_path / "杏铃"
    char_dir.mkdir()
    (char_dir / "prompt.md").write_text("# prompt\nprompt body", encoding="utf-8")
    (char_dir / "soul.md").write_text("# soul\nsoul body", encoding="utf-8")
    (char_dir / "SKILL.md").write_text(
        "---\n"
        "name: 杏铃\n"
        "description: test\n"
        "---\n\n"
        "# skill\nskill body",
        encoding="utf-8",
    )
    resource_dir = char_dir / "resource"
    resource_dir.mkdir()
    (resource_dir / "notes.md").write_text("# notes\nresource body", encoding="utf-8")

    char = load_character(char_dir)
    prompt = build_system_prompt(char)

    assert char.name == "杏铃"
    assert char.skill == "# skill\nskill body"
    assert "# prompt\nprompt body" in prompt
    assert "# skill\nskill body" in prompt
    assert "# soul\nsoul body" in prompt
    assert "# notes\nresource body" in prompt


def test_build_system_prompt_orders_skill_before_soul_and_resources(tmp_path: Path):
    char_dir = tmp_path / "角色"
    char_dir.mkdir()
    (char_dir / "prompt.md").write_text("prompt", encoding="utf-8")
    (char_dir / "soul.md").write_text("soul", encoding="utf-8")
    (char_dir / "SKILL.md").write_text("---\nname: 角色\n---\nskill", encoding="utf-8")
    resource_dir = char_dir / "resource"
    resource_dir.mkdir()
    (resource_dir / "a.md").write_text("resource", encoding="utf-8")

    char = load_character(char_dir)
    prompt = build_system_prompt(char)

    assert prompt.index("prompt") < prompt.index("skill")
    assert prompt.index("skill") < prompt.index("soul")
    assert prompt.index("soul") < prompt.index("resource")
