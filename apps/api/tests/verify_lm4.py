"""LM4 验收：推断记忆须 confirm 后才注入。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path
API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import _get_test_client, check, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    marker = f"LM4INFER{uuid.uuid4().hex[:8].upper()}"
    token = login("13900000099", "test123456")
    client = _get_test_client()

    code, inferred = req(
        "POST",
        "/agent/memories",
        token=token,
        body={
            "scope": "user",
            "fact_text": f"推断独有标记{marker}偏好视频脚本",
            "source": "inferred",
            "is_confirmed": True,
        },
    )
    mem_id = inferred.get("id")
    results.append(
        check(
            "VLM4-1 推断记忆默认未确认",
            code == 200 and inferred.get("is_confirmed") is False,
            str(inferred.get("is_confirmed")),
        )
    )

    r = client.get(
        "/api/v1/agent/memory-context",
        params={"q": marker},
        headers={"Authorization": f"Bearer {token}"},
    )
    results.append(
        check(
            "VLM4-2 未确认不注入",
            r.status_code == 200 and marker not in r.json().get("context", ""),
            r.json().get("context", "")[:60],
        )
    )

    code, confirmed = req("POST", f"/agent/memories/{mem_id}/confirm", token=token)
    r2 = client.get(
        "/api/v1/agent/memory-context",
        params={"q": marker},
        headers={"Authorization": f"Bearer {token}"},
    )
    results.append(
        check(
            "VLM4-3 确认后可注入",
            code == 200 and confirmed.get("is_confirmed") is True and marker in r2.json().get("context", ""),
            r2.json().get("context", "")[:60],
        )
    )
    code, explicit = req(
        "POST",
        "/agent/memories",
        token=token,
        body={"scope": "user", "fact_text": "明确偏好公众号", "source": "explicit"},
    )
    results.append(check("VLM4-4 显式记忆直接可用", explicit.get("is_confirmed") is True, str(explicit.get("is_confirmed"))))

    proc = subprocess.run([sys.executable, "tests/verify_lm3.py"], cwd=API_ROOT)
    results.append(check("VLM4-5 verify_lm3 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== LM4", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
