#!/usr/bin/env python3
"""A14-B 查看原因 + 重新提交验收。对照 PRD 01-管理端UI.html #a14b。"""

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
from tests.verify_shop_a14 import _ensure_merchant, _on_sale_product  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "ChannelMappings.vue"


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


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA14B-UI 原因抽屉与重提",
            _page_has(
                WEB,
                "外部审核被拒",
                "抖店驳回码",
                "修改并重新提交",
                "去编辑商品",
                "openReason",
                "resubmit",
                "#a14b",
            ),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    secret = f"a14b_{uuid.uuid4().hex[:10]}"
    code, cfg = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "enabled_combos": ["1A"],
            "douyin_shop_id": f"dy_{uuid.uuid4().hex[:8]}",
            "douyin_webhook_secret": secret,
        },
    )
    assert code == 200, cfg

    pid = _on_sale_product(merchant)
    ch_pid = f"Dou{uuid.uuid4().hex[:8]}"
    code, mapping = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel": "douyin",
            "channel_product_id": ch_pid,
            "combo": "1A",
        },
    )
    assert code == 200, mapping
    mid = mapping["id"]

    code, rejected = req(
        "POST",
        f"/shop/channel-mappings/{mid}/external-audit",
        token=merchant,
        body={
            "result": "rejected",
            "reject_code": "CATEGORY_MISMATCH",
            "reject_reason": "商品类目与资质不符，请调整类目后提交审核",
        },
    )
    results.append(
        check(
            "VA14B-1 外部拒审→阻断",
            code == 200
            and rejected.get("status") == "blocked"
            and rejected.get("external_audit_status") == "rejected"
            and rejected.get("mount_blocked_code") == "CATEGORY_MISMATCH"
            and "类目" in (rejected.get("mount_blocked_reason") or ""),
            f"{code} {rejected}",
        )
    )

    code, pending = req(
        "POST",
        f"/shop/channel-mappings/{mid}/resubmit",
        token=merchant,
        body={"note": "已调整类目"},
    )
    results.append(
        check(
            "VA14B-2 重新提交→pending",
            code == 200
            and pending.get("status") == "pending"
            and pending.get("external_audit_status") == "submitted"
            and pending.get("channel_product_id") == ch_pid,
            f"{code} {pending}",
        )
    )

    code, again = req(
        "POST",
        f"/shop/channel-mappings/{mid}/resubmit",
        token=merchant,
        body={},
    )
    results.append(
        check(
            "VA14B-3 非阻断不可重提",
            code == 422 and ("阻断" in _err_text(again) or "被拒" in _err_text(again)),
            f"{code} {_err_text(again)}",
        )
    )

    code, approved = req(
        "POST",
        f"/shop/channel-mappings/{mid}/external-audit",
        token=merchant,
        body={"result": "approved"},
    )
    results.append(
        check(
            "VA14B-4 重提后过审→mapped",
            code == 200 and approved.get("status") == "mapped",
            f"{code} {approved.get('status')}",
        )
    )

    code, logs = req(
        "GET",
        f"/shop/channel-mappings/{mid}/logs?category=external_audit",
        token=merchant,
    )
    evs = [i.get("event") for i in (logs.get("items") or [])]
    results.append(
        check(
            "VA14B-5 日志含拒审/重提/通过",
            code == 200
            and "external_audit_rejected" in evs
            and "external_audit_resubmitted" in evs
            and "external_audit_approved" in evs,
            f"{code} {evs}",
        )
    )

    # 另建商品再阻断，验证已阻断 Tab
    pid2 = _on_sale_product(merchant)
    code2, m2 = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid2,
            "channel": "douyin",
            "channel_product_id": f"Dou{uuid.uuid4().hex[:8]}",
            "combo": "1A",
        },
    )
    assert code2 == 200, m2
    req(
        "POST",
        f"/shop/channel-mappings/{m2['id']}/external-audit",
        token=merchant,
        body={
            "result": "rejected",
            "reject_code": "TITLE_INVALID",
            "reject_reason": "标题不合规请修改",
        },
    )
    code, mlist = req(
        "GET", "/shop/channel-mappings?status=blocked&page=1&page_size=20", token=merchant
    )
    results.append(
        check(
            "VA14B-6 已阻断列表可筛",
            code == 200 and (mlist.get("total") or 0) >= 1,
            f"{code} {mlist.get('total')}",
        )
    )

    passed = sum(1 for x in results if x)
    print(f"\nA14-B: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
