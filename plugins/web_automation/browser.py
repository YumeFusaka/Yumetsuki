from __future__ import annotations

from typing import Any, Callable


def run_headless(callback: Callable[..., Any]) -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            return callback(page)
        finally:
            browser.close()


def run_visible(callback: Callable[..., Any]) -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()
        return callback(page)
