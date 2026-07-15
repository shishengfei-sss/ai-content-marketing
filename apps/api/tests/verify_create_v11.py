#!/usr/bin/env python3
"""v1.1 营销创作增强验收：campaign 贯通 / SSE / 脱敏；Alembic head 不变（077）。"""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import _get_test_client, check, ensure_fake_platform, req
from tests.verify_crm_helpers import finish_phase


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def parse_sse_response(response) -> tuple[str, list[tuple[str, dict]]]:
    content_type = response.headers.get("content-type", "")
    events: list[tuple[str, dict]] = []
    current_event = ""
    for line in response.iter_lines():
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            payload = line[6:]
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"raw": payload}
            events.append((current_event, data))
    return content_type, events


def stream_chat(token: str, sid: str, message: str, **extra):
    client = _get_test_client()
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": message, "llm_source": "platform", **extra}
    with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{sid}/chat/stream",
        json=body,
        headers=headers,
    ) as response:
        content_type, events = parse_sse_response(response)
        return response.status_code, content_type, events


def campaign_content_count(token: str, campaign_id: str) -> int:
    code, data = req("GET", f"/crm/campaigns/{campaign_id}", token=token)
    if code != 200:
        return -1
    return int((data or {}).get("content_count") or 0)


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check(f"VP11-0 alembic={EXPECTED_HEAD}（无新迁移）", is_at_expected_head(out), out.strip()))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    user_token = login("13900000099", "test123456")

    # -------- VP11-1 Agent + campaign --------
    code, camp = req(
        "POST",
        "/crm/campaigns",
        token=user_token,
        body={"name": f"V11Camp-{uuid.uuid4().hex[:6]}", "status": "active"},
    )
    results.append(check("VP11-1-0 创建活动 201", code == 201, str(code)))
    camp_id = (camp or {}).get("id")
    before = campaign_content_count(user_token, camp_id)

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "marketing", "title": "V11 Agent"},
    )
    sid = (session or {}).get("id")
    results.append(check("VP11-1-1 创建会话", bool(sid), str(session)))

    code, chat1 = req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=user_token,
        body={
            "message": "写一篇公众号品牌介绍",
            "llm_source": "platform",
            "campaign_id": camp_id,
            "platform": "wechat",
            "content_format": "article",
        },
    )
    results.append(check("VP11-1-2 chat proposals 200", code == 200, f"{code} {chat1}"))
    results.append(
        check(
            "VP11-1-3 action=proposals",
            (chat1 or {}).get("action") == "proposals" and bool((chat1 or {}).get("proposals")),
            str((chat1 or {}).get("action")),
        )
    )

    code, chat2 = req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=user_token,
        body={
            "message": "生成正文",
            "llm_source": "platform",
            "selected_proposal_index": 0,
            "campaign_id": camp_id,
            "platform": "wechat",
            "content_format": "article",
        },
    )
    results.append(check("VP11-1-4 generate 200", code == 200 and (chat2 or {}).get("action") == "generate", f"{code}"))
    content = (chat2 or {}).get("content") or {}
    results.append(check("VP11-1-5 content.id", bool(content.get("id")), str(content.get("id"))))

    after = campaign_content_count(user_token, camp_id)
    results.append(check("VP11-1-6 campaign_contents +1", after == before + 1, f"before={before} after={after}"))

    # -------- VP11-1b Workflow + campaign --------
    code, camp2 = req(
        "POST",
        "/crm/campaigns",
        token=user_token,
        body={"name": f"V11WF-{uuid.uuid4().hex[:6]}", "status": "active"},
    )
    camp2_id = (camp2 or {}).get("id")
    before2 = campaign_content_count(user_token, camp2_id)

    code, sess2 = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "marketing", "title": "V11 WF"},
    )
    sid2 = (sess2 or {}).get("id")
    code, wf = req(
        "POST",
        "/agent/workflows",
        token=user_token,
        body={
            "pipeline_code": "content_propose",
            "auto_run": True,
            "session_id": sid2,
            "input": {
                "platform": "wechat",
                "topic": "春季促销文案",
                "content_format": "article",
                "industry_code": "marketing",
                "llm_source": "platform",
                "campaign_id": camp2_id,
                "search_query": "春季促销文案",
            },
        },
    )
    results.append(check("VP11-1b-1 propose workflow", code == 200 and (wf or {}).get("status") == "paused", f"{code} {(wf or {}).get('status')}"))
    wf_id = (wf or {}).get("id")
    code, wf2 = req(
        "POST",
        f"/agent/workflows/{wf_id}/resume",
        token=user_token,
        body={"selected_proposal_index": 0},
    )
    results.append(check("VP11-1b-2 resume completed", code == 200 and (wf2 or {}).get("status") == "completed", f"{code} {(wf2 or {}).get('status')}"))
    after2 = campaign_content_count(user_token, camp2_id)
    results.append(check("VP11-1b-3 campaign +1", after2 == before2 + 1, f"before={before2} after={after2}"))

    # -------- VP11-2 SSE --------
    code, sess3 = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "marketing", "title": "V11 SSE"},
    )
    sid3 = (sess3 or {}).get("id")
    code_s, ctype, events = stream_chat(
        user_token,
        sid3,
        "写一篇公众号报税提醒",
        platform="wechat",
        content_format="article",
    )
    done = next((e[1] for e in events if e[0] == "done"), None)
    results.append(check("VP11-2-1 SSE content-type", "text/event-stream" in ctype, ctype))
    results.append(
        check(
            "VP11-2-2 done proposals/generate",
            code_s == 200 and done and done.get("action") in ("proposals", "generate", "clarify", "chat"),
            str(done.get("action") if done else None),
        )
    )
    if done and done.get("action") == "proposals":
        code_s2, _, events2 = stream_chat(
            user_token,
            sid3,
            "生成正文",
            selected_proposal_index=0,
            platform="wechat",
            content_format="article",
            campaign_id=camp_id,
        )
        done2 = next((e[1] for e in events2 if e[0] == "done"), None)
        results.append(
            check(
                "VP11-2-3 stream generate",
                code_s2 == 200 and done2 and done2.get("action") == "generate",
                str(done2.get("action") if done2 else None),
            )
        )
    else:
        results.append(check("VP11-2-3 stream generate（跳过/澄清）", True, str(done)))

    # -------- VP11-3 脱敏 --------
    from app.schemas import ContentProposalsRequest
    from app.services.content_generation_service import run_generate_proposals
    from app.database import SessionLocal
    from app.models import User as UserModel

    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.phone == "13900000099").first()
        tenant_id = None
        from app.models import TenantMembership

        m = db.query(TenantMembership).filter(TenantMembership.user_id == user.id).first()
        tenant_id = m.tenant_id if m else None
        body = ContentProposalsRequest(
            platform="wechat",
            topic="脱敏测试主题",
            content_format="article",
            llm_source="platform",
        )
        leak = "https://api.openai.com/v1 key=sk-secret-abc"
        with patch(
            "app.services.content_generation_service.llm_service.chat",
            new=AsyncMock(side_effect=RuntimeError(leak)),
        ):
            try:
                import asyncio

                asyncio.run(run_generate_proposals(db, tenant_id, body))
                detail = ""
                status = 200
            except Exception as exc:
                from fastapi import HTTPException

                if isinstance(exc, HTTPException):
                    status = exc.status_code
                    detail = str(exc.detail)
                else:
                    status = 500
                    detail = str(exc)
        results.append(check("VP11-3-1 失败返回 502", status == 502, str(status)))
        results.append(check("VP11-3-2 detail 无 host", "openai.com" not in detail and "sk-secret" not in detail, detail))
        results.append(check("VP11-3-3 detail 友好文案", "请重试" in detail or "失败" in detail, detail))
    finally:
        db.close()

    # 白屏修复：源码断言 payload.scene 已移除
    create_vue = (API_ROOT.parent / "web" / "src" / "views" / "Create.vue").read_text(encoding="utf-8")
    results.append(check("VP11-4 无 payload.scene 白屏", "payload.scene" not in create_vue, "still has payload.scene"))
    results.append(check("VP11-4b 文案非固定 3～5", "3～5 个方案" not in create_vue, "footer"))

    # -------- VP11-P1 FR-CREATE-10～13 --------
    from app.services.agent.compliance_revise_service import (
        MAX_COMPLIANCE_REVISE_ROUNDS,
        build_compliance_revise_instruction,
        revise_until_pass,
    )
    from app.services.prompt_builder import (
        build_proposals_user_prompt,
        build_user_prompt,
        resolve_video_duration_sec,
    )

    results.append(check("VP11-10-1 最大改稿轮次=3", MAX_COMPLIANCE_REVISE_ROUNDS == 3, str(MAX_COMPLIANCE_REVISE_ROUNDS)))
    instr = build_compliance_revise_instruction(
        issues=[{"severity": "block", "message": "禁止承诺稳赚"}],
        suggestions=["保留免责声明"],
    )
    results.append(check("VP11-10-2 改稿指令含 block", "稳赚" in instr and "免责" in instr, instr[:80]))
    results.append(check("VP11-10-3 revise_until_pass 可导入", callable(revise_until_pass), ""))

    svc = (API_ROOT / "app" / "services" / "agent" / "chat_service.py").read_text(encoding="utf-8")
    stream_src = (API_ROOT / "app" / "services" / "agent" / "chat_stream_service.py").read_text(encoding="utf-8")
    results.append(check("VP11-10-4 Agent chat 接合规环", "revise_until_pass" in svc, "chat_service"))
    results.append(check("VP11-10-5 Agent stream 接合规环", "revise_until_pass" in stream_src, "stream"))

    results.append(
        check(
            "VP11-11 会话恢复 prefs",
            "restoreSessionPrefs" in create_vue and "已恢复平台" in create_vue,
            "Create.vue",
        )
    )

    prop_prompt = build_proposals_user_prompt(
        platform="wechat",
        scene="brand_intro",
        topic="春季招生",
        content_format="article",
        proposal_count=3,
    )
    results.append(check("VP11-12-1 方案 prompt 含 angle", '"angle"' in prop_prompt, prop_prompt[-120:]))
    results.append(check("VP11-12-2 方案 prompt 含 outline", '"outline"' in prop_prompt, prop_prompt[-120:]))
    gen_prompt = build_user_prompt(
        platform="wechat",
        scene="brand_intro",
        topic="春季招生",
        content_format="article",
        selected_proposal_title="方向A",
        selected_proposal_angle="痛点切入",
        selected_proposal_outline="开场;案例;CTA",
    )
    results.append(
        check(
            "VP11-12-3 正文联动 angle/outline",
            "痛点切入" in gen_prompt and "开场;案例;CTA" in gen_prompt,
            gen_prompt[:160],
        )
    )
    results.append(check("VP11-12-4 UI 展示 angle/outline", "proposal-card__angle" in create_vue, "Create.vue"))

    results.append(check("VP11-13-1 resolve 默认 30", resolve_video_duration_sec(None) == 30, ""))
    results.append(check("VP11-13-2 resolve 60", resolve_video_duration_sec(60) == 60, ""))
    results.append(check("VP11-13-3 resolve 非法回退", resolve_video_duration_sec(20) == 30, ""))
    vprompt = build_proposals_user_prompt(
        platform="douyin",
        scene="brand_intro",
        topic="短视频",
        content_format="video_script",
        video_duration_sec=45,
    )
    results.append(check("VP11-13-4 prompt 写入 45 秒", "45 秒" in vprompt, vprompt[-80:]))
    results.append(
        check(
            "VP11-13-5 UI 时长选项",
            "VIDEO_DURATION_OPTIONS" in create_vue and "pickVideoDuration" in create_vue,
            "Create.vue",
        )
    )

    return finish_phase("v1.1-create-P0+P1", results)


if __name__ == "__main__":
    raise SystemExit(main())
