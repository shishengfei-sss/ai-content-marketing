#!/usr/bin/env python3
"""A23 公域对接设置。对照 PRD 01#a23 · #a23-t · #a23-s · #a23-webhook。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ChannelSettings.vue"
HUB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "SettingsHub.vue"
A14 = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ChannelMappings.vue"


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


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA23-UI 公域对接页",
            _page_has(
                WEB,
                "#a23",
                "选链路 / 选路径",
                "绑定外部店铺",
                "回调验通",
                "保存绑店",
                "发送测试",
                "保存对接设置",
                "链路 ①",
                "路径 A",
                "外部店铺 ID",
            )
            and _page_has(HUB, "公域对接", "/shop/channel-settings")
            and _page_has(A14, "/shop/channel-settings"),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    admin = login("13800000000", "admin123456", "platform")

    code, empty = req(
        "POST",
        "/shop/channel-settings/bind",
        token=merchant,
        body={"douyin_shop_id": "   "},
    )
    results.append(
        check(
            "VA23-1 空店铺 ID TC-A23-E01",
            code == 422 and "外部店铺 ID" in _err(empty),
            f"{code} {_err(empty)}",
        )
    )

    shop_id = f"dy_{uuid.uuid4().hex[:8]}"
    code, bound = req(
        "POST",
        "/shop/channel-settings/bind",
        token=merchant,
        body={"douyin_shop_id": shop_id},
    )
    results.append(
        check(
            "VA23-2 保存绑店 TC-A23-F01",
            code == 200
            and bound.get("bind_status") == "available"
            and bound.get("douyin_shop_id") == shop_id,
            f"{code} {bound}",
        )
    )

    code, path_b = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={"deal_link": "1", "path_mode": "B", "douyin_shop_id": shop_id},
    )
    results.append(
        check(
            "VA23-3 路径 B 灰显",
            code == 422 and "未开通" in _err(path_b),
            f"{code} {_err(path_b)}",
        )
    )

    code, link2 = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={"deal_link": "2", "path_mode": "A", "douyin_shop_id": shop_id},
    )
    results.append(
        check(
            "VA23-4 链路② 套餐未开通",
            code == 422 and "套餐未开通" in _err(link2),
            f"{code} {_err(link2)}",
        )
    )

    code, saved = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={"deal_link": "1", "path_mode": "A", "douyin_shop_id": shop_id},
    )
    results.append(
        check(
            "VA23-5 保存对接设置",
            code == 200 and saved.get("combo_label") == "链路① · 路径A",
            f"{code} {saved}",
        )
    )

    req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={"douyin_shop_id": shop_id, "douyin_webhook_secret": ""},
    )
    code, no_cb = req("POST", "/shop/channel-settings/send-test", token=merchant, body={})
    results.append(
        check(
            "VA23-6 无密钥不可验通",
            code == 422 and "回调未配置" in _err(no_cb),
            f"{code} {_err(no_cb)}",
        )
    )

    secret = f"a23_{uuid.uuid4().hex[:10]}"
    code, with_sec = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "douyin_shop_id": shop_id,
            "douyin_webhook_secret": secret,
            "enabled_combos": ["1A"],
        },
    )
    results.append(
        check(
            "VA23-7 写入密钥后已配置",
            code == 200 and with_sec.get("douyin_configured") is True,
            f"{code} {with_sec}",
        )
    )

    code, tested = req("POST", "/shop/channel-settings/send-test", token=merchant, body={})
    results.append(
        check(
            "VA23-8 发送测试验通",
            code == 200 and tested.get("webhook_verified") is True,
            f"{code} {tested}",
        )
    )

    code, forbidden = req(
        "POST",
        "/shop/channel-settings/bind",
        token=admin,
        body={"douyin_shop_id": "dy_forbidden"},
    )
    results.append(
        check(
            "VA23-9 平台账号无商家权 TC-A23-E02",
            code in (401, 403),
            f"{code}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA23 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
