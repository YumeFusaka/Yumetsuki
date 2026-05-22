import re
from dataclasses import dataclass

_EMOTION_RE = re.compile(r"\[emotion:(\w+)\]")


@dataclass
class ProcessedText:
    clean_text: str
    emotion: str | None
    thinking: str = ""


class TextProcessor:
    def process(self, text: str) -> ProcessedText:
        match = _EMOTION_RE.search(text)
        emotion = match.group(1) if match else None
        clean = _EMOTION_RE.sub("", text)
        return ProcessedText(clean_text=clean, emotion=emotion)
