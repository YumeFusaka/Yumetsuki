from __future__ import annotations

from enum import IntEnum
from pathlib import Path

import yaml

from sdk.base import BasePlugin, tool
from plugins.system_control.open import (
    do_open_application,
    do_open_browser,
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

    @tool(description="打开指定应用程序")
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

    @tool(description="打开文件管理器，可指定目录路径")
    def open_file_manager(self, path: str = "") -> str:
        denied = self._check_permission(PermissionLevel.LOW)
        if denied:
            return denied
        return do_open_file_manager(path)

    @tool(description="用默认程序打开指定文件")
    def open_file(self, path: str) -> str:
        denied = self._check_permission(PermissionLevel.MEDIUM)
        if denied:
            return denied
        return do_open_file(path)

    @tool(description="用默认浏览器打开指定 URL")
    def open_url(self, url: str) -> str:
        denied = self._check_permission(PermissionLevel.MEDIUM)
        if denied:
            return denied
        return do_open_url(url)

    @tool(description="执行系统命令并返回输出")
    def run_command(self, command: str, timeout: int = 30) -> str:
        denied = self._check_permission(PermissionLevel.HIGH)
        if denied:
            return denied
        return do_run_command(command, timeout)
