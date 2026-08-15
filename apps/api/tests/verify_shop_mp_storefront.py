#!/usr/bin/env python3
"""买家店首页 / 商品详情 / 下单支付 API 验收。对照 M02～M05。"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.seed_shop_demo import COURSE_NAME, DEMO_PREFIX, DRAFT_NAME, seed  # noqa: E402


def _buyer_login(tenant_id: str, openid: str) -> str:
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    info = seed(reset=False)
    tenant_id = info["tenant_id"]
    shop_id = info["shop_id"]

    code, store = req("GET", f"/mp/shop/store?shop_id={shop_id}")
    products = (store or {}).get("products") or []
    course = next((p for p in products if p.get("name") == COURSE_NAME), None)
    results.append(
        check(
            "MP-STORE M02 店首页",
            code == 200
            and store.get("shop", {}).get("id") == shop_id
            and len(products) >= 3
            and course is not None,
            f"{code} total={len(products)}",
        )
    )

    if not course:
        print("MP-STORE: 无演示课程，跳过后续")
        return 1

    code, detail = req("GET", f"/mp/shop/products/{course['id']}")
    results.append(
        check(
            "MP-STORE M03 商品详情",
            code == 200
            and detail.get("purchase_state") in ("not_purchased", "purchased", "trial_available")
            and detail.get("name") == COURSE_NAME,
            f"{code} {detail.get('purchase_state')}",
        )
    )

    openid = f"mp_store_{uuid.uuid4().hex[:8]}"
    buyer = _buyer_login(tenant_id, openid)
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    code, _ = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("MP-STORE 绑定手机", code == 200, str(code)))

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course["id"]})
    order = (created or {}).get("order") or created
    results.append(
        check(
            "MP-STORE M04 创建订单",
            code == 200 and order.get("status") == "pending_payment",
            f"{code} {order.get('status')}",
        )
    )

    if order.get("id"):
        code, paid = req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})
        paid_order = (paid or {}).get("order") or paid
        results.append(
            check(
                "MP-STORE M05 Mock 支付",
                code == 200 and paid_order.get("status") == "paid",
                f"{code} {paid_order.get('status')}",
            )
        )

        code, detail2 = req("GET", f"/mp/shop/products/{course['id']}", token=buyer)
        results.append(
            check(
                "MP-STORE M03 已购状态",
                code == 200 and detail2.get("purchase_state") == "purchased",
                f"{code} {detail2.get('purchase_state')}",
            )
        )

    # 搜索
    code, searched = req("GET", f"/mp/shop/store?shop_id={shop_id}&q={DEMO_PREFIX}")
    results.append(
        check(
            "MP-STORE M02 搜索",
            code == 200 and (searched.get("total") or 0) >= 1,
            f"{code} total={searched.get('total')}",
        )
    )

    names = {p.get("name") for p in products}
    results.append(
        check(
            "MP-STORE M02 仅在售",
            DRAFT_NAME not in names and all(p.get("status") == "on_sale" for p in products),
            f"names={sorted(names)}",
        )
    )

    code, by_price = req("GET", f"/mp/shop/store?shop_id={shop_id}&sort=price_asc")
    prices = [int(p.get("price_cents") or 0) for p in (by_price or {}).get("products") or []]
    results.append(
        check(
            "MP-STORE M02 价格升序",
            code == 200 and prices == sorted(prices) and len(prices) >= 2,
            f"{code} {prices}",
        )
    )
    code, page1 = req("GET", f"/mp/shop/store?shop_id={shop_id}&page=1&page_size=2")
    results.append(
        check(
            "MP-STORE M02 分页 has_more",
            code == 200
            and len((page1 or {}).get("products") or []) == 2
            and page1.get("has_more") is True,
            f"{code} n={len((page1 or {}).get('products') or [])} more={page1.get('has_more')}",
        )
    )

    lessons = (detail or {}).get("lessons") or []
    trial = next((l for l in lessons if l.get("is_trial")), None)
    results.append(
        check(
            "MP-STORE M03 试看未锁定",
            trial is not None and trial.get("locked") is False,
            f"trial={trial}",
        )
    )

    code, typed = req("GET", f"/mp/shop/store?shop_id={shop_id}&type=course")
    typed_items = (typed or {}).get("products") or []
    results.append(
        check(
            "MP-STORE M02 类型 Chip 课程",
            code == 200 and typed_items and all(p.get("type") == "course" for p in typed_items),
            f"{code} types={[p.get('type') for p in typed_items]}",
        )
    )

    code, empty = req("GET", f"/mp/shop/store?shop_id={shop_id}&q=NOHIT_ZZZZ_DEMO")
    results.append(
        check(
            "MP-STORE M02 搜索无命中",
            code == 200 and (empty.get("total") or 0) == 0,
            f"{code} total={empty.get('total')}",
        )
    )

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopStore

    db = SessionLocal()
    shop_row = None
    prev = "active"
    try:
        shop_row = db.query(ShopStore).filter(uuid_eq(ShopStore.id, uuid.UUID(shop_id))).first()
        prev = shop_row.status
        shop_row.status = "paused"
        db.commit()
        code, paused = req("GET", f"/mp/shop/store?shop_id={shop_id}")
        results.append(
            check(
                "MP-STORE M02 暂停营业 403",
                code == 403 and "暂停营业" in str(paused),
                f"{code} {paused}",
            )
        )
    finally:
        if shop_row is not None:
            shop_row.status = prev
            db.commit()
        db.close()

    passed = all(results)
    print(f"\nverify_shop_mp_storefront: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
