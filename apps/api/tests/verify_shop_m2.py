#!/usr/bin/env python3
"""M2 商家状态机验收：暂停/恢复/清退 + A20 校验。对照执行计划 §6.2。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _pick_active_enterprise(admin: str) -> str:
    code, data = req("GET", "/admin/shop/merchants", token=admin)
    assert code == 200, data
    for item in data.get("items") or []:
        if (
            item.get("merchant_id")
            and item.get("onboarding_status") == "active"
            and item.get("entity_type") == "enterprise"
        ):
            return item["tenant_id"]
    raise RuntimeError("no active enterprise merchant")


def _cs_token() -> str:
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    phone = "13800000088"
    password = "cs12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城管家测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def main() -> int:
    results: list[bool] = []
    admin = login("13800000000", "admin123456")
    tenant_id = _pick_active_enterprise(admin)

    # VS-M2-01 active→suspended→active
    code_s, d1 = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/suspend",
        token=admin,
        body={"reason_code": "other", "reason_text": "验收暂停原因足够"},
    )
    code_r, d2 = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/resume",
        token=admin,
        body={"note": "验收恢复"},
    )
    results.append(
        check(
            "VS-M2-01 active→suspended→active",
            code_s == 200
            and d1.get("onboarding_status") == "suspended"
            and code_r == 200
            and d2.get("onboarding_status") == "active",
            f"s={code_s}/{d1.get('onboarding_status')} r={code_r}/{d2.get('onboarding_status')}",
        )
    )

    # VS-M2-04 无 merchant.manage → 403（管家）
    cs = _cs_token()
    code_403, _ = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/suspend",
        token=cs,
        body={"reason_code": "other", "reason_text": "应被拒绝的暂停"},
    )
    results.append(check("VS-M2-04 无 manage → 403", code_403 == 403, str(code_403)))

    # VS-M2-01 后再暂停，供清退路径
    req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/suspend",
        token=admin,
        body={"reason_code": "violation", "reason_text": "准备清退前暂停"},
    )

    # VS-M2-02 suspended→closed；再次清退 409/422
    code_c, d3 = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/close",
        token=admin,
        body={
            "reason_code": "merchant_request",
            "reason_text": "验收清退说明足够",
            "ack_irreversible": True,
        },
    )
    code_c2, d4 = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/close",
        token=admin,
        body={
            "reason_code": "merchant_request",
            "reason_text": "再次清退应失败",
            "ack_irreversible": True,
        },
    )
    results.append(
        check(
            "VS-M2-02 suspended→closed 且不可再清",
            code_c == 200
            and d3.get("onboarding_status") == "closed"
            and code_c2 in (409, 422),
            f"c={code_c} c2={code_c2}",
        )
    )

    # VS-M2-03 closed 开通订阅 422
    code_sub, sub = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "paid_amount_cents": 0,
            "remark": "closed should fail",
        },
    )
    results.append(
        check("VS-M2-03 closed 开通订阅 422", code_sub == 422 and "清退" in str(sub), f"{code_sub} {sub}")
    )

    # 交易闸单测
    from app.database import SessionLocal
    from app.services.shop.merchant_status_service import assert_merchant_not_blocked_for_trade

    db = SessionLocal()
    blocked = False
    try:
        assert_merchant_not_blocked_for_trade(db, uuid.UUID(str(tenant_id)))
    except Exception as e:
        blocked = "清退" in str(getattr(e, "detail", e))
    finally:
        db.close()
    results.append(check("VS-M2-03b 新购闸", blocked, "trade gate"))

    # VS-M2-05 自申必填校验（商家账号）
    try:
        merch = login("13900000102", "demo123456")
    except Exception:
        merch = None
    if merch:
        code_m, data_m = req(
            "POST",
            "/shop/onboarding/applications",
            token=merch,
            body={
                "entity_type": "personal",
                "legal_name": "缺证号测试",
                "contact_name": "测试",
                "contact_mobile": "13900001111",
                "qualification_files": {"id_card_front": "x", "id_card_back": "y"},
            },
        )
        results.append(
            check("VS-M2-05 自申缺证号 422", code_m == 422, f"{code_m} {data_m}")
        )
        # VS-M2-06 pending 再自申 → 409（若已 reviewing/pending）
        code_dup, data_dup = req(
            "POST",
            "/shop/onboarding/applications",
            token=merch,
            body={
                "entity_type": "personal",
                "legal_name": "重复提交",
                "contact_name": "测试",
                "contact_mobile": "13900001111",
                "id_no": "110101199001011234",
                "qualification_files": {
                    "id_card_front": "f1",
                    "id_card_back": "f2",
                    "handheld": "f3",
                },
            },
        )
        results.append(
            check(
                "VS-M2-06 pending/已入驻再自申",
                code_dup in (409, 422),
                f"{code_dup} {data_dup}",
            )
        )
    else:
        results.append(check("VS-M2-05 自申缺证号 422", False, "no merchant login"))
        results.append(check("VS-M2-06 pending/已入驻再自申", False, "no merchant login"))

    # VS-M2-07 清退后写接口拒：resume 422
    code_resume, dr = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/resume",
        token=admin,
        body={"note": "不可恢复"},
    )
    results.append(
        check("VS-M2-07 清退后 resume 拒", code_resume == 422 and "清退" in str(dr), f"{code_resume}")
    )

    # UI 文件
    web = API_ROOT.parent / "web" / "src" / "views" / "admin" / "shop" / "MerchantDetail.vue"
    results.append(check("VS-M2-UI 详情含清退", web.is_file() and "清退" in web.read_text(encoding="utf-8"), ""))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
