"""可编程 Fake LLM，用于 Agent 自动测试（无外网）。"""

from __future__ import annotations

import json

from app.services.llm.base import LLMMessage, LLMProvider, LLMResponse

MOCK_PROPOSALS = json.dumps(
    [
        {"title": "测试方案 A", "angle": "角度A", "outline": "大纲A"},
        {"title": "测试方案 B", "angle": "角度B", "outline": "大纲B"},
        {"title": "测试方案 C", "angle": "角度C", "outline": "大纲C"},
    ],
    ensure_ascii=False,
)


def _extract_proposal_topic(user_text: str) -> str:
    for marker in ("用户选题：", "主题是", "主题：", "选题："):
        if marker in user_text:
            line = user_text.split(marker, 1)[1].split("\n")[0].strip()
            if line and line not in ("...", "…"):
                return line[:80]
    for line in user_text.splitlines():
        text = line.strip()
        if len(text) >= 4 and not text.startswith("请为"):
            return text[:80]
    return "营销内容"


def _build_mock_proposals(user_text: str, *, count: int = 3) -> str:
    """对齐选题 prompt：仅 title 字段，一句话创作方向。"""
    topic = _extract_proposal_topic(user_text)
    platform = "小红书" if ("小红书" in user_text or "xhs" in user_text) else "公众号"
    if "抖音" in user_text or "douyin" in user_text:
        platform = "抖音"
    angles = [
        f"用真实客户故事切入{topic}，突出前后变化与可复用经验",
        f"以从业者第一视角拆解{topic}的关键步骤与常见误区",
        f"用对比清单呈现{topic}的亮点，适合{platform}读者快速扫读",
        f"从目标受众痛点出发，讲清为什么现在需要关注{topic}",
        f"结合节日/热点氛围包装{topic}，强调情绪共鸣与行动引导",
    ]
    items = [{"title": a[:40]} for a in angles[: max(3, min(count, 5))]]
    while len(items) < 3:
        items.append({"title": f"围绕{topic[:20]}给出另一种{platform}创作切入点"[:40]})
    return json.dumps(items[:count if count >= 3 else 3], ensure_ascii=False)
MOCK_ARTICLE = "测试正文\n\n本文仅供参考，具体政策以税务机关最新规定为准。"
MOCK_REVISED = "测试改稿正文\n\n本文仅供参考，具体政策以税务机关最新规定为准。"
MOCK_PAIN_ANALYSIS = json.dumps(
    {
        "pain_points": ["担心错过报税期", "不了解最新政策"],
        "target_audience": "小微企业主",
        "analysis_summary": "用户需要及时、易懂的报税提醒。",
        "writing_guidance": "聚焦时效性与操作步骤，先分析痛点勿写正文。",
    },
    ensure_ascii=False,
)
MOCK_STRATEGY = json.dumps(
    {
        "proposals": [
            {"title": "测试方案 A", "angle": "角度A", "outline": "大纲A"},
            {"title": "测试方案 B", "angle": "角度B", "outline": "大纲B"},
            {"title": "测试方案 C", "angle": "角度C", "outline": "大纲C"},
        ],
        "selected_index": 0,
        "selection_rationale": "方案 A 直击报税焦虑，标题清晰易传播。",
    },
    ensure_ascii=False,
)
MOCK_SEO = json.dumps(
    {
        "title_candidates": [
            "小微企业报税提醒：别错过申报期",
            "2026 财税合规指南：申报要点一览",
            "老板必看：记账报税省心攻略",
        ],
        "tags": ["财税", "公众号", "报税提醒", "合规"],
    },
    ensure_ascii=False,
)


def _intent_json(action: str, **kwargs) -> str:
    payload = {"action": action, "scene": "brand_intro", "topic": "", "clarify_question": None}
    payload.update(kwargs)
    return json.dumps(payload, ensure_ascii=False)


class FakeLLMProvider(LLMProvider):
    provider_name = "fake"

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_sec: int = 60,
    ) -> LLMResponse:
        system_text = " ".join(m.content for m in messages if m.role == "system")
        user_text = messages[-1].content if messages else ""
        convo_text = " ".join(m.content for m in messages)

        if "创作预检" in system_text:
            if "你好" in user_text and len(user_text.strip()) < 12:
                content = json.dumps(
                    {"action": "clarify", "topic": "", "clarify_question": "请说明具体创作主题与目标读者。"},
                    ensure_ascii=False,
                )
            elif user_text.strip() in ("写脚本", "帮我写", "写一篇", "写一下"):
                content = json.dumps(
                    {
                        "action": "clarify",
                        "topic": "",
                        "clarify_question": "请补充具体主题、受众或核心要点。",
                    },
                    ensure_ascii=False,
                )
            else:
                content = json.dumps(
                    {"action": "proceed", "topic": "税务合规营销内容", "clarify_question": None},
                    ensure_ascii=False,
                )
        elif "意图解析" in system_text:
            if "帮我写点东西" in user_text:
                content = _intent_json("clarify", clarify_question="请问要发布到哪个平台？")
            elif "抖音文章" in user_text or ("douyin" in user_text.lower() and "article" in user_text.lower()):
                content = _intent_json(
                    "proposals",
                    platform="douyin",
                    content_format="article",
                    topic="抖音文章测试",
                )
            elif "生成正文" in user_text or "选定方案" in user_text or "selected_proposal_index" in user_text:
                content = _intent_json(
                    "generate",
                    platform="wechat",
                    content_format="article",
                    topic="报税提醒",
                    selected_proposal_index=0,
                )
            elif "公众号" in user_text or "报税" in user_text:
                content = _intent_json(
                    "proposals",
                    platform="wechat",
                    content_format="article",
                    topic="报税提醒",
                )
            else:
                content = _intent_json("chat", topic=user_text[:100])
        elif "选题策划" in system_text or "JSON 数组" in system_text:
            import re

            m = re.search(r"恰好\s*(\d+)\s*个", user_text)
            count = int(m.group(1)) if m else 3
            m2 = re.search(r"(\d+)\s*到\s*(\d+)\s*个", user_text)
            if m2 and not m:
                count = int(m2.group(1))
            content = _build_mock_proposals(user_text, count=max(3, count))
        elif "Agent ReAct" in system_text or "ReAct 编排器" in system_text:
            import re

            m = re.search(r"已完成工具结果数=(\d+)", convo_text)
            tool_results = int(m.group(1)) if m else convo_text.count("工具结果:")
            if "INFINITE_LOOP_TEST" in convo_text or "会话目标=INFINITE_LOOP_TEST" in convo_text:
                content = json.dumps({"step": "tool_call", "tool": "get_quota", "arguments": {}})
            elif "先查知识库" in convo_text and tool_results == 0:
                content = json.dumps(
                    {
                        "step": "tool_call",
                        "tool": "search_knowledge",
                        "arguments": {"query": "小红书种草"},
                    },
                    ensure_ascii=False,
                )
            elif "先查知识库" in convo_text and tool_results == 1:
                content = json.dumps(
                    {
                        "step": "tool_call",
                        "tool": "generate_proposals",
                        "arguments": {
                            "platform": "xhs",
                            "scene": "brand_intro",
                            "topic": "品牌种草笔记",
                            "content_format": "note",
                            "llm_source": "platform",
                        },
                    },
                    ensure_ascii=False,
                )
            elif "先查知识库" in convo_text and tool_results >= 2:
                content = json.dumps(
                    {
                        "step": "done",
                        "action": "proposals",
                        "message": "已检索知识库并生成小红书方案。",
                    },
                    ensure_ascii=False,
                )
            else:
                content = json.dumps(
                    {"step": "done", "action": "chat", "message": "ReAct 测试完成。"},
                    ensure_ascii=False,
                )
        elif "营销内容策略分析师" in system_text or "不要撰写正文" in system_text:
            content = MOCK_PAIN_ANALYSIS
        elif "营销选题策略师" in system_text or "selected_index" in system_text:
            content = MOCK_STRATEGY
        elif "内容质检编辑" in system_text:
            content = MOCK_REVISED
        elif "SEO 优化" in system_text or "SEO 优化助手" in system_text:
            content = MOCK_SEO
        elif "合规审查" in system_text or "合规审查员" in system_text:
            if "绝对保证" in user_text or "100%成功" in user_text:
                content = json.dumps(
                    {
                        "status": "block",
                        "issues": [
                            {
                                "code": "FORBIDDEN_CLAIM",
                                "severity": "block",
                                "message": "含违规承诺用语",
                            }
                        ],
                        "suggestions": ["请删除夸大承诺用语"],
                    },
                    ensure_ascii=False,
                )
            elif "仅供参考" not in user_text and "以税务机关最新规定为准" not in user_text:
                content = json.dumps(
                    {
                        "status": "warn",
                        "issues": [
                            {
                                "code": "MISSING_DISCLAIMER",
                                "severity": "warn",
                                "message": "缺少免责声明",
                            }
                        ],
                        "suggestions": ["建议补充免责声明"],
                    },
                    ensure_ascii=False,
                )
            else:
                content = json.dumps(
                    {"status": "pass", "issues": [], "suggestions": []},
                    ensure_ascii=False,
                )
        elif "编辑助手" in system_text or "修改指令" in user_text:
            content = MOCK_REVISED
        elif "会话摘要" in system_text or "摘要助手" in system_text:
            content = json.dumps(
                {
                    "summary": "用户讨论了公众号报税提醒内容创作。",
                    "topics": ["公众号", "报税提醒"],
                },
                ensure_ascii=False,
            )
        elif "clarify" in user_text.lower() or user_text.strip() in ("", "帮我写点东西"):
            content = json.dumps(
                {"action": "clarify", "clarify_question": "请问要发布到哪个平台？"},
                ensure_ascii=False,
            )
        else:
            content = MOCK_ARTICLE
        return LLMResponse(content=content, model=model or "fake-model", provider=self.provider_name)

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
