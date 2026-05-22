from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from urllib.parse import quote_plus

_APP_ALIASES: dict[str, list[str]] = {
    "edge": ["msedge", "microsoft-edge"],
    "chrome": ["chrome", "google-chrome"],
    "firefox": ["firefox"],
    "notepad": ["notepad"],
    "vscode": ["code"],
    "code": ["code"],
    "explorer": ["explorer"],
    "cmd": ["cmd"],
    "powershell": ["powershell", "pwsh"],
    "terminal": ["wt"],
    "calculator": ["calc"],
    "paint": ["mspaint"],
}

_COMMON_PATHS: dict[str, str] = {
    "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
}

_DEFAULT_BROWSER_HOME_URL = "https://www.bing.com"


def _resolve_application(name: str) -> str | None:
    """尝试多种方式查找应用程序路径。"""
    normalized = name.lower().strip()
    candidates = [normalized]
    if normalized in _APP_ALIASES:
        candidates = _APP_ALIASES[normalized]

    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
        if candidate in _COMMON_PATHS:
            common = _COMMON_PATHS[candidate]
            if os.path.isfile(common):
                return common
    return None


def do_open_application(name: str) -> str:
    path = _resolve_application(name)
    if path is None:
        return f"找不到应用程序：{name}"
    try:
        subprocess.Popen([path])
        return f"已打开应用程序：{name}"
    except OSError as e:
        return f"打开应用程序失败：{name}，错误：{e}"


def do_open_browser() -> str:
    try:
        os.startfile(_DEFAULT_BROWSER_HOME_URL)
        return "已打开系统默认浏览器"
    except OSError as e:
        return f"打开浏览器失败：{e}"


def do_search_in_browser(query: str, engine: str = "") -> str:
    engine_name = engine if engine in ("bing", "google") else "bing"
    if engine_name == "google":
        url = f"https://www.google.com/search?q={quote_plus(query)}"
    else:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
    try:
        os.startfile(url)
        return f"已使用默认浏览器搜索：{query}"
    except OSError as e:
        return f"打开浏览器失败：{e}"


def do_open_file_manager(path: str) -> str:
    target = path or os.path.expanduser("~")
    try:
        os.startfile(target)
        return f"已打开文件管理器：{target}"
    except OSError as e:
        return f"打开文件管理器失败：{e}"


def do_open_file(path: str) -> str:
    if not os.path.exists(path):
        return f"文件不存在：{path}"
    try:
        os.startfile(path)
        return f"已打开文件：{path}"
    except OSError as e:
        return f"打开文件失败：{path}，错误：{e}"


def do_open_url(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"已打开 URL：{url}"
    except Exception as e:
        return f"打开 URL 失败：{e}"
