from __future__ import annotations

from pathlib import Path
from typing import Any


_EXTRACT_JS = """
() => {
    const scripts = document.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());
    return document.body ? document.body.innerText : '';
}
"""


def extract_text(page: Any, url: str, max_length: int = 2000) -> str:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        text = page.evaluate(_EXTRACT_JS)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容已截断)"
        return text if text else "页面无文本内容"
    except Exception as e:
        return f"提取页面文本失败：{e}"


def screenshot(page: Any, url: str, save_path: str) -> str:
    try:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.screenshot(path=str(path), full_page=True)
        return f"截图已保存：{save_path}"
    except Exception as e:
        return f"截图失败：{e}"
