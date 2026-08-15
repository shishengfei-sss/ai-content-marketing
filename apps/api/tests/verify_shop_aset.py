#!/usr/bin/env python3
"""A-SET 设置中心。对照 PRD 01#a-settings · #s-account。"""

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
from tests.verify_shop_a16 import _force_admin, login  # noqa: E402

HUB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "SettingsHub.vue"
ACCOUNT = REPO_ROOT / "apps" / "web" / "src" / "views" / "SettingsAccount.vue"
NAV = REPO_ROOT / "apps" / "web" / "src" / "config" / "permissions.js"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"


def _has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VASET-UI 设置中心卡片",
            _has(
                HUB,
                "#a-settings",
                "我的账号",
                "支付与进件",
                "短信 / 领权",
                "公域对接",
                "套餐信息",
                "单店设置",
                "角色与成员",
                "/shop/store-settings",
            ),
            str(HUB),
        )
    )
    results.append(
        check(
            "VASET-UI 我的账号页",
            _has(ACCOUNT, "#s-account", "昵称", "登录手机号", "修改密码", "保存"),
            str(ACCOUNT),
        )
    )
    results.append(
        check(
            "VASET-路由 中心=/shop/settings · A19=/shop/store-settings",
            _has(ROUTER, "ShopSettingsHub", "shop/store-settings", "settings/account"),
            str(ROUTER),
        )
    )
    nav_text = NAV.read_text(encoding="utf-8")
    results.append(
        check(
            "VASET-侧栏 设置进中心",
            "shop-settings-hub" in nav_text
            and "path: '/shop/settings'" in nav_text
            and "title: '设置'" in nav_text
            and "shop-payment" not in nav_text,
            "nav hub only",
        )
    )

    merchant, tid = _ensure_merchant()
    _force_admin("13900000099", tid)
    merchant = login("13900000099", "test123456")

    code, me = req("GET", "/auth/me", token=merchant)
    old_name = me.get("display_name") if code == 200 else ""
    new_name = "ASET联测昵称"
    code, patched = req("PATCH", "/auth/me", token=merchant, body={"display_name": new_name})
    results.append(
        check(
            "VASET-1 PATCH 昵称",
            code == 200 and patched.get("display_name") == new_name,
            f"{code} {patched}",
        )
    )
    code, bad = req("PATCH", "/auth/me", token=merchant, body={"display_name": "A"})
    detail = str((bad or {}).get("detail") if isinstance(bad, dict) else bad)
    results.append(
        check(
            "VASET-2 昵称过短",
            code == 422 and ("2–30" in detail or "2-30" in detail or "昵称" in detail),
            f"{code} {detail}",
        )
    )
    # 还原
    if old_name and len(str(old_name).strip()) >= 2:
        req("PATCH", "/auth/me", token=merchant, body={"display_name": old_name})

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA-SET result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
