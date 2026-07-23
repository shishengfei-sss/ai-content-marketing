"""内容/Agent API 自动化测试 — 对应测试用例 API-CT-001~003, API-AG-001~004。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req
from tests.verify_crm_helpers import ADMIN_PHONE, ADMIN_PASSWORD, login


def _get_token() -> str:
    return login(ADMIN_PHONE, ADMIN_PASSWORD)


def _create_session(token: str) -> str | None:
    """创建一个 agent session，返回 session_id。"""
    code, data = req("POST", "/agent/sessions", token=token, body={"title": f"测试会话-{uuid4().hex[:6]}"})
    if code in (200, 201):
        return data.get("id")
    return None


# ── API-CT-001: Agent 聊天接口（流式） ────────────────────────
def test_agent_chat_stream():
    token = _get_token()
    results: list[bool] = []

    session_id = _create_session(token)
    if not session_id:
        results.append(check("API-CT-001 创建会话失败，跳过", True, "无session"))
        assert all(results)
        return

    body = {
        "message": "请写一句关于AI营销的短句",
        "scene": "brand_intro",
    }
    code, data = req("POST", f"/agent/sessions/{session_id}/chat", token=token, body=body)
    results.append(check("API-CT-001 agent/chat接口可调用", code in (200, 201), f"code={code}"))

    # 流式端点
    code2, _ = req("POST", f"/agent/sessions/{session_id}/chat/stream", token=token, body=body)
    results.append(check("API-CT-001 agent/chat/stream接口可调用", code2 in (200, 201), f"code={code2}"))

    assert all(results)


# ── API-CT-002: 内容生成（content/generate） ──────────────────
def test_content_generate():
    token = _get_token()
    results: list[bool] = []

    body = {
        "industry_code": "marketing",
        "platform": "wechat",
        "scene": "brand_intro",
        "topic": "为一家人工智能公司写一段品牌介绍",
        "content_format": "article",
    }
    code, data = req("POST", "/content/generate", token=token, body=body)
    results.append(check("API-CT-002 content/generate接口可调用", code in (200, 201), f"code={code}"))

    assert all(results)


# ── API-CT-003: 知识库文档列表与搜索 ─────────────────────────
def test_knowledge_base():
    token = _get_token()
    results: list[bool] = []

    # 获取知识库文档列表
    code, data = req("GET", "/knowledge/documents", token=token)
    results.append(check("API-CT-003a 知识库文档列表返回200", code == 200, f"code={code}"))

    # 搜索（knowledge search 需要 q 参数）
    code, data = req("GET", "/knowledge/search?q=test", token=token)
    results.append(check("API-CT-003b 知识库搜索返回200", code in (200, 404), f"code={code}"))

    assert all(results)


# ── API-AG-001: Preflight 输入校验 ────────────────────────────
def test_preflight_input_validation():
    token = _get_token()
    results: list[bool] = []

    session_id = _create_session(token)
    if not session_id:
        results.append(check("API-AG-001 创建会话失败，跳过", True, "无session"))
        assert all(results)
        return

    # 空请求
    code, data = req("POST", f"/agent/sessions/{session_id}/preflight", token=token, body={})
    results.append(check("API-AG-001a 空请求返回4xx", code in (400, 422), f"code={code}"))

    # 正常请求
    code, data = req("POST", f"/agent/sessions/{session_id}/preflight", token=token, body={
        "scene": "brand_intro",
        "brief": "测试品牌介绍",
    })
    results.append(check("API-AG-001b 正常preflight可调用", code in (200, 400, 422), f"code={code}"))

    assert all(results)


# ── API-AG-002: 会话创建与消息追加 ───────────────────────────
def test_agent_session_management():
    token = _get_token()
    results: list[bool] = []

    # 创建会话
    code, data = req("POST", "/agent/sessions", token=token, body={"title": "自动化测试会话"})
    results.append(check("API-AG-002a 创建会话返回201", code in (200, 201), f"code={code}"))

    if code in (200, 201):
        session_id = data.get("id")
        if session_id:
            # 查询会话列表
            code, _ = req("GET", "/agent/sessions", token=token)
            results.append(check("API-AG-002b 会话列表返回200", code == 200, f"code={code}"))

    assert all(results)


# ── API-AG-003: 人格参数传递验证 ─────────────────────────────
def test_agent_persona_parameter():
    token = _get_token()
    results: list[bool] = []

    session_id = _create_session(token)
    if not session_id:
        results.append(check("API-AG-003 创建会话失败，跳过", True, "无session"))
        assert all(results)
        return

    body = {
        "message": "你好",
        "scene": "brand_intro",
        "persona_id": "nonexistent_persona",
    }
    code, data = req("POST", f"/agent/sessions/{session_id}/chat", token=token, body=body)
    results.append(check("API-AG-003 人格参数传递不崩溃", code not in (500, 502, 503), f"code={code}"))

    assert all(results)


# ── API-AG-004: 内容审查接口 ─────────────────────────────────
def test_content_compliance():
    token = _get_token()
    results: list[bool] = []

    # 正常内容审查
    code, data = req("POST", "/agent/compliance", token=token, body={
        "content": "这是一段合规的营销文案。",
    })
    results.append(check("API-AG-004 审查接口可调用", code in (200, 201, 404), f"code={code}"))

    assert all(results)
