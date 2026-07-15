#!/usr/bin/env python3
"""v1.0 订单/合同增强 P0：审批/税率/模板分类/高级筛选/关联订单回款汇总；alembic head=068。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.verify_crm_helpers import (
    ADMIN_PHONE,
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    req,
    sales_token,
)


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def ensure_approve_permission(db) -> None:
    """既有租户可能缺 crm.order.approve，补齐到 admin / sales_manager。"""
    from app.models import TenantRole, TenantRolePermission, User
    from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_SALES_MANAGER

    admin = db.query(User).filter(User.phone == ADMIN_PHONE).first()
    if not admin or not admin.tenant_id:
        return
    roles = (
        db.query(TenantRole)
        .filter(
            TenantRole.tenant_id == admin.tenant_id,
            TenantRole.code.in_([SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_SALES_MANAGER]),
        )
        .all()
    )
    for role in roles:
        exists = (
            db.query(TenantRolePermission)
            .filter(
                TenantRolePermission.role_id == role.id,
                TenantRolePermission.permission_code == "crm.order.approve",
            )
            .first()
        )
        if not exists:
            db.add(TenantRolePermission(role_id=role.id, permission_code="crm.order.approve"))
    db.commit()


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
        ensure_approve_permission(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()
    results: list[bool] = []

    out = alembic_head()
    results.append(check(f"VP0-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    # 准备客户
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={
            "company_name": f"OrdP0客户-{uuid.uuid4().hex[:6]}",
            "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
        },
    )
    results.append(check("VP0-pre 创建客户 201", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    # 审批规则：金额 >= 10000
    code, rule = req(
        "POST",
        "/crm/approval-rules",
        token=admin_tok,
        body={
            "name": f"P0大额审批-{uuid.uuid4().hex[:4]}",
            "min_amount": 10000,
            "max_amount": None,
            "approver_role": "sales_manager",
            "approval_type": "sequential",
            "is_active": True,
        },
    )
    results.append(check("VP0-1-0 创建审批规则 201", code == 201, f"{code} {rule}"))
    rule_id = (rule or {}).get("id")

    # VP0-1 有规则：submit → pending_approval → approve → confirmed
    code, order_hi = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"P0大额订单-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [
                {
                    "name": "服务A",
                    "quantity": 1,
                    "unit_price": 15000,
                    "discount_rate": 0,
                    "tax_rate": 6,
                }
            ],
        },
    )
    results.append(check("VP0-1-1 创建大额订单 201", code == 201, f"{code} {order_hi}"))
    order_hi_id = (order_hi or {}).get("id")
    results.append(
        check(
            "VP0-1-1b amount>=10000",
            float((order_hi or {}).get("amount") or 0) >= 10000,
            str((order_hi or {}).get("amount")),
        )
    )

    code, submitted = req("POST", f"/crm/orders/{order_hi_id}/submit", token=sales_tok)
    results.append(check("VP0-1-2 submit 200", code == 200, f"{code} {submitted}"))
    results.append(
        check(
            "VP0-1-3 status=pending_approval",
            (submitted or {}).get("status") == "pending_approval",
            str((submitted or {}).get("status")),
        )
    )

    code, confirmed = req("POST", f"/crm/orders/{order_hi_id}/approve", token=admin_tok)
    results.append(check("VP0-1-4 approve 200", code == 200, f"{code} {confirmed}"))
    results.append(
        check(
            "VP0-1-5 status=confirmed",
            (confirmed or {}).get("status") == "confirmed",
            str((confirmed or {}).get("status")),
        )
    )

    # VP0-2 无规则命中（小额）：confirm → confirmed
    code, order_lo = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"P0小额订单-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "服务B", "quantity": 1, "unit_price": 500, "discount_rate": 0}],
        },
    )
    results.append(check("VP0-2-1 创建小额订单 201", code == 201, f"{code} {order_lo}"))
    order_lo_id = (order_lo or {}).get("id")
    code, confirmed_lo = req("POST", f"/crm/orders/{order_lo_id}/confirm", token=sales_tok)
    results.append(check("VP0-2-2 confirm 200", code == 200, f"{code} {confirmed_lo}"))
    results.append(
        check(
            "VP0-2-3 status=confirmed",
            (confirmed_lo or {}).get("status") == "confirmed",
            str((confirmed_lo or {}).get("status")),
        )
    )

    # VP0-3 reject
    code, order_rej = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"P0驳回订单-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "服务C", "quantity": 1, "unit_price": 20000}],
        },
    )
    results.append(check("VP0-3-1 创建待驳回订单 201", code == 201, f"{code}"))
    order_rej_id = (order_rej or {}).get("id")
    code, _ = req("POST", f"/crm/orders/{order_rej_id}/submit", token=sales_tok)
    code, rejected = req(
        "POST",
        f"/crm/orders/{order_rej_id}/reject",
        token=admin_tok,
        body={"reason": "折扣过大，请调整后重提"},
    )
    results.append(check("VP0-3-2 reject 200", code == 200, f"{code} {rejected}"))
    results.append(
        check(
            "VP0-3-3 status=rejected",
            (rejected or {}).get("status") == "rejected",
            str((rejected or {}).get("status")),
        )
    )
    code, apprs = req("GET", f"/crm/orders/{order_rej_id}/approvals", token=sales_tok)
    results.append(check("VP0-3-4 approvals 200", code == 200, str(code)))
    reason = ((apprs or [{}])[0] or {}).get("reject_reason") if apprs else None
    results.append(check("VP0-3-5 reject_reason", reason == "折扣过大，请调整后重提", str(reason)))

    # VP0-4 tax_rate 写入；含税可算
    code, order_tax = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"P0税率订单-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [
                {
                    "name": "含税行",
                    "quantity": 2,
                    "unit_price": 1000,
                    "discount_rate": 10,
                    "tax_rate": 13,
                }
            ],
        },
    )
    results.append(check("VP0-4-1 创建含税订单 201", code == 201, f"{code} {order_tax}"))
    lines = (order_tax or {}).get("lines") or []
    line0 = lines[0] if lines else {}
    # 折后未税 = 2*1000*(1-0.1)=1800；税=1800*0.13=234
    results.append(check("VP0-4-2 tax_rate=13", float(line0.get("tax_rate") or 0) == 13, str(line0.get("tax_rate"))))
    results.append(
        check(
            "VP0-4-3 tax_amount≈234",
            abs(float(line0.get("tax_amount") or 0) - 234) < 0.01,
            str(line0.get("tax_amount")),
        )
    )
    results.append(
        check(
            "VP0-4-4 line_total≈1800",
            abs(float(line0.get("line_total") or 0) - 1800) < 0.01,
            str(line0.get("line_total")),
        )
    )
    incl = float(line0.get("line_total") or 0) + float(line0.get("tax_amount") or 0)
    results.append(check("VP0-4-5 含税=2034", abs(incl - 2034) < 0.01, str(incl)))

    # 清理规则（避免污染后续大额验收）
    if rule_id:
        req("DELETE", f"/crm/approval-rules/{rule_id}", token=admin_tok)

    # -------- Day B: VP0-5～7 --------
    # VP0-5 合同附件 entity_type=contract
    code, contract = req(
        "POST",
        "/crm/contracts",
        token=admin_tok,
        body={
            "title": f"P0合同附-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "contract_type": "new",
            "amount": 1000,
            "file_url": f"/legacy/contracts/{uuid.uuid4().hex}.pdf",
        },
    )
    results.append(check("VP0-5-1 创建合同 201", code == 201, f"{code}"))
    contract_id = (contract or {}).get("id")

    from tests.http_client import _get_test_client

    client = _get_test_client()
    up = client.post(
        f"/api/v1/crm/attachments?entity_type=contract&entity_id={contract_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        files={"file": ("contract-p0.txt", b"contract body", "text/plain")},
    )
    results.append(
        check("VP0-5-2 上传合同附件 201", up.status_code == 201, f"{up.status_code} {up.text[:200]}")
    )
    code, att_list = req(
        "GET",
        f"/crm/attachments?entity_type=contract&entity_id={contract_id}",
        token=admin_tok,
    )
    results.append(check("VP0-5-3 列表含附件", code == 200 and len(att_list or []) >= 1, str(att_list)))
    results.append(
        check(
            "VP0-5-4 entity_type=contract",
            all(a.get("entity_type") == "contract" for a in (att_list or [])),
            str(att_list),
        )
    )

    # VP0-6 从模板创建合同
    code, tpl = req(
        "POST",
        "/crm/contract-templates",
        token=admin_tok,
        body={
            "name": f"P0模板-{uuid.uuid4().hex[:4]}",
            "category": "销售",
            "content": "甲方：{{company_name}}，金额：{{amount}}",
            "variables": ["company_name", "amount"],
            "is_active": True,
        },
    )
    results.append(check("VP0-6-1 创建模板 201", code == 201, f"{code} {tpl}"))
    tpl_id = (tpl or {}).get("id")
    code, from_tpl = req(
        "POST",
        "/crm/contracts/from-template",
        token=admin_tok,
        body={
            "template_id": tpl_id,
            "customer_id": cust_id,
            "title": "模板生成合同",
            "variable_values": {"company_name": "测试科技", "amount": "58000"},
            "amount": 58000,
        },
    )
    results.append(check("VP0-6-2 from-template 201", code == 201, f"{code} {from_tpl}"))
    body_text = ((from_tpl or {}).get("extra_data") or {}).get("body", "")
    results.append(
        check(
            "VP0-6-3 变量渲染",
            "测试科技" in body_text and "58000" in body_text,
            body_text,
        )
    )
    results.append(
        check(
            "VP0-6-4 amount=58000",
            float((from_tpl or {}).get("amount") or 0) == 58000,
            str((from_tpl or {}).get("amount")),
        )
    )

    # VP0-7 category_id 关联
    code, cat = req(
        "POST",
        "/crm/product-categories",
        token=admin_tok,
        body={"name": f"P0分类-{uuid.uuid4().hex[:4]}", "sort_order": 1, "is_active": True},
    )
    results.append(check("VP0-7-1 创建分类 201", code == 201, f"{code} {cat}"))
    cat_id = (cat or {}).get("id")
    code, prod = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={
            "name": f"P0产品-{uuid.uuid4().hex[:4]}",
            "list_price": 99,
            "category_id": cat_id,
            "is_active": True,
        },
    )
    results.append(check("VP0-7-2 创建产品带分类 201", code == 201, f"{code} {prod}"))
    results.append(
        check(
            "VP0-7-3 category_id 回写",
            (prod or {}).get("category_id") == cat_id,
            str((prod or {}).get("category_id")),
        )
    )

    # -------- Day C: VP0-8～10 / VP0-13 --------
    import json
    from urllib.parse import quote

    # VP0-8 Campaign filters：status=draft
    code, camp_a = req(
        "POST",
        "/crm/campaigns",
        token=admin_tok,
        body={"name": f"P0筛选活动-draft-{uuid.uuid4().hex[:4]}", "status": "draft"},
    )
    results.append(check("VP0-8-0 创建 draft 活动 201", code == 201, str(code)))
    code, camp_b = req(
        "POST",
        "/crm/campaigns",
        token=admin_tok,
        body={"name": f"P0筛选活动-active-{uuid.uuid4().hex[:4]}", "status": "active"},
    )
    results.append(check("VP0-8-0b 创建 active 活动 201", code == 201, str(code)))
    camp_filters = quote(
        json.dumps(
            {"logic": "and", "conditions": [{"field_key": "status", "op": "eq", "value": "draft"}]},
            ensure_ascii=False,
        )
    )
    code, camp_list = req("GET", f"/crm/campaigns?filters={camp_filters}&page_size=100", token=admin_tok)
    results.append(check("VP0-8-1 Campaign filters 200", code == 200, str(code)))
    results.append(
        check("VP0-8-2 filters_applied", (camp_list or {}).get("filters_applied") is True, str(camp_list))
    )
    camp_items = (camp_list or {}).get("items") or []
    results.append(
        check(
            "VP0-8-3 仅 draft",
            all(i.get("status") == "draft" for i in camp_items) and any(
                i.get("id") == (camp_a or {}).get("id") for i in camp_items
            ),
            f"n={len(camp_items)}",
        )
    )

    # VP0-9 Product filters：category_id
    prod_filters = quote(
        json.dumps(
            {
                "logic": "and",
                "conditions": [{"field_key": "category_id", "op": "eq", "value": cat_id}],
            },
            ensure_ascii=False,
        )
    )
    code, prod_list = req("GET", f"/crm/products?filters={prod_filters}&page_size=100", token=admin_tok)
    results.append(check("VP0-9-1 Product filters 200", code == 200, f"{code}"))
    results.append(
        check("VP0-9-2 filters_applied", (prod_list or {}).get("filters_applied") is True, str(prod_list))
    )
    prod_items = (prod_list or {}).get("items") or []
    results.append(
        check(
            "VP0-9-3 命中分类产品",
            any(i.get("id") == (prod or {}).get("id") for i in prod_items),
            f"n={len(prod_items)}",
        )
    )

    # VP0-10 保存视图 + view_id 查询
    code, view = req(
        "POST",
        "/crm/views",
        token=admin_tok,
        body={
            "entity_type": "campaign",
            "name": f"P0视图-{uuid.uuid4().hex[:4]}",
            "filters": {"logic": "and", "conditions": [{"field_key": "status", "op": "eq", "value": "active"}]},
            "is_public": False,
        },
    )
    results.append(check("VP0-10-1 创建 campaign 视图 201", code == 201, f"{code} {view}"))
    view_id = (view or {}).get("id")
    code, view_list = req("GET", f"/crm/campaigns?view_id={view_id}&page_size=100", token=admin_tok)
    results.append(check("VP0-10-2 view_id 列表 200", code == 200, str(code)))
    results.append(
        check(
            "VP0-10-3 视图生效 active",
            all(i.get("status") == "active" for i in ((view_list or {}).get("items") or [])),
            str((view_list or {}).get("items")),
        )
    )
    results.append(
        check(
            "VP0-10-4 view_id 回写",
            (view_list or {}).get("view_id") == view_id,
            str((view_list or {}).get("view_id")),
        )
    )

    # VP0-13 Order 列设置读写
    code, pref0 = req("GET", "/me/view-preferences/order", token=admin_tok)
    results.append(check("VP0-13-1 GET 列偏好 200", code == 200, str(code)))
    cols = (pref0 or {}).get("columns") or []
    if not cols:
        # 若空则用 list_fields 初始化再保存
        code, ol = req("GET", "/crm/orders?page_size=1", token=admin_tok)
        cols = (ol or {}).get("list_fields") or []
    save_cols = [
        {"field_key": c.get("field_key"), "visible": c.get("visible", True), "order": i}
        for i, c in enumerate(cols)
        if c.get("field_key")
    ]
    if save_cols:
        # 翻转第一列可见性验证写回
        save_cols[0]["visible"] = not bool(save_cols[0].get("visible", True))
        code, pref1 = req("PUT", "/me/view-preferences/order", token=admin_tok, body={"columns": save_cols})
        results.append(check("VP0-13-2 PUT 列设置 200", code == 200, f"{code} {pref1}"))
        code, pref2 = req("GET", "/me/view-preferences/order", token=admin_tok)
        got = {(c.get("field_key"), c.get("visible")) for c in ((pref2 or {}).get("columns") or [])}
        expect_key = save_cols[0]["field_key"]
        expect_vis = save_cols[0]["visible"]
        results.append(
            check(
                "VP0-13-3 列设置持久化",
                (expect_key, expect_vis) in got,
                f"expect=({expect_key},{expect_vis}) got={got}",
            )
        )
        # 恢复
        save_cols[0]["visible"] = not expect_vis
        req("PUT", "/me/view-preferences/order", token=admin_tok, body={"columns": save_cols})
    else:
        results.append(check("VP0-13-2 有可写列", False, "no columns"))

    # -------- Day D: VP0-11 合同关联订单 + 回款汇总字段 --------
    code, c_rel = req(
        "POST",
        "/crm/contracts",
        token=admin_tok,
        body={
            "title": f"P0关联订单合同-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "contract_type": "new",
            "amount": 8800,
            "status": "signed",
            "signed_amount": 8800,
        },
    )
    results.append(check("VP0-11-1 创建已签合同 201", code == 201, f"{code} {c_rel}"))
    cid = (c_rel or {}).get("id")

    code, conv = req("POST", f"/crm/contracts/{cid}/convert-to-order", token=admin_tok)
    results.append(check("VP0-11-2 合同转订单 201", code == 201, f"{code} {conv}"))
    linked_order_id = (conv or {}).get("order_id")
    results.append(check("VP0-11-3 返回 order_id", bool(linked_order_id), str(conv)))

    code, related = req("GET", f"/crm/orders?contract_id={cid}&page_size=50", token=admin_tok)
    results.append(check("VP0-11-4 按合同筛订单 200", code == 200, str(code)))
    rel_items = (related or {}).get("items") or []
    results.append(
        check(
            "VP0-11-5 列表含关联订单",
            any(i.get("id") == linked_order_id for i in rel_items),
            f"order={linked_order_id} n={len(rel_items)}",
        )
    )
    results.append(
        check(
            "VP0-11-6 contract_id 匹配",
            any(i.get("id") == linked_order_id and i.get("contract_id") == cid for i in rel_items),
            str([(i.get("id"), i.get("contract_id")) for i in rel_items[:5]]),
        )
    )

    # 回款列表带订单计划/已回/逾期汇总字段
    code, pay = req(
        "POST",
        "/crm/payments",
        token=admin_tok,
        body={
            "order_id": linked_order_id,
            "amount": 100,
            "method": "bank",
            "status": "pending",
        },
    )
    results.append(check("VP0-11-7 登记回款 201", code == 201, f"{code} {pay}"))
    code, pays = req("GET", "/crm/payments?page_size=50", token=admin_tok)
    results.append(check("VP0-11-8 回款列表 200", code == 200, str(code)))
    pay_hit = next((p for p in ((pays or {}).get("items") or []) if p.get("id") == (pay or {}).get("id")), None)
    results.append(
        check(
            "VP0-11-9 回款含订单汇总字段",
            pay_hit is not None
            and "order_plan_total" in pay_hit
            and "order_paid_total" in pay_hit
            and "order_overdue_amount" in pay_hit,
            str(pay_hit),
        )
    )

    # -------- Day E: VP0-12 / VP0-14 / VP0-15 --------
    # VP0-12 H5 pages.json 含 contract/payment/product
    mp_pages = (API_ROOT.parents[1] / "apps" / "mp" / "src" / "pages.json").read_text(encoding="utf-8")
    results.append(
        check(
            "VP0-12-1 pages 含 contract-detail",
            "pages/crm/contract-detail" in mp_pages,
            "missing contract-detail",
        )
    )
    results.append(
        check(
            "VP0-12-2 pages 含 payment-detail",
            "pages/crm/payment-detail" in mp_pages,
            "missing payment-detail",
        )
    )
    results.append(
        check("VP0-12-3 pages 含 products", "pages/crm/products" in mp_pages, "missing products")
    )
    for rel in (
        "pages/crm/contract-detail.vue",
        "pages/crm/payment-detail.vue",
        "pages/crm/products.vue",
        "pages/crm/order-detail.vue",
    ):
        p = API_ROOT.parents[1] / "apps" / "mp" / "src" / rel
        results.append(check(f"VP0-12-f {rel}", p.is_file(), str(p)))

    # VP0-14 draft 订单 confirm 路径
    code, o_draft = req(
        "POST",
        "/crm/orders",
        token=admin_tok,
        body={
            "title": f"P0-H5确认-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [
                {
                    "name": "确认测",
                    "quantity": 1,
                    "unit_price": 10,
                    "discount_rate": 0,
                }
            ],
        },
    )
    results.append(check("VP0-14-1 创建 draft 订单 201", code == 201, f"{code}"))
    oid14 = (o_draft or {}).get("id")
    code, confirmed14 = req("POST", f"/crm/orders/{oid14}/confirm", token=admin_tok)
    results.append(check("VP0-14-2 confirm 200", code == 200, f"{code} {confirmed14}"))
    results.append(
        check(
            "VP0-14-3 status=confirmed",
            (confirmed14 or {}).get("status") == "confirmed",
            str((confirmed14 or {}).get("status")),
        )
    )
    # order-detail 含动作入口（静态 smoke）
    od_src = (API_ROOT.parents[1] / "apps" / "mp" / "src" / "pages" / "crm" / "order-detail.vue").read_text(
        encoding="utf-8"
    )
    results.append(
        check(
            "VP0-14-4 H5 order-detail 含 confirm/approve",
            "confirmOrder" in od_src and "approveOrder" in od_src and "cancelOrder" in od_src,
            "missing actions",
        )
    )

    # VP0-15 Order 跟进 activity POST
    code, act = req(
        "POST",
        "/crm/activities",
        token=admin_tok,
        body={
            "entity_type": "order",
            "entity_id": oid14,
            "activity_type": "call",
            "content": f"P0订单跟进-{uuid.uuid4().hex[:6]}",
        },
    )
    results.append(check("VP0-15-1 order activity 201", code == 201, f"{code} {act}"))
    results.append(
        check(
            "VP0-15-2 entity_type=order",
            (act or {}).get("entity_type") == "order" and str((act or {}).get("entity_id")) == str(oid14),
            str(act),
        )
    )
    code, acts = req(
        "GET",
        f"/crm/activities?entity_type=order&entity_id={oid14}",
        token=admin_tok,
    )
    results.append(check("VP0-15-3 列表跟进 200", code == 200, str(code)))
    results.append(
        check(
            "VP0-15-4 列表含该跟进",
            any(a.get("id") == (act or {}).get("id") for a in (acts or [])),
            str(acts),
        )
    )

    return finish_phase("v1.0-order-contract-P0", results)


if __name__ == "__main__":
    raise SystemExit(main())
