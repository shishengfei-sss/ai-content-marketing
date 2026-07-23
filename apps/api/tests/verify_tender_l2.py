#!/usr/bin/env python3
"""v1.3 招标线索 L2：ICP + 匹配 + claim→leads（不建 Deal）。"""
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
    results.append(check(f"VT2-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()[:200]))

    pa = login("13800000000", "admin123456")
    tok = login("13900000099", "test123456")
    tag = uuid.uuid4().hex[:6]

    code, bad = req(
        "PUT",
        "/crm/icp-config",
        token=tok,
        body={
            "target_industries": ["医疗"],
            "target_regions": ["浙江"],
            "weight_industry": 50,
            "weight_company_size": 20,
            "weight_region": 15,
            "weight_budget": 20,
            "weight_urgency": 15,  # sum=120
            "is_active": True,
        },
    )
    results.append(check("VT2-1 ICP 权重≠100 拒写", code in (400, 422), f"{code} {bad}"))

    code, icp = req(
        "PUT",
        "/crm/icp-config",
        token=tok,
        body={
            "target_industries": ["医疗"],
            "target_regions": ["浙江"],
            "min_budget_threshold": 10000,
            "include_keywords": ["泵"],
            "exclude_keywords": [],
            "weight_industry": 30,
            "weight_company_size": 20,
            "weight_region": 15,
            "weight_budget": 20,
            "weight_urgency": 15,
            "is_active": True,
        },
    )
    results.append(check("VT2-2 ICP 保存 200", code == 200, f"{code} {icp}"))

    code, lead = req(
        "POST",
        "/admin/platform-tender-leads",
        token=pa,
        body={
            "buyer_name": f"匹配医院-{tag}",
            "industry": "医疗器械",
            "region": "浙江杭州",
            "product_name": "离心泵",
            "budget_max": 80000,
            "source_url": f"https://example.com/t/{tag}",
            "has_source_document": True,
            "status": "draft",
        },
    )
    results.append(check("VT2-3 建 L1", code == 201, f"{code}"))
    lid = (lead or {}).get("id")

    if lid:
        code, pub = req("POST", f"/admin/platform-tender-leads/{lid}/publish", token=pa)
        results.append(check("VT2-4 发布触发匹配", code == 200, f"{code}"))

        code, listed = req("GET", "/crm/tender-leads?status=pending", token=tok)
        items = (listed or {}).get("items") or []
        hit = next((i for i in items if i.get("platform_tender_lead_id") == lid), None)
        results.append(
            check(
                "VT2-5 L2 列表有匹配分",
                code == 200 and hit is not None and int(hit.get("match_score") or 0) > 0,
                str(hit),
            )
        )
        results.append(
            check(
                "VT2-5b 原文链接只读可见",
                bool(hit and hit.get("source_url")),
                str((hit or {}).get("source_url")),
            )
        )

        scored_id = (hit or {}).get("id")
        if scored_id:
            # deals before
            code, deals_before = req("GET", "/crm/deals?page=1&page_size=1", token=tok)
            total_before = (deals_before or {}).get("total") if code == 200 else None

            code, claim = req("POST", f"/crm/tender-leads/{scored_id}/claim", token=tok)
            results.append(
                check(
                    "VT2-6 claim 创建 leads",
                    code == 200 and bool((claim or {}).get("lead_id")) and (claim or {}).get("deal_created") is False,
                    f"{code} {claim}",
                )
            )
            lead_id = (claim or {}).get("lead_id")
            if lead_id:
                code, crm_lead = req("GET", f"/crm/leads/{lead_id}", token=tok)
                results.append(check("VT2-6b 线索可读", code == 200, f"{code}"))

            code, deals_after = req("GET", "/crm/deals?page=1&page_size=1", token=tok)
            total_after = (deals_after or {}).get("total") if code == 200 else None
            if total_before is not None and total_after is not None:
                results.append(
                    check("VT2-6c 未新建 Deal", total_after == total_before, f"{total_before}->{total_after}")
                )

            # ignore path on another lead
            code, lead2 = req(
                "POST",
                "/admin/platform-tender-leads",
                token=pa,
                body={
                    "buyer_name": f"忽略单-{tag}",
                    "industry": "医疗",
                    "region": "浙江",
                    "product_name": "泵",
                    "source_url": f"https://example.com/x/{tag}",
                    "has_source_document": True,
                    "status": "draft",
                },
            )
            lid2 = (lead2 or {}).get("id")
            if lid2:
                req("POST", f"/admin/platform-tender-leads/{lid2}/publish", token=pa)
                code, listed2 = req("GET", "/crm/tender-leads?status=pending", token=tok)
                hit2 = next(
                    (i for i in ((listed2 or {}).get("items") or []) if i.get("platform_tender_lead_id") == lid2),
                    None,
                )
                if hit2:
                    sid2 = hit2["id"]
                    code, _ = req("POST", f"/crm/tender-leads/{sid2}/ignore", token=tok)
                    results.append(check("VT2-7 ignore", code == 200, f"{code}"))
                    code, blocked = req("POST", f"/crm/tender-leads/{sid2}/claim", token=tok)
                    results.append(check("VT2-7b ignore 后不可 claim", code == 409, f"{code} {blocked}"))
                    req("DELETE", f"/admin/platform-tender-leads/{lid2}", token=pa)

        req("DELETE", f"/admin/platform-tender-leads/{lid}", token=pa)

    return finish_phase("v1.3-tender-l2", results)


if __name__ == "__main__":
    raise SystemExit(main())
