from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserSessionState:
    is_open: bool
    url: str = ""
    title: str = ""


@dataclass(frozen=True)
class BrowserActionResult:
    ok: bool
    action: str
    message: str
    url: str = ""
    title: str = ""
    text_preview: str = ""

    def to_text(self) -> str:
        state = "成功" if self.ok else "失败"
        lines = [
            f"动作：{self.action}",
            f"状态：{state}",
            f"消息：{self.message}",
        ]
        if self.url:
            lines.append(f"URL：{self.url}")
        if self.title:
            lines.append(f"标题：{self.title}")
        if self.text_preview:
            lines.append("页面摘要：")
            lines.append(self.text_preview)
        return "\n".join(lines)


def format_state_summary(state: BrowserSessionState) -> str:
    if not state.is_open:
        return "浏览器会话未打开。"
    lines = ["浏览器会话已打开。"]
    if state.url:
        lines.append(f"URL：{state.url}")
    if state.title:
        lines.append(f"标题：{state.title}")
    return "\n".join(lines)
