#!/usr/bin/env python3
"""P04 平台类目 + A03 提审类目。对照 PRD 06#p04 · 01#a03。"""

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

ADMIN_WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "CategoriesList.vue"
A03_WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ProductEdit.vue"


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


def _err_text(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    if isinstance(d, list):
        return " ".join(
            str(x.get("msg") or x.get("message") or x) if isinstance(x, dict) else str(x)
            for x in d
        )
    return str(d)


def _ensure_cs_user() -> str:
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
            u.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password, "platform")


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VP04-UI 平台类目页",
            _page_has(
                ADMIN_WEB,
                "#p04",
                "#p04-list",
                "#p04d",
                "#p04c",
                "类目编码",
                "平台费率",
                "需资质",
                "+ 新增类目",
                "启用（需审批）",
                "提交审批",
                "审批人（只读）",
                "确认禁用",
                "列设置",
                "导出",
                "高级筛选",
                "影响说明（只读）",
                "原因类型",
                "data-testid=\"shop-categories\"",
            )
            or _page_has(
                ADMIN_WEB,
                "#p04",
                "#p04d",
                "类目编码",
                "平台费率",
                "需资质",
                "+ 新增类目",
                "启用（需审批）",
                "提交审批",
                "审批人（只读）",
            ),
            str(ADMIN_WEB),
        )
    )
    results.append(
        check(
            "VA03-UI 平台类目下拉",
            _page_has(
                A03_WEB,
                "平台类目",
                "platform-categories",
                "请补全平台类目",
                "category_id",
            ),
            str(A03_WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    code, listing = req("GET", "/admin/shop/categories?page_size=50", token=admin)
    results.append(
        check(
            "VP04-1 列表含种子类目",
            code == 200
            and listing.get("total", 0) >= 3
            and any(i.get("code") == "cat.vocational" for i in (listing.get("items") or [])),
            f"{code} total={listing.get('total')}",
        )
    )

    code, created = req(
        "POST",
        "/admin/shop/categories",
        token=admin,
        body={
            "parent_id": None,
            "name": f"验类目-{uuid.uuid4().hex[:6]}",
            "code_source": "auto",
            "platform_fee_bps": 150,
            "settlement_rule": "standard",
            "require_qualifications": ["ICP备案"],
        },
    )
    results.append(
        check(
            "VP04-2 新增类目",
            code == 200
            and created.get("status") == "enabled"
            and created.get("code", "").startswith("cat."),
            f"{code} {created}",
        )
    )
    cid = created.get("id") if code == 200 else None

    code, empty_name = req(
        "POST",
        "/admin/shop/categories",
        token=admin,
        body={"name": "", "code_source": "auto", "platform_fee_bps": 100, "settlement_rule": "standard"},
    )
    results.append(
        check(
            "TC-P04-E01 名称为空",
            code == 422 and "名称" in _err_text(empty_name),
            f"{code} {empty_name}",
        )
    )
    if cid:
        code, dup = req(
            "POST",
            "/admin/shop/categories",
            token=admin,
            body={
                "name": created["name"],
                "code_source": "auto",
                "platform_fee_bps": 100,
                "settlement_rule": "standard",
            },
        )
        results.append(
            check(
                "TC-P04-E02 同层重名",
                code == 422 and "同层" in _err_text(dup),
                f"{code} {dup}",
            )
        )
        code, one = req("GET", f"/admin/shop/categories/{cid}", token=admin)
        results.append(
            check(
                "VP04-2b 详情含在售引用",
                code == 200 and one.get("id") == cid and one.get("on_sale_ref_count") is not None,
                f"{code} {one.get('on_sale_ref_count')}",
            )
        )

    code, miss = req("GET", "/admin/shop/categories?q=ZZZNONE&page_size=20", token=admin)
    results.append(
        check(
            "TC-P04-L01 搜索空态",
            code == 200 and miss.get("total") == 0,
            f"{code} {miss.get('total')}",
        )
    )
    cs = _ensure_cs_user()
    code, forbidden = req("GET", "/admin/shop/categories", token=cs)
    results.append(
        check(
            "TC-P04-P01 无权限",
            code == 403,
            f"{code} {forbidden}",
        )
    )

    if cid:
        code, patched = req(
            "PATCH",
            f"/admin/shop/categories/{cid}",
            token=admin,
            body={"platform_fee_bps": 220, "name": created["name"] + "-改"},
        )
        results.append(
            check(
                "VP04-3 编辑费率",
                code == 200 and patched.get("platform_fee_bps") == 220,
                f"{code} {patched}",
            )
        )
        code, disabled = req(
            "POST",
            f"/admin/shop/categories/{cid}/disable",
            token=admin,
            body={"reason_type": "政策调整", "reason": "验收禁用说明"},
        )
        results.append(
            check(
                "VP04-4 禁用→禁入",
                code == 200 and disabled.get("status") == "blocked",
                f"{code} {disabled}",
            )
        )
        results.append(
            check(
                "VP04-4b 禁入状态含禁用人日期 TC-P04-D",
                "由" in str(disabled.get("blocked_status_label") or "")
                and "禁入（" in str(disabled.get("blocked_status_label") or ""),
                f"label={disabled.get('blocked_status_label')}",
            )
        )
        code, app = req(
            "POST",
            f"/admin/shop/categories/{cid}/enable",
            token=admin,
            body={
                "reason": "验收启用理由充分",
                "platform_fee_bps": 250,
                "require_qualifications": ["办学许可证"],
            },
        )
        results.append(
            check(
                "VP04-5a 提交启用审批→pending",
                code == 200
                and app.get("status") == "pending"
                and app.get("proposed_platform_fee_bps") == 250,
                f"{code} {app}",
            )
        )
        results.append(
            check(
                "VP04-5a2 审批单当前状态含禁用人",
                "由" in str((app or {}).get("status_label") or "")
                and "禁入（" in str((app or {}).get("status_label") or ""),
                f"status_label={(app or {}).get('status_label')}",
            )
        )
        app_id = app.get("id") if code == 200 else None
        code, still = req("GET", f"/admin/shop/categories?page_size=50&q={created['name'][:8]}", token=admin)
        row_pending = next(
            (i for i in (still.get("items") or []) if i.get("id") == cid),
            None,
        )
        results.append(
            check(
                "VP04-5b 提交后仍禁入+待审",
                row_pending
                and row_pending.get("status") == "blocked"
                and row_pending.get("pending_enable_application_id") == app_id,
                f"{row_pending}",
            )
        )
        # 驳回路径
        code, rejected = req(
            "POST",
            f"/admin/shop/categories/enable-applications/{app_id}/reject",
            token=admin,
            body={"reject_reason": "验收驳回原因说明"},
        )
        results.append(
            check(
                "VP04-5c 驳回保留禁入",
                code == 200 and rejected.get("status") == "rejected",
                f"{code} {rejected}",
            )
        )
        code, app2 = req(
            "POST",
            f"/admin/shop/categories/{cid}/enable",
            token=admin,
            body={
                "reason": "再次申请启用理由",
                "platform_fee_bps": 220,
                "require_qualifications": ["ICP备案"],
            },
        )
        app2_id = app2.get("id") if code == 200 else None
        code, approved = req(
            "POST",
            f"/admin/shop/categories/enable-applications/{app2_id}/approve",
            token=admin,
        )
        results.append(
            check(
                "VP04-5d 通过→启用+拟设费率",
                code == 200 and approved.get("status") == "approved",
                f"{code} {approved}",
            )
        )
        code, after = req("GET", "/admin/shop/categories?page_size=50", token=admin)
        row_on = next((i for i in (after.get("items") or []) if i.get("id") == cid), None)
        results.append(
            check(
                "VP04-5e 类目已启用费率落地",
                row_on
                and row_on.get("status") == "enabled"
                and row_on.get("platform_fee_bps") == 220
                and "ICP备案" in (row_on.get("require_qualifications") or []),
                f"{row_on}",
            )
        )
    else:
        for name in (
            "VP04-3 编辑费率",
            "VP04-4 禁用→禁入",
            "VP04-4b 禁入状态含禁用人日期 TC-P04-D",
            "VP04-5a 提交启用审批→pending",
            "VP04-5a2 审批单当前状态含禁用人",
            "VP04-5b 提交后仍禁入+待审",
            "VP04-5c 驳回保留禁入",
            "VP04-5d 通过→启用+拟设费率",
            "VP04-5e 类目已启用费率落地",
        ):
            results.append(check(name, False, "no category id"))

    # 商家端下拉
    from tests.verify_shop_a14 import _ensure_merchant

    merchant, _tid = _ensure_merchant()
    code, mch_cats = req("GET", "/shop/platform-categories?status=enabled", token=merchant)
    results.append(
        check(
            "VP04-6 商家可见启用类目",
            code == 200
            and len(mch_cats.get("items") or []) >= 1
            and all(i.get("status") == "enabled" for i in (mch_cats.get("items") or [])),
            f"{code} n={len(mch_cats.get('items') or [])}",
        )
    )

    from tests.http_client import _get_test_client

    client = _get_test_client()
    cover = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG", "image/png")},
    ).json()["file_url"]
    code, col = req(
        "POST",
        "/shop/columns",
        token=merchant,
        body={"title": f"P04col-{uuid.uuid4().hex[:6]}", "intro": "d"},
    )
    assert code in (200, 201), col
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "L1",
            "duration_sec": 60,
            "media_type": "video",
            "media_url": "https://example.com/p04.mp4",
        },
    )
    assert code in (200, 201), les
    req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)

    code, prod = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"P04课-{uuid.uuid4().hex[:6]}",
            "price_cents": 9900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    results.append(
        check(
            "VP04-7 新建默认带类目",
            code == 200 and prod.get("category_id"),
            f"{code} {prod.get('category_id')}",
        )
    )

    # 重新拉列表拿真正的 blocked（如医疗健康）
    code, listing2 = req("GET", "/admin/shop/categories?page_size=50&status=blocked", token=admin)
    blocked_row = (listing2.get("items") or [None])[0] if code == 200 else None

    if blocked_row and prod.get("id"):
        code, bad = req(
            "PATCH",
            f"/shop/products/{prod['id']}",
            token=merchant,
            body={"category_id": blocked_row["id"]},
        )
        results.append(
            check(
                "VP04-8 禁售类目不可选",
                code == 422 and "禁售" in _err_text(bad),
                f"{code} {bad}",
            )
        )
        from uuid import UUID as UUIDType

        from app.database import SessionLocal, uuid_eq
        from app.models.shop import ShopProduct

        db = SessionLocal()
        try:
            p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(prod["id"]))).first()
            p.category_id = None
            db.commit()
        finally:
            db.close()
        code, submit = req(
            "POST",
            f"/shop/products/{prod['id']}/submit-review",
            token=merchant,
            body={},
        )
        results.append(
            check(
                "VP04-9 无类目不可提审",
                code == 422 and "平台类目" in _err_text(submit),
                f"{code} {submit}",
            )
        )
    else:
        results.append(check("VP04-8 禁售类目不可选", False, f"blocked={blocked_row}"))
        results.append(check("VP04-9 无类目不可提审", False, "no product"))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP04: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
