#!/usr/bin/env python3
"""P01 平台经营看板。对照 PRD 06#p01 · #p01-cs · #p01-finance · §8.14.1。"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "PlatformDashboard.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AdminLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"


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
            "VP01-UI 看板页 TC-P01-F01",
            _page_has(
                WEB,
                "#p01",
                "全站经营看板",
                "导出日报",
                "本月 GMV",
                "待审商品",
                "商家",
                "订单",
                "状态",
                "最近活跃",
            )
            and _page_has(LAYOUT, "概览", "/admin/shop/dashboard")
            and _page_has(ROUTER, "shop/dashboard", "PlatformDashboard"),
            str(WEB),
        )
    )

    from app.permissions import PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS
    from app.services.shop.p01_analytics_service import CS_ORDER, FINANCE_ORDER, OPS_ORDER

    results.append(
        check(
            "VP01-CS 管家模板含 analytics TC-P01-F02",
            "platform.shop.analytics" in PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS
            and "pending_product_reviews" not in CS_ORDER
            and "open_moderation_cases" not in CS_ORDER
            and "pending_renewals" not in CS_ORDER
            and "expiring_soon_merchants" in CS_ORDER,
            str(CS_ORDER),
        )
    )
    results.append(
        check(
            "VP01-FIN 财务 widget_order",
            FINANCE_ORDER[0] == "settlement_batches_pending"
            and "pending_product_reviews" not in FINANCE_ORDER
            and OPS_ORDER[0] == "pending_product_reviews",
            str(FINANCE_ORDER),
        )
    )

    merchant, _tid = _ensure_merchant()
    admin = login("13800000000", "admin123456", "platform")

    code, summary = req("GET", "/admin/shop/analytics/summary", token=admin)
    widgets = (summary or {}).get("widgets") or {}
    order = (summary or {}).get("widget_order") or []
    table = (summary or {}).get("merchant_table") or {}
    results.append(
        check(
            "VP01-0 summary 结构 TC-P01-F01",
            code == 200
            and summary.get("scope") == "all"
            and isinstance(widgets, dict)
            and isinstance(order, list)
            and "gmv_month_cents" in widgets
            and widgets.get("gmv_month_cents") is not None
            and widgets.get("pending_product_reviews") is not None
            and widgets.get("pending_onboarding") is not None
            and summary.get("title") == "全站经营看板"
            and table.get("kind") == "top_gmv_merchants",
            f"{code} scope={summary.get('scope') if isinstance(summary, dict) else summary} title={summary.get('title') if isinstance(summary, dict) else None}",
        )
    )
    results.append(
        check(
            "VP01-1 运营待办卡置顶",
            order[:4]
            == [
                "pending_product_reviews",
                "pending_onboarding",
                "open_moderation_cases",
                "pending_renewals",
            ],
            str(order),
        )
    )

    code, trends = req("GET", "/admin/shop/analytics/trends?range=7d", token=admin)
    points = (trends or {}).get("points") or []
    results.append(
        check(
            "VP01-2 trends 7d",
            code == 200 and trends.get("range") == "7d" and len(points) == 7 and trends.get("scope") == "all",
            f"{code} {len(points)}",
        )
    )
    code, bad = req("GET", "/admin/shop/analytics/trends?range=90d", token=admin)
    results.append(
        check(
            "VP01-3 非法 range 422",
            code == 422,
            f"{code} {bad}",
        )
    )

    today = date.today().isoformat()
    code, csv_body = req(
        "POST", "/admin/shop/analytics/export-daily", token=admin, body={"date": today}
    )
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VP01-4 导出日报 CSV",
            code == 200 and "本月 GMV" in csv_text and "商家" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )

    code, forbidden = req("GET", "/admin/shop/analytics/summary", token=merchant)
    results.append(
        check(
            "VP01-5 商家无平台权 TC-P01-E01",
            code in (401, 403),
            f"{code}",
        )
    )

    results.append(
        check(
            "VP01-6 下钻 P09 query 兼容 pending_review TC-P01-F03",
            _page_has(
                REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "ProductReviews.vue",
                "pending_review",
            )
            and _page_has(
                REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "OnboardingApplications.vue",
                "route.query.status",
            ),
            "P09/P03 query",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nP01 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
