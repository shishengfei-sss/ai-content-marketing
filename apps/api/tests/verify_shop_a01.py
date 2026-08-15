#!/usr/bin/env python3
"""A01 交易看板。对照 PRD 01#a01。"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant, login  # noqa: E402
from tests.verify_shop_a16 import _force_admin  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "DashboardOverview.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AppLayout.vue"
COMPOSABLE = REPO_ROOT / "apps" / "web" / "src" / "composables" / "useCurrentShop.js"
PROD = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ProductsList.vue"
ORDERS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "OrdersList.vue"
COLS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ColumnsList.vue"
PKGS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "DigitalPackagesList.vue"
OFFERS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ServiceOffersList.vue"
BOOKINGS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "BookingsList.vue"
BUYERS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "BuyersList.vue"
INVOICES = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "InvoicesList.vue"
ENTS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "EntitlementsList.vue"
VERIFS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "Verifications.vue"
MAPS = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ChannelMappings.vue"
NAV = REPO_ROOT / "apps" / "web" / "src" / "config" / "permissions.js"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"


def _has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _ensure_store(tid: str) -> str | None:
    from uuid import UUID as _UUID

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount
    from app.services.shop.product_service import ensure_default_shop

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, _UUID(tid)))
            .first()
        )
        if not m:
            return None
        store = ensure_default_shop(db, _UUID(tid), m)
        db.commit()
        return str(store.id)
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA01-UI 交易看板页",
            _has(
                WEB,
                "#a01",
                "交易看板",
                "成交额",
                "订单数",
                "支付转化*（可隐）",
                "待处理退款",
                "待核销 →",
                "待开票 →",
                "待领权公域单 →",
                "下架商品数",
                "成交额按日",
                "品类占比",
                "渠道占比",
                "最近订单",
                "单号 / 商品 / 买家",
            ),
            str(WEB),
        )
    )
    dash = WEB.read_text(encoding="utf-8")
    results.append(
        check(
            "VA01-UI 看板不再放页内切店",
            "顶栏切店壳未做" not in dash and 'placeholder="当前店铺：全部"' not in dash,
            str(WEB),
        )
    )
    results.append(
        check(
            "VA01-UI 导出积压任务弹窗",
            "导出积压 CSV" in dash
            and "export-tasks" in dash
            and "api.post" in dash
            and "/shop/orders/export" in dash
            and "导出任务" in dash
            and "ElMessageBox" not in dash,
            "backlog export dialog",
        )
    )
    results.append(
        check(
            "VA01-UI 顶栏当前店铺",
            _has(
                LAYOUT,
                "#a01-select-spec",
                "当前店铺：",
                "shop-current-store",
                "useCurrentShop",
            ),
            str(LAYOUT),
        )
    )
    results.append(
        check(
            "VA01-UI 切店 composable",
            _has(
                COMPOSABLE,
                "#a01-select-spec",
                "shop.current_shop_id",
                "/shop/stores/options",
                "shop:current-shop-changed",
            ),
            str(COMPOSABLE),
        )
    )
    results.append(
        check(
            "VA01-UI 商品/订单带当前店",
            _has(PROD, "useCurrentShop", "shop_id: currentId")
            and _has(ORDERS, "useCurrentShop", "shop_id: currentId"),
            f"{PROD.name} {ORDERS.name}",
        )
    )
    scoped_pages = (
        (COLS, "专栏"),
        (PKGS, "资料包"),
        (OFFERS, "服务"),
        (BOOKINGS, "预约"),
        (BUYERS, "买家"),
        (INVOICES, "发票"),
        (ENTS, "权益"),
        (VERIFS, "核销"),
        (MAPS, "公域映射"),
    )
    missing = [label for path, label in scoped_pages if not _has(path, "useCurrentShop", "shop_id: currentId")]
    results.append(
        check(
            "VA01-UI 专栏至公域映射带当前店",
            not missing,
            ",".join(missing) or "ok",
        )
    )
    results.append(
        check(
            "VA01-路由 /shop/overview",
            _has(ROUTER, "ShopOverview", "shop/overview", "shop/dashboard"),
            str(ROUTER),
        )
    )
    nav = NAV.read_text(encoding="utf-8")
    idx_ov = nav.find("shop-overview")
    idx_pr = nav.find("shop-products")
    results.append(
        check(
            "VA01-侧栏 概览在商品前",
            "title: '概览'" in nav and 0 <= idx_ov < idx_pr,
            "nav order",
        )
    )

    merchant, tid = _ensure_merchant()
    _force_admin("13900000099", tid)
    merchant = login("13900000099", "test123456")

    code, summary = req("GET", "/shop/analytics/summary?range=today", token=merchant)
    results.append(
        check(
            "VA01-1 summary 今日",
            code == 200
            and isinstance(summary.get("gmv_cents"), int)
            and isinstance(summary.get("order_count"), int)
            and summary.get("payment_conversion") is None
            and "pending_refunds" in summary
            and "pending_verify" in summary
            and "pending_invoices" in summary
            and "pending_claims" in summary
            and "off_sale_products" in summary
            and isinstance(summary.get("stores"), list)
            and isinstance((summary.get("resume") or {}).get("show"), bool),
            f"{code} keys={list(summary) if isinstance(summary, dict) else summary}",
        )
    )

    code, s7 = req("GET", "/shop/analytics/summary?range=7d", token=merchant)
    results.append(
        check(
            "VA01-2 summary 近7日",
            code == 200 and s7.get("range") == "7d" and s7.get("order_count") >= 0,
            f"{code} {s7.get('range') if isinstance(s7, dict) else s7}",
        )
    )

    code, trends = req("GET", "/shop/analytics/trends?range=30d", token=merchant)
    results.append(
        check(
            "VA01-3 trends 近30日",
            code == 200
            and isinstance(trends.get("daily"), list)
            and len(trends.get("daily") or []) >= 30
            and isinstance(trends.get("by_category"), list)
            and isinstance(trends.get("by_channel"), list),
            f"{code} days={len((trends or {}).get('daily') or [])}",
        )
    )

    code, recent = req("GET", "/shop/analytics/recent-orders?page_size=10", token=merchant)
    results.append(
        check(
            "VA01-4 最近订单",
            code == 200
            and isinstance(recent.get("items"), list)
            and recent.get("page_size") == 10
            and isinstance(recent.get("total"), int),
            f"{code} total={recent.get('total') if isinstance(recent, dict) else recent}",
        )
    )

    start = (date.today() - timedelta(days=100)).isoformat()
    end = date.today().isoformat()
    code, too_long = req(
        "GET",
        f"/shop/analytics/summary?range=custom&date_from={start}&date_to={end}",
        token=merchant,
    )
    results.append(
        check(
            "VA01-5 自定义超 90 天",
            code == 422,
            f"{code} {too_long}",
        )
    )

    code, bad = req("GET", "/shop/analytics/summary?range=year", token=merchant)
    results.append(check("VA01-6 非法 range", code == 422, f"{code} {bad}"))

    code, custom_need = req("GET", "/shop/analytics/summary?range=custom", token=merchant)
    results.append(
        check("VA01-7 自定义缺日期", code == 422, f"{code} {custom_need}")
    )

    code, anon = req("GET", "/shop/analytics/summary")
    results.append(check("VA01-8 无 token", code in (401, 403), f"{code}"))

    stores = summary.get("stores") or []
    if stores:
        sid = stores[0]["id"]
        code, one = req(
            "GET", f"/shop/analytics/summary?range=today&shop_id={sid}", token=merchant
        )
        results.append(
            check(
                "VA01-9 切店 shop_id",
                code == 200 and str(one.get("shop_id")) == str(sid),
                f"{code} {one.get('shop_id') if isinstance(one, dict) else one}",
            )
        )
    else:
        results.append(check("VA01-9 切店 shop_id", True, "no stores skip-ok"))

    code, opts = req("GET", "/shop/stores/options", token=merchant)
    results.append(
        check(
            "VA01-10 顶栏店铺选项",
            code == 200
            and isinstance(opts.get("items"), list)
            and ("plan_label" in opts)
            and ("role_label" in opts),
            f"{code} {opts if not isinstance(opts, dict) else {k: opts.get(k) for k in ('plan_label', 'role_label', 'store_scope')}}",
        )
    )
    if isinstance(opts, dict) and opts.get("items"):
        oid = str(opts["items"][0]["id"])
        store_ids = {str(s.get("id")) for s in stores}
        results.append(
            check(
                "VA01-11 options 与 summary 同源",
                oid in store_ids or not store_ids,
                f"oid={oid} n_summary={len(store_ids)}",
            )
        )
    else:
        results.append(check("VA01-11 options 与 summary 同源", True, "no option skip-ok"))

    if isinstance(opts, dict) and not (opts.get("items") or []):
        _ensure_store(tid)
        code, opts = req("GET", "/shop/stores/options", token=merchant)

    if isinstance(opts, dict) and opts.get("items"):
        sid = str(opts["items"][0]["id"])
        title = f"A01切店-{uuid.uuid4().hex[:6]}"
        code, created = req(
            "POST",
            "/shop/columns",
            token=merchant,
            body={"title": title, "shop_id": sid},
        )
        results.append(
            check(
                "VA01-13 当前店可建专栏",
                code == 201 and created.get("title") == title and str(created.get("shop_id")) == sid,
                f"{code} {created}",
            )
        )
        code, listed = req(
            "GET", f"/shop/columns?shop_id={sid}&q={title}", token=merchant
        )
        titles = [i.get("title") for i in (listed.get("items") or [])] if isinstance(listed, dict) else []
        results.append(
            check(
                "VA01-14 当前店列表可见",
                code == 200 and title in titles,
                f"{code} titles={titles}",
            )
        )
        fake = str(uuid.uuid4())
        code, empty = req(
            "GET", f"/shop/columns?shop_id={fake}&q={title}", token=merchant
        )
        empty_titles = [i.get("title") for i in (empty.get("items") or [])] if isinstance(empty, dict) else []
        results.append(
            check(
                "VA01-15 他店 UUID 不可见该专栏",
                code == 200 and title not in empty_titles and empty.get("total", 0) == 0,
                f"{code} {empty if not isinstance(empty, dict) else empty.get('total')}",
            )
        )
        if len(opts["items"]) >= 2:
            sid2 = str(opts["items"][1]["id"])
            title2 = f"A01他店-{uuid.uuid4().hex[:6]}"
            req(
                "POST",
                "/shop/columns",
                token=merchant,
                body={"title": title2, "shop_id": sid2},
            )
            code, a_only = req(
                "GET", f"/shop/columns?shop_id={sid}&q={title2}", token=merchant
            )
            a_titles = [i.get("title") for i in (a_only.get("items") or [])] if isinstance(a_only, dict) else []
            results.append(
                check(
                    "VA01-16 两店专栏互不可见",
                    code == 200 and title2 not in a_titles,
                    f"{code} {a_titles}",
                )
            )
        else:
            results.append(check("VA01-16 两店专栏互不可见", True, "single store skip-ok"))
        scoped_ok = True
        for path in (
            f"/shop/bookings?shop_id={fake}",
            f"/shop/buyers?shop_id={fake}",
            f"/shop/invoices?shop_id={fake}",
            f"/shop/entitlements?shop_id={fake}",
            f"/shop/verifications?shop_id={fake}",
            f"/shop/digital-packages?shop_id={fake}",
            f"/shop/service-offers?shop_id={fake}",
            f"/shop/channel-mappings?shop_id={fake}",
        ):
            c, body = req("GET", path, token=merchant)
            if c != 200 or (isinstance(body, dict) and body.get("total", 0) != 0):
                scoped_ok = False
                break
        results.append(
            check(
                "VA01-17 履约列表他店为空",
                scoped_ok,
                f"{path} {c} {body if not isinstance(body, dict) else body.get('total')}",
            )
        )
    else:
        results.append(check("VA01-13 当前店可建专栏", False, "no store"))
        results.append(check("VA01-14 当前店列表可见", False, "no store"))
        results.append(check("VA01-15 他店 UUID 不可见该专栏", False, "no store"))
        results.append(check("VA01-16 两店专栏互不可见", True, "no store skip-ok"))
        results.append(check("VA01-17 履约列表他店为空", False, "no store"))

    code, anon_opt = req("GET", "/shop/stores/options")
    results.append(check("VA01-12 options 无 token", code in (401, 403), f"{code}"))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA01 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
