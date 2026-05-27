from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    audio_mode: str = "auto"
    ref_audio_path: str = ""
    reference_mode: str = "auto"
    prompt_lang: str = "zh"
    output_lang: str = "zh"
    prompt_text: str = ""


class ASRConfig(BaseModel):
    engine: str = "faster_whisper"
    model_path: str = "data/models/stt/faster-whisper-large-v3-turbo"
    device: str = "cpu"
    compute_type: str = "int8"
    transcribe_timeout_seconds: int = 120
    language: str = "zh"
    record_timeout_seconds: int = 20
    silence_threshold: float = 0.02
    silence_duration_ms: int = 1200


class MCPServerConfig(BaseModel):
    name: str = ""
    transport: str = "stdio"
    command: str = ""
    url: str = ""
    enabled: bool = True
    connect_timeout_seconds: int = 10
    request_timeout_seconds: int = 10
    retry_attempts: int = 0


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


class ChatDisplayConfig(BaseModel):
    font_scale: float = 1.3
    bubble_scale: float = 1.0


class PassiveInteractionConfig(BaseModel):
    idle_threshold_seconds: int = 300
    bubble_max_width: int = 600
    bubble_duration_seconds: int = 8


class VisionConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = False
    ocr_engine: str = "rapidocr"
    language: str = "ch"
    screenshot_dir: str = "data/vision"
    max_text_chars: int = 2000
    explicit_trigger_only: bool = True

    @field_validator("ocr_engine", mode="before")
    @classmethod
    def normalize_ocr_engine(cls, value):
        engine = str(value or "rapidocr").strip().lower()
        if engine == "tesseract":
            return "rapidocr"
        if engine in {"rapidocr", "paddleocr"}:
            return engine
        return "rapidocr"

    @field_validator("language", mode="before")
    @classmethod
    def normalize_ocr_language(cls, value):
        language = str(value or "ch").strip().lower()
        legacy_languages = {
            "chi_sim",
            "chi_sim+eng",
            "chi_tra",
            "chi_tra+eng",
            "zh",
            "zh-cn",
            "zh_cn",
        }
        if language in legacy_languages:
            return "ch"
        if language in {"eng", "english"}:
            return "en"
        return language or "ch"

    @field_validator("explicit_trigger_only", mode="before")
    @classmethod
    def keep_explicit_trigger_only(cls, value):
        return True


class SystemConfig(BaseModel):
    language: str = "zh-CN"
    theme: str = "sakura"
    font_family: str = "Microsoft YaHei"
    font_size: int = 14
    proxy: str = ""
    chat_display: ChatDisplayConfig = Field(default_factory=ChatDisplayConfig)
    passive_interaction: PassiveInteractionConfig = Field(default_factory=PassiveInteractionConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    logging: "LoggingConfig" = Field(default_factory=lambda: LoggingConfig())


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
    browser_headless: bool = False
    browser_timeout_ms: int = 15000
    page_wait_timeout_ms: int = 10000
    session_screenshot_dir: str = "data/browser_sessions"
    max_extract_length: int = 4000


class SessionContextConfig(BaseModel):
    recent_turns_limit: int = 8
    working_facts_limit: int = 12
    prompt_facts_limit: int = 3
    prompt_turns_limit: int = 2
    constraint_ttl_turns: int = 12
    mem0_promotion_importance: float = 0.9


class TTSRuntimeConfig(BaseModel):
    pcm_read_timeout_seconds: int = 15
    segment_total_timeout_seconds: int = 45
    max_translation_workers: int = 1
    max_tts_workers: int = 2
    tts_queue_limit: int = 16


class EventBusRuntimeConfig(BaseModel):
    log_max_buffer: int = 200
    log_flush_interval_ms: int = 80
    ui_dispatch_throttle_ms: int = 0


class LoggingConfig(BaseModel):
    enabled: bool = True
    log_root: str = "data/logs"
    system_flush_interval_ms: int = 200
    ui_buffer_limit: int = 500


class AgentConfig(BaseModel):
    planner: PlannerConfig = PlannerConfig()
    reflector: ReflectorConfig = ReflectorConfig()
    multi_step: MultiStepConfig = MultiStepConfig()
    proactive: ProactiveConfig = ProactiveConfig()
    system_control: SystemControlConfig = SystemControlConfig()
    web_automation: WebAutomationConfig = WebAutomationConfig()
    session_context: SessionContextConfig = SessionContextConfig()
    tts_runtime: TTSRuntimeConfig = TTSRuntimeConfig()
    event_bus_runtime: EventBusRuntimeConfig = EventBusRuntimeConfig()
