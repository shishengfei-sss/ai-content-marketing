"""v0.6 通用营销顾问验收默认参数（E-6 回归统一）。"""

from __future__ import annotations

ADVISOR_CODE = "marketing"
DEFAULT_SCENE = "brand_intro"
DEFAULT_TOPIC = "品牌营销内容"


def session_body(title: str, **overrides) -> dict:
    body = {"title": title}
    body.update(overrides)
    return body


def workflow_input(**overrides) -> dict:
    base = {
        "platform": "wechat",
        "topic": DEFAULT_TOPIC,
        "scene": DEFAULT_SCENE,
        "content_format": "article",
        "industry_code": ADVISOR_CODE,
        "llm_source": "platform",
        "search_query": DEFAULT_TOPIC,
    }
    base.update(overrides)
    return base


def proposals_body(**overrides) -> dict:
    base = {
        "industry_code": ADVISOR_CODE,
        "platform": "wechat",
        "scene": DEFAULT_SCENE,
        "topic": DEFAULT_TOPIC,
        "content_format": "article",
        "llm_source": "platform",
    }
    base.update(overrides)
    return base


def generate_body(selected_proposal: dict, **overrides) -> dict:
    base = {
        "industry_code": ADVISOR_CODE,
        "platform": "wechat",
        "scene": DEFAULT_SCENE,
        "topic": DEFAULT_TOPIC,
        "content_format": "article",
        "llm_source": "platform",
        "selected_proposal": selected_proposal,
    }
    base.update(overrides)
    return base
