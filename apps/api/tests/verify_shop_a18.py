#!/usr/bin/env python3
"""A18 套餐信息。对照 PRD 01#a18 · §8.6。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "SubscriptionEntitlements.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA18-UI 套餐信息页",
            _page_has(
                WEB,
                "#a18",
                "套餐信息",
                "合并后可用额度",
                "生效中订阅",
                "申请升级 / 加购",
                "主套餐",
                "联系管家",
            ),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    code, overview = req("GET", "/shop/subscription/overview", token=merchant)
    results.append(
        check(
            "VA18-1 overview",
            code == 200
            and overview.get("state") == "onboarded"
            and isinstance(overview.get("usage_groups"), list)
            and isinstance(overview.get("summary"), dict)
            and isinstance(overview.get("subscriptions"), list),
            f"{code} keys={list(overview) if isinstance(overview, dict) else overview}",
        )
    )

    items = overview.get("usage_items") or []
    codes = {i.get("code") for i in items}
    results.append(
        check(
            "VA18-2 含店铺/商品/提审用量",
            "quota.max_shops" in codes
            and "quota.max_products" in codes
            and "usage.product_review_submit" in codes,
            str(codes),
        )
    )
    shops = next((i for i in items if i.get("code") == "quota.max_shops"), {})
    results.append(
        check(
            "VA18-3 店铺 used 为整数",
            isinstance(shops.get("used"), int) and shops.get("used") >= 0 and "label" in shops,
            str(shops),
        )
    )

    code, usage = req("GET", "/shop/subscription/usage", token=merchant)
    results.append(
        check(
            "VA18-4 usage 接口",
            code == 200 and isinstance(usage.get("items"), list) and len(usage["items"]) >= 3,
            f"{code} {usage}",
        )
    )

    code, ents = req("GET", "/shop/subscription/entitlements", token=merchant)
    results.append(
        check(
            "VA18-5 entitlements 兼容",
            code == 200
            and ents.get("state") == "onboarded"
            and isinstance(ents.get("quotas"), dict)
            and isinstance(ents.get("usage_groups"), list),
            f"{code}",
        )
    )

    code, subs = req("GET", "/shop/subscription/subscriptions", token=merchant)
    results.append(
        check(
            "VA18-6 subscriptions 列表",
            code == 200 and isinstance(subs.get("items"), list),
            f"{code} {subs}",
        )
    )

    # 中文 label，无内部技术码进 UI 文案核心区（功能码仍可在 API）
    labels = " ".join(str(i.get("label")) for i in items)
    results.append(
        check(
            "VA18-7 展示中文名",
            "店铺数" in labels and "在售商品槽位" in labels,
            labels,
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA18: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
