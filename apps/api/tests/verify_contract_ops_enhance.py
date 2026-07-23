#!/usr/bin/env python3
"""合同增强：状态动作/审批/复制/批量/导出/补充协议回写。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.verify_crm_helpers import (  # noqa: E402
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    req,
)


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    tok = admin_token()
    results: list[bool] = []

    code, cust = req(
        "POST",
        "/crm/customers",
        token=tok,
        body={"company_name": f"CtrEnh客户-{uuid.uuid4().hex[:6]}", "mobile": f"137{uuid.uuid4().hex[:8]}"[:11]},
    )
    results.append(check("pre 客户", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    code, c = req(
        "POST",
        "/crm/contracts",
        token=tok,
        body={
            "title": f"增强合同-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "contract_type": "new",
            "amount": 10000,
            "lines": [{"name": "服务", "quantity": 1, "unit_price": 10000}],
        },
    )
    results.append(check("1 创建", code == 201, str(code)))
    cid = (c or {}).get("id")

    code, patched = req("PATCH", f"/crm/contracts/{cid}", token=tok, body={"status": "signed", "title": c["title"]})
    results.append(
        check("2 PATCH 忽略 status", code == 200 and (patched or {}).get("status") == "draft", str((patched or {}).get("status")))
    )

    code, sent = req("POST", f"/crm/contracts/{cid}/send", token=tok)
    results.append(check("3 send→sent", code == 200 and (sent or {}).get("status") == "sent", str(code)))

    code, submitted = req("POST", f"/crm/contracts/{cid}/submit", token=tok)
    # 可能 pending_approval 或仍 sent
    st = (submitted or {}).get("status")
    results.append(check("4 submit", code == 200 and st in ("sent", "pending_approval"), f"{code} {st}"))
    if st == "pending_approval":
        code, approved = req("POST", f"/crm/contracts/{cid}/approve", token=tok)
        results.append(check("4b approve→sent", code == 200 and (approved or {}).get("status") == "sent", str(code)))

    code, signed = req("POST", f"/crm/contracts/{cid}/sign", token=tok, body={"signed_amount": 9800})
    results.append(
        check(
            "5 sign",
            code == 200 and (signed or {}).get("status") == "signed" and float((signed or {}).get("signed_amount") or 0) == 9800,
            str(signed),
        )
    )
    results.append(
        check(
            "5b amount_diff",
            (signed or {}).get("amount_diff") is not None and abs(float((signed or {}).get("amount_diff")) + 200) < 0.01,
            str((signed or {}).get("amount_diff")),
        )
    )

    # 签署后不可直改金额
    code, lock = req("PATCH", f"/crm/contracts/{cid}", token=tok, body={"amount": 1})
    results.append(check("6 签署后禁改金额", code == 409, str(code)))

    code, act = req("POST", f"/crm/contracts/{cid}/activate", token=tok)
    results.append(check("7 activate", code == 200 and (act or {}).get("status") == "executing", str(code)))

    # 补充协议回写
    code, amd = req(
        "POST",
        f"/crm/contracts/{cid}/amendments",
        token=tok,
        body={"title": "加价", "change_type": "amount_change", "amount_delta": 500},
    )
    results.append(check("8 amend create", code == 201, str(code)))
    amd_id = (amd or {}).get("id")
    code, exe = req("POST", f"/crm/contracts/amendments/{amd_id}/execute", token=tok)
    results.append(check("8b execute", code == 200 and (exe or {}).get("status") == "executed", str(code)))
    code, after = req("GET", f"/crm/contracts/{cid}", token=tok)
    results.append(
        check(
            "8c amount+signed 回写",
            abs(float((after or {}).get("amount") or 0) - 10500) < 0.01
            and abs(float((after or {}).get("signed_amount") or 0) - 10300) < 0.01,
            str({k: (after or {}).get(k) for k in ("amount", "signed_amount")}),
        )
    )

    code, cloned = req("POST", f"/crm/contracts/{cid}/clone", token=tok)
    results.append(check("9 clone", code == 201 and (cloned or {}).get("status") == "draft", str(code)))

    code, renewed = req("POST", f"/crm/contracts/{cid}/renew-contract", token=tok)
    results.append(
        check(
            "10 renew-contract",
            code == 201 and (renewed or {}).get("contract_type") == "renewal",
            str(renewed),
        )
    )

    # 批量
    code, c2 = req(
        "POST",
        "/crm/contracts",
        token=tok,
        body={"title": f"批A-{uuid.uuid4().hex[:4]}", "customer_id": cust_id, "amount": 10, "lines": [{"name": "x", "quantity": 1, "unit_price": 10}]},
    )
    code, c3 = req(
        "POST",
        "/crm/contracts",
        token=tok,
        body={"title": f"批B-{uuid.uuid4().hex[:4]}", "customer_id": cust_id, "amount": 10, "lines": [{"name": "y", "quantity": 1, "unit_price": 10}]},
    )
    ids = [(c2 or {}).get("id"), (c3 or {}).get("id")]
    code, batch = req("POST", "/crm/contracts/batch-action", token=tok, body={"contract_ids": ids, "action": "send"})
    results.append(check("11 batch send", code == 200 and (batch or {}).get("succeeded", 0) >= 1, str(batch)))

    code, _ = req("POST", f"/crm/contracts/{cid}/terminate", token=tok)
    results.append(check("12 terminate", code == 200, str(code)))

    # 删除保护：executing/terminated 不可删；草稿可删
    code, _ = req("DELETE", f"/crm/contracts/{cid}", token=tok)
    results.append(check("13 终止后不可删", code == 409, str(code)))

    code, export_body = req("GET", "/crm/export/contracts?format=csv", token=tok)
    results.append(check("14 export", code == 200, f"{code} type={type(export_body)}"))

    return finish_phase("contract-ops-enhance", results)


if __name__ == "__main__":
    raise SystemExit(main())
