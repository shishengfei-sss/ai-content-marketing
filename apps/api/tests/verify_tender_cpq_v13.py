#!/usr/bin/env python3
"""v1.3 招标线索（平台公共池）+ 轻量 CPQ 验收。

--mode doc   文档门禁 + 既有 quotes/price-books 回归（实现前默认）
--mode impl  全量 VT13（实现后启用；未实现时失败）

硬决议：无爬虫；L1 仅平台；claim 不直建 Deal；CPQ 写入现有 quotes。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WEB_ROOT = API_ROOT.parent / "web"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req
from tests.verify_crm_helpers import finish_phase

EXPECTED_V13_HEAD = "083"


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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def verify_doc(results: list[bool]) -> None:
    srs = REPO_ROOT / "docs" / "需求规格.md"
    plan = REPO_ROOT / "docs" / "v1.3-招标线索与CPQ执行计划.md"
    roadmap = REPO_ROOT / "docs" / "版本交付线梳理.md"
    prd = REPO_ROOT / "商机与CPQ-prd" / "mvp-prd-v2.html"

    results.append(check("VT13-D0-1 SRS 存在", srs.is_file(), str(srs)))
    results.append(check("VT13-D0-2 执行计划存在", plan.is_file(), str(plan)))
    results.append(check("VT13-D0-3 交付线存在", roadmap.is_file(), str(roadmap)))
    results.append(check("VT13-D0-4 PRD 存在", prd.is_file(), str(prd)))

    srs_text = _read(srs)
    plan_text = _read(plan)
    roadmap_text = _read(roadmap)
    prd_text = _read(prd)

    results.append(
        check(
            "VT13-D1-1 SRS §3.24 / FR-TENDER",
            "### 3.24" in srs_text and "FR-TENDER-08" in srs_text and "FR-CPQ-07" in srs_text,
            "missing FR blocks",
        )
    )
    results.append(
        check(
            "VT13-D1-2 SRS D3 写入 quotes",
            "强制写入现有 `quotes`" in srs_text or "写入现有 `quotes`" in srs_text,
            "D3 missing",
        )
    )
    results.append(
        check(
            "VT13-D1-3 SRS 无爬虫 / 方案 A",
            "无爬虫" in srs_text
            and "platform_tender_leads" in srs_text
            and ("不可" in srs_text and "投稿" in srs_text),
            "platform pool / no crawler missing",
        )
    )
    results.append(
        check(
            "VT13-D1-4 路线图 v1.3 + A/B≥v1.4",
            "**v1.3**" in srs_text and "≥v1.4" in srs_text,
            "roadmap versioning",
        )
    )
    results.append(
        check(
            "VT13-D1-5 执行计划 D5/D6",
            "方案 A" in plan_text and "无爬虫" in plan_text and "platform_tender_leads" in plan_text,
            "plan D5/D6",
        )
    )
    results.append(
        check(
            "VT13-D1-6 交付线已交付 v1.3",
            "v1.3" in roadmap_text
            and "quotes" in roadmap_text
            and "无爬虫" in roadmap_text
            and ("已交付" in roadmap_text or "✅" in roadmap_text),
            "roadmap file",
        )
    )
    results.append(
        check(
            "VT13-D2-1 PRD 公共池路由",
            "/admin/platform-tender-leads" in prd_text and "platform_tender_leads" in prd_text,
            "prd L1",
        )
    )
    results.append(
        check(
            "VT13-D2-2 PRD 附件 AI / 方案 A",
            "附件" in prd_text
            and ("人审" in prd_text or "确认" in prd_text)
            and ("不可投稿" in prd_text or "租户不可" in prd_text),
            "prd attachment / scheme A",
        )
    )
    results.append(
        check(
            "VT13-D2-2b PRD/SRS 原文链接 source_url",
            "source_url" in prd_text
            and "原文链接" in prd_text
            and "source_url" in srs_text
            and "原文链接" in srs_text,
            "source_url missing",
        )
    )
    results.append(
        check(
            "VT13-D2-3 PRD 无 crawler 路由",
            "/admin/crawler" not in prd_text and "crawler_sources" not in prd_text,
            "prd still has crawler",
        )
    )
    results.append(
        check(
            "VT13-D4-1 计划无 crawler 表",
            "crawler_sources" not in plan_text,
            "plan still has crawler_sources",
        )
    )

    token = login("13900000099", "test123456")
    code, quotes = req("GET", "/crm/quotes", token=token)
    results.append(check("VT13-D3-1 quotes 列表", code == 200, f"{code}"))
    code, books = req("GET", "/crm/price-books", token=token)
    results.append(check("VT13-D3-2 price-books 列表", code == 200, f"{code}"))
    _ = quotes, books


def _run_phase_main(label: str, module_name: str) -> tuple[bool, str]:
    """同进程调用分阶段脚本 main()，避免多 TestClient 子进程撑爆内存。"""
    from tests.http_client import reset_test_client

    reset_test_client()
    try:
        mod = __import__(f"tests.{module_name}", fromlist=["main"])
        code = int(mod.main())
        return code == 0, f"exit={code}"
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 1
        return code == 0, f"SystemExit={code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"[:400]
    finally:
        reset_test_client()


def verify_impl(results: list[bool]) -> None:
    import os

    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    out = alembic_current()
    results.append(
        check(
            f"VT13-00 alembic head contains {EXPECTED_V13_HEAD}",
            EXPECTED_V13_HEAD != "TBD_V13" and EXPECTED_V13_HEAD in out and "head" in out.lower(),
            out.strip()[:200] or "empty; set EXPECTED_V13_HEAD after migrations",
        )
    )

    token = login("13900000099", "test123456")

    code, _ = req("GET", "/crm/tender-leads", token=token)
    results.append(check("VT13-01-route tender-leads 200", code == 200, f"{code}"))

    code_admin, _ = req("GET", "/admin/platform-tender-leads", token=token)
    results.append(check("VT13-08 非平台 Admin 公共池 403", code_admin == 403, f"status={code_admin}"))

    code_calc, _ = req("POST", "/crm/cpq/calculate", token=token, body={})
    results.append(
        check(
            "VT13-04 calculate 已挂载",
            code_calc not in (404, 405),
            f"status={code_calc}",
        )
    )

    code_an, analytics = req("GET", "/crm/tender-lead-analytics", token=token)
    results.append(
        check(
            "VT13-13 效果看板可达",
            code_an == 200 and isinstance(analytics, dict) and "follow_rate" in (analytics or {}),
            f"{code_an}",
        )
    )

    router = _read(WEB_ROOT / "src" / "router.js")
    results.append(check("VT13-11-1 路由 tender-leads", "tender-leads" in router, "router.js"))
    results.append(check("VT13-11-2 路由 platform-tender", "platform-tender" in router, "router.js"))
    results.append(check("VT13-11-3 路由 cpq", "cpq" in router, "router.js"))
    results.append(
        check(
            "VT13-11-4 路由 tender-lead-analytics",
            "tender-lead-analytics" in router,
            "router.js",
        )
    )

    phases = [
        ("VT13-phase-cpq", "verify_cpq_w12"),
        ("VT13-phase-l1", "verify_tender_l1"),
        ("VT13-phase-l2", "verify_tender_l2"),
        ("VT13-phase-parse", "verify_tender_parse"),
        ("VT13-phase-analytics-cpq10", "verify_tender_analytics_cpq10"),
    ]
    for label, mod_name in phases:
        ok, detail = _run_phase_main(label, mod_name)
        safe = detail.encode("ascii", errors="replace").decode("ascii")
        results.append(check(f"{label} {mod_name}", ok, safe[:400]))


def main() -> int:
    parser = argparse.ArgumentParser(description="v1.3 platform tender pool + CPQ verify")
    parser.add_argument("--mode", choices=("doc", "impl"), default="doc")
    args = parser.parse_args()

    results: list[bool] = []
    if args.mode == "doc":
        verify_doc(results)
        return finish_phase("v1.3-tender-cpq-DOC", results)

    verify_doc(results)
    verify_impl(results)
    return finish_phase("v1.3-tender-cpq-IMPL", results)


if __name__ == "__main__":
    raise SystemExit(main())
