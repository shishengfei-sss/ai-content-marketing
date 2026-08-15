#!/usr/bin/env python3
"""A16 角色与成员。对照 PRD 01#a16 · #a16a · §8.7.1。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal, uuid_eq  # noqa: E402
from app.models import TenantMembership, TenantRole, User  # noqa: E402
from app.permissions import SYSTEM_ROLE_ADMIN  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402
from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant, login  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "RolesMembers.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _detail(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    return str(data.get("detail", data))


def _force_admin(phone: str, tenant_id: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.phone == phone).first()
        admin = (
            db.query(TenantRole)
            .filter(uuid_eq(TenantRole.tenant_id, UUID(tenant_id)), TenantRole.code == SYSTEM_ROLE_ADMIN)
            .first()
        )
        assert user and admin
        mem = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.user_id, user.id),
                uuid_eq(TenantMembership.tenant_id, UUID(tenant_id)),
            )
            .first()
        )
        if mem:
            mem.role_id = admin.id
            mem.is_active = True
        else:
            db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=UUID(tenant_id),
                    role_id=admin.id,
                    is_active=True,
                )
            )
        user.hashed_password = hash_password("test123456")
        db.commit()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA16-UI 角色与成员页",
            _page_has(
                WEB,
                "#a16",
                "角色与成员",
                "内置角色",
                "分配成员",
                "权限矩阵",
                "店铺范围",
                "禁用此角色",
            ),
            str(WEB),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    _force_admin("13900000099", tenant_id)
    merchant = login("13900000099", "test123456")

    code, roles = req("GET", "/shop/roles", token=merchant)
    codes = {r.get("code") for r in roles} if isinstance(roles, list) else set()
    results.append(
        check(
            "VA16-1 角色列表含内置",
            code == 200
            and {"admin", "shop_admin", "shop_content", "shop_support", "shop_clerk"} <= codes
            and all("enabled" in r and "member_count" in r for r in roles),
            f"{code} {codes}",
        )
    )

    # 确保 clerk 启用且无人
    clerk = next((r for r in roles if r["code"] == "shop_clerk"), {})
    if clerk and not clerk.get("enabled"):
        req("POST", "/shop/roles/shop_clerk/enable", token=merchant, body={})

    # 清空 clerk 成员（若有）
    code, mems = req("GET", "/shop/members?role_code=shop_clerk", token=merchant)
    for m in (mems.get("items") or []) if code == 200 else []:
        req("DELETE", f"/shop/members/{m['user_id']}", token=merchant)

    code, disabled = req("POST", "/shop/roles/shop_clerk/disable", token=merchant, body={})
    results.append(
        check(
            "VA16-2 禁用店员",
            code == 200 and disabled.get("enabled") is False,
            f"{code} {disabled}",
        )
    )

    code, bad = req(
        "POST",
        "/shop/members",
        token=merchant,
        body={
            "user_id": str(uuid.uuid4()),
            "role_code": "shop_clerk",
            "store_scope": "selected",
            "store_ids": [],
        },
    )
    results.append(
        check(
            "VA16-3 禁用角色不可分配",
            code == 422 and ("角色已禁用" in _detail(bad) or "成员须为企业成员" in _detail(bad)),
            f"{code} {_detail(bad)}",
        )
    )
    # 上面可能先拦成员不存在；再测已存在成员 + 禁用角色
    code, cands = req("GET", "/shop/members/candidates", token=merchant)
    cand_id = (cands.get("items") or [{}])[0].get("user_id") if code == 200 else None
    if cand_id:
        code, bad2 = req(
            "POST",
            "/shop/members",
            token=merchant,
            body={
                "user_id": cand_id,
                "role_code": "shop_clerk",
                "store_scope": "selected",
                "store_ids": [str(uuid.uuid4())],
            },
        )
        results.append(
            check(
                "VA16-3b 禁用角色不可分配(真成员)",
                code == 422 and "角色已禁用" in _detail(bad2),
                f"{code} {_detail(bad2)}",
            )
        )
    else:
        results.append(check("VA16-3b 禁用角色不可分配(真成员)", False, "no candidates"))

    code, enabled = req("POST", "/shop/roles/shop_clerk/enable", token=merchant, body={})
    results.append(
        check(
            "VA16-4 启用店员",
            code == 200 and enabled.get("enabled") is True,
            f"{code} {enabled}",
        )
    )

    code, stores = req("GET", "/shop/stores?page=1&page_size=20", token=merchant)
    shop_id = (stores.get("items") or [{}])[0].get("id") if code == 200 else None
    results.append(check("VA16-5 有店铺可绑", bool(shop_id), str(stores)[:200]))

    # 创建第二成员用于分配
    phone2 = f"139{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        admin_role = (
            db.query(TenantRole)
            .filter(uuid_eq(TenantRole.tenant_id, UUID(tenant_id)), TenantRole.code == "editor")
            .first()
        )
        if not admin_role:
            admin_role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.tenant_id, UUID(tenant_id)))
                .first()
            )
        u2 = User(
            id=uuid.uuid4(),
            phone=phone2,
            display_name="A16联测店员",
            hashed_password=hash_password("test123456"),
            tenant_id=UUID(tenant_id),
        )
        db.add(u2)
        db.flush()
        db.add(
            TenantMembership(
                id=uuid.uuid4(),
                user_id=u2.id,
                tenant_id=UUID(tenant_id),
                role_id=admin_role.id,
                is_active=True,
            )
        )
        db.commit()
        uid2 = str(u2.id)

    code, multi = req(
        "POST",
        "/shop/members",
        token=merchant,
        body={
            "user_id": uid2,
            "role_code": "shop_clerk",
            "store_scope": "selected",
            "store_ids": [shop_id, shop_id] if shop_id else [],
        },
    )
    # duplicate ids still length 1 after pydantic? send two different if needed
    # Better: try with empty and wrong count
    code, multi = req(
        "POST",
        "/shop/members",
        token=merchant,
        body={
            "user_id": uid2,
            "role_code": "shop_clerk",
            "store_scope": "all",
            "store_ids": [],
        },
    )
    results.append(
        check(
            "VA16-6 店员须单店",
            code == 422 and "店员仅能绑定一个店铺" in _detail(multi),
            f"{code} {_detail(multi)}",
        )
    )

    code, assigned = req(
        "POST",
        "/shop/members",
        token=merchant,
        body={
            "user_id": uid2,
            "role_code": "shop_clerk",
            "store_scope": "selected",
            "store_ids": [shop_id],
        },
    )
    results.append(
        check(
            "VA16-7 分配店员成功",
            code == 200
            and assigned.get("role_code") == "shop_clerk"
            and assigned.get("store_scope") == "selected"
            and shop_id in (assigned.get("store_ids") or []),
            f"{code} {assigned}",
        )
    )

    code, block = req("POST", "/shop/roles/shop_clerk/disable", token=merchant, body={})
    results.append(
        check(
            "VA16-8 有成员不可禁用",
            code == 422 and "仍有成员绑定" in _detail(block),
            f"{code} {_detail(block)}",
        )
    )

    code, content = req(
        "PATCH",
        f"/shop/members/{uid2}",
        token=merchant,
        body={"role_code": "shop_content", "store_scope": "all", "store_ids": []},
    )
    results.append(
        check(
            "VA16-9 换绑内容运营",
            code == 200 and content.get("role_code") == "shop_content",
            f"{code} {content}",
        )
    )

    code, removed = req("DELETE", f"/shop/members/{uid2}", token=merchant)
    results.append(
        check(
            "VA16-10 移除商城角色",
            code == 200 and removed.get("ok") is True,
            f"{code} {removed}",
        )
    )

    code, admin_block = req("POST", "/shop/roles/admin/disable", token=merchant, body={})
    results.append(
        check(
            "VA16-11 系统角色不可禁用",
            code == 422 and "系统角色不可操作" in _detail(admin_block),
            f"{code} {_detail(admin_block)}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA16 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
