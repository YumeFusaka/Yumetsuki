from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


def search_bing(page: Any, query: str, count: int = 5) -> list[dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".b_algo", timeout=10000)

    items = page.query_selector_all(".b_algo")
    results: list[dict[str, str]] = []
    for item in items[:count]:
        link_el = item.query_selector("h2 a")
        snippet_el = item.query_selector(".b_caption p")
        if link_el:
            title = link_el.inner_text()
            href = link_el.get_attribute("href") or ""
            snippet = snippet_el.inner_text() if snippet_el else ""
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def search_google(page: Any, query: str, count: int = 5) -> list[dict[str, str]]:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector(".g", timeout=10000)

    items = page.query_selector_all(".g")
    results: list[dict[str, str]] = []
    for item in items[:count]:
        link_el = item.query_selector("a")
        title_el = item.query_selector("h3")
        snippet_el = item.query_selector("[data-sncf], .VwiC3b")
        if link_el and title_el:
            title = title_el.inner_text()
            href = link_el.get_attribute("href") or ""
            snippet = snippet_el.inner_text() if snippet_el else ""
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def format_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "未找到搜索结果"
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines).strip()
