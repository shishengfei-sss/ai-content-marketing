"""M2 验收：JWT active_tenant_id、选/切换公司、租户隔离。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.services.auth_service import create_access_token
from tests.http_client import check, req
from tests.test_helpers import ensure_multi_tenant_user, restore_single_company_user


def decode_payload(token: str) -> dict:
    from jose import jwt

    from app.config import settings

    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def main() -> int:
    results: list[bool] = []
    phone = "13900008888"
    password = "Test123456"

    db = SessionLocal()
    try:
        restore_single_company_user(db)
        ensure_multi_tenant_user(db, phone, password)
    finally:
        db.close()

    code, single = req("POST", "/auth/login", body={"phone": "13900000099", "password": "test123456"})
    if code != 200:
        req(
            "POST",
            "/auth/register",
            body={
                "phone": "13900000099",
                "password": "test123456",
                "tenant_name": "M2单公司",
                "industry_code": "finance",
                "display_name": "单公司",
            },
        )
        code, single = req("POST", "/auth/login", body={"phone": "13900000099", "password": "test123456"})
    single_token = single["access_token"]
    payload = decode_payload(single_token)
    results.append(check("V2-1 单公司token含active_tenant", bool(payload.get("active_tenant_id"))))
    code, me = req("GET", "/auth/me", token=single_token)
    results.append(check("V2-1 /me有active_tenant", code == 200 and me.get("active_tenant") is not None))
    code, _ = req("GET", "/content", token=single_token)
    results.append(check("V2-1 单公司可访问内容", code == 200))

    code, multi = req("POST", "/auth/login", body={"phone": phone, "password": password})
    results.append(check("V2-2 多公司登录", code == 200))
    multi_token = multi["access_token"]
    results.append(
        check(
            "V2-2 need_select_tenant",
            multi.get("need_select_tenant") is True,
            str(multi.get("need_select_tenant")),
        )
    )
    code, me_multi = req("GET", "/auth/me", token=multi_token)
    results.append(
        check(
            "V2-2 /me need_select",
            code == 200 and me_multi.get("need_select_tenant") is True and len(me_multi.get("tenants", [])) >= 2,
            f"tenants={len(me_multi.get('tenants', []))}",
        )
    )

    code, _ = req("GET", "/content", token=multi_token)
    results.append(check("V2-3 未选公司403", code == 403))

    tenant_a = me_multi["tenants"][0]["id"]
    tenant_b = me_multi["tenants"][1]["id"]
    code, sel = req("POST", "/auth/select-tenant", token=multi_token, body={"tenant_id": tenant_a})
    results.append(check("V2-4 select-tenant", code == 200))
    sel_token = sel["access_token"]
    code, _ = req("GET", "/content", token=sel_token)
    results.append(check("V2-4 选A后可访问", code == 200))

    code, sw = req("POST", "/auth/switch-tenant", token=sel_token, body={"tenant_id": tenant_b})
    results.append(check("V2-5 switch-tenant", code == 200))

    fake_tid = str(uuid4())
    code, _ = req("POST", "/auth/select-tenant", token=multi_token, body={"tenant_id": fake_tid})
    results.append(check("V2-6 非法tenant 403", code == 403))

    bad_token = create_access_token(
        decode_payload(multi_token)["sub"],
        {"role": "user", "active_tenant_id": fake_tid},
    )
    code, _ = req("GET", "/content", token=bad_token)
    results.append(check("V2-8 JWT篡改403", code == 403))

    passed = all(results)
    print("\n=== M2", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
