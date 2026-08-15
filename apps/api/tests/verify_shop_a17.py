#!/usr/bin/env python3
"""A17 店铺管理 / 开业闸。对照 PRD 01#a17 · #a17a–d。"""

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
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "StoresList.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _err(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    return str(d)


def _bump_max_shops(tenant_id: str, max_shops: int = 5) -> None:
    from uuid import UUID

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount, ShopSubscriptionPlan

    tid = UUID(str(tenant_id))
    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, tid))
            .first()
        )
        assert m, "merchant missing"
        m.store_quota = max_shops
        free = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == "free").first()
        if free:
            q = dict(free.quotas or {})
            q["quota.max_shops"] = max_shops
            free.quotas = q
        # 若有 active 订阅 snapshot，一并抬高 max_shops
        from app.models.shop import ShopMerchantSubscription
        from app.services.shop.entitlement_service import is_subscription_active

        for sub in (
            db.query(ShopMerchantSubscription)
            .filter(uuid_eq(ShopMerchantSubscription.tenant_id, tid))
            .all()
        ):
            if not is_subscription_active(sub):
                continue
            snap = dict(sub.plan_snapshot or {})
            quotas = dict(snap.get("quotas") or {})
            quotas["quota.max_shops"] = max_shops
            snap["quotas"] = quotas
            sub.plan_snapshot = snap
        db.commit()
    finally:
        db.close()


def _force_product_on_sale(product_id: str) -> None:
    from uuid import UUID

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct

    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUID(str(product_id)))).first()
        assert p
        p.status = "on_sale"
        db.commit()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA17-UI 店铺列表页",
            _page_has(
                WEB,
                "#a17",
                "我的店铺",
                "新建店铺",
                "店铺短码",
                "本月 GMV",
                "确认开业",
                "恢复营业",
                "高级筛选",
                "列设置",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/stores/export",
                "/shop/stores/export-tasks/",
            ),
            str(WEB),
        )
    )

    merchant, tid = _ensure_merchant()
    code, listing = req("GET", "/shop/stores", token=merchant)
    results.append(
        check(
            "VA17-1 列表含配额",
            code == 200
            and isinstance(listing.get("items"), list)
            and isinstance(listing.get("quota"), dict)
            and "used" in listing["quota"]
            and "status_counts" in listing,
            f"{code} {listing}",
        )
    )
    code, st_csv = req("GET", "/shop/stores/export", token=merchant)
    results.append(
        check(
            "VA17-E0 GET 导出含默认列",
            code == 200 and "店铺名" in str(st_csv) and "店铺短码" in str(st_csv),
            f"{code} {str(st_csv)[:80]}",
        )
    )
    code, st_task = req("POST", "/shop/stores/export", token=merchant, body={})
    results.append(
        check(
            "VA17-E1 POST 导出任务已完成",
            code == 200
            and isinstance(st_task, dict)
            and st_task.get("status") == "done"
            and st_task.get("resource") == "stores"
            and st_task.get("id"),
            f"{code} {st_task}",
        )
    )
    st_task_id = (st_task or {}).get("id") if isinstance(st_task, dict) else None
    if st_task_id:
        code, st_file = req("GET", f"/shop/stores/export-tasks/{st_task_id}/file", token=merchant)
        results.append(
            check(
                "VA17-E2 任务文件可下载",
                code == 200 and "店铺名" in str(st_file) and "状态" in str(st_file),
                f"{code} head={str(st_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VA17-E2 任务文件可下载", False, "no task id"))
    code, st_cols = req(
        "POST",
        "/shop/stores/export",
        token=merchant,
        body={"columns": ["name", "status"]},
    )
    if code == 200 and isinstance(st_cols, dict) and st_cols.get("id"):
        code2, st_col_csv = req(
            "GET",
            f"/shop/stores/export-tasks/{st_cols['id']}/file",
            token=merchant,
        )
        head = str(st_col_csv).splitlines()[0] if st_col_csv else ""
        results.append(
            check(
                "VA17-E3 列配置导出表头",
                code2 == 200 and "店铺名" in head and "状态" in head and "店铺短码" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA17-E3 列配置导出表头", False, f"{code} {st_cols}"))
    code, plat_st = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_st_token = (
        plat_st.get("access_token") if code == 200 and isinstance(plat_st, dict) else None
    )
    code, st_forbidden = req("POST", "/shop/stores/export", token=plat_st_token, body={})
    results.append(
        check(
            "VA17-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {st_forbidden}",
        )
    )
    first = (listing.get("items") or [{}])[0] if code == 200 else {}
    shop_id = first.get("id")

    # 抬配额后新建
    _bump_max_shops(tid, 20)
    slug = f"a17{uuid.uuid4().hex[:6]}"
    code, created = req(
        "POST",
        "/shop/stores",
        token=merchant,
        body={"name": f"待开业分店-{slug[-4:]}", "slug": slug, "intro": "验"},
    )
    results.append(
        check(
            "VA17-2 新建默认草稿",
            code == 201 and created.get("status") == "draft" and created.get("slug") == slug,
            f"{code} {created}",
        )
    )
    new_id = created.get("id") if code == 201 else None

    code, dup = req(
        "POST",
        "/shop/stores",
        token=merchant,
        body={"name": "重复短码", "slug": slug},
    )
    results.append(
        check(
            "VA17-3 短码冲突",
            code == 422 and "短码" in _err(dup),
            f"{code} {dup}",
        )
    )

    if new_id:
        code, bad_open = req("POST", f"/shop/stores/{new_id}/open", token=merchant)
        results.append(
            check(
                "VA17-4 无在售拒开业",
                code == 422 and "在售" in _err(bad_open),
                f"{code} {bad_open}",
            )
        )

        # 空名拒开业
        from uuid import UUID

        from app.database import SessionLocal, uuid_eq
        from app.models.shop import ShopStore

        db = SessionLocal()
        try:
            s = db.query(ShopStore).filter(uuid_eq(ShopStore.id, UUID(str(new_id)))).first()
            s.name = "x"  # 1 字，不满足 2–100
            db.commit()
        finally:
            db.close()
        code, bad_a19 = req("POST", f"/shop/stores/{new_id}/open", token=merchant)
        results.append(
            check(
                "VA17-5 未完善设置拒开业",
                code == 422 and "单店设置" in _err(bad_a19),
                f"{code} {bad_a19}",
            )
        )
        db = SessionLocal()
        try:
            s = db.query(ShopStore).filter(uuid_eq(ShopStore.id, UUID(str(new_id)))).first()
            s.name = f"待开业分店-{slug[-4:]}"
            db.commit()
        finally:
            db.close()

        # 造在售商品
        from tests.http_client import _get_test_client

        client = _get_test_client()
        cover = client.post(
            "/api/v1/shop/content/files",
            headers={"Authorization": f"Bearer {merchant}"},
            files={"file": ("a17.png", b"\x89PNG", "image/png")},
        ).json()["file_url"]
        code, col = req(
            "POST",
            "/shop/columns",
            token=merchant,
            body={"title": f"A17col-{uuid.uuid4().hex[:6]}", "intro": "d", "shop_id": new_id},
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
                "media_url": "https://example.com/a17.mp4",
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
                "shop_id": new_id,
                "type": "course",
                "name": f"A17课-{uuid.uuid4().hex[:6]}",
                "price_cents": 9900,
                "cover_url": cover,
                "ref_type": "column",
                "ref_id": col["id"],
            },
        )
        assert code == 200, prod
        _force_product_on_sale(prod["id"])

        code, opened = req("POST", f"/shop/stores/{new_id}/open", token=merchant)
        results.append(
            check(
                "VA17-6 开业成功",
                code == 200 and opened.get("status") == "active",
                f"{code} {opened}",
            )
        )

        code, paused = req("POST", f"/shop/stores/{new_id}/pause", token=merchant)
        results.append(
            check(
                "VA17-7 暂停",
                code == 200 and paused.get("status") == "paused",
                f"{code} {paused}",
            )
        )

        code, resumed = req("POST", f"/shop/stores/{new_id}/resume", token=merchant)
        results.append(
            check(
                "VA17-8 恢复营业",
                code == 200 and resumed.get("status") == "active",
                f"{code} {resumed}",
            )
        )

        code, again = req("POST", f"/shop/stores/{new_id}/open", token=merchant)
        results.append(
            check(
                "VA17-9 非草稿拒开业",
                code == 422 and "草稿" in _err(again),
                f"{code} {again}",
            )
        )

    _bump_max_shops(tid, 20)  # 恢复，避免污染
    # 还原 free 默认配额，避免污染其它用例
    from app.database import SessionLocal
    from app.models.shop import ShopSubscriptionPlan

    db = SessionLocal()
    try:
        free = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == "free").first()
        if free:
            q = dict(free.quotas or {})
            q["quota.max_shops"] = 1
            free.quotas = q
            db.commit()
    finally:
        db.close()

    # 达上限：再压到 used 数量
    code, listing2 = req("GET", "/shop/stores", token=merchant)
    used = (listing2.get("quota") or {}).get("used") or 1
    _bump_max_shops(tid, int(used))
    code, limited = req(
        "POST",
        "/shop/stores",
        token=merchant,
        body={"name": "超额店", "slug": f"over{uuid.uuid4().hex[:5]}"},
    )
    results.append(
        check(
            "VA17-10 达上限拒绝",
            code == 422 and "上限" in _err(limited),
            f"{code} {limited}",
        )
    )
    _bump_max_shops(tid, max(int(used) + 5, 10))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA17: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
