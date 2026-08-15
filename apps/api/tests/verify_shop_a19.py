#!/usr/bin/env python3
"""A19 单店设置。对照 PRD 01#a19。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "StoreSettings.vue"


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


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA19-UI 单店设置页",
            _page_has(
                WEB,
                "#a19",
                "店铺名称（对外）",
                "保存本店展示",
                "退款默认",
                "保存退款默认",
                "默认平台类目",
                "未支付关单",
            ),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    code, settings = req("GET", "/shop/stores/settings", token=merchant)
    mins = settings.get("close_order_minutes") if isinstance(settings, dict) else None
    results.append(
        check(
            "VA19-1 读取设置",
            code == 200
            and settings.get("shop_id")
            and isinstance(mins, int)
            and 5 <= mins <= 1440
            and settings.get("default_refund_policy") in (
                "always_allow",
                "before_fulfill",
                "manual_only",
            ),
            f"{code} {settings}",
        )
    )
    shop_id = settings.get("shop_id") if code == 200 else None

    # 取启用类目
    code, cats = req("GET", "/shop/platform-categories?status=enabled", token=merchant)
    cat_id = (cats.get("items") or [{}])[0].get("id") if code == 200 else None

    new_name = f"智学课堂-{uuid.uuid4().hex[:4]}"
    code, saved = req(
        "PATCH",
        "/shop/stores/settings/display",
        token=merchant,
        body={
            "shop_id": shop_id,
            "name": new_name,
            "intro": "专注职业技能与考证培训",
            "service_phone": "020-12345678",
            "theme_color": "#1677ff",
            "close_order_minutes": 45,
            "default_category_id": cat_id,
        },
    )
    results.append(
        check(
            "VA19-2 保存本店展示",
            code == 200
            and saved.get("name") == new_name
            and saved.get("close_order_minutes") == 45
            and (not cat_id or saved.get("default_category_id") == cat_id),
            f"{code} {saved}",
        )
    )

    code, bad = req(
        "PATCH",
        "/shop/stores/settings/display",
        token=merchant,
        body={"name": "", "shop_id": shop_id},
    )
    results.append(
        check(
            "VA19-3 空店名拒绝",
            code == 422 and "店铺名称" in _err(bad),
            f"{code} {bad}",
        )
    )

    code, refund = req(
        "PATCH",
        "/shop/stores/settings/refund",
        token=merchant,
        body={"shop_id": shop_id, "default_refund_policy": "always_allow"},
    )
    results.append(
        check(
            "VA19-4 保存退款默认",
            code == 200 and refund.get("default_refund_policy") == "always_allow",
            f"{code} {refund}",
        )
    )

    # 新建商品应继承退款默认
    from tests.http_client import _get_test_client

    client = _get_test_client()
    cover = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("a19.png", b"\x89PNG", "image/png")},
    ).json()["file_url"]
    code, col = req(
        "POST",
        "/shop/columns",
        token=merchant,
        body={"title": f"A19col-{uuid.uuid4().hex[:6]}", "intro": "d"},
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
            "media_url": "https://example.com/a19.mp4",
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
            "name": f"A19课-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    results.append(
        check(
            "VA19-5 新建商品继承退款默认",
            code == 200 and prod.get("refund_policy") == "always_allow",
            f"{code} {prod.get('refund_policy')}",
        )
    )
    results.append(
        check(
            "VA19-6 新建商品继承默认类目",
            code == 200 and (not cat_id or prod.get("category_id") == cat_id),
            f"{prod.get('category_id')} vs {cat_id}",
        )
    )

    # 恢复默认退款，避免污染其它用例
    req(
        "PATCH",
        "/shop/stores/settings/refund",
        token=merchant,
        body={"shop_id": shop_id, "default_refund_policy": "before_fulfill"},
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA19: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
