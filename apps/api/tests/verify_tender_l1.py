#!/usr/bin/env python3
"""v1.3 招标线索 L1 冒烟：CRUD + source_url + 非平台 403。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check, req
from tests.verify_crm_helpers import finish_phase


def alembic_current() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    out = alembic_current()
    results.append(check(f"VT1-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()[:200]))

    pa = login("13800000000", "admin123456")
    tenant_user = login("13900000099", "test123456")
    tag = uuid.uuid4().hex[:6]

    code, _ = req("GET", "/admin/platform-tender-leads", token=tenant_user)
    results.append(check("VT1-1 非平台 403", code == 403, f"{code}"))

    code, denied = req(
        "POST",
        "/admin/platform-tender-leads",
        token=pa,
        body={
            "buyer_name": f"缺链医院-{tag}",
            "product_name": "泵",
            "has_source_document": True,
            "source_url": None,
            "status": "draft",
        },
    )
    results.append(check("VT1-2 有原文缺 source_url 拒写", code == 400, f"{code} {denied}"))

    code, lead = req(
        "POST",
        "/admin/platform-tender-leads",
        token=pa,
        body={
            "buyer_name": f"市立医院-{tag}",
            "industry": "医疗",
            "region": "浙江",
            "product_name": "离心泵",
            "quantity": "2台",
            "source_url": f"https://example.com/tender/{tag}",
            "has_source_document": True,
            "status": "draft",
            "source_channel": "manual",
        },
    )
    results.append(check("VT1-3 创建 L1 201", code == 201, f"{code} {lead}"))
    lid = (lead or {}).get("id")
    results.append(
        check(
            "VT1-3b 持久化 source_url",
            bool(lid) and (lead or {}).get("source_url", "").endswith(tag),
            str((lead or {}).get("source_url")),
        )
    )

    if lid:
        code, pub_fail = req(
            "POST",
            "/admin/platform-tender-leads",
            token=pa,
            body={
                "buyer_name": f"无链发布-{tag}",
                "status": "published",
                "has_source_document": False,
                "source_url": None,
            },
        )
        results.append(check("VT1-4 无链接直接 published 拒写", code == 400, f"{code} {pub_fail}"))

        code, published = req("POST", f"/admin/platform-tender-leads/{lid}/publish", token=pa)
        results.append(
            check(
                "VT1-5 发布成功",
                code == 200 and (published or {}).get("status") == "published",
                f"{code} {published}",
            )
        )

        code, listed = req("GET", f"/admin/platform-tender-leads?status=published&q={tag}", token=pa)
        items = (listed or {}).get("items") if isinstance(listed, dict) else []
        results.append(
            check(
                "VT1-6 列表含已发布",
                code == 200 and any(i.get("id") == lid for i in (items or [])),
                f"{code}",
            )
        )

        code, unpub = req("POST", f"/admin/platform-tender-leads/{lid}/unpublish", token=pa)
        results.append(check("VT1-7 下架", code == 200 and (unpub or {}).get("status") == "unpublished", str(code)))

        req("DELETE", f"/admin/platform-tender-leads/{lid}", token=pa)

    return finish_phase("v1.3-tender-l1", results)


if __name__ == "__main__":
    raise SystemExit(main())
