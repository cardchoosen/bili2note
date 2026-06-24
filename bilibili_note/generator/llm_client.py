"""OpenAI 兼容 LLM 客户端。

通过标准 /v1/chat/completions 接口调用，支持任意 OpenAI 兼容服务。
带自动重试，处理连接中断、超时等瞬时错误。
"""

from __future__ import annotations

import time

import httpx

from ..log import warn

_RETRYABLE = (
    httpx.RemoteProtocolError,
    httpx.ReadTimeout,
    httpx.ConnectError,
    httpx.ReadError,
)
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # 首次重试等待秒数，之后翻倍


def is_api_configured(config: dict) -> bool:
    """判断 config 是否已配置可用的 LLM API。"""
    llm = config.get("llm", {})
    return bool(llm.get("api_key") and llm.get("base_url"))


class LLMClient:
    """OpenAI 兼容接口客户端。累计 token 用量。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
        max_tokens: int = 0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    @classmethod
    def from_config(cls, config: dict) -> "LLMClient":
        llm = config["llm"]
        return cls(
            base_url=llm["base_url"],
            api_key=llm["api_key"],
            model=llm.get("model", "glm-5.2"),
            timeout=llm.get("timeout", 120),
            max_tokens=llm.get("max_tokens", 0),
        )

    def chat(self, system: str, user: str, temperature: float = 0.7) -> str:
        """调用 chat completions，返回生成的文本，同时累计 token 用量。

        瞬时网络错误自动重试（最多 3 次，指数退避）。
        """
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if self.max_tokens and self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    url, json=payload, headers=headers, timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"]
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF * (2 ** attempt)
                    warn(
                        f"LLM 请求失败，{wait:.0f}s 后重试 "
                        f"({attempt + 1}/{_MAX_RETRIES}): {exc}"
                    )
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def get_usage(self) -> dict:
        """返回累计 token 用量。"""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
        }

    def reset_usage(self) -> dict:
        """返回当前累计用量并归零，用于分步骤统计。"""
        usage = self.get_usage()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        return usage
