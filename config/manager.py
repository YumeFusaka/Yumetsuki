from pathlib import Path
import yaml
from config.schema import APIConfig, MCPConfig, MemoryConfig, SystemConfig


class ConfigManager:
    def __init__(self, config_dir: Path | str | None = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "data" / "config"
        self._dir = Path(config_dir)
        self.api = self._load_api()
        self.system = self._load_system()
        self.mcp = self._load_mcp()
        self.memory = self._load_memory()

    def _load_api(self) -> APIConfig:
        path = self._dir / "api.yaml"
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return APIConfig(**data)
        return APIConfig()

    def _load_system(self) -> SystemConfig:
        path = self._dir / "system_config.yaml"
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return SystemConfig(**data)
        return SystemConfig()

    def _load_mcp(self) -> MCPConfig:
        path = self._dir / "mcp.yaml"
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return MCPConfig(**data)
        return MCPConfig()

    def _load_memory(self) -> MemoryConfig:
        path = self._dir / "memory.yaml"
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return MemoryConfig(**data)
        return MemoryConfig()

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self.save_api()
        self.save_system()
        self.save_mcp()

    def save_api(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        api_path = self._dir / "api.yaml"
        api_path.write_text(yaml.dump(self.api.model_dump(), allow_unicode=True, default_flow_style=False), encoding="utf-8")

    def save_system(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        sys_path = self._dir / "system_config.yaml"
        sys_path.write_text(yaml.dump(self.system.model_dump(), allow_unicode=True, default_flow_style=False), encoding="utf-8")

    def save_mcp(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        mcp_path = self._dir / "mcp.yaml"
        mcp_path.write_text(yaml.dump(self.mcp.model_dump(), allow_unicode=True, default_flow_style=False), encoding="utf-8")

    def save_memory(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        memory_path = self._dir / "memory.yaml"
        memory_path.write_text(
            yaml.dump(self.memory.model_dump(), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
