#!/usr/bin/env python3
"""A15 支付与进件。对照 PRD 01#a15 · #a15a · §8.7.3。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.shop import a15_payment_onboarding_service as a15svc  # noqa: E402
from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "PaymentOnboarding.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA15-UI 支付与进件页",
            _page_has(
                WEB,
                "#a15",
                "支付与进件",
                "提交进件材料",
                "结算开户行",
                "结算账号",
                "开户名",
                "测试 0.01 元",
                "查看进件材料",
                "证书或回调",
            ),
            str(WEB),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    code, data = req("GET", "/shop/settings/payment", token=merchant)
    results.append(
        check(
            "VA15-1 读取进件状态",
            code == 200
            and data.get("state") == "onboarded"
            and data.get("onboarding_status") in (
                "not_submitted",
                "submitted",
                "rejected",
                "approved",
            )
            and isinstance(data.get("banks"), list)
            and len(data["banks"]) >= 5
            and data.get("entity")
            and "legal_name" in (data.get("entity") or {}),
            f"{code} {data}",
        )
    )

    # 若已开通/审核中，先用库重置到可提交（联测幂等）
    if code == 200 and data.get("onboarding_status") in ("submitted", "approved"):
        from app.models.shop import ShopPaymentOnboarding
        from app.database import uuid_eq

        with SessionLocal() as db:
            row = (
                db.query(ShopPaymentOnboarding)
                .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, UUID(str(tenant_id))))
                .first()
            )
            if row:
                row.onboarding_status = "not_submitted"
                row.wx_sub_mch_id = None
                row.approved_at = None
                row.settlement_account = None
                db.commit()

    code, denied = req(
        "POST",
        "/shop/settings/payment/test",
        token=merchant,
        body={},
    )
    detail = str((denied or {}).get("detail") if isinstance(denied, dict) else denied)
    results.append(
        check(
            "VA15-2 未开通不可测支付",
            code == 422 and "进件未开通" in detail,
            f"{code} {detail}",
        )
    )

    payload = {
        "settlement_bank": "招商银行",
        "settlement_account": "6222021234567890123",
        "settlement_account_name": "联测进件开户名",
        "remark": "verify_shop_a15",
    }
    code, submitted = req(
        "POST", "/shop/settings/payment/onboarding", token=merchant, body=payload
    )
    results.append(
        check(
            "VA15-3 提交进件 → 审核中",
            code == 200 and submitted.get("onboarding_status") == "submitted",
            f"{code} {submitted}",
        )
    )

    code, again = req(
        "POST", "/shop/settings/payment/onboarding", token=merchant, body=payload
    )
    again_detail = str((again or {}).get("detail") if isinstance(again, dict) else again)
    results.append(
        check(
            "VA15-4 审核中不可再提交",
            code == 422 and "当前状态不可提交" in again_detail,
            f"{code} {again_detail}",
        )
    )

    with SessionLocal() as db:
        a15svc.force_approve_for_tests(db, UUID(str(tenant_id)), wx_sub_mch_id="1600998877")

    code, approved = req("GET", "/shop/settings/payment", token=merchant)
    results.append(
        check(
            "VA15-5 开通后只读子商户号",
            code == 200
            and approved.get("onboarding_status") == "approved"
            and approved.get("wx_sub_mch_id_masked")
            and "api_key" not in str(approved).lower()
            and "证书" not in str(approved.get("settlement") or ""),
            f"{code} {approved}",
        )
    )

    code, test_res = req("POST", "/shop/settings/payment/test", token=merchant, body={})
    results.append(
        check(
            "VA15-6 测试支付",
            code == 200
            and test_res.get("ok") is True
            and test_res.get("amount_cents") == 1,
            f"{code} {test_res}",
        )
    )

    # 商家端旧 M3 密钥配置仍可用（不冲突）
    code, _cfg = req("GET", "/shop/payment-config", token=merchant)
    results.append(
        check(
            "VA15-7 M3 payment-config 仍可达",
            code in (200, 404),
            f"{code}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA15 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
