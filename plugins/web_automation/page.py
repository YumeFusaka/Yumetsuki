from __future__ import annotations

from pathlib import Path
from typing import Any

from plugins.web_automation.session import BrowserActionResult


_EXTRACT_JS = """
() => {
    const scripts = document.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());
    return document.body ? document.body.innerText : '';
}
"""


def _page_title(page: Any) -> str:
    try:
        return page.title()
    except Exception:
        return ""


def _current_url(page: Any) -> str:
    return getattr(page, "url", "") or ""


def navigate_current(page: Any, url: str, timeout_ms: int = 15000) -> BrowserActionResult:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        return BrowserActionResult(True, "navigate", "已打开页面", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "navigate", f"打开页面失败：{exc}", _current_url(page), _page_title(page))


def click_selector(page: Any, selector: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.click(selector, timeout=timeout_ms)
        return BrowserActionResult(True, "click", f"已点击：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "click", f"点击失败：{exc}", _current_url(page), _page_title(page))


def fill_selector(page: Any, selector: str, text: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.fill(selector, text, timeout=timeout_ms)
        return BrowserActionResult(True, "fill", f"已填写：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "fill", f"填写失败：{exc}", _current_url(page), _page_title(page))


def wait_for_selector(page: Any, selector: str, timeout_ms: int = 10000) -> BrowserActionResult:
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
        return BrowserActionResult(True, "wait", f"已等待到元素：{selector}", _current_url(page), _page_title(page))
    except Exception as exc:
        return BrowserActionResult(False, "wait", f"等待失败：{exc}", _current_url(page), _page_title(page))


def extract_current_text(page: Any, max_length: int = 4000) -> BrowserActionResult:
    try:
        text = page.evaluate(_EXTRACT_JS)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容已截断)"
        return BrowserActionResult(
            True,
            "extract",
            "已提取当前页面文本",
            _current_url(page),
            _page_title(page),
            text or "页面无文本内容",
        )
    except Exception as exc:
        return BrowserActionResult(False, "extract", f"提取失败：{exc}", _current_url(page), _page_title(page))


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
