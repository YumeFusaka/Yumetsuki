from pathlib import Path
import yaml
from config.schema import APIConfig, SystemConfig


class ConfigManager:
    def __init__(self, config_dir: Path | str | None = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "data" / "config"
        self._dir = Path(config_dir)
        self.api = self._load_api()
        self.system = self._load_system()

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

    def save(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        api_path = self._dir / "api.yaml"
        api_path.write_text(yaml.dump(self.api.model_dump(), allow_unicode=True, default_flow_style=False), encoding="utf-8")
        sys_path = self._dir / "system_config.yaml"
        sys_path.write_text(yaml.dump(self.system.model_dump(), allow_unicode=True, default_flow_style=False), encoding="utf-8")
