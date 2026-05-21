from __future__ import annotations

import json
import logging
from typing import Any

from config.schema import LLMConfig

logger = logging.getLogger(__name__)


class AgentLLMHelper:
    """Agent 内部轻量 LLM 调用。与主对话共享配置但独立调用，不影响对话历史。"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client = self._create_client(config)

    def _create_client(self, config: LLMConfig):
        from openai import OpenAI
        return OpenAI(api_key=config.api_key, base_url=config.base_url)

    def judge(self, system_prompt: str, user_prompt: str, max_tokens: int = 200) -> str:
        """单次非流式调用，返回纯文本。用于精判/反思等内部决策。"""
        try:
            response = self._client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                temperature=0.3,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning(f"AgentLLMHelper.judge failed: {exc}")
            return ""

    def judge_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 200) -> dict[str, Any]:
        """单次非流式调用，解析 JSON 输出。解析失败返回空 dict。"""
        raw = self.judge(system_prompt, user_prompt, max_tokens)
        if not raw:
            return {}
        # 尝试提取 JSON（兼容 markdown code block 包裹）
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"AgentLLMHelper.judge_json parse failed: {raw[:100]}")
            return {}
