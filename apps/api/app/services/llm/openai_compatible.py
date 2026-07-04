"""OpenAI 兼容协议的大模型实现。

DeepSeek、通义等均走 /v1/chat/completions；DeepSeek 为默认 provider。
"""

import httpx

from app.services.llm.base import LLMMessage, LLMProvider, LLMResponse


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
