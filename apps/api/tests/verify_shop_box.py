#!/usr/bin/env python3
"""开箱交付自检 BOX-D1 / D2 / D7。对照 27-开箱交付验收.md · 开箱即用交付标准 §4～§5。

不代勾 BOX-SMOKE（须产品本人）。D3/D5 页面走通见启动说明；买家 M02～M05 已交付 API + H5 页。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.seed_shop_demo import ACCOUNTS, COURSE_NAME, DEMO_PREFIX, seed  # noqa: E402


def login(phone: str, password: str, workspace: str | None = None) -> tuple[int, dict]:
    body: dict = {"phone": phone, "password": password}
    if workspace:
        body["workspace_mode"] = workspace
    return req("POST", "/auth/login", body=body)


def main() -> int:
    results: list[bool] = []

    info1 = seed(reset=False)
    info2 = seed(reset=False)
    results.append(check("BOX-D1-B1 二次种子不炸", info1["tenant_id"] == info2["tenant_id"], info2["tenant_id"]))

    from app.config import settings
    from app.database import SessionLocal
    from app.models.shop import ShopBuyer, ShopEntitlement, ShopMerchantAccount, ShopOnboardingApplication, ShopProduct

    db = SessionLocal()
    try:
        statuses = {s for (s,) in db.query(ShopMerchantAccount.status).distinct().all()}
        pending_ob = db.query(ShopOnboardingApplication).filter(ShopOnboardingApplication.status == "pending").count()
        demo_on_sale = (
            db.query(ShopProduct)
            .filter(ShopProduct.name.like(f"{DEMO_PREFIX}%"), ShopProduct.status == "on_sale")
            .count()
        )
        ents = db.query(ShopEntitlement).filter(ShopEntitlement.status == "active").count()
        buyers = db.query(ShopBuyer).filter(ShopBuyer.wx_openid == "demo_buyer_paid").count()
        types = {
            t
            for (t,) in db.query(ShopProduct.type)
            .filter(ShopProduct.name.like(f"{DEMO_PREFIX}%"), ShopProduct.status == "on_sale")
            .distinct()
            .all()
        }
    finally:
        db.close()

    results.append(
        check(
            "BOX-D1-B2 商家状态机齐全",
            {"active", "suspended", "closed"}.issubset(statuses) and pending_ob >= 1,
            f"status={sorted(statuses)} pending_ob={pending_ob}",
        )
    )
    results.append(
        check(
            "BOX-D1-S1 演示前缀商品三类在售",
            demo_on_sale >= 3 and {"course", "digital", "service"}.issubset(types),
            f"on_sale={demo_on_sale} types={sorted(types)} course={COURSE_NAME}",
        )
    )
    results.append(check("BOX-D1 已购权益+买家", ents >= 1 and buyers >= 1, f"ents={ents} buyers={buyers}"))

    for key, ws in (
        ("platform_super", "platform"),
        ("platform_ops", "platform"),
        ("platform_cs", "platform"),
        ("merchant_active", "merchant"),
        ("merchant_reviewing", "merchant"),
        ("merchant_none", "merchant"),
        ("merchant_suspended", "merchant"),
        ("merchant_closed", "merchant"),
    ):
        acc = ACCOUNTS[key]
        code, data = login(acc["phone"], acc["password"], ws)
        results.append(check(f"BOX-D2 可登 {key}", code == 200 and bool(data.get("access_token")), str(code)))

    code, data = login(ACCOUNTS["merchant_active"]["phone"], "wrong-password-xx", "merchant")
    detail = str(data.get("detail") or data)
    results.append(
        check(
            "BOX-D2-B2 错密中文提示",
            code in (401, 403) and any(ch in detail for ch in ("密码", "错误", "账号")),
            f"{code} {detail[:80]}",
        )
    )

    results.append(
        check(
            "BOX-D7 Mock 支付默认开",
            str(getattr(settings, "WECHAT_PAY_MOCK", "1")) in ("1", "true", "True")
            and str(getattr(settings, "WECHAT_PAY_MODE", "stub")) in ("stub", "mock"),
            f"MOCK={settings.WECHAT_PAY_MOCK} MODE={settings.WECHAT_PAY_MODE}",
        )
    )
    results.append(
        check(
            "BOX-D7 短信 Mock 默认",
            str(getattr(settings, "SMS_PROVIDER", "mock")).lower() == "mock",
            str(settings.SMS_PROVIDER),
        )
    )

    print(f"tenant_id={info2['tenant_id']}")
    print(f"claim={info2['claim_token']}")
    ok = all(results)
    print(f"{'PASS' if ok else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
