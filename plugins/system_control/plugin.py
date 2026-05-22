from __future__ import annotations

from enum import IntEnum
from pathlib import Path

import yaml

from sdk.base import BasePlugin, tool
from plugins.system_control.open import (
    do_open_application,
    do_open_browser,
    do_search_in_browser,
    do_open_file_manager,
    do_open_file,
    do_open_url,
)
from plugins.system_control.command import do_run_command


class PermissionLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


_LEVEL_NAMES = {"low": PermissionLevel.LOW, "medium": PermissionLevel.MEDIUM, "high": PermissionLevel.HIGH}


def _load_permission_level() -> PermissionLevel:
    config_path = Path(__file__).parent.parent.parent / "data" / "config" / "agent.yaml"
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        level_str = data.get("system_control", {}).get("permission_level", "low")
        return _LEVEL_NAMES.get(level_str, PermissionLevel.LOW)
    return PermissionLevel.LOW


class Plugin(BasePlugin):
    name = "system_control"
    description = "系统控制：打开应用、浏览器、文件、执行命令"

    def __init__(self):
        super().__init__()
        self._permission_level = _load_permission_level()

    def _check_permission(self, required: PermissionLevel) -> str | None:
        if self._permission_level >= required:
            return None
        current_name = self._permission_level.name.lower()
        required_name = required.name.lower()
        return f"权限不足：当前等级为 {current_name}，该操作需要 {required_name} 及以上"

    @tool(description="打开指定应用程序", params={"name": "应用程序名称，如 notepad、chrome、code"})
    def open_application(self, name: str) -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        return do_open_application(name)

    @tool(description="打开默认浏览器")
    def open_browser(self) -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        return do_open_browser()

    @tool(
        description="使用系统默认浏览器直接搜索关键词，适用于“用浏览器搜索 xxx”“打开浏览器搜索 xxx”这类场景",
        params={"query": "搜索关键词", "engine": "搜索引擎：bing 或 google，留空默认 bing"},
    )
    def search_in_browser(self, query: str, engine: str = "") -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        return do_search_in_browser(query, engine)

    @tool(description="打开文件管理器", params={"path": "要打开的目录路径，如 C:/Users 或 D:/Projects，留空则打开用户主目录"})
    def open_file_manager(self, path: str = "") -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        return do_open_file_manager(path)

    @tool(description="用默认程序打开指定文件", params={"path": "文件的完整路径，如 C:/Documents/report.pdf"})
    def open_file(self, path: str) -> str:
        denied = self._check_permission(PermissionLevel.MEDIUM)
        if denied:
            return denied
        return do_open_file(path)

    @tool(description="用默认浏览器打开指定 URL", params={"url": "要打开的网址，如 https://www.google.com"})
    def open_url(self, url: str) -> str:
        denied = self._check_permission(PermissionLevel.MEDIUM)
        if denied:
            return denied
        return do_open_url(url)

    @tool(description="执行系统命令并返回输出", params={"command": "要执行的命令，如 dir、ipconfig", "timeout": "超时秒数，默认30"})
    def run_command(self, command: str, timeout: int = 30) -> str:
        denied = self._check_permission(PermissionLevel.HIGH)
        if denied:
            return denied
        return do_run_command(command, timeout)
