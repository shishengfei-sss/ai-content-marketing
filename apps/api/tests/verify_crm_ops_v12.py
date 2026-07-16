#!/usr/bin/env python3
"""v1.2 CRM 运营报表与提醒验收：trade-report / dashboard reminders / assignment UI；Head=077。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web"
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check, ensure_fake_platform, req
from tests.verify_crm_helpers import finish_phase


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    out = alembic_head()
    results.append(check(f"VP12-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    token = login("13800000000", "admin123456")
    ensure_fake_platform(token)
    user_token = login("13900000099", "test123456")

    code, report = req("GET", "/analytics/trade-report", token=user_token)
    results.append(check("VP12-1-1 trade-report 200", code == 200, f"{code}"))
    results.append(
        check(
            "VP12-1-2 keys",
            isinstance(report, dict)
            and "paths" in report
            and "payment_rate" in report
            and "aging" in report
            and "owners" in report,
            str(list((report or {}).keys())[:12]),
        )
    )
    paths = (report or {}).get("paths") or []
    results.append(check("VP12-1-3 四路径", len(paths) == 4, str(paths)))

    code, dash = req("GET", "/dashboard/stats", token=user_token)
    results.append(check("VP12-2-1 dashboard 200", code == 200, str(code)))
    results.append(
        check(
            "VP12-2-2 reminder fields",
            isinstance(dash, dict)
            and "payment_due_7d" in dash
            and "payment_overdue" in dash
            and "contract_expiring_30d" in dash,
            str({k: (dash or {}).get(k) for k in ("payment_due_7d", "payment_overdue", "contract_expiring_30d")}),
        )
    )

    marker = uuid.uuid4().hex[:6]
    code, rule = req(
        "POST",
        "/crm/assignment-rules",
        token=user_token,
        body={
            "name": f"V12-{marker}",
            "condition_json": {"field": "source", "operator": "contains", "value": marker},
            "assign_type": "round_robin",
            "priority": 1,
            "is_active": True,
        },
    )
    results.append(check("VP12-3-1 创建分配规则 201", code == 201, f"{code} {rule}"))
    rule_id = (rule or {}).get("id")
    code, rules = req("GET", "/crm/assignment-rules", token=user_token)
    results.append(
        check(
            "VP12-3-2 列表含新建",
            code == 200 and isinstance(rules, list) and any(r.get("id") == rule_id for r in rules),
            str(code),
        )
    )
    if rule_id:
        code, _ = req(
            "PATCH",
            f"/crm/assignment-rules/{rule_id}",
            token=user_token,
            body={"is_active": False},
        )
        results.append(check("VP12-3-3 更新规则", code == 200, str(code)))
        code, _ = req("DELETE", f"/crm/assignment-rules/{rule_id}", token=user_token)
        results.append(check("VP12-3-4 删除规则", code == 204, str(code)))
    else:
        results.append(check("VP12-3-3 更新规则（跳过）", False, "no id"))
        results.append(check("VP12-3-4 删除规则（跳过）", False, "no id"))

    trade_vue = (WEB_ROOT / "src" / "views" / "crm" / "TradeReport.vue").read_text(encoding="utf-8")
    assign_vue = (WEB_ROOT / "src" / "views" / "SettingsAssignmentRules.vue").read_text(encoding="utf-8")
    router_js = (WEB_ROOT / "src" / "router.js").read_text(encoding="utf-8")
    dash_vue = (WEB_ROOT / "src" / "views" / "Dashboard.vue").read_text(encoding="utf-8")
    results.append(check("VP12-4-1 TradeReport 页", "tradeReport" in trade_vue, "TradeReport.vue"))
    results.append(check("VP12-4-2 Assignment UI", "listAssignmentRules" in assign_vue, "SettingsAssignmentRules.vue"))
    results.append(check("VP12-4-3 路由 trade-report", "crm/trade-report" in router_js, "router"))
    results.append(check("VP12-4-4 路由 assignment-rules", "assignment-rules" in router_js, "router"))
    results.append(check("VP12-4-5 工作台提醒卡片", "payment_due_7d" in dash_vue and "contract_expiring_30d" in dash_vue, "Dashboard"))

    # -------- P1 --------
    code, dur = req("GET", "/analytics/deal-stage-duration", token=user_token)
    results.append(check("VP12-5-1 deal-stage-duration 200", code == 200, f"{code}"))
    results.append(
        check(
            "VP12-5-2 stages 结构",
            isinstance(dur, dict)
            and isinstance(dur.get("stages"), list)
            and (
                len(dur["stages"]) == 0
                or all(k in dur["stages"][0] for k in ("stage_id", "avg_days", "max_days", "sample_count"))
            ),
            str((dur or {}).get("stages", [])[:1]),
        )
    )

    order_vue = (WEB_ROOT / "src" / "views" / "crm" / "OrderDetail.vue").read_text(encoding="utf-8")
    funnel_vue = (WEB_ROOT / "src" / "views" / "crm" / "DealFunnel.vue").read_text(encoding="utf-8")
    results.append(
        check(
            "VP12-6-1 发票核销 UI",
            "matchInvoicePayment" in order_vue and "openMatchInvoice" in order_vue,
            "OrderDetail",
        )
    )
    results.append(
        check(
            "VP12-6-2 退款 Tab",
            'name="refunds"' in order_vue and "openRefund" in order_vue and "listOrderRefunds" in order_vue,
            "OrderDetail",
        )
    )
    results.append(
        check(
            "VP12-7-1 阶段停留 Tab",
            "dealStageDuration" in funnel_vue and 'name="duration"' in funnel_vue,
            "DealFunnel",
        )
    )

    return finish_phase("v1.2-crm-ops-P0+P1", results)


if __name__ == "__main__":
    raise SystemExit(main())
