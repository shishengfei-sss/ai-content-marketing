#!/usr/bin/env python3
"""P04-E / P08-F 平台业务编码规则。对照 06#p04e · #p08f · 04#platform-code-rule。"""

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

ADMIN_CAT = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "CategoriesList.vue"
ADMIN_CODES = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "RolesAndCodes.vue"


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


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP04E-UI 类目页编码规则入口",
            _page_has(
                ADMIN_CAT,
                "#p04e",
                "编码规则",
                "保存规则",
                "继承父 code",
                "shop_category",
            ),
            str(ADMIN_CAT),
        )
    )
    results.append(
        check(
            "VP08F-UI 角色与编码页",
            _page_has(
                ADMIN_CODES,
                "#p08f",
                "编码规则",
                "恢复全部默认",
                "entity_type",
            ),
            str(ADMIN_CODES),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    code, listing = req("GET", "/admin/shop/number-rules", token=admin)
    items = listing.get("items") or []
    results.append(
        check(
            "VP08F-1 列表含 11 类实体",
            code == 200 and len(items) >= 11 and any(i.get("entity_type") == "shop_category" for i in items),
            f"{code} n={len(items)}",
        )
    )

    code, cat_rule = req("GET", "/admin/shop/number-rules/shop_category", token=admin)
    results.append(
        check(
            "VP04E-1 类目规则默认",
            code == 200
            and cat_rule.get("prefix") == "cat."
            and cat_rule.get("inherit_parent_code") is True
            and cat_rule.get("enabled") is True,
            f"{code} {cat_rule}",
        )
    )

    code, prev = req(
        "POST",
        "/admin/shop/number-rules/shop_category/preview",
        token=admin,
        body={"parent_id": None},
    )
    results.append(
        check(
            "VP04E-2 根类目预览",
            code == 200 and str(prev.get("code", "")).startswith("cat."),
            f"{code} {prev}",
        )
    )

    # 取职业培训作父
    code, cats = req("GET", "/admin/shop/categories?page_size=50", token=admin)
    parent = next((i for i in (cats.get("items") or []) if i.get("code") == "cat.vocational"), None)
    if parent:
        code, prev2 = req(
            "POST",
            "/admin/shop/number-rules/shop_category/preview",
            token=admin,
            body={"parent_id": parent["id"]},
        )
        results.append(
            check(
                "VP04E-3 子类目继承父 code 预览",
                code == 200 and str(prev2.get("code", "")).startswith("cat.vocational."),
                f"{code} {prev2}",
            )
        )
    else:
        results.append(check("VP04E-3 子类目继承父 code 预览", False, "no cat.vocational"))

    code, created = req(
        "POST",
        "/admin/shop/categories",
        token=admin,
        body={
            "parent_id": parent["id"] if parent else None,
            "name": f"编码验-{uuid.uuid4().hex[:6]}",
            "code_source": "auto",
            "platform_fee_bps": 200,
            "settlement_rule": "standard",
        },
    )
    results.append(
        check(
            "VP04E-4 新增走规则生成",
            code == 200
            and created.get("code_source") == "auto"
            and (
                (parent and str(created.get("code", "")).startswith("cat.vocational."))
                or (not parent and str(created.get("code", "")).startswith("cat."))
            ),
            f"{code} {created.get('code')}",
        )
    )

    code, updated = req(
        "PUT",
        "/admin/shop/number-rules/shop_category",
        token=admin,
        body={"seq_width": 4, "inherit_parent_code": True, "enabled": True},
    )
    results.append(
        check(
            "VP04E-5 保存规则",
            code == 200 and updated.get("seq_width") == 4,
            f"{code} {updated}",
        )
    )
    # 恢复默认宽度
    req(
        "PUT",
        "/admin/shop/number-rules/shop_category",
        token=admin,
        body={"seq_width": 3, "prefix": "cat.", "date_format": "", "reset_period": "once"},
    )

    code, disabled = req(
        "PUT",
        "/admin/shop/number-rules/shop_category",
        token=admin,
        body={"enabled": False},
    )
    results.append(
        check(
            "VP04E-6 关闭规则",
            code == 200 and disabled.get("enabled") is False,
            f"{code} {disabled}",
        )
    )
    code, fail = req(
        "POST",
        "/admin/shop/categories",
        token=admin,
        body={
            "name": f"手工必填-{uuid.uuid4().hex[:6]}",
            "code_source": "auto",
            "platform_fee_bps": 100,
            "settlement_rule": "standard",
        },
    )
    results.append(
        check(
            "VP04E-7 规则关闭禁止自动码",
            code == 422 and "手工" in str(fail),
            f"{code} {fail}",
        )
    )
    # 恢复启用
    req(
        "PUT",
        "/admin/shop/number-rules/shop_category",
        token=admin,
        body={"enabled": True, "prefix": "cat.", "seq_width": 3, "inherit_parent_code": True},
    )

    results.append(
        check(
            "VP04E-UI2 财务只读预览文案",
            _page_has(ADMIN_CAT, "canSaveCodeRule", "本页仅预览，保存须平台超管"),
            str(ADMIN_CAT),
        )
    )

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
    fin = login(phone, password, "platform")
    code_fin, data_fin = req(
        "PUT",
        "/admin/shop/number-rules/shop_category",
        token=fin,
        body={"seq_width": 5},
    )
    results.append(
        check(
            "VP04E-8 财务保存编码规则 403",
            code_fin == 403,
            f"{code_fin} {data_fin}",
        )
    )
    code_get, got = req("GET", "/admin/shop/number-rules/shop_category", token=fin)
    results.append(
        check(
            "VP04E-9 财务可读类目规则",
            code_get == 200 and got.get("prefix") == "cat.",
            f"{code_get} {got}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP04E/P08F: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
