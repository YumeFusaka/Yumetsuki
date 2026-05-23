from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TTSAudioFormat:
    transport: Literal["wav", "pcm_stream"]
    sample_rate: int
    channels: int
    sample_width: int


@dataclass(frozen=True)
class TTSStreamEvent:
    kind: Literal["start", "chunk", "end", "error"]
    format: TTSAudioFormat | None = None
    data: bytes | None = None
    message: str = ""
