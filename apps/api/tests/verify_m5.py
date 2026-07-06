"""M5 验收：忘记密码。"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req

PHONE = "13900007777"
OLD_PASS = "Test123456"
NEW_PASS = "NewPass123456"


def main():
    results = []
    code, _ = req(
        "POST",
        "/auth/register",
        body={"phone": PHONE, "password": OLD_PASS, "tenant_name": "M5测试公司", "industry_code": "finance", "display_name": "M5"},
    )
    if code not in (200, 400):
        print("register", code)

    code, send = req("POST", "/auth/password/forgot/send-code", body={"phone": PHONE})
    results.append(check("V5-1 send-code", code == 200, str(send)))

    code, reset = req(
        "POST",
        "/auth/password/forgot/reset",
        body={"phone": PHONE, "code": "1111", "password": NEW_PASS},
    )
    results.append(check("V5-1 reset 1111", code == 200, str(reset)))
    results.append(check("V5-3 无token", "access_token" not in (reset if isinstance(reset, dict) else {})))

    code, _ = req("POST", "/auth/login", body={"phone": PHONE, "password": OLD_PASS})
    results.append(check("V5-2 旧密码失败", code == 401, str(code)))

    code, login = req("POST", "/auth/login", body={"phone": PHONE, "password": NEW_PASS})
    results.append(check("V5-2 新密码成功", code == 200))

    req("POST", "/auth/sms/send", body={"phone": PHONE})
    code, _ = req(
        "POST",
        "/auth/password/forgot/reset",
        body={"phone": PHONE, "code": "1111", "password": "AnotherPass123"},
    )
    results.append(check("V5-4 login码不能reset", code == 400, str(code)))

    passed = all(results)
    print("\n=== M5", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
