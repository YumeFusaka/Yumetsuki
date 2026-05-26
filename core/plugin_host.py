from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from sdk.base import BasePlugin

TOOL_NAME_SEPARATOR = "__"


@dataclass(frozen=True)
class PluginLoadError:
    plugin: str
    message: str


@dataclass(frozen=True)
class PluginStatus:
    name: str
    path: str
    loaded: bool
    tools_count: int = 0
    description: str = ""
    message: str = ""


class PluginHost:
    def __init__(self, plugins_dir: Path | str):
        self._plugins_dir = Path(plugins_dir)
        self.plugins: list[BasePlugin] = []
        self.errors: list[PluginLoadError] = []
        self.statuses: list[PluginStatus] = []

    def load(self) -> None:
        self.plugins.clear()
        self.errors.clear()
        self.statuses.clear()
        if not self._plugins_dir.is_dir():
            return

        for plugin_dir in sorted(path for path in self._plugins_dir.iterdir() if path.is_dir()):
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                continue
            try:
                module = self._load_module(plugin_dir.name, plugin_file)
                plugin_cls = getattr(module, "Plugin")
                plugin = plugin_cls()
                if not isinstance(plugin, BasePlugin):
                    raise TypeError("Plugin must inherit sdk.base.BasePlugin")
                self.plugins.append(plugin)
                self.statuses.append(PluginStatus(
                    name=plugin.name,
                    path=str(plugin_dir.resolve()),
                    loaded=True,
                    tools_count=len(plugin.tools()),
                    description=plugin.description,
                    message="loaded",
                ))
            except Exception as exc:
                message = str(exc)
                self.errors.append(PluginLoadError(plugin=plugin_dir.name, message=message))
                self.statuses.append(PluginStatus(
                    name=plugin_dir.name,
                    path=str(plugin_dir.resolve()),
                    loaded=False,
                    message=message,
                ))

    def tool_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for plugin in self.plugins:
            for spec in plugin.tools():
                specs.append(spec.as_openai_tool(f"{plugin.name}{TOOL_NAME_SEPARATOR}{spec.name}"))
        return specs

    def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        plugin_name, sep, tool_name = qualified_name.partition(TOOL_NAME_SEPARATOR)
        if not sep:
            raise ValueError(f"Tool name must be qualified as plugin__tool: {qualified_name}")
        for plugin in self.plugins:
            if plugin.name == plugin_name:
                return plugin.call_tool(tool_name, arguments)
        raise ValueError(f"Unknown plugin: {plugin_name}")

    def _load_module(self, plugin_name: str, plugin_file: Path) -> ModuleType:
        module_name = f"yumetsuki_plugin_{plugin_name}"
        spec = spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin module: {plugin_file}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
