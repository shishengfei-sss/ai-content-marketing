"""LM2 验收：会话摘要 + recall。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import UUID

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.models import TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_EDITOR
from app.services.auth_service import hash_password
from tests.alembic_head import is_at_expected_head
from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def ensure_co_editor(db, tenant_id: UUID, phone: str = "13900007777") -> str:
    password = "Test123456"
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name="LM2同事",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.hashed_password = hash_password(password)
        user.is_active = True
    editor_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_EDITOR)
        .first()
    )
    if not editor_role:
        raise RuntimeError("editor role not found")
    existing = (
        db.query(TenantMembership)
        .filter(TenantMembership.user_id == user.id, TenantMembership.tenant_id == tenant_id)
        .first()
    )
    if existing:
        existing.is_active = True
        existing.role_id = editor_role.id
    else:
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=tenant_id,
                role_id=editor_role.id,
                is_active=True,
            )
        )
    user.tenant_id = tenant_id
    db.commit()
    return phone


def select_tenant(token: str, tenant_id: str) -> str:
    code, me = req("GET", "/auth/me", token=token)
    active_tid = (me.get("active_tenant") or {}).get("id")
    if me.get("need_select_tenant") or str(active_tid) != str(tenant_id):
        code, sel = req("POST", "/auth/select-tenant", token=token, body={"tenant_id": tenant_id})
        if code != 200:
            code, sel = req("POST", "/auth/switch-tenant", token=token, body={"tenant_id": tenant_id})
        if code == 200:
            return sel["access_token"]
    return token


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    db = SessionLocal()
    try:
        return table in inspect(db.bind).get_table_names()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VLM2-1 alembic=022(head)", is_at_expected_head(out), out.strip()))
    results.append(check("VLM2-1 表 agent_session_summaries", table_exists("agent_session_summaries")))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    admin_token = login("13900000099", "test123456")
    code, me = req("GET", "/auth/me", token=admin_token)
    tenant_id = (me.get("active_tenant") or {}).get("id")

    db = SessionLocal()
    try:
        co_phone = ensure_co_editor(db, UUID(str(tenant_id)))
    finally:
        db.close()
    co_token = select_tenant(login(co_phone, "Test123456"), tenant_id)

    code, session = req(
        "POST",
        "/agent/sessions",
        token=admin_token,
        body={"industry_code": "marketing", "title": "LM2摘要测试"},
    )
    sid = session.get("id")
    if not sid:
        print("[FAIL] 创建会话失败")
        return 1

    for role, content in [
        ("user", "帮我写公众号报税提醒"),
        ("assistant", "好的，已生成公众号方案。"),
    ]:
        req(
            "POST",
            f"/agent/sessions/{sid}/messages",
            token=admin_token,
            body={"role": role, "content": content},
        )

    code, summary = req("POST", f"/agent/sessions/{sid}/summary", token=admin_token)
    results.append(
        check(
            "VLM2-2 生成摘要",
            code == 200 and summary.get("summary_text") and "公众号" in summary.get("summary_text", ""),
            summary.get("summary_text", "")[:60],
        )
    )

    code, got = req("GET", f"/agent/sessions/{sid}/summary", token=admin_token)
    results.append(
        check(
            "VLM2-3 GET 摘要",
            code == 200 and got.get("id") == summary.get("id"),
            str(got.get("message_count")),
        )
    )

    req(
        "POST",
        "/agent/memories",
        token=admin_token,
        body={"scope": "user", "fact_text": "偏好公众号长文风格", "category": "style"},
    )
    from tests.http_client import _get_test_client

    client = _get_test_client()
    r = client.get(
        "/api/v1/agent/recall",
        params={"q": "公众号"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    recall = r.json()
    results.append(
        check(
            "VLM2-4 recall 命中摘要/记忆",
            r.status_code == 200
            and (
                any("公众号" in s.get("summary_text", "") for s in recall.get("session_summaries", []))
                or any("公众号" in f.get("fact_text", "") for f in recall.get("memory_facts", []))
            ),
            f"summaries={len(recall.get('session_summaries', []))} facts={len(recall.get('memory_facts', []))}",
        )
    )

    code, _ = req("GET", f"/agent/sessions/{sid}/summary", token=co_token)
    results.append(check("VLM2-5 他人会话摘要404", code == 404, str(code)))

    proc = subprocess.run([sys.executable, "-B", "tests/verify_lm1.py"], cwd=API_ROOT)
    results.append(check("VLM2-6 verify_lm1 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== LM2", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
