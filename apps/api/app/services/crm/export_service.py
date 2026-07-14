"""线索/客户导出。"""

from __future__ import annotations

import csv
import io
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.crm import Customer, Lead


def _leads_rows(db: Session, tenant_id: UUID) -> list[dict]:
    rows = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant_id, Lead.deleted_at.is_(None))
        .order_by(Lead.created_at.desc())
        .limit(5000)
        .all()
    )
    return [
        {
            "编号": r.lead_number or "",
            "公司名称": r.company_name or "",
            "联系人": r.contact_name or "",
            "手机": r.mobile or "",
            "来源": r.source or "",
            "职位": r.title or "",
            "评分": r.lead_score if r.lead_score is not None else "",
            "部门": r.department or "",
            "国家": r.country or "",
            "状态": r.status or "",
            "负责人": str(r.owner_user_id or ""),
            "创建时间": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def _customers_rows(db: Session, tenant_id: UUID) -> list[dict]:
    rows = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.deleted_at.is_(None))
        .order_by(Customer.created_at.desc())
        .limit(5000)
        .all()
    )
    return [
        {
            "编号": r.customer_number or "",
            "客户名称": r.company_name or "",
            "手机": r.mobile or "",
            "来源": r.source or "",
            "类型": r.type or "",
            "状态": r.status or "",
            "累计成交": float(r.total_revenue or 0),
            "最近成交日": str(r.last_deal_date or ""),
            "转化评分": r.converted_lead_score if r.converted_lead_score is not None else "",
            "标签": ",".join(r.tags) if isinstance(r.tags, list) else "",
            "负责人": str(r.owner_user_id or ""),
            "创建时间": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def export_csv(db: Session, tenant_id: UUID, entity_type: str) -> tuple[str, bytes]:
    if entity_type == "lead":
        data = _leads_rows(db, tenant_id)
        filename = "leads.csv"
    elif entity_type == "customer":
        data = _customers_rows(db, tenant_id)
        filename = "customers.csv"
    else:
        raise HTTPException(status_code=400, detail="仅支持 lead/customer")
    buf = io.StringIO()
    if not data:
        buf.write("\ufeff")
        return filename, buf.getvalue().encode("utf-8-sig")
    writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)
    return filename, ("\ufeff" + buf.getvalue()).encode("utf-8-sig")


def export_xlsx(db: Session, tenant_id: UUID, entity_type: str) -> tuple[str, bytes]:
    try:
        import openpyxl
    except ImportError as e:
        raise HTTPException(status_code=500, detail="需要 openpyxl") from e
    if entity_type == "lead":
        data = _leads_rows(db, tenant_id)
        filename = "leads.xlsx"
        sheet_name = "线索"
    elif entity_type == "customer":
        data = _customers_rows(db, tenant_id)
        filename = "customers.xlsx"
        sheet_name = "客户"
    else:
        raise HTTPException(status_code=400, detail="仅支持 lead/customer")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    if data:
        headers = list(data[0].keys())
        ws.append(headers)
        for row in data:
            ws.append([row.get(h, "") for h in headers])
    out = io.BytesIO()
    wb.save(out)
    return filename, out.getvalue()
