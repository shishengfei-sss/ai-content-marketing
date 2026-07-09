"""MM1 验收：记忆管理 API 权限 + Web/H5 页面接入。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

API_ROOT = Path(__file__).resolve().parents[1]
WEB_MEMORY = API_ROOT.parent / "web" / "src" / "views" / "SettingsMemory.vue"
MP_MEMORY = API_ROOT.parent / "mp" / "src" / "pages" / "settings" / "memory.vue"
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.models import TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_EDITOR
from app.services.auth_service import hash_password
from tests.http_client import check, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def ensure_co_editor(db, tenant_id: UUID, phone: str = "13900008888", password: str = "Test123456") -> str:
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name="MM1同事",
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


def main() -> int:
    results: list[bool] = []

    web_text = WEB_MEMORY.read_text(encoding="utf-8") if WEB_MEMORY.is_file() else ""
    mp_text = MP_MEMORY.read_text(encoding="utf-8") if MP_MEMORY.is_file() else ""
    results.append(
        check(
            "VMM1-1 Web SettingsMemory.vue 接 agentApi",
            "agentApi.listMemories" in web_text and "agentApi.deleteMemory" in web_text,
            "ok" if "agentApi.listMemories" in web_text else "missing",
        )
    )
    results.append(
        check(
            "VMM1-2 H5 memory.vue 接 agentApi",
            "agentApi.listMemories" in mp_text and "agentApi.confirmMemory" in mp_text,
            "ok" if "agentApi.listMemories" in mp_text else "missing",
        )
    )

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
    if co_me.get("need_select_tenant"):
        code, sel = req(
            "POST",
            "/auth/select-tenant",
            token=co_token,
            body={"tenant_id": tenant_id},
        )
        if code == 200:
            co_token = sel["access_token"]

    code, tenant_mem = req(
        "POST",
        "/agent/memories",
        token=admin_token,
        body={"scope": "tenant", "fact_text": "MM1企业记忆删除测试", "category": "brand"},
    )
    tenant_mem_id = tenant_mem.get("id")
    results.append(check("VMM1-3 创建 tenant 记忆", code == 200 and tenant_mem_id, str(tenant_mem_id)))

    code, _ = req("DELETE", f"/agent/memories/{tenant_mem_id}", token=co_token)
    results.append(check("VMM1-4 editor 不可删 tenant 记忆", code == 403, str(code)))

    code, _ = req("DELETE", f"/agent/memories/{tenant_mem_id}", token=admin_token)
    code2, _ = req("GET", f"/agent/memories/{tenant_mem_id}", token=admin_token)
    results.append(check("VMM1-5 admin 可删 tenant 记忆", code == 200 and code2 == 404, f"del={code} get={code2}"))

    code, user_mem = req(
        "POST",
        "/agent/memories",
        token=co_token,
        body={"scope": "user", "fact_text": "MM1个人记忆删除测试", "category": "preference"},
    )
    user_mem_id = user_mem.get("id")
    code, _ = req("DELETE", f"/agent/memories/{user_mem_id}", token=co_token)
    results.append(check("VMM1-6 editor 可删本人 user 记忆", code == 200, str(code)))

    code, inferred = req(
        "POST",
        "/agent/memories",
        token=co_token,
        body={
            "scope": "user",
            "fact_text": "MM1推断待确认",
            "source": "inferred",
        },
    )
    inf_id = inferred.get("id")
    results.append(
        check(
            "VMM1-7 推断记忆待确认",
            code == 200 and inferred.get("is_confirmed") is False,
            str(inferred.get("is_confirmed")),
        )
    )
    code, confirmed = req("POST", f"/agent/memories/{inf_id}/confirm", token=co_token)
    results.append(
        check("VMM1-8 用户可确认推断记忆", code == 200 and confirmed.get("is_confirmed") is True, str(code))
    )
    req("DELETE", f"/agent/memories/{inf_id}", token=co_token)

    passed = all(results)
    print("\n=== MM1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
