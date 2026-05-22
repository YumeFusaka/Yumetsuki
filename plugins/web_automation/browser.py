from __future__ import annotations

from typing import Any, Callable

from playwright.sync_api import sync_playwright, Page


def run_headless(callback: Callable[[Page], Any]) -> Any:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            return callback(page)
        finally:
            browser.close()


def run_visible(callback: Callable[[Page], Any]) -> Any:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page()
        return callback(page)
