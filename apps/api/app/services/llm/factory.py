"""LLM Provider 注册表。

按 provider 名称返回单例实现；不支持的名字抛出 ValueError。
"""

from app.services.llm.base import LLMProvider
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.openai_compatible import DashScopeProvider, DeepSeekProvider, OpenAICompatibleProvider

PROVIDERS: dict[str, LLMProvider] = {
    "deepseek": DeepSeekProvider(),
    "openai_compatible": OpenAICompatibleProvider(),
    "dashscope": DashScopeProvider(),
    "fake": FakeLLMProvider(),
}


def get_provider(name: str) -> LLMProvider:
    provider = PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Unsupported LLM provider: {name}")
    return provider
