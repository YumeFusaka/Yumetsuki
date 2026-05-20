from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "openai_compat"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int = 2048


class TTSConfig(BaseModel):
    engine: str = "none"
    api_url: str = "http://127.0.0.1:9880"


class APIConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()


class SystemConfig(BaseModel):
    language: str = "zh-CN"
    theme: str = "dark"
    font_family: str = "Microsoft YaHei"
    font_size: int = 14
