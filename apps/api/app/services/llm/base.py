from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str


class LLMProvider:
    provider_name: str = "base"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ) -> LLMResponse:
        raise NotImplementedError

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
        yield  # pragma: no cover
