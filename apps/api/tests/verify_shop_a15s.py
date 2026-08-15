#!/usr/bin/env python3
"""A15-S 短信与领权。对照 PRD 01#a15-sms · §8.7.3。"""

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
from app.services.shop import a15_sms_settings_service as smsvc  # noqa: E402
from tests.http_client import check, req  # noqa: E402
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "SmsClaimSettings.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _detail(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    return str(data.get("detail", data))


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA15S-UI 短信领权页",
            _page_has(
                WEB,
                "#a15-sms",
                "短信与领权",
                "短信签名（只读）",
                "领权短信模板（只读）",
                "领权过期天数",
                "领权链接域名",
                "保存领权参数",
                "发送测试短信",
                "校验可达",
            ),
            str(WEB),
        )
    )

    merchant, tenant_id = _ensure_merchant()

    # 确保未分配态可测
    from app.database import uuid_eq
    from app.models.shop import ShopTenantSettings

    with SessionLocal() as db:
        row = (
            db.query(ShopTenantSettings)
            .filter(uuid_eq(ShopTenantSettings.tenant_id, UUID(str(tenant_id))))
            .first()
        )
        if row:
            row.sms_signature_id = None
            row.claim_template_id = None
            row.claim_landing_base = None
            row.domain_verified_at = None
            row.domain_verified_base = None
            row.claim_expire_days = 7
            db.commit()

    code, data = req("GET", "/shop/settings/sms", token=merchant)
    results.append(
        check(
            "VA15S-1 未分配只读态",
            code == 200
            and data.get("config_status") == "unassigned"
            and data.get("can_save") is False
            and data.get("sms_signature") is None,
            f"{code} {data}",
        )
    )

    code, denied = req(
        "PUT",
        "/shop/settings/sms",
        token=merchant,
        body={"claim_landing_base": "https://shop.example.local", "claim_expire_days": 7},
    )
    results.append(
        check(
            "VA15S-2 未分配不可保存",
            code == 422 and "待平台配置" in _detail(denied),
            f"{code} {_detail(denied)}",
        )
    )

    with SessionLocal() as db:
        smsvc.force_assign_sms_for_tests(db, UUID(str(tenant_id)))

    code, assigned = req("GET", "/shop/settings/sms", token=merchant)
    results.append(
        check(
            "VA15S-3 分配后可读签名模板",
            code == 200
            and assigned.get("config_status") == "assigned"
            and assigned.get("sms_signature")
            and assigned.get("claim_template_code_masked")
            and "SMS_" in str(assigned.get("claim_template_code_masked")),
            f"{code} {assigned}",
        )
    )

    code, bad = req(
        "PUT",
        "/shop/settings/sms",
        token=merchant,
        body={"claim_landing_base": "https://shop.example.local", "claim_expire_days": 7},
    )
    results.append(
        check(
            "VA15S-4 未校验域名不可保存",
            code == 422 and "域名不可达" in _detail(bad),
            f"{code} {_detail(bad)}",
        )
    )

    code, chk = req(
        "POST",
        "/shop/settings/sms/check-domain",
        token=merchant,
        body={"claim_landing_base": "https://shop.example.local"},
    )
    results.append(
        check(
            "VA15S-5 校验可达",
            code == 200 and chk.get("ok") is True,
            f"{code} {chk}",
        )
    )

    code, saved = req(
        "PUT",
        "/shop/settings/sms",
        token=merchant,
        body={"claim_landing_base": "https://shop.example.local", "claim_expire_days": 10},
    )
    results.append(
        check(
            "VA15S-6 保存领权参数",
            code == 200
            and saved.get("claim_expire_days") == 10
            and (saved.get("claim_landing_base") or "").startswith("https://shop.example.local"),
            f"{code} {saved}",
        )
    )

    code, test_res = req(
        "POST",
        "/shop/settings/sms/test",
        token=merchant,
        body={"mobile": "13800138000"},
    )
    results.append(
        check(
            "VA15S-7 发送测试短信",
            code == 200 and test_res.get("ok") is True,
            f"{code} {test_res}",
        )
    )

    code, after = req("GET", "/shop/settings/sms", token=merchant)
    used = ((after.get("usage") or {}).get("claim_sms_month") or {}).get("used")
    results.append(
        check(
            "VA15S-8 用量计入",
            code == 200 and isinstance(used, int) and used >= 1,
            f"{code} used={used}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA15-S result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
