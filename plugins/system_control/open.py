from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser


def do_open_application(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        return f"找不到应用程序：{name}"
    try:
        subprocess.Popen([path])
        return f"已打开应用程序：{name}"
    except OSError as e:
        return f"打开应用程序失败：{name}，错误：{e}"


def do_open_browser() -> str:
    try:
        webbrowser.open("")
        return "已打开默认浏览器"
    except Exception as e:
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
