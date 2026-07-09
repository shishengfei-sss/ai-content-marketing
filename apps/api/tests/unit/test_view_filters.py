"""CRM 列表视图筛选单元测试。"""
from __future__ import annotations

import uuid

from app.database import SessionLocal
from app.models.crm import EntityFieldDefinition, Lead
from app.services.crm.view_service import _field_expr, apply_view_filters


def _seed_field(db, tenant_id: uuid.UUID, *, storage: str = "seed") -> EntityFieldDefinition:
    row = EntityFieldDefinition(
        tenant_id=tenant_id,
        entity_type="lead",
        field_key="source",
        label="线索来源",
        field_type="select",
        storage=storage,
    )
    db.add(row)
    db.flush()
    return row


def test_field_expr_prefers_model_column_over_seed_storage():
    db = SessionLocal()
    try:
        tenant_id = uuid.uuid4()
        field_def = _seed_field(db, tenant_id, storage="seed")
        expr = _field_expr(Lead, field_def)
        assert expr is Lead.source
    finally:
        db.rollback()
        db.close()


def test_apply_view_filters_source_eq():
    db = SessionLocal()
    try:
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        _seed_field(db, tenant_id, storage="seed")

        for company, source in [("A", "导入"), ("B", None), ("C", "导入"), ("D", "官网")]:
            db.add(
                Lead(
                    tenant_id=tenant_id,
                    owner_user_id=owner_id,
                    created_by_user_id=owner_id,
                    company_name=company,
                    status="潜在",
                    source=source,
                )
            )
        db.flush()

        query = db.query(Lead).filter(Lead.tenant_id == tenant_id, Lead.deleted_at.is_(None))
        filtered = apply_view_filters(
            query,
            db,
            tenant_id,
            "lead",
            {"logic": "and", "conditions": [{"field_key": "source", "op": "eq", "value": "导入"}]},
        )
        names = sorted(row.company_name for row in filtered.all())
        assert names == ["A", "C"]
    finally:
        db.rollback()
        db.close()
