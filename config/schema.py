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


class ASRConfig(BaseModel):
    engine: str = "none"
    model_path: str = ""


class MCPServerConfig(BaseModel):
    name: str = ""
    transport: str = "stdio"
    command: str = ""
    url: str = ""
    enabled: bool = True


class MCPConfig(BaseModel):
    servers: list[MCPServerConfig] = []


class APIConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    asr: ASRConfig = ASRConfig()


class SystemConfig(BaseModel):
    language: str = "zh-CN"
    theme: str = "dark"
    font_family: str = "Microsoft YaHei"
    font_size: int = 14
    proxy: str = ""
