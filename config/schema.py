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
    ref_audio_path: str = ""
    reference_mode: str = "auto"
    prompt_lang: str = "zh"
    output_lang: str = "zh"
    prompt_text: str = ""


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


class MemoryConfig(BaseModel):
    enabled: bool = False
    storage_dir: str = "data/memory"
    user_id: str = "default-user"
    embedding_model_path: str = ""
    top_k: int = 5


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


# --- Agent Config ---


class PlannerConfig(BaseModel):
    llm_judge_enabled: bool = True
    complexity_threshold: int = 80
    judge_max_tokens: int = 300
    extra_trigger_keywords: list[str] = []


class ReflectorConfig(BaseModel):
    enabled: bool = True
    deep_threshold: int = 30
    reflect_max_tokens: int = 300
    extract_types: list[str] = ["preference", "fact", "emotion", "topic"]


class MultiStepConfig(BaseModel):
    enabled: bool = True
    max_steps: int = 3
    step_timeout: float = 30.0
    total_timeout: float = 60.0


class ProactiveEventConfig(BaseModel):
    name: str = ""
    type: str = "timer"
    condition: str = ""
    prompt_template: str = ""
    cooldown_minutes: int = 60


class ProactiveConfig(BaseModel):
    enabled: bool = False
    idle_interval_minutes: int = 30
    min_interval_minutes: int = 10
    active_hours_start: int = 8
    active_hours_end: int = 23
    events: list[ProactiveEventConfig] = []


class SystemControlConfig(BaseModel):
    permission_level: str = "low"


class WebAutomationConfig(BaseModel):
    permission_level: str = "medium"
    default_engine: str = "bing"
    screenshot_dir: str = "data/screenshots"


class AgentConfig(BaseModel):
    planner: PlannerConfig = PlannerConfig()
    reflector: ReflectorConfig = ReflectorConfig()
    multi_step: MultiStepConfig = MultiStepConfig()
    proactive: ProactiveConfig = ProactiveConfig()
    system_control: SystemControlConfig = SystemControlConfig()
    web_automation: WebAutomationConfig = WebAutomationConfig()
