from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent.tool_argument_normalizer import (
    SEARCH_QUERY_TOOLS,
    extract_search_query,
    is_current_page_read_request,
    normalize_tool_arguments,
)
from config.schema import PlannerConfig
from core.tool_registry import ToolEntry


@dataclass(frozen=True)
class AgentPlan:
    mode: str  # "chat" | "tool" | "multi_step"
    goal: str
    tool_name: str | None = None
    arguments: dict[str, object] = field(default_factory=dict)
    needs_multi_step: bool = False
    steps: list[str] = field(default_factory=list)


# LLM 精判 system prompt
_JUDGE_SYSTEM_PROMPT = """你是一个意图分类器。根据用户输入和可用工具列表，判断用户意图并提取工具参数。
输出严格 JSON，不要输出其他内容：
{"mode": "chat"|"tool"|"multi_step", "goal": "简短描述", "tool_name": "工具名或null", "arguments": {}, "needs_multi_step": true|false, "steps": ["步骤1", "步骤2"]}

规则：
- 普通对话/闲聊/问候 → mode=chat
- 明确需要调用某个工具 → mode=tool, tool_name=工具qualified_name, arguments=根据工具参数schema从用户输入中提取的参数值
- 需要多步操作（先做A再做B）→ mode=multi_step, needs_multi_step=true, steps列出每步
- 如果不确定，选 chat
- arguments 的 key 必须严格匹配工具参数 schema 中的参数名
- 用户说"打开浏览器"时，优先选择 system_control__open_browser
- 用户说"用浏览器搜索 xxx"、"打开浏览器搜索 xxx"、"在浏览器里搜 xxx"时，优先选择 system_control__search_in_browser
- 用户只是说"点击浏览器里的条目/当前网页上的按钮/浏览器里第几个结果"时，不要选择 open_browser，也不要为系统默认浏览器新开 web_session_open；系统默认浏览器不能被 Playwright 直接接管
- 只有当用户明确要求返回搜索结果文本、后台静默搜索、提取网页内容、截图网页、或明确要求展示自动化搜索过程时，才选择 web_automation 工具
- web_search_visible 是 Playwright 自动化可见窗口，不等同于系统默认浏览器当前窗口
- web_session_open 只在用户明确要求"自动化浏览器/Playwright/持续浏览器会话"时使用
- 仔细识别工具 description 中"可见/后台"、"默认浏览器/自动化浏览器"、"打开窗口/静默"等关键差异，按用户原意选择"""

# 多动作模式关键词
_MULTI_ACTION_PATTERNS = (
    "先", "然后", "再", "接着", "之后",
    "并且", "同时", "顺便",
    "帮我.*然后", "帮我.*再",
)

class AgentPlanner:
    _TOOL_INTENT_KEYWORDS = (
        "搜索", "查", "查找", "找一下", "帮我", "执行",
        "搜", "打开", "启动", "点击", "find", "search", "lookup", "open",
    )

    def __init__(
        self,
        config: PlannerConfig | None = None,
        llm_helper=None,
    ):
        self._config = config or PlannerConfig()
        self._llm = llm_helper

    def plan(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan:
        """分层路由：快速路由 → 按需 LLM 精判。"""
        fast_result = self._fast_route(user_input, tools)
        if self._is_guarded_chat_plan(user_input, fast_result):
            return self._normalize_plan(user_input, fast_result)

        # 如果 LLM 精判未启用或无 LLM helper，直接返回快速路由结果
        if not self._config.llm_judge_enabled or self._llm is None:
            return self._normalize_plan(user_input, fast_result)

        # 判断是否需要升级到 LLM 精判
        if not self._should_escalate(user_input, fast_result):
            return self._normalize_plan(user_input, fast_result)

        # LLM 精判
        judge_result = self._llm_judge(user_input, tools)
        if judge_result is not None:
            return self._normalize_plan(user_input, judge_result)

        # 精判失败，降级为快速路由结果
        return self._normalize_plan(user_input, fast_result)

    def _fast_route(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan:
        """关键词匹配快速路由（零开销）。"""
        if is_current_page_read_request(user_input):
            return AgentPlan(mode="chat", goal="read current page with visual context")
        normalized = user_input.lower()
        if not self._looks_like_tool_request(normalized):
            return AgentPlan(mode="chat", goal="reply")

        preferred = self._prefer_browser_tool(user_input, tools)
        if preferred is not None:
            return preferred
        if self._mentions_browser_without_supported_direct_action(user_input):
            return AgentPlan(mode="chat", goal="browser context needs visual observation or explicit automation session")

        for tool in tools:
            if self._matches_tool(normalized, tool):
                return AgentPlan(
                    mode="tool",
                    goal=f"use {tool.qualified_name}",
                    tool_name=tool.qualified_name,
                    arguments=self._guess_arguments(user_input, tool),
                )

        default_search = self._prefer_default_search_tool(user_input, tools)
        if default_search is not None:
            return default_search

        return AgentPlan(mode="chat", goal="reply")

    def _prefer_browser_tool(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan | None:
        text = user_input.lower()
        if "浏览器" not in user_input and "browser" not in text:
            return None

        if any(keyword in user_input for keyword in ("搜索", "搜", "查")) or any(
            keyword in text for keyword in ("search", "find", "lookup")
        ):
            tool = self._find_tool_by_name(tools, "system_control__search_in_browser")
            if tool is not None:
                return AgentPlan(
                    mode="tool",
                    goal=f"use {tool.qualified_name}",
                    tool_name=tool.qualified_name,
                    arguments=self._guess_browser_search_arguments(user_input, tool),
                )

        if not self._has_browser_open_intent(user_input):
            return None

        tool = self._find_tool_by_name(tools, "system_control__open_browser")
        if tool is not None:
            return AgentPlan(
                mode="tool",
                goal=f"use {tool.qualified_name}",
                tool_name=tool.qualified_name,
                arguments=self._guess_arguments(user_input, tool),
            )
        return None

    def _guess_browser_search_arguments(self, user_input: str, tool: ToolEntry) -> dict[str, object]:
        query = self._extract_browser_search_query(user_input)
        if query:
            return {"query": query}
        return self._guess_arguments(user_input, tool)

    def _prefer_default_search_tool(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan | None:
        query = self._extract_browser_search_query(user_input)
        if not query:
            return None
        tool = self._find_tool_by_name(tools, "system_control__search_in_browser")
        if tool is None:
            return None
        return AgentPlan(
            mode="tool",
            goal=f"use {tool.qualified_name}",
            tool_name=tool.qualified_name,
            arguments={"query": query},
        )

    def _extract_browser_search_query(self, user_input: str) -> str:
        return extract_search_query(user_input)

    @staticmethod
    def _clean_extracted_query(query: str) -> str:
        return query.strip(" \t\r\n：:，,。.!！?？\"'“”‘’")

    def _normalize_plan(self, user_input: str, plan: AgentPlan) -> AgentPlan:
        if plan.tool_name not in SEARCH_QUERY_TOOLS:
            return plan
        arguments, changes = normalize_tool_arguments(plan.tool_name, plan.arguments, user_input)
        if not changes:
            return plan
        return AgentPlan(
            mode=plan.mode,
            goal=plan.goal,
            tool_name=plan.tool_name,
            arguments=arguments,
            needs_multi_step=plan.needs_multi_step,
            steps=list(plan.steps),
        )

    @staticmethod
    def _has_browser_open_intent(user_input: str) -> bool:
        compact = "".join(user_input.split()).lower()
        return any(
            marker in compact
            for marker in (
                "打开浏览器",
                "启动浏览器",
                "开浏览器",
                "openbrowser",
                "launchbrowser",
            )
        )

    @staticmethod
    def _mentions_browser_without_supported_direct_action(user_input: str) -> bool:
        text = user_input.lower()
        if "浏览器" not in user_input and "browser" not in text:
            return False
        if any(keyword in user_input for keyword in ("搜索", "搜", "查")):
            return False
        if AgentPlanner._has_browser_open_intent(user_input):
            return False
        direct_control_words = ("点击", "点开", "打开第", "选择", "输入", "填写", "按下")
        return any(word in user_input for word in direct_control_words)

    def _find_tool_by_name(self, tools: list[ToolEntry], qualified_name: str) -> ToolEntry | None:
        for tool in tools:
            if tool.qualified_name == qualified_name:
                return tool
        return None

    def _guess_arguments(self, user_input: str, tool: ToolEntry) -> dict[str, object]:
        """快速路由 fallback：根据工具 schema 尝试填充参数。"""
        params = tool.schema.get("parameters", {})
        properties = params.get("properties", {})
        required = list(params.get("required", []))
        if not properties:
            return {}
        if len(required) == 1:
            return {required[0]: user_input}
        if len(properties) == 1:
            return {list(properties.keys())[0]: user_input}
        return {k: user_input for k in required} if required else {}

    def _should_escalate(self, user_input: str, fast_result: AgentPlan) -> bool:
        """判断是否需要 LLM 精判。"""
        if self._is_guarded_chat_plan(user_input, fast_result):
            return False

        # 快速路由命中工具 → 需要精判确认
        if fast_result.mode == "tool":
            return True

        # 输入超过复杂度阈值
        if len(user_input) > self._config.complexity_threshold:
            return True

        # 多动作模式
        if self._has_multi_action_pattern(user_input):
            return True

        # 自定义触发关键词
        normalized = user_input.lower()
        for kw in self._config.extra_trigger_keywords:
            if kw.lower() in normalized:
                return True

        return False

    @staticmethod
    def _is_guarded_chat_plan(user_input: str, fast_result: AgentPlan) -> bool:
        if fast_result.mode != "chat":
            return False
        if is_current_page_read_request(user_input):
            return True
        return fast_result.goal in {
            "read current page with visual context",
            "browser context needs visual observation or explicit automation session",
        }

    def _has_multi_action_pattern(self, user_input: str) -> bool:
        """检测多动作模式。"""
        for pattern in _MULTI_ACTION_PATTERNS:
            if re.search(pattern, user_input):
                return True
        return False

    def _llm_judge(self, user_input: str, tools: list[ToolEntry]) -> AgentPlan | None:
        """调用 LLM 做意图精判 + 参数提取。失败返回 None。"""
        tool_desc = "\n".join(
            f"- {t.qualified_name}: {t.schema.get('description', '')} | 参数: {self._format_params(t)}"
            for t in tools
        ) or "无可用工具"

        user_prompt = f"可用工具:\n{tool_desc}\n\n用户输入: {user_input}"

        result = self._llm.judge_json(
            _JUDGE_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=self._config.judge_max_tokens,
        )

        if not result or "mode" not in result:
            return None

        mode = result.get("mode", "chat")
        if mode not in ("chat", "tool", "multi_step"):
            mode = "chat"

        tool_name = result.get("tool_name")
        # 验证工具名存在
        if mode == "tool" and tool_name:
            valid_names = {t.qualified_name for t in tools}
            if tool_name not in valid_names:
                tool_name = None
                mode = "chat"

        needs_multi_step = result.get("needs_multi_step", False)
        steps = result.get("steps", []) or []

        if mode == "multi_step":
            needs_multi_step = True

        arguments = result.get("arguments", {}) or {}

        return AgentPlan(
            mode=mode,
            goal=result.get("goal", ""),
            tool_name=tool_name,
            arguments=arguments,
            needs_multi_step=needs_multi_step,
            steps=steps,
        )

    def _format_params(self, tool: ToolEntry) -> str:
        """格式化工具参数 schema 供 LLM 阅读。"""
        params = tool.schema.get("parameters", {})
        properties = params.get("properties", {})
        required = set(params.get("required", []))
        if not properties:
            return "无参数"
        parts = []
        for name, info in properties.items():
            req = "(必填)" if name in required else "(可选)"
            desc = info.get("description", "")
            desc_str = f" - {desc}" if desc else ""
            parts.append(f"{name}: {info.get('type', 'string')}{req}{desc_str}")
        return "; ".join(parts)

    def _looks_like_tool_request(self, normalized_input: str) -> bool:
        return any(keyword in normalized_input for keyword in self._TOOL_INTENT_KEYWORDS)

    def _matches_tool(self, normalized_input: str, tool: ToolEntry) -> bool:
        haystacks = [
            tool.qualified_name.lower(),
            tool.name.lower(),
            str(tool.schema.get("description", "")).lower(),
        ]
        return any(
            any(token and token in normalized_input for token in self._tokenize(text))
            for text in haystacks
        )

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.replace("__", " ").replace("_", " ").replace("-", " ")
        tokens: list[str] = []
        for part in re.findall(r"[一-鿿]{2,}|[a-zA-Z0-9]+", normalized):
            tokens.append(part)
            if re.fullmatch(r"[一-鿿]{2,}", part):
                tokens.extend(self._cn_ngrams(part))
        return list(dict.fromkeys(token for token in tokens if len(token) >= 2))

    def _cn_ngrams(self, text: str) -> list[str]:
        grams: list[str] = []
        for size in range(2, min(5, len(text) + 1)):
            for index in range(0, len(text) - size + 1):
                grams.append(text[index:index + size])
        return grams
