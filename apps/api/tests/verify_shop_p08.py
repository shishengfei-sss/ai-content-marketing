#!/usr/bin/env python3
"""P08 角色与编码。对照 PRD 06#p08 · #p08a · #p08b · #p08f · TC-P08-F01/F02/E01。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "RolesAndCodes.vue"
USERS = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "AdminUsers.vue"


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = req("POST", "/auth/login", body=body)
    assert code == 200, data
    return data["access_token"]


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _err(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    if isinstance(d, list):
        return " ".join(str(x) for x in d)
    return str(d)


def _ensure_cs_user() -> tuple[str, str]:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    phone = "13800000088"
    password = "cs12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城管家测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.platform_shop_permissions = None
            u.hashed_password = hash_password(password)
        db.commit()
        uid = str(u.id)
    finally:
        db.close()
    return login(phone, password, "platform"), uid


def _ensure_finance_user() -> str:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_FINANCE
    from app.services.auth_service import hash_password

    phone = "13800000077"
    password = "fin12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城财务测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_FINANCE,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_FINANCE
            u.hashed_password = hash_password(password)
            u.is_active = True
        db.commit()
    finally:
        db.close()
    return login(phone, password, "platform")


def main() -> int:
    results: list[bool] = []
    page_text = WEB.read_text(encoding="utf-8") if WEB.is_file() else ""
    results.append(
        check(
            "VP08-UI 角色页文案",
            _page_has(
                WEB,
                "#p08a",
                "#p08f",
                "平台超管",
                "日常运营",
                "商家管家",
                "财务结算",
                "查看权限",
                "绑定账号",
                "编码规则",
                "恢复全部默认",
                "entity_type",
                "列设置",
                "导出",
                "刷新预览",
                "data-testid=\"shop-roles-codes\"",
            )
            and "客服" not in page_text,
            str(WEB),
        )
    )
    results.append(
        check(
            "VP08-UI-AU 账号管理商城列",
            _page_has(
                USERS,
                "账号角色",
                "编辑商城权限",
                "data-testid=\"shop-edit-shop-perms\"",
                "变更记录",
                "data-testid=\"shop-perm-audit-timeline\"",
            ),
            str(USERS),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    cs, cs_id = _ensure_cs_user()

    code, catalog = req("GET", "/admin/shop/permissions/catalog", token=admin)
    perms = catalog.get("permissions") or []
    roles = catalog.get("roles") or []
    templates = catalog.get("role_templates") or []
    results.append(
        check(
            "TC-P08-F01 Catalog 数量",
            code == 200 and len(perms) == 19,
            f"{code} n={len(perms)}",
        )
    )
    results.append(
        check(
            "VP08-1 四角色+三模板",
            len(roles) == 4
            and set(templates) == {"platform_shop_ops", "platform_shop_cs", "platform_shop_finance"}
            and {r.get("name") for r in roles} == {"平台超管", "日常运营", "商家管家", "财务结算"},
            f"roles={[(r.get('name'), r.get('code')) for r in roles]}",
        )
    )

    cs_role = next((r for r in roles if r.get("code") == "platform_shop_cs"), {})
    cs_defaults = set(cs_role.get("default_permissions") or [])
    results.append(
        check(
            "TC-P08-F02 管家默认权",
            "platform.shop.onboarding.initiate" in cs_defaults
            and "platform.shop.subscription.manage" not in cs_defaults,
            str(sorted(cs_defaults)),
        )
    )
    results.append(
        check(
            "VP08-2 管家矩阵无审核/开通",
            any(
                row.get("code") == "platform.shop.approve" and row.get("granted") is False
                for row in (cs_role.get("matrix") or [])
            )
            and any(
                row.get("code") == "platform.shop.onboarding.initiate" and row.get("granted") is True
                for row in (cs_role.get("matrix") or [])
            ),
            str(cs_role.get("matrix")),
        )
    )

    code, forbidden = req(
        "PATCH",
        f"/admin/users/{cs_id}",
        token=cs,
        body={"platform_shop_role": "platform_shop_ops"},
    )
    results.append(
        check(
            "TC-P08-E01 无授权权改角色",
            code == 403 and "无账号管理权限" in _err(forbidden),
            f"{code} {_err(forbidden)}",
        )
    )

    code, bound = req(
        "PATCH",
        f"/admin/users/{cs_id}",
        token=admin,
        body={"platform_shop_role": "platform_shop_cs"},
    )
    results.append(
        check(
            "VP08-3 超管可绑定管家",
            code == 200 and bound.get("platform_shop_role") == "platform_shop_cs",
            f"{code} {bound.get('platform_shop_role')}",
        )
    )

    slim = [p for p in cs_defaults if p != "platform.shop.merchant.tag"]
    code, tuned = req(
        "PATCH",
        f"/admin/users/{cs_id}",
        token=admin,
        body={
            "platform_shop_role": "platform_shop_cs",
            "platform_shop_permissions": slim,
        },
    )
    results.append(
        check(
            "VP08-4 微调收回 tag",
            code == 200 and "platform.shop.merchant.tag" not in (tuned.get("platform_shop_permissions") or []),
            f"{code} {tuned.get('platform_shop_permissions')}",
        )
    )
    code, audits = req("GET", f"/admin/users/{cs_id}/shop-permission-audits", token=admin)
    items = audits.get("items") or []
    latest = items[0] if items else {}
    summary = str(latest.get("summary") or "")
    results.append(
        check(
            "VP08-4b 保存写变更记录",
            code == 200
            and latest.get("action") == "tune_permissions"
            and latest.get("action_label") == "微调权限"
            and "收回" in summary
            and "挂接已有标签" in summary
            and bool(latest.get("operator_name")),
            f"{code} n={len(items)} latest={latest}",
        )
    )
    code, cs_audits = req("GET", f"/admin/users/{cs_id}/shop-permission-audits", token=cs)
    results.append(
        check(
            "VP08-4c 管家不可查变更记录",
            code == 403 and "无账号管理权限" in _err(cs_audits),
            f"{code} {_err(cs_audits)}",
        )
    )
    code, extra = req(
        "PATCH",
        f"/admin/users/{cs_id}",
        token=admin,
        body={
            "platform_shop_role": "platform_shop_cs",
            "platform_shop_permissions": list(cs_defaults) + ["platform.shop.settlement"],
        },
    )
    results.append(
        check(
            "VP08-5 不可加超角色默认",
            code == 422 and "超出" in _err(extra),
            f"{code} {_err(extra)}",
        )
    )
    req(
        "PATCH",
        f"/admin/users/{cs_id}",
        token=admin,
        body={"platform_shop_role": "platform_shop_cs", "platform_shop_permissions": None},
    )

    code, listing = req("GET", "/admin/shop/number-rules", token=admin)
    items = listing.get("items") or []
    types = [it.get("entity_type") for it in items]
    expected_types = [
        "shop_merchant",
        "shop_onboarding",
        "renewal_application",
        "service_log",
        "shop_category",
        "shop_plan",
        "shop_plan_feature",
        "shop_subscription",
        "settlement_batch",
        "shop_store",
        "moderation_case",
    ]
    results.append(
        check(
            "VP08-6 编码规则 11 类",
            code == 200 and types == expected_types,
            f"{code} n={len(items)} types={types}",
        )
    )
    merchant_row = next((x for x in items if x.get("entity_type") == "shop_merchant"), {})
    code, preview = req(
        "POST",
        "/admin/shop/number-rules/shop_merchant/preview",
        token=admin,
        body={"prefix": "ZX", "date_format": "%Y%m%d", "seq_width": 4, "reset_period": "once"},
    )
    results.append(
        check(
            "VP08-6b 预览下一号草稿前缀",
            code == 200
            and str(preview.get("code") or "").startswith("ZX")
            and preview.get("entity_type") == "shop_merchant"
            and merchant_row.get("prefix") == "SH",
            f"{code} {preview} saved_prefix={merchant_row.get('prefix')}",
        )
    )
    code, cs_put = req(
        "PUT",
        "/admin/shop/number-rules/shop_merchant",
        token=cs,
        body={"prefix": "XX"},
    )
    results.append(
        check(
            "VP08-7 管家不可改编码规则",
            code == 403,
            f"{code} {_err(cs_put)}",
        )
    )
    fin = _ensure_finance_user()
    code, fin_get = req("GET", "/admin/shop/number-rules", token=fin)
    code_put, fin_put = req(
        "PUT",
        "/admin/shop/number-rules/shop_merchant",
        token=fin,
        body={"prefix": "FF"},
    )
    results.append(
        check(
            "VP08-8 财务可读不可改编码",
            code == 200 and isinstance(fin_get.get("items"), list) and code_put == 403,
            f"get={code} put={code_put} {_err(fin_put)}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP08: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
