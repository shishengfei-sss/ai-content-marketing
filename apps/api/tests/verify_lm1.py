"""LM1 验收：Agent 长期记忆 CRUD + scope 隔离。"""
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
from tests.http_client import check, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def ensure_co_editor(db, tenant_id: UUID, phone: str = "13900007777", password: str = "Test123456") -> str:
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name="LM1同事",
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
        raise RuntimeError("editor role not found for tenant")
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
    results.append(check("VLM1-1 alembic=022(head)", is_at_expected_head(out), out.strip()))
    results.append(check("VLM1-1 表 agent_memory_facts", table_exists("agent_memory_facts")))

    admin_token = login("13900000099", "test123456")
    code, me = req("GET", "/auth/me", token=admin_token)
    tenant_id = (me.get("active_tenant") or {}).get("id")

    db = SessionLocal()
    try:
        co_phone = ensure_co_editor(db, UUID(str(tenant_id)))
    finally:
        db.close()
    co_token = login(co_phone, "Test123456")
    code, co_me = req("GET", "/auth/me", token=co_token)
    active_tid = (co_me.get("active_tenant") or {}).get("id")
    if co_me.get("need_select_tenant") or str(active_tid) != str(tenant_id):
        code, sel = req(
            "POST",
            "/auth/select-tenant",
            token=co_token,
            body={"tenant_id": tenant_id},
        )
        if code != 200:
            code, sel = req(
                "POST",
                "/auth/switch-tenant",
                token=co_token,
                body={"tenant_id": tenant_id},
            )
        if code == 200:
            co_token = sel["access_token"]

    code, user_mem = req(
        "POST",
        "/agent/memories",
        token=admin_token,
        body={"scope": "user", "fact_text": "偏爱公众号长文", "category": "style"},
    )
    user_mem_id = user_mem.get("id")
    results.append(
        check(
            "VLM1-2 创建 user 记忆",
            code == 200 and user_mem.get("scope") == "user" and user_mem.get("user_id"),
            str(user_mem)[:80],
        )
    )

    code, user_list = req("GET", "/agent/memories?scope=user", token=admin_token)
    results.append(
        check(
            "VLM1-3 本人可见 user 记忆",
            code == 200 and any(m.get("id") == user_mem_id for m in (user_list or [])),
            str(len(user_list) if isinstance(user_list, list) else code),
        )
    )

    code, _ = req("GET", f"/agent/memories/{user_mem_id}", token=co_token)
    results.append(check("VLM1-4 同事不可见 user 记忆", code == 404, str(code)))

    code, tenant_mem = req(
        "POST",
        "/agent/memories",
        token=admin_token,
        body={"scope": "tenant", "fact_text": "公司主打代理记账", "category": "brand"},
    )
    tenant_mem_id = tenant_mem.get("id")
    results.append(check("VLM1-5 创建 tenant 记忆", code == 200 and tenant_mem.get("scope") == "tenant", str(tenant_mem_id)))

    code, co_tenant_list = req("GET", "/agent/memories?scope=tenant", token=co_token)
    results.append(
        check(
            "VLM1-6 同事可见 tenant 记忆",
            code == 200 and any(m.get("id") == tenant_mem_id for m in (co_tenant_list or [])),
            str(len(co_tenant_list) if isinstance(co_tenant_list, list) else code),
        )
    )

    pa_token = login("13800000000", "admin123456")
    code, _ = req("GET", f"/agent/memories/{tenant_mem_id}", token=pa_token)
    results.append(check("VLM1-7 平台管理员不可读", code == 403, str(code)))

    code, updated = req(
        "PATCH",
        f"/agent/memories/{user_mem_id}",
        token=admin_token,
        body={"fact_text": "偏爱公众号+小红书"},
    )
    results.append(check("VLM1-8 PATCH 更新", code == 200 and "小红书" in updated.get("fact_text", ""), updated.get("fact_text", "")[:40]))

    code, _ = req("DELETE", f"/agent/memories/{user_mem_id}", token=admin_token)
    code2, _ = req("GET", f"/agent/memories/{user_mem_id}", token=admin_token)
    results.append(check("VLM1-9 DELETE", code == 200 and code2 == 404, f"del={code} get={code2}"))

    proc = subprocess.run([sys.executable, "-B", "tests/verify_b4.py"], cwd=API_ROOT)
    results.append(check("VLM1-10 verify_b4 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== LM1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
