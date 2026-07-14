"""CRM 保存列表视图服务。"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Query, Session

from app.dependencies import TenantContext
from app.models.crm import Customer, Deal, EntityFieldDefinition, EntityListView, Lead, Quote, Contract, Order, Payment
from app.permissions import SYSTEM_ROLE_ADMIN
from app.services.crm.schema_service import (
    ensure_entity_schema,
    list_active_fields,
    list_column_out,
    normalize_list_column,
    resolve_list_columns,
)

VIEW_ENTITY_TYPES = frozenset({"lead", "customer", "task", "campaign", "deal", "quote", "contract", "order", "payment"})

LEAD_SEARCH_COLUMNS = (
    Lead.company_name,
    Lead.contact_name,
    Lead.mobile,
    Lead.phone,
    Lead.email,
)

DEAL_SEARCH_COLUMNS = (
    Deal.title,
)

QUOTE_SEARCH_COLUMNS = (Quote.subject, Quote.quote_number)
CONTRACT_SEARCH_COLUMNS = (Contract.title, Contract.contract_number)
ORDER_SEARCH_COLUMNS = (Order.title, Order.order_number)
PAYMENT_SEARCH_COLUMNS = (Payment.payment_number,)


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def _is_admin(ctx: TenantContext) -> bool:
    return ctx.membership.role.is_system and ctx.membership.role.code == SYSTEM_ROLE_ADMIN


def _can_manage_public(ctx: TenantContext) -> bool:
    return _is_admin(ctx) or "crm.view.manage_public" in _perm_set(ctx)


def validate_view_entity_type(entity_type: str) -> None:
    if entity_type not in VIEW_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的 entity_type: {entity_type}")


def _field_storage_map(db: Session, tenant_id: UUID, entity_type: str) -> dict[str, EntityFieldDefinition]:
    ensure_entity_schema(db, tenant_id, entity_type)
    fields = list_active_fields(db, tenant_id, entity_type)
    return {f.field_key: f for f in fields}


def _model_for_entity(entity_type: str):
    if entity_type == "lead":
        return Lead
    if entity_type == "customer":
        return Customer
    if entity_type == "deal":
        return Deal
    if entity_type == "quote":
        return Quote
    if entity_type == "contract":
        return Contract
    if entity_type == "order":
        return Order
    if entity_type == "payment":
        return Payment
    raise HTTPException(status_code=400, detail=f"视图筛选暂未支持 {entity_type}")


def _field_expr(model, field_def: EntityFieldDefinition):
    key = field_def.field_key
    # 业务表列优先：历史租户 schema 可能仍标记为 seed，但数据在 ORM 列上
    if hasattr(model, key):
        return getattr(model, key)
    return func.json_extract(model.extra_data, f"$.{key}")


def _apply_condition(query: Query, model, field_def: EntityFieldDefinition, cond: dict) -> Query:
    op = cond.get("op", "eq")
    value = cond.get("value")
    expr = _field_expr(model, field_def)

    if op == "eq":
        return query.filter(expr == value)
    if op == "neq":
        return query.filter(expr != value)
    if op == "in":
        vals = value if isinstance(value, list) else [value]
        return query.filter(expr.in_(vals))
    if op == "contains" and value is not None:
        return query.filter(expr.contains(str(value)))
    if op == "is_empty":
        return query.filter(or_(expr.is_(None), expr == ""))
    if op == "gt":
        return query.filter(cast(expr, String) > str(value))
    if op == "gte":
        return query.filter(cast(expr, String) >= str(value))
    if op == "lt":
        return query.filter(cast(expr, String) < str(value))
    if op == "lte":
        return query.filter(cast(expr, String) <= str(value))
    raise HTTPException(status_code=400, detail=f"不支持的操作符: {op}")


def apply_view_filters(
    query: Query,
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    filters: dict | None,
) -> Query:
    if not filters:
        return query
    conditions = filters.get("conditions") or []
    if not conditions:
        return query

    model = _model_for_entity(entity_type)
    field_map = _field_storage_map(db, tenant_id, entity_type)

    for cond in conditions:
        key = cond.get("field_key")
        if not key:
            continue
        field_def = field_map.get(key)
        if not field_def or not field_def.is_active:
            if key.startswith("cf_"):
                raise HTTPException(status_code=400, detail=f"未知筛选字段: {key}")
            if not hasattr(model, key):
                continue
            # schema 未登记但 ORM 有列的系统字段（如 source/status）
            field_def = SimpleNamespace(field_key=key, storage="db")
        query = _apply_condition(query, model, field_def, cond)
    return query


def apply_view_search(query: Query, entity_type: str, search_q: str | None) -> Query:
    if not search_q or not search_q.strip():
        return query
    if entity_type == "lead":
        pattern = f"%{search_q.strip()}%"
        return query.filter(
            or_(
                Lead.company_name.like(pattern),
                Lead.contact_name.like(pattern),
                Lead.mobile.like(pattern),
                Lead.phone.like(pattern),
                Lead.email.like(pattern),
            )
        )
    if entity_type == "customer":
        pattern = f"%{search_q.strip()}%"
        return query.filter(
            or_(
                Customer.company_name.like(pattern),
                Customer.mobile.like(pattern),
                Customer.phone.like(pattern),
                Customer.email.like(pattern),
            )
        )
    if entity_type == "deal":
        pattern = f"%{search_q.strip()}%"
        return query.filter(Deal.title.like(pattern))
    if entity_type == "quote":
        pattern = f"%{search_q.strip()}%"
        return query.filter(or_(Quote.subject.like(pattern), Quote.quote_number.like(pattern)))
    if entity_type == "contract":
        pattern = f"%{search_q.strip()}%"
        return query.filter(or_(Contract.title.like(pattern), Contract.contract_number.like(pattern)))
    if entity_type == "order":
        pattern = f"%{search_q.strip()}%"
        return query.filter(or_(Order.title.like(pattern), Order.order_number.like(pattern)))
    if entity_type == "payment":
        pattern = f"%{search_q.strip()}%"
        return query.filter(Payment.payment_number.like(pattern))
    return query


def apply_view_sort(query: Query, entity_type: str, sort: list | None):
    if not sort:
        if entity_type == "lead":
            return query.order_by(Lead.updated_at.desc())
        if entity_type == "customer":
            return query.order_by(Customer.updated_at.desc())
        if entity_type == "deal":
            return query.order_by(Deal.updated_at.desc())
        if entity_type == "quote":
            return query.order_by(Quote.updated_at.desc())
        if entity_type == "contract":
            return query.order_by(Contract.updated_at.desc())
        if entity_type == "order":
            return query.order_by(Order.updated_at.desc())
        if entity_type == "payment":
            return query.order_by(Payment.updated_at.desc())
        return query
    model = _model_for_entity(entity_type)
    order_clauses = []
    for item in sort:
        key = item.get("field_key")
        direction = (item.get("dir") or "desc").lower()
        if not key or not hasattr(model, key):
            continue
        col = getattr(model, key)
        order_clauses.append(col.desc() if direction == "desc" else col.asc())
    if order_clauses:
        return query.order_by(*order_clauses)
    if entity_type == "lead":
        return query.order_by(Lead.updated_at.desc())
    if entity_type == "customer":
        return query.order_by(Customer.updated_at.desc())
    if entity_type == "deal":
        return query.order_by(Deal.updated_at.desc())
    if entity_type == "quote":
        return query.order_by(Quote.updated_at.desc())
    if entity_type == "contract":
        return query.order_by(Contract.updated_at.desc())
    if entity_type == "order":
        return query.order_by(Order.updated_at.desc())
    if entity_type == "payment":
        return query.order_by(Payment.updated_at.desc())
    return query


def list_visible_views(
    db: Session, ctx: TenantContext, entity_type: str | None = None
) -> list[EntityListView]:
    q = db.query(EntityListView).filter(EntityListView.tenant_id == ctx.tenant_id)
    if entity_type:
        validate_view_entity_type(entity_type)
        q = q.filter(EntityListView.entity_type == entity_type)
    q = q.filter(
        or_(
            EntityListView.owner_user_id == ctx.user.id,
            EntityListView.is_public.is_(True),
        )
    )
    return q.order_by(EntityListView.is_pinned.desc(), EntityListView.name).all()


def get_view(db: Session, tenant_id: UUID, view_id: UUID) -> EntityListView | None:
    return (
        db.query(EntityListView)
        .filter(EntityListView.id == view_id, EntityListView.tenant_id == tenant_id)
        .first()
    )


def assert_can_access_view(ctx: TenantContext, view: EntityListView) -> None:
    if view.owner_user_id == ctx.user.id or view.is_public:
        return
    raise HTTPException(status_code=403, detail="无权访问该视图")


def assert_can_edit_view(ctx: TenantContext, view: EntityListView) -> None:
    if view.owner_user_id == ctx.user.id or _is_admin(ctx):
        return
    raise HTTPException(status_code=403, detail="无权修改该视图")


def _clear_default_views(
    db: Session, tenant_id: UUID, user_id: UUID, entity_type: str, exclude_id: UUID | None = None
) -> None:
    q = db.query(EntityListView).filter(
        EntityListView.tenant_id == tenant_id,
        EntityListView.owner_user_id == user_id,
        EntityListView.entity_type == entity_type,
        EntityListView.is_default.is_(True),
    )
    if exclude_id:
        q = q.filter(EntityListView.id != exclude_id)
    q.update({EntityListView.is_default: False}, synchronize_session=False)


def create_view(db: Session, ctx: TenantContext, data) -> EntityListView:
    validate_view_entity_type(data.entity_type)
    if data.is_public and not _can_manage_public(ctx):
        raise HTTPException(status_code=403, detail="无权创建公开视图")

    if data.is_default:
        _clear_default_views(db, ctx.tenant_id, ctx.user.id, data.entity_type)

    view = EntityListView(
        tenant_id=ctx.tenant_id,
        entity_type=data.entity_type,
        name=data.name.strip(),
        owner_user_id=ctx.user.id,
        is_public=data.is_public,
        is_pinned=data.is_pinned,
        is_default=data.is_default,
        filters=data.filters.model_dump() if hasattr(data.filters, "model_dump") else data.filters,
        sort=[s.model_dump() if hasattr(s, "model_dump") else s for s in data.sort],
        columns=[
            normalize_list_column(
                data.entity_type,
                c.get("field_key") if isinstance(c, dict) else c.field_key,
                visible=c.get("visible", True) if isinstance(c, dict) else c.visible,
                width=c.get("width") if isinstance(c, dict) else c.width,
                order=c.get("order", i) if isinstance(c, dict) else c.order,
            )
            for i, c in enumerate(
                [c.model_dump() if hasattr(c, "model_dump") else c for c in data.columns]
            )
        ],
        search_q=data.search_q,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


def update_view(db: Session, ctx: TenantContext, view: EntityListView, data) -> EntityListView:
    assert_can_edit_view(ctx, view)
    if data.is_public is True and not _can_manage_public(ctx):
        raise HTTPException(status_code=403, detail="无权设为公开视图")

    if data.name is not None:
        view.name = data.name.strip()
    if data.is_public is not None:
        view.is_public = data.is_public
    if data.is_pinned is not None:
        view.is_pinned = data.is_pinned
    if data.is_default is not None:
        if data.is_default:
            _clear_default_views(db, ctx.tenant_id, view.owner_user_id, view.entity_type, view.id)
        view.is_default = data.is_default
    if data.filters is not None:
        view.filters = data.filters.model_dump()
    if data.sort is not None:
        view.sort = [s.model_dump() for s in data.sort]
    if data.columns is not None:
        view.columns = [
            normalize_list_column(
                view.entity_type,
                c.field_key,
                visible=c.visible,
                width=c.width,
                order=c.order,
            )
            for c in data.columns
        ]
    if data.search_q is not None:
        view.search_q = data.search_q
    view.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(view)
    return view


def delete_view(db: Session, ctx: TenantContext, view: EntityListView) -> None:
    assert_can_edit_view(ctx, view)
    db.delete(view)
    db.commit()


def resolve_view_list_columns(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    entity_type: str,
    view: EntityListView | None,
) -> list[dict]:
    if view and view.columns:
        fields = list_active_fields(db, tenant_id, entity_type)
        field_map = {f.field_key: f for f in fields}
        cols: list[dict] = []
        for i, col in enumerate(view.columns):
            key = col.get("field_key")
            f = field_map.get(key)
            if not f:
                continue
            cols.append(
                list_column_out(
                    entity_type,
                    f,
                    visible=col.get("visible", True),
                    width=col.get("width") or f.list_width,
                    order=col.get("order", i),
                )
            )
        if cols:
            return sorted(cols, key=lambda c: c["order"])
    return resolve_list_columns(db, tenant_id, user_id, entity_type)
