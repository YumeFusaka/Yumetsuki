from __future__ import annotations

import re
from typing import Any


SEARCH_QUERY_TOOLS = {
    "system_control__search_in_browser",
    "web_automation__web_search",
    "web_automation__web_search_visible",
}

WEB_SESSION_OPEN_TOOL = "web_automation__web_session_open"


def extract_search_query(user_input: str) -> str:
    text = str(user_input or "").strip()
    patterns = (
        r"^(?:请|麻烦)?(?:帮我)?(?:用|使用|在)?(?:浏览器)?(?:里|中)?(?:重新|再次|再)?(?:搜索|搜|查询|查找|查)(?:一下|下)?\s*[:：,，]?\s*(?P<query>.+)$",
        r"^(?:请|麻烦)?(?:帮我)?(?:在|用|使用|打开)?浏览器(?:里|中)?(?:帮我)?(?:重新|再次|再)?(?:搜索|搜|查询|查找|查)(?:一下|下)?\s*[:：,，]?\s*(?P<query>.+)$",
        r"(?:重新|再次|再)?(?:搜索|搜|查询|查找|查)(?:一下|下)?\s*[:：,，]?\s*(?P<query>.+?)\s*(?:用|使用|在)?浏览器(?:里|中)?$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        query = clean_extracted_query(match.group("query"))
        if query:
            return query
    return ""


def clean_extracted_query(query: str) -> str:
    return str(query or "").strip(" \t\r\n：:，,。.!！?？\"'“”‘’")


def normalize_tool_arguments(
    tool_name: str | None,
    arguments: dict[str, Any] | None,
    user_input: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = dict(arguments or {})
    changes: dict[str, Any] = {}
    if tool_name not in SEARCH_QUERY_TOOLS:
        return normalized, changes

    raw_query = str(normalized.get("query", "") or "")
    query = extract_search_query(raw_query) or extract_search_query(user_input)
    if query and query != raw_query:
        normalized["query"] = query
        changes["query"] = {"from": raw_query, "to": query}
    return normalized, changes


def is_explicit_web_automation_request(user_input: str) -> bool:
    text = str(user_input or "").lower()
    compact = "".join(str(user_input or "").split()).lower()
    explicit_markers = (
        "playwright",
        "自动化浏览器",
        "网页自动化",
        "自动化窗口",
        "可见自动化",
        "持续浏览器会话",
        "持续会话",
        "web_session",
        "websession",
    )
    return any(marker in compact or marker in text for marker in explicit_markers)


def should_block_web_session_open(tool_name: str | None, user_input: str) -> bool:
    return tool_name == WEB_SESSION_OPEN_TOOL and not is_explicit_web_automation_request(user_input)


def is_current_page_read_request(user_input: str) -> bool:
    text = "".join(str(user_input or "").split()).lower()
    if not text:
        return False
    page_markers = (
        "这个页面",
        "这个网页",
        "当前页面",
        "当前网页",
        "搜索页",
        "搜索结果页",
        "你搜索的",
        "刚才搜索",
        "刚刚搜索",
        "打开的页面",
        "打开的网页",
        "这页",
    )
    read_markers = (
        "看看",
        "看一下",
        "看下",
        "阅读",
        "读一下",
        "读读",
        "有什么内容",
        "写了什么",
        "页面内容",
        "网页内容",
        "总结",
        "介绍",
    )
    explicit_new_search = (
        text.startswith("搜索")
        or text.startswith("搜")
        or text.startswith("查询")
        or text.startswith("查找")
        or "重新搜索" in text
        or "再搜索" in text
    )
    return not explicit_new_search and any(marker in text for marker in page_markers) and any(
        marker in text for marker in read_markers
    )
