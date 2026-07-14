"""客户联系人决策链。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.crm import Contact, Customer


def get_decision_chain(db: Session, tenant_id: UUID, customer_id: UUID) -> dict:
    customer = (
        db.query(Customer)
        .filter(
            uuid_eq(Customer.id, customer_id),
            Customer.tenant_id == tenant_id,
            Customer.deleted_at.is_(None),
        )
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    contacts = (
        db.query(Contact)
        .filter(
            Contact.tenant_id == tenant_id,
            uuid_eq(Contact.customer_id, customer_id),
            Contact.deleted_at.is_(None),
        )
        .all()
    )
    nodes = []
    edges = []
    ids = {c.id for c in contacts}
    for c in contacts:
        nodes.append(
            {
                "id": str(c.id),
                "name": c.name,
                "title": c.title,
                "department": c.department,
                "contact_role": c.contact_role,
                "is_primary": c.is_primary,
            }
        )
        if c.reports_to_contact_id and c.reports_to_contact_id in ids:
            edges.append(
                {
                    "from": str(c.id),
                    "to": str(c.reports_to_contact_id),
                    "relation": "reports_to",
                }
            )
    # 按角色粗分层，便于前端画图
    role_rank = {"决策者": 0, "影响者": 1, "评估者": 2, "使用者": 3}
    layers: dict[str, list[str]] = {}
    for n in nodes:
        key = n.get("contact_role") or "未标注"
        layers.setdefault(key, []).append(n["id"])
    return {
        "customer_id": str(customer_id),
        "company_name": customer.company_name,
        "nodes": nodes,
        "edges": edges,
        "layers": layers,
        "role_rank": role_rank,
    }
