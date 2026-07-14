#!/usr/bin/env python3
"""CRM-2/3 Phase D-H 验收：产品/报价/合同/订单/回款 全链路。

覆盖：
  D  产品 CRUD
  E  报价 CRUD + 明细 + 发送 + 接受 + 转订单
  F  合同 CRUD + 签署 + 重复转订单
  G  订单 CRUD + 明细 + 确认 + 取消
  H  回款计划 + 实际回款 + 确认 + 冲销
  路径 商机 -> 报价 -> 订单、商机 -> 合同 -> 订单（合同重复生成订单）

详见 docs/v0.7-crm-deal执行计划.md §Phase D-H。
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.verify_crm_helpers import (
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    req,
    run_step_parser,
    sales_token,
)


def _ensure_customer(admin_tok: str) -> str:
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={
            "company_name": f"交易测试客户-{uuid.uuid4().hex[:6]}",
            "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
        },
    )
    assert code == 201, cust
    return cust["id"]


def step_d_product(results: list[bool]) -> None:
    """产品 CRUD。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    code = f"P{uuid.uuid4().hex[:6]}"
    # 创建
    code_, prod = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={
            "code": code,
            "name": f"测试产品-{code}",
            "unit": "套",
            "list_price": 1999.00,
            "cost_price": 1200.00,
            "is_active": True,
        },
    )
    results.append(check("VD-1 创建产品 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    pid = prod["id"]
    results.append(check("VD-2 产品 id 返回", pid is not None, ""))

    # 编码唯一冲突
    code_, _ = req("POST", "/crm/products", token=admin_tok, body={"code": code, "name": "重复"})
    results.append(check("VD-3 编码冲突 409", code_ == 409, str(code_)))

    # 列表（按编码搜索）
    code_, lst = req("GET", f"/crm/products?q={code}", token=admin_tok)
    results.append(check("VD-4 列表 200", code_ == 200, str(code_)))
    results.append(check("VD-5 能搜到产品", lst["total"] >= 1, str(lst.get("total"))))

    # 详情
    code_, p2 = req("GET", f"/crm/products/{pid}", token=admin_tok)
    results.append(check("VD-6 详情 200", code_ == 200, str(code_)))
    results.append(check("VD-7 详情字段", p2["code"] == code, p2.get("code")))

    # 编辑
    code_, p3 = req("PATCH", f"/crm/products/{pid}", token=admin_tok, body={"list_price": 2999.00})
    results.append(check("VD-8 编辑 200", code_ == 200, str(code_)))
    results.append(check("VD-9 价格更新", float(p3["list_price"]) == 2999.00, str(p3["list_price"])))

    # 删除
    code_, _ = req("DELETE", f"/crm/products/{pid}", token=admin_tok)
    results.append(check("VD-10 删除 204", code_ == 204, str(code_)))


def step_e_quote(results: list[bool]) -> None:
    """报价 CRUD + 明细 + 发送 + 接受 + 转订单。"""
    admin_tok = admin_token()
    sales_tok = sales_token()
    customer_id = _ensure_customer(admin_tok)

    # 创建产品用于明细
    pcode = f"QP{uuid.uuid4().hex[:6]}"
    code_, prod = req(
        "POST",
        "/crm/products",
        token=admin_tok,
        body={"code": pcode, "name": f"报价产品-{pcode}", "list_price": 500.00},
    )
    assert code_ == 201, prod
    product_id = prod["id"]

    # 创建报价 + 明细
    code_, quote = req(
        "POST",
        "/crm/quotes",
        token=sales_tok,
        body={
            "customer_id": customer_id,
            "subject": f"测试报价-{uuid.uuid4().hex[:6]}",
            "status": "draft",
            "lines": [
                {"name": "产品A", "quantity": 2, "unit_price": 500, "line_total": 1000},
                {"name": "产品B", "quantity": 1, "unit_price": 200, "line_total": 200},
            ],
        },
    )
    results.append(check("VE-1 创建报价 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    qid = quote["id"]
    results.append(check("VE-2 自动生成报价单号", quote["quote_number"].startswith("BJ"), quote["quote_number"]))
    results.append(check("VE-3 明细回填", len(quote["lines"]) == 2, str(len(quote.get("lines", [])))))
    # total = 1000 + 200 = 1200
    results.append(check("VE-4 total 自动计算", float(quote["total_amount"]) == 1200, str(quote["total_amount"])))

    # 列表
    code_, lst = req("GET", f"/crm/quotes?status=draft", token=sales_tok)
    results.append(check("VE-5 列表 200", code_ == 200, str(code_)))

    # 编辑明细 -> 重算
    code_, q2 = req(
        "PATCH",
        f"/crm/quotes/{qid}",
        token=sales_tok,
        body={"lines": [{"name": "产品A", "quantity": 3, "unit_price": 500, "line_total": 1500}]},
    )
    results.append(check("VE-6 编辑报价 200", code_ == 200, str(code_)))
    results.append(check("VE-7 重算 total", float(q2["total_amount"]) == 1500, str(q2["total_amount"])))

    # 发送（sales 无 send 权限，用 admin）
    code_, q3 = req("POST", f"/crm/quotes/{qid}/send", token=admin_tok)
    results.append(check("VE-8 发送 200", code_ == 200, str(code_)))
    results.append(check("VE-9 状态 sent", q3["status"] == "sent", q3["status"]))

    # 接受
    code_, q4 = req("POST", f"/crm/quotes/{qid}/accept", token=admin_tok)
    results.append(check("VE-10 接受 200", code_ == 200, str(code_)))
    results.append(check("VE-11 状态 accepted", q4["status"] == "accepted", q4["status"]))

    # 转订单（sales 有 crm.order.convert）
    code_, out = req("POST", f"/crm/quotes/{qid}/convert-to-order", token=sales_tok)
    results.append(check("VE-12 报价转订单 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    order_id = out["order_id"]
    # 校验订单
    code_, order = req("GET", f"/crm/orders/{order_id}", token=sales_tok)
    results.append(check("VE-13 订单存在 200", code_ == 200, str(code_)))
    results.append(check("VE-14 订单 source=quote", order["source"] == "quote", order["source"]))
    results.append(check("VE-15 订单明细复制", len(order["lines"]) == 1, str(len(order.get("lines", [])))))
    results.append(check("VE-16 报价状态 ordered", q4["status"] == "accepted", ""))  # q4 是 accept 后的

    # 重复转单 -> 409
    code_, _ = req("POST", f"/crm/quotes/{qid}/convert-to-order", token=sales_tok)
    results.append(check("VE-17 重复转单 409", code_ == 409, str(code_)))

    # 删除报价（sales 无 delete 权限，用 admin）
    code_, _ = req("DELETE", f"/crm/quotes/{qid}", token=admin_tok)
    results.append(check("VE-18 删除报价 204", code_ == 204, str(code_)))


def step_f_contract(results: list[bool]) -> None:
    """合同 CRUD + 签署 + 重复转订单。sales 角色无合同写权限，全流程用 admin。"""
    admin_tok = admin_token()
    sales_tok = sales_token()
    customer_id = _ensure_customer(admin_tok)

    # 创建合同
    code_, contract = req(
        "POST",
        "/crm/contracts",
        token=admin_tok,
        body={
            "customer_id": customer_id,
            "title": f"测试合同-{uuid.uuid4().hex[:6]}",
            "contract_type": "new",
            "amount": 50000,
        },
    )
    results.append(check("VF-1 创建合同 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    cid = contract["id"]
    results.append(check("VF-2 自动合同号", contract["contract_number"].startswith("HT"), contract["contract_number"]))

    # 未签署不可转单（用 admin，避免 sales 看不到 admin 的合同而 403）
    code_, _ = req("POST", f"/crm/contracts/{cid}/convert-to-order", token=admin_tok)
    results.append(check("VF-3 未签署转单 409", code_ == 409, str(code_)))

    # 签署（sales 无 sign 权限，用 admin）
    code_, c2 = req(
        "POST",
        f"/crm/contracts/{cid}/sign",
        token=admin_tok,
        body={"signed_amount": 48000},
    )
    results.append(check("VF-4 签署 200", code_ == 200, str(code_)))
    results.append(check("VF-5 状态 signed", c2["status"] == "signed", c2["status"]))
    results.append(check("VF-6 signed_amount", float(c2["signed_amount"]) == 48000, str(c2["signed_amount"])))
    results.append(check("VF-7 signed_at 落库", c2["signed_at"] is not None, ""))

    # 第一次转订单（admin 操作，因合同属 admin；sales 无 list_all 不可见）
    code_, out1 = req("POST", f"/crm/contracts/{cid}/convert-to-order", token=admin_tok)
    results.append(check("VF-8 合同转订单1 201", code_ == 201, str(code_)))
    order1_id = out1["order_id"]
    code_, o1 = req("GET", f"/crm/orders/{order1_id}", token=admin_tok)
    results.append(check("VF-9 订单 source=contract", o1["source"] == "contract", o1["source"]))
    results.append(check("VF-10 订单金额=签署金额", float(o1["amount"]) == 48000, str(o1["amount"])))

    # 第二次转订单（合同可重复生成）
    code_, out2 = req("POST", f"/crm/contracts/{cid}/convert-to-order", token=admin_tok)
    results.append(check("VF-11 合同重复转单 201", code_ == 201, str(code_)))
    results.append(check("VF-12 两次订单不同", out1["order_id"] != out2["order_id"], ""))

    # 删除合同（sales 无 delete 权限，用 admin）
    code_, _ = req("DELETE", f"/crm/contracts/{cid}", token=admin_tok)
    results.append(check("VF-13 删除合同 204", code_ == 204, str(code_)))


def step_g_order(results: list[bool]) -> None:
    """订单 CRUD + 明细 + 确认 + 取消。"""
    admin_tok = admin_token()
    sales_tok = sales_token()
    customer_id = _ensure_customer(admin_tok)

    # 直接创建订单
    code_, order = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"测试订单-{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id,
            "source": "deal",
            "amount": 3000,
            "lines": [{"name": "服务费", "quantity": 1, "unit_price": 3000, "line_total": 3000}],
        },
    )
    results.append(check("VG-1 创建订单 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    oid = order["id"]
    results.append(check("VG-2 自动单号", order["order_number"].startswith("DD"), order["order_number"]))
    results.append(check("VG-3 默认 draft", order["status"] == "draft", order["status"]))
    results.append(check("VG-4 明细回填", len(order["lines"]) == 1, str(len(order.get("lines", [])))))

    # 列表
    code_, lst = req("GET", "/crm/orders?status=draft", token=sales_tok)
    results.append(check("VG-5 列表 200", code_ == 200, str(code_)))

    # 确认
    code_, o2 = req("POST", f"/crm/orders/{oid}/confirm", token=sales_tok)
    results.append(check("VG-6 确认 200", code_ == 200, str(code_)))
    results.append(check("VG-7 状态 confirmed", o2["status"] == "confirmed", o2["status"]))

    # 取消
    code_, o3 = req("POST", f"/crm/orders/{oid}/cancel", token=sales_tok)
    results.append(check("VG-8 取消 200", code_ == 200, str(code_)))
    results.append(check("VG-9 状态 cancelled", o3["status"] == "cancelled", o3["status"]))

    # 已取消不可再次确认
    code_, _ = req("POST", f"/crm/orders/{oid}/confirm", token=sales_tok)
    results.append(check("VG-10 已取消不可确认 409", code_ == 409, str(code_)))

    # 删除（sales 无 delete 权限，用 admin）
    code_, _ = req("DELETE", f"/crm/orders/{oid}", token=admin_tok)
    results.append(check("VG-11 删除订单 204", code_ == 204, str(code_)))


def step_h_payment(results: list[bool]) -> None:
    """回款计划 + 实际回款 + 确认 + 冲销。"""
    admin_tok = admin_token()
    sales_tok = sales_token()
    customer_id = _ensure_customer(admin_tok)

    # 先建一个订单
    code_, order = req(
        "POST",
        "/crm/orders",
        token=sales_tok,
        body={
            "title": f"回款测试订单-{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id,
            "source": "deal",
            "amount": 10000,
        },
    )
    assert code_ == 201, order
    oid = order["id"]

    # 创建回款计划（2 期）
    from datetime import datetime, timedelta

    plan_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
    code_, plan1 = req(
        "POST",
        f"/crm/payments/orders/{oid}/plans",
        token=sales_tok,
        body={"installment_no": 1, "plan_date": plan_date, "plan_amount": 5000},
    )
    results.append(check("VH-1 创建回款计划 201", code_ == 201, str(code_)))
    plan_id = plan1["id"]

    # 列表计划
    code_, plans = req("GET", f"/crm/payments/orders/{oid}/plans", token=sales_tok)
    results.append(check("VH-2 列表计划 200", code_ == 200, str(code_)))
    results.append(check("VH-3 计划数 >=1", len(plans) >= 1, str(len(plans))))

    # 登记实际回款
    code_, pay = req(
        "POST",
        "/crm/payments",
        token=sales_tok,
        body={
            "order_id": oid,
            "plan_id": plan_id,
            "amount": 5000,
            "method": "bank",
            "status": "pending",
        },
    )
    results.append(check("VH-4 登记回款 201", code_ == 201, str(code_)))
    if code_ != 201:
        return
    pid = pay["id"]
    results.append(check("VH-5 自动回款号", pay["payment_number"].startswith("HK"), pay["payment_number"]))

    # 确认到账（sales 无 confirm 权限，用 admin）
    code_, pay2 = req("POST", f"/crm/payments/{pid}/confirm", token=admin_tok)
    results.append(check("VH-6 确认到账 200", code_ == 200, str(code_)))
    results.append(check("VH-7 状态 confirmed", pay2["status"] == "confirmed", pay2["status"]))

    # 冲销
    code_, pay3 = req("POST", f"/crm/payments/{pid}/reverse", token=admin_tok)
    results.append(check("VH-8 冲销 200", code_ == 200, str(code_)))
    results.append(check("VH-9 状态 reversed", pay3["status"] == "reversed", pay3["status"]))

    # 已冲销不可再次确认
    code_, _ = req("POST", f"/crm/payments/{pid}/confirm", token=admin_tok)
    results.append(check("VH-10 已冲销不可确认 409", code_ == 409, str(code_)))

    # 删除回款（sales 无 delete 权限，用 admin）
    code_, _ = req("DELETE", f"/crm/payments/{pid}", token=admin_tok)
    results.append(check("VH-11 删除回款 204", code_ == 204, str(code_)))

    # 删除计划
    code_, _ = req("DELETE", f"/crm/payments/plans/{plan_id}", token=admin_tok)
    results.append(check("VH-12 删除计划 204", code_ == 204, str(code_)))


STEPS = {
    "D": step_d_product,
    "E": step_e_quote,
    "F": step_f_contract,
    "G": step_g_order,
    "H": step_h_payment,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2/3 D-H", results)


if __name__ == "__main__":
    raise SystemExit(main())
