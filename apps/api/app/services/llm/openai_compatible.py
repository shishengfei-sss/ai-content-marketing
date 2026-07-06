"""OpenAI 兼容协议的大模型实现。

DeepSeek、通义等均走 /v1/chat/completions；DeepSeek 为默认 provider。
开发期 api_key=`mock` 时返回固定内容，便于无 Key 联调。
"""

import json

import httpx

from app.services.llm.base import LLMMessage, LLMProvider, LLMResponse

MOCK_PROPOSALS_JSON = json.dumps(
    [
        {"title": "稳健理财三原则：先保障再增值", "angle": "", "outline": ""},
        {"title": "2026年家庭资产配置入门指南", "angle": "", "outline": ""},
        {"title": "普通人如何避开理财常见误区", "angle": "", "outline": ""},
    ],
    ensure_ascii=False,
)
MOCK_ARTICLE = (
    "## 稳健理财三原则\n\n"
    "在不确定的市场环境中，普通家庭应遵循「先保障、再储备、后增值」三步走。"
    "首先配置基础保障，其次建立 3-6 个月应急金，再用闲置资金做分散投资。\n\n"
    "本文仅供营销参考，不构成投资建议。"
)


def _mock_chat(messages: list[LLMMessage], *, model: str, provider_name: str) -> LLMResponse:
    system_text = " ".join(m.content for m in messages if m.role == "system")
    if "选题策划" in system_text or "JSON 数组" in system_text:
        return LLMResponse(content=MOCK_PROPOSALS_JSON, model=model, provider=provider_name)
    return LLMResponse(content=MOCK_ARTICLE, model=model, provider=provider_name)


class OpenAICompatibleProvider(LLMProvider):
    provider_name = "openai_compatible"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ) -> LLMResponse:
        if api_key == "mock":
            return _mock_chat(messages, model=model, provider_name=self.provider_name)

        url = base_url.rstrip("/") + "/v1/chat/completions"
        if base_url.rstrip("/").endswith("/v1"):
            url = base_url.rstrip("/") + "/chat/completions"

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        used_model = data.get("model", model)
        return LLMResponse(content=content, model=used_model, provider=self.provider_name)

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ):
        result = await self.chat(
            messages,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_sec=timeout_sec,
        )
        text = result.content
        step = max(1, len(text) // 4) if text else 1
        for i in range(0, len(text), step):
            yield text[i : i + step]


class DeepSeekProvider(OpenAICompatibleProvider):
    provider_name = "deepseek"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ) -> LLMResponse:
        result = await super().chat(
            messages,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_sec=timeout_sec,
        )
        return LLMResponse(content=result.content, model=result.model, provider=self.provider_name)


class DashScopeProvider(OpenAICompatibleProvider):
    provider_name = "dashscope"
