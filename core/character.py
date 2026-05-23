from pathlib import Path
from dataclasses import dataclass, field
import yaml


@dataclass
class Emotion:
    name: str
    sprite: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class Character:
    name: str
    prompt: str
    skill: str
    soul: str
    emotions: list[Emotion] = field(default_factory=list)
    resources: dict[str, str] = field(default_factory=dict)


def load_character(char_dir: Path) -> Character:
    char_dir = Path(char_dir)

    # 读取 prompt.md
    prompt_path = char_dir / "prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    # 读取 soul.md
    soul_path = char_dir / "soul.md"
    soul = soul_path.read_text(encoding="utf-8") if soul_path.exists() else ""

    # 读取 SKILL.md 获取名称和正文
    skill_path = char_dir / "SKILL.md"
    name = char_dir.name
    skill = ""
    if skill_path.exists():
        content = skill_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.index("---", 3)
            frontmatter = yaml.safe_load(content[3:end])
            name = frontmatter.get("name", name)
            skill = content[end + 3:].lstrip()
        else:
            skill = content

    # 读取 sprites.yaml
    emotions = []
    sprites_yaml = char_dir / "sprites.yaml"
    if sprites_yaml.exists():
        data = yaml.safe_load(sprites_yaml.read_text(encoding="utf-8")) or {}
        for e in data.get("emotions", []):
            emotions.append(Emotion(name=e["name"], sprite=e["sprite"], aliases=e.get("aliases", [])))

    # 读取 resource/ 目录
    resources = {}
    res_dir = char_dir / "resource"
    if res_dir.is_dir():
        for f in res_dir.glob("*.md"):
            resources[f.stem] = f.read_text(encoding="utf-8")

    return Character(
        name=name,
        prompt=prompt,
        skill=skill,
        soul=soul,
        emotions=emotions,
        resources=resources,
    )


def build_system_prompt(char: Character) -> str:
    parts = [char.prompt]
    if char.skill:
        parts.append(char.skill)
    if char.soul:
        parts.append(char.soul)
    for key, content in char.resources.items():
        parts.append(content)
    if char.emotions:
        emotion_names = [e.name for e in char.emotions]
        parts.append(
            "## 情绪标签规则\n\n"
            "每次回复时，必须在回复开头插入一个情绪标签来表达当前情绪状态。\n"
            "格式：`[emotion:情绪名]`，紧跟回复内容，不要换行。\n\n"
            f"可用情绪：{', '.join(emotion_names)}\n\n"
            "示例：`[emotion:温柔]你好呀，今天过得怎么样？`\n"
            "示例：`[emotion:超开心]呀呀呀！太棒了！`\n"
            "示例：`[emotion:突然脸红]那、那个...人家才没有...`\n\n"
            "根据回复内容的情感自然选择最匹配的情绪，每条回复只用一个标签。"
        )
    return "\n\n---\n\n".join(parts)
