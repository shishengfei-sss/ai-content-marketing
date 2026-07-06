"""FakeLLM 单元测试。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.services.llm.base import LLMMessage
from app.services.llm.fake import FakeLLMProvider, MOCK_PROPOSALS


async def _run():
    provider = FakeLLMProvider()
    r1 = await provider.chat(
        [LLMMessage(role="system", content="选题策划 JSON 数组")],
        model="fake",
        api_key="x",
        base_url="",
    )
    r2 = await provider.chat(
        [LLMMessage(role="system", content="选题策划 JSON 数组")],
        model="fake",
        api_key="x",
        base_url="",
    )
    assert r1.content == r2.content == MOCK_PROPOSALS
    r3 = await provider.chat(
        [LLMMessage(role="user", content="hello")],
        model="fake",
        api_key="x",
        base_url="",
    )
    assert "测试正文" in r3.content


def test_fake_llm_deterministic():
    asyncio.run(_run())
