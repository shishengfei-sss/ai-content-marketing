from app.services.llm.base import LLMProvider
from app.services.llm.openai_compatible import DashScopeProvider, DeepSeekProvider, OpenAICompatibleProvider

PROVIDERS: dict[str, LLMProvider] = {
    "deepseek": DeepSeekProvider(),
    "openai_compatible": OpenAICompatibleProvider(),
    "dashscope": DashScopeProvider(),
}


def get_provider(name: str) -> LLMProvider:
    provider = PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Unsupported LLM provider: {name}")
    return provider
