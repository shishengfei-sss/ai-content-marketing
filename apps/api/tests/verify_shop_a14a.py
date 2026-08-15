#!/usr/bin/env python3
"""A14-A 新建映射三步向导验收。对照 PRD 01-管理端UI.html #a14a · #a14a-step1/2/3。"""

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


def _second_on_sale_product(token: str, exclude_id: str) -> str:
    """再造一个可映射在售商品（避免 product_already_mapped）。"""
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct

    db = SessionLocal()
    try:
        src = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, uuid.UUID(str(exclude_id)))).first()
        assert src, "source product missing"
        p = ShopProduct(
            id=uuid.uuid4(),
            tenant_id=src.tenant_id,
            shop_id=src.shop_id,
            name=f"A14A副品-{uuid.uuid4().hex[:6]}",
            type=src.type or "course",
            status="on_sale",
            price_cents=int(src.price_cents or 9900),
            last_review_id=src.last_review_id,
            cover_url=getattr(src, "cover_url", None),
        )
        db.add(p)
        db.commit()
        return str(p.id)
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA14A-UI 三步向导抽屉",
            _page_has(
                WEB,
                "#a14a",
                "1 选品与店",
                "2 同步抖店",
                "3 确认提交",
                "同步并下一步",
                "提交映射",
                "preview-sync",
                "submit_mode: 'audit'",
                "抖店展示标题",
                "抖店类目",
                "openWizard",
            ),
            str(WEB),
        )
    )

    merchant, _tid = _ensure_merchant()
    secret = f"a14a_{uuid.uuid4().hex[:10]}"
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
    # 若该品已有活跃映射，换副品
    code, listing = req("GET", "/shop/channel-mappings?page_size=50", token=merchant)
    assert code == 200, listing
    busy = {
        str(i.get("product_id"))
        for i in (listing.get("items") or [])
        if i.get("status") in ("mapped", "pending", "paused", "syncing")
    }
    if pid in busy:
        pid = _second_on_sale_product(merchant, pid)

    # 步2：预同步
    code, preview = req(
        "POST",
        "/shop/channel-mappings/preview-sync",
        token=merchant,
        body={
            "product_id": pid,
            "combo": "1A",
            "external_title": "A14A验收课",
            "external_category": "教育培训 / 职业技能",
            "sync_mode": "create_new",
        },
    )
    results.append(
        check(
            "VA14A-1 preview-sync 预分配外部 ID",
            code == 200
            and (preview.get("channel_product_id") or "").startswith("Dou")
            and preview.get("external_title") == "A14A验收课"
            and preview.get("price_cents") is not None,
            f"{code} {preview}",
        )
    )
    ch_pid = preview.get("channel_product_id") if code == 200 else f"Dou{uuid.uuid4().hex[:8]}"

    # 标题过短
    code, bad = req(
        "POST",
        "/shop/channel-mappings/preview-sync",
        token=merchant,
        body={
            "product_id": pid,
            "combo": "1A",
            "external_title": "A",
            "external_category": "教育培训 / 职业技能",
            "sync_mode": "create_new",
        },
    )
    results.append(
        check(
            "VA14A-2 标题过短 422",
            code == 422 and ("2" in _err_text(bad) or "标题" in _err_text(bad)),
            f"{code} {bad}",
        )
    )

    # 步3：提交 audit
    code, mapping = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel": "douyin",
            "channel_product_id": ch_pid,
            "combo": "1A",
            "external_title": "A14A验收课",
            "external_category": "教育培训 / 职业技能",
            "sync_mode": "create_new",
            "submit_mode": "audit",
        },
    )
    results.append(
        check(
            "VA14A-3 提交→pending+submitted",
            code == 200
            and mapping.get("status") == "pending"
            and mapping.get("external_audit_status") == "submitted"
            and mapping.get("channel_product_id") == ch_pid,
            f"{code} {mapping}",
        )
    )
    mid = mapping.get("id") if code == 200 else None

    # 同品不可再映射
    code, dup = req(
        "POST",
        "/shop/channel-mappings/preview-sync",
        token=merchant,
        body={
            "product_id": pid,
            "combo": "1A",
            "external_title": "重复映射",
            "external_category": "教育培训 / 职业技能",
            "sync_mode": "create_new",
        },
    )
    results.append(
        check(
            "VA14A-4 同品活跃映射禁预同步",
            code == 409 and "product_already_mapped" in _err_text(dup),
            f"{code} {dup}",
        )
    )

    # 外部过审 → mapped
    if mid:
        code, approved = req(
            "POST",
            f"/shop/channel-mappings/{mid}/external-audit",
            token=merchant,
            body={"result": "approved"},
        )
        results.append(
            check(
                "VA14A-5 外部过审→mapped",
                code == 200
                and approved.get("status") == "mapped"
                and approved.get("external_audit_status") == "approved",
                f"{code} {approved}",
            )
        )
    else:
        results.append(check("VA14A-5 外部过审→mapped", False, "no mapping id"))

    # 旧兼容：submit_mode 默认仍可 mapped（用副品）
    pid2 = _second_on_sale_product(merchant, pid)
    code, legacy = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid2,
            "channel": "douyin",
            "channel_product_id": f"DouLEG{uuid.uuid4().hex[:8]}",
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VA14A-6 兼容直挂 mapped",
            code == 200 and legacy.get("status") == "mapped",
            f"{code} {legacy}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA14-A: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
