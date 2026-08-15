#!/usr/bin/env python3
"""P02-C/D/F 暂停 / 恢复 / 清退。对照 PRD 06#p02c · #p02d · #p02f。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "admin" / "shop" / "MerchantsList.vue"


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


def _ensure_cs_user() -> str:
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
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def _pick_active(admin: str) -> str | None:
    code, data = req("GET", "/admin/shop/merchants?page_size=50", token=admin)
    if code != 200:
        return None
    for item in data.get("items") or []:
        if item.get("merchant_id") and item.get("onboarding_status") == "active":
            return item["tenant_id"]
    return None


def _create_and_approve(admin: str) -> str | None:
    code, opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin)
    items = (opts or {}).get("items") or []
    if code != 200 or not items:
        return None
    tid = items[0]["tenant_id"]
    code, created = req(
        "POST",
        "/admin/shop/onboarding/applications",
        token=admin,
        body={
            "tenant_id": tid,
            "entity_type": "enterprise",
            "legal_name": f"验收清退主体-{uuid.uuid4().hex[:6]}",
            "display_name": f"验收清退商家-{uuid.uuid4().hex[:6]}",
            "contact_name": "测试联系人",
            "contact_mobile": "13900003333",
            "unified_social_credit_code": "91110000MA01234567",
            "legal_rep_name": "张三",
        },
    )
    if code != 201:
        return None
    app_id = created.get("id")
    code_a, approved = req(
        "POST",
        f"/admin/shop/onboarding/applications/{app_id}/approve",
        token=admin,
        body={"plan_label": "7天试用基础版", "trial_days": 7, "store_quota": 1},
    )
    if code_a != 200:
        return None
    return approved.get("tenant_id") or tid


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "VP02C-UI 暂停/恢复/清退栏位 TC-P02-F01",
            _page_has(
                WEB,
                "#p02c",
                "#p02d",
                "#p02f",
                "影响说明（只读）",
                "暂停原因",
                "确认暂停",
                "恢复后影响（只读）",
                "确认恢复",
                "确认清退",
                "我已知晓清退不可恢复",
                'data-testid="shop-merchants"',
            )
            and "即将开放" not in WEB.read_text(encoding="utf-8"),
            str(WEB),
        )
    )

    admin = login("13800000000", "admin123456", "platform")
    tid = _pick_active(admin)

    if tid:
        code_e, empty = req(
            "POST",
            f"/admin/shop/merchants/{tid}/suspend",
            token=admin,
            body={"reason_code": "violation", "reason_text": ""},
        )
        results.append(
            check(
                "VP02C-E01 暂停说明为空 422 TC-P02C-F01-B1",
                code_e == 422 and "暂停原因" in _err(empty),
                f"{code_e} {_err(empty)}",
            )
        )
        code_s, d1 = req(
            "POST",
            f"/admin/shop/merchants/{tid}/suspend",
            token=admin,
            body={"reason_code": "arrears", "reason_text": "验收暂停原因足够"},
        )
        results.append(
            check(
                "VP02C-F01 暂停成功 TC-P02C-F01",
                code_s == 200 and d1.get("onboarding_status") == "suspended",
                f"{code_s} {_err(d1)}",
            )
        )
        code_r, d2 = req(
            "POST",
            f"/admin/shop/merchants/{tid}/resume",
            token=admin,
            body={"note": "验收恢复"},
        )
        results.append(
            check(
                "VP02D-F01 恢复成功",
                code_r == 200 and d2.get("onboarding_status") == "active",
                f"{code_r} {_err(d2)}",
            )
        )
        code_ack, ack = req(
            "POST",
            f"/admin/shop/merchants/{tid}/close",
            token=admin,
            body={"reason_code": "violation", "reason_text": "合同终止平台清退验收", "ack_irreversible": False},
        )
        results.append(
            check(
                "VP02F-E01 未勾不可恢复 422 TC-P02F-E01",
                code_ack == 422 and "不可恢复" in _err(ack),
                f"{code_ack} {_err(ack)}",
            )
        )
    else:
        results.append(check("VP02C-E01 暂停说明为空 422 TC-P02C-F01-B1", False, "无 active 商家"))
        results.append(check("VP02C-F01 暂停成功 TC-P02C-F01", False, "跳过"))
        results.append(check("VP02D-F01 恢复成功", False, "跳过"))
        results.append(check("VP02F-E01 未勾不可恢复 422 TC-P02F-E01", False, "跳过"))

    close_tid = _create_and_approve(admin)
    if close_tid:
        code_c, d3 = req(
            "POST",
            f"/admin/shop/merchants/{close_tid}/close",
            token=admin,
            body={
                "reason_code": "merchant_request",
                "reason_text": "合同终止，平台清退",
                "ack_irreversible": True,
            },
        )
        results.append(
            check(
                "VP02F-F01 清退成功 TC-P02F-F01",
                code_c == 200 and d3.get("onboarding_status") == "closed",
                f"{code_c} {_err(d3)}",
            )
        )
        code_c2, d4 = req(
            "POST",
            f"/admin/shop/merchants/{close_tid}/close",
            token=admin,
            body={
                "reason_code": "merchant_request",
                "reason_text": "再次清退应失败",
                "ack_irreversible": True,
            },
        )
        results.append(
            check(
                "VP02F-E02 重复清退 409 TC-P02F-E02",
                code_c2 == 409,
                f"{code_c2} {_err(d4)}",
            )
        )
    else:
        results.append(check("VP02F-F01 清退成功 TC-P02F-F01", False, "无可用租户"))
        results.append(check("VP02F-E02 重复清退 409 TC-P02F-E02", False, "跳过"))

    cs = _ensure_cs_user()
    target = tid or close_tid or str(uuid.uuid4())
    code_cs, data_cs = req(
        "POST",
        f"/admin/shop/merchants/{target}/suspend",
        token=cs,
        body={"reason_code": "other", "reason_text": "应被拒绝的暂停"},
    )
    results.append(
        check(
            "VP02C-P01 无管理权 403 TC-P02C-E02",
            code_cs == 403,
            f"{code_cs} {_err(data_cs)}",
        )
    )

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
