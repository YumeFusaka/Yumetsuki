from dataclasses import dataclass


@dataclass(frozen=True)
class STTResult:
    text: str
    language: str = ""
    confidence: float = 0.0
    error: str = ""
