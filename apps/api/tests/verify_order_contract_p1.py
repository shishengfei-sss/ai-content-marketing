#!/usr/bin/env python3
"""v1.0 订单履约 P1：修订/发货/发票 + 合同/回款 + 营销ROI + 产品SKU/价目；alembic head=077。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.verify_crm_helpers import (
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    req,
)


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    results: list[bool] = []

    out = alembic_head()
    results.append(check(f"VP1-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={"company_name": f"OrdP1客户-{uuid.uuid4().hex[:6]}", "mobile": f"138{uuid.uuid4().hex[:8]}"[:11]},
    )
    results.append(check("VP1-pre 创建客户 201", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    # -------- VP1-1 修订 + 重审 --------
    code, order = req(
        "POST",
        "/crm/orders",
        token=admin_tok,
        body={
            "title": f"P1修订源-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "服务A", "quantity": 1, "unit_price": 500, "discount_rate": 0}],
        },
    )
    results.append(check("VP1-1-1 创建订单 201", code == 201, f"{code}"))
    oid = (order or {}).get("id")
    code, confirmed = req("POST", f"/crm/orders/{oid}/confirm", token=admin_tok)
    results.append(check("VP1-1-2 confirm 200", code == 200 and (confirmed or {}).get("status") == "confirmed", str(code)))

    code, revised = req(
        "POST",
        f"/crm/orders/{oid}/revise",
        token=admin_tok,
        body={"reason": "价格调整", "lines": [{"name": "服务A", "quantity": 1, "unit_price": 600, "discount_rate": 0}]},
    )
    results.append(check("VP1-1-3 revise 201", code == 201, f"{code} {revised}"))
    rid = (revised or {}).get("id")
    results.append(check("VP1-1-4 version=2", (revised or {}).get("version") == 2, str((revised or {}).get("version"))))
    results.append(
        check(
            "VP1-1-5 parent_order_id",
            str((revised or {}).get("parent_order_id")) == str(oid),
            str((revised or {}).get("parent_order_id")),
        )
    )
    results.append(
        check(
            "VP1-1-6 修订后已确认或待审",
            (revised or {}).get("status") in ("confirmed", "pending_approval"),
            str((revised or {}).get("status")),
        )
    )
    code, old = req("GET", f"/crm/orders/{oid}", token=admin_tok)
    results.append(check("VP1-1-7 原单 superseded", (old or {}).get("status") == "superseded", str((old or {}).get("status"))))

    code, revs = req("GET", f"/crm/orders/{rid}/revisions", token=admin_tok)
    results.append(check("VP1-1-8 revisions 200", code == 200 and len(revs or []) >= 2, f"{code} n={len(revs or [])}"))

    code, again = req("POST", f"/crm/orders/{oid}/revise", token=admin_tok, body={"reason": "再改"})
    results.append(check("VP1-1-9 superseded 再修订 409", code == 409, str(code)))

    # -------- VP1-2 发货 --------
    # 用已确认的修订单
    if (revised or {}).get("status") == "pending_approval":
        code, revised = req("POST", f"/crm/orders/{rid}/approve", token=admin_tok)
        results.append(check("VP1-2-0 审批通过", code == 200, str(code)))
    lines = (revised or {}).get("lines") or []
    line_id = lines[0]["id"] if lines else None
    code, dn = req(
        "POST",
        f"/crm/orders/{rid}/deliveries",
        token=admin_tok,
        body={
            "carrier": "顺丰",
            "tracking_number": f"SF{uuid.uuid4().hex[:10]}",
            "items": [{"order_line_id": line_id, "quantity": 1}] if line_id else [],
        },
    )
    results.append(check("VP1-2-1 创建发货 201", code == 201, f"{code} {dn}"))
    did = (dn or {}).get("id")
    results.append(check("VP1-2-2 status=preparing", (dn or {}).get("status") == "preparing", str((dn or {}).get("status"))))
    code, shipped = req("POST", f"/crm/deliveries/{did}/ship", token=admin_tok)
    results.append(check("VP1-2-3 ship", code == 200 and (shipped or {}).get("status") == "shipped", str(code)))
    results.append(check("VP1-2-4 shipped_at", bool((shipped or {}).get("shipped_at")), str(shipped)))
    code, delivered = req("POST", f"/crm/deliveries/{did}/deliver", token=admin_tok)
    results.append(check("VP1-2-5 deliver", code == 200 and (delivered or {}).get("status") == "delivered", str(code)))
    code, dlist = req("GET", f"/crm/orders/{rid}/deliveries", token=admin_tok)
    results.append(check("VP1-2-6 列表含发货", code == 200 and any(i.get("id") == did for i in (dlist or [])), str(code)))

    # -------- VP1-3 发票 --------
    code, inv = req(
        "POST",
        f"/crm/orders/{rid}/invoices",
        token=admin_tok,
        body={"invoice_type": "vat", "amount": 600, "tax_amount": 36},
    )
    results.append(check("VP1-3-1 创建发票 201", code == 201, f"{code} {inv}"))
    iid = (inv or {}).get("id")
    results.append(
        check(
            "VP1-3-2 total_amount=636",
            abs(float((inv or {}).get("total_amount") or 0) - 636) < 0.01,
            str((inv or {}).get("total_amount")),
        )
    )
    code, issued = req("POST", f"/crm/invoices/{iid}/issue", token=admin_tok)
    results.append(check("VP1-3-3 issue", code == 200 and (issued or {}).get("status") == "issued", str(code)))
    results.append(check("VP1-3-4 issued_at", bool((issued or {}).get("issued_at")), str(issued)))

    code, pay = req(
        "POST",
        "/crm/payments",
        token=admin_tok,
        body={"order_id": rid, "amount": 300, "method": "bank", "status": "confirmed"},
    )
    results.append(check("VP1-3-5 登记回款 201", code == 201, f"{code}"))
    pid = (pay or {}).get("id")
    code, matched = req(
        "POST",
        f"/crm/invoices/{iid}/payments",
        token=admin_tok,
        body={"payment_id": pid, "matched_amount": 300},
    )
    results.append(check("VP1-3-6 核销 201", code == 201, f"{code} {matched}"))
    results.append(
        check(
            "VP1-3-7 matched_amount",
            abs(float((matched or {}).get("matched_amount") or 0) - 300) < 0.01,
            str(matched),
        )
    )
    code, voided = req("POST", f"/crm/invoices/{iid}/void", token=admin_tok)
    results.append(check("VP1-3-8 void", code == 200 and (voided or {}).get("status") == "void", str(code)))

    # -------- VP1-4 合同到期 + 补充协议 + 续约 --------
    end_soon = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    code, cexp = req(
        "POST",
        "/crm/contracts",
        token=admin_tok,
        body={
            "title": f"P1到期-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "contract_type": "new",
            "amount": 8000,
            "end_date": end_soon,
        },
    )
    results.append(check("VP1-4-1 创建合同 201", code == 201, f"{code}"))
    cid_exp = (cexp or {}).get("id")
    code, signed = req("POST", f"/crm/contracts/{cid_exp}/sign", token=admin_tok, body={"signed_amount": 8000})
    results.append(check("VP1-4-2 签署 200", code == 200 and (signed or {}).get("status") == "signed", str(code)))

    from app.database import SessionLocal
    from app.services.crm.contract_expiry_job import process_contract_expiry

    db2 = SessionLocal()
    try:
        stats = process_contract_expiry(db2, window_days=30, create_renewal=True)
    finally:
        db2.close()
    results.append(
        check(
            "VP1-4-3 expiry job 有通知或续约",
            (stats.get("notified") or 0) >= 1 or (stats.get("renewed") or 0) >= 1,
            str(stats),
        )
    )

    code, c_after = req("GET", f"/crm/contracts/{cid_exp}", token=admin_tok)
    extra = (c_after or {}).get("extra_data") or {}
    results.append(
        check(
            "VP1-4-4 extra_data 已写标记",
            bool(extra.get("expiry_notified_on") or extra.get("renewal_deal_id")),
            str(extra),
        )
    )
    renew_deal_id = extra.get("renewal_deal_id")
    if renew_deal_id:
        code, deal = req("GET", f"/crm/deals/{renew_deal_id}", token=admin_tok)
        results.append(
            check(
                "VP1-4-5 续约 Deal deal_type=续约",
                code == 200 and (deal or {}).get("deal_type") == "续约",
                f"{code} {(deal or {}).get('deal_type')}",
            )
        )
    else:
        code, renew = req("POST", f"/crm/contracts/{cid_exp}/renew", token=admin_tok)
        results.append(check("VP1-4-5 renew API 201", code == 201, f"{code} {renew}"))
        renew_deal_id = (renew or {}).get("deal_id")

    code, am = req(
        "POST",
        f"/crm/contracts/{cid_exp}/amendments",
        token=admin_tok,
        body={"title": "加价补充", "change_type": "amount_change", "amount_delta": 500},
    )
    results.append(check("VP1-4-6 补充协议 201", code == 201, f"{code} {am}"))
    amid = (am or {}).get("id")
    results.append(check("VP1-4-7 status=draft", (am or {}).get("status") == "draft", str((am or {}).get("status"))))
    code, approved_am = req("POST", f"/crm/contracts/amendments/{amid}/approve", token=admin_tok)
    results.append(check("VP1-4-8 approve", code == 200 and (approved_am or {}).get("status") == "approved", str(code)))
    code, executed_am = req("POST", f"/crm/contracts/amendments/{amid}/execute", token=admin_tok)
    results.append(check("VP1-4-9 execute", code == 200 and (executed_am or {}).get("status") == "executed", str(code)))
    code, c_amt = req("GET", f"/crm/contracts/{cid_exp}", token=admin_tok)
    results.append(
        check(
            "VP1-4-10 合同金额+500",
            abs(float((c_amt or {}).get("amount") or 0) - 8500) < 0.01,
            str((c_amt or {}).get("amount")),
        )
    )
    code, am_list = req("GET", f"/crm/contracts/{cid_exp}/amendments", token=admin_tok)
    results.append(check("VP1-4-11 协议列表", code == 200 and any(i.get("id") == amid for i in (am_list or [])), str(code)))

    # -------- VP1-5 退款 + 应收 --------
    code, rf = req(
        "POST",
        "/crm/payments/refunds",
        token=admin_tok,
        body={"order_id": rid, "original_payment_id": pid, "amount": 50, "reason": "部分退款"},
    )
    results.append(check("VP1-5-1 创建退款 201", code == 201, f"{code} {rf}"))
    rfid = (rf or {}).get("id")
    results.append(check("VP1-5-2 status=pending", (rf or {}).get("status") == "pending", str((rf or {}).get("status"))))
    code, rf_ok = req("POST", f"/crm/payments/refunds/{rfid}/approve", token=admin_tok)
    results.append(check("VP1-5-3 approve", code == 200 and (rf_ok or {}).get("status") == "approved", str(code)))
    code, rf_done = req("POST", f"/crm/payments/refunds/{rfid}/complete", token=admin_tok)
    results.append(check("VP1-5-4 complete", code == 200 and (rf_done or {}).get("status") == "completed", str(code)))
    code, rf_list = req("GET", f"/crm/payments/orders/{rid}/refunds", token=admin_tok)
    results.append(check("VP1-5-5 退款列表", code == 200 and any(i.get("id") == rfid for i in (rf_list or [])), str(code)))

    plan_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    code, plan = req(
        "POST",
        f"/crm/payments/orders/{rid}/plans",
        token=admin_tok,
        body={"installment_no": 1, "plan_date": plan_date, "plan_amount": 1000},
    )
    results.append(check("VP1-5-6 回款计划 201", code == 201, f"{code} {plan}"))
    code, recv = req("GET", "/crm/payments/receivables", token=admin_tok)
    results.append(check("VP1-5-7 receivables 200", code == 200, str(code)))
    results.append(
        check(
            "VP1-5-8 buckets 存在",
            isinstance((recv or {}).get("buckets"), dict) and "d30" in ((recv or {}).get("buckets") or {}),
            str((recv or {}).get("buckets")),
        )
    )
    code, pay_detail = req("GET", f"/crm/payments/{pid}", token=admin_tok)
    results.append(check("VP1-5-9 payment detail 200", code == 200 and (pay_detail or {}).get("id") == pid, str(code)))

    # -------- VP1-6 渠道执行 + ROI + 细分 --------
    code, camp = req(
        "POST",
        "/crm/campaigns",
        token=admin_tok,
        body={"name": f"P1ROI-{uuid.uuid4().hex[:6]}", "status": "active", "budget": 10000, "channels": ["公众号"]},
    )
    results.append(check("VP1-6-1 创建活动 201", code == 201, f"{code}"))
    camp_id = (camp or {}).get("id")
    results.append(check("VP1-6-2 budget=10000", abs(float((camp or {}).get("budget") or 0) - 10000) < 0.01, str((camp or {}).get("budget"))))

    code, ex = req(
        "POST",
        f"/crm/campaigns/{camp_id}/channel-executions",
        token=admin_tok,
        body={
            "channel": "公众号",
            "content_type": "ad",
            "cost": 2000,
            "impressions": 10000,
            "clicks": 500,
            "leads_generated": 20,
            "status": "published",
        },
    )
    results.append(check("VP1-6-3 渠道执行 201", code == 201, f"{code} {ex}"))
    results.append(check("VP1-6-4 cost=2000", abs(float((ex or {}).get("cost") or 0) - 2000) < 0.01, str((ex or {}).get("cost"))))

    code, perf = req("GET", f"/crm/campaigns/{camp_id}/performance", token=admin_tok)
    results.append(check("VP1-6-5 performance 200", code == 200, str(code)))
    results.append(
        check(
            "VP1-6-6 total_cost=2000",
            abs(float((perf or {}).get("total_cost") or 0) - 2000) < 0.01,
            str((perf or {}).get("total_cost")),
        )
    )
    results.append(check("VP1-6-7 by_channel 非空", len((perf or {}).get("by_channel") or []) >= 1, str(perf)))

    code, camp2 = req("GET", f"/crm/campaigns/{camp_id}", token=admin_tok)
    results.append(
        check(
            "VP1-6-8 spent 同步",
            abs(float((camp2 or {}).get("spent") or 0) - 2000) < 0.01,
            str((camp2 or {}).get("spent")),
        )
    )

    code, seg = req(
        "POST",
        "/crm/segments",
        token=admin_tok,
        body={"name": f"高价值-{uuid.uuid4().hex[:4]}", "rules": {"and": [{"field": "status", "op": "=", "value": "成交"}]}, "estimated_count": 10},
    )
    results.append(check("VP1-6-9 细分 201", code == 201, f"{code}"))
    seg_id = (seg or {}).get("id")
    code, camp_seg = req("PATCH", f"/crm/campaigns/{camp_id}", token=admin_tok, body={"target_segment_id": seg_id})
    results.append(
        check(
            "VP1-6-10 关联细分",
            code == 200 and str((camp_seg or {}).get("target_segment_id")) == str(seg_id),
            str((camp_seg or {}).get("target_segment_id")),
        )
    )

    # -------- VP1-7 变体 + 价目 --------
    code, prod = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={"name": f"P1产品-{uuid.uuid4().hex[:6]}", "list_price": 999, "unit": "套"},
    )
    results.append(check("VP1-7-1 创建产品 201", code == 201, f"{code}"))
    prod_id = (prod or {}).get("id")

    code, var = req(
        "POST",
        f"/crm/products/{prod_id}/variants",
        token=admin_tok,
        body={
            "sku": f"SKU-{uuid.uuid4().hex[:8]}",
            "variant_name": "专业版",
            "list_price": 1299,
            "attributes": {"席位": "100"},
        },
    )
    results.append(check("VP1-7-2 变体 201", code == 201, f"{code} {var}"))
    vid = (var or {}).get("id")

    code, book = req(
        "POST",
        "/crm/price-books",
        token=admin_tok,
        body={"name": f"标准价-{uuid.uuid4().hex[:4]}", "is_default": True},
    )
    results.append(check("VP1-7-3 价目表 201", code == 201, f"{code}"))
    book_id = (book or {}).get("id")

    code, entry = req(
        "POST",
        f"/crm/price-books/{book_id}/entries",
        token=admin_tok,
        body={"product_id": prod_id, "variant_id": vid, "unit_price": 1199, "min_quantity": 1},
    )
    results.append(check("VP1-7-4 价目条目 201", code == 201, f"{code} {entry}"))

    code, vlist = req("GET", f"/crm/products/{prod_id}/variants", token=admin_tok)
    results.append(check("VP1-7-5 变体列表", code == 200 and any(i.get("id") == vid for i in (vlist or [])), str(code)))
    code, elist = req("GET", f"/crm/products/{prod_id}/price-entries", token=admin_tok)
    results.append(
        check(
            "VP1-7-6 产品价目",
            code == 200 and any(i.get("id") == (entry or {}).get("id") for i in (elist or [])),
            str(code),
        )
    )
    code, detail = req("GET", f"/crm/products/{prod_id}", token=admin_tok)
    results.append(check("VP1-7-7 产品详情 200", code == 200 and (detail or {}).get("id") == prod_id, str(code)))

    return finish_phase("v1.0-order-contract-P1-GHI", results)


if __name__ == "__main__":
    raise SystemExit(main())
