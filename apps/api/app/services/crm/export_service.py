"""线索/客户导出（可见范围 + 列表查询条件 + 与列表一致的可见列）。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Query, Session

from app.dependencies import TenantContext
from app.models import User
from app.models.crm import Customer, Lead, Order, Contract
from app.services.crm.crm_scope_service import (
    apply_customer_list_scope,
    apply_lead_list_scope,
    apply_order_list_scope,
    apply_contract_list_scope,
)
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)

EXPORT_ROW_LIMIT = 5000
_BEIJING = timezone(timedelta(hours=8))


def _build_lead_query(
    db: Session,
    ctx: TenantContext,
    *,
    view_id: UUID | None = None,
    q: str | None = None,
    status: str | None = None,
    source: str | None = None,
    owner_id: UUID | None = None,
    campaign_id: UUID | None = None,
    filters: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> Query:
    query = db.query(Lead).filter(Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None))
    query = apply_lead_list_scope(query, ctx, db)

    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)
        query = apply_view_filters(query, db, ctx.tenant_id, "lead", active_view.filters)
        query = apply_view_search(query, "lead", active_view.search_q)
        query = apply_view_sort(query, "lead", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "lead", parsed_filters)
        if status:
            query = query.filter(Lead.status == status)
        if source:
            query = query.filter(Lead.source == source)
        query = apply_view_search(query, "lead", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "lead", sort_spec)

    if owner_id is not None:
        query = query.filter(Lead.owner_user_id == owner_id)
    if campaign_id is not None:
        query = query.filter(Lead.campaign_id == campaign_id)
    return query


def _build_customer_query(
    db: Session,
    ctx: TenantContext,
    *,
    view_id: UUID | None = None,
    q: str | None = None,
    status: str | None = None,
    owner_id: UUID | None = None,
    filters: str | None = None,
) -> Query:
    query = db.query(Customer).filter(Customer.tenant_id == ctx.tenant_id, Customer.deleted_at.is_(None))
    query = apply_customer_list_scope(query, ctx, db)

    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)
        query = apply_view_filters(query, db, ctx.tenant_id, "customer", active_view.filters)
        query = apply_view_search(query, "customer", active_view.search_q)
        query = apply_view_sort(query, "customer", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "customer", parsed_filters)
        if status:
            query = query.filter(Customer.status == status)
        query = apply_view_search(query, "customer", q)
        query = apply_view_sort(query, "customer", None)

    if owner_id is not None:
        query = query.filter(Customer.owner_user_id == owner_id)
    return query


def _build_order_query(
    db: Session,
    ctx: TenantContext,
    *,
    view_id: UUID | None = None,
    q: str | None = None,
    status: str | None = None,
    customer_id: UUID | None = None,
    deal_id: UUID | None = None,
    contract_id: UUID | None = None,
    filters: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> Query:
    query = db.query(Order).filter(Order.tenant_id == ctx.tenant_id, Order.deleted_at.is_(None))
    query = apply_order_list_scope(query, ctx, db)

    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)
        query = apply_view_filters(query, db, ctx.tenant_id, "order", active_view.filters)
        query = apply_view_search(query, "order", active_view.search_q)
        query = apply_view_sort(query, "order", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "order", parsed_filters)
        elif status:
            query = query.filter(Order.status == status)
        query = apply_view_search(query, "order", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "order", sort_spec)

    if customer_id is not None:
        query = query.filter(Order.customer_id == customer_id)
    if deal_id is not None:
        query = query.filter(Order.deal_id == deal_id)
    if contract_id is not None:
        query = query.filter(Order.contract_id == contract_id)
    return query


def _build_contract_query(
    db: Session,
    ctx: TenantContext,
    *,
    view_id: UUID | None = None,
    q: str | None = None,
    status: str | None = None,
    customer_id: UUID | None = None,
    deal_id: UUID | None = None,
    filters: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> Query:
    query = db.query(Contract).filter(Contract.tenant_id == ctx.tenant_id, Contract.deleted_at.is_(None))
    query = apply_contract_list_scope(query, ctx, db)

    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)
        query = apply_view_filters(query, db, ctx.tenant_id, "contract", active_view.filters)
        query = apply_view_search(query, "contract", active_view.search_q)
        query = apply_view_sort(query, "contract", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "contract", parsed_filters)
        elif status:
            query = query.filter(Contract.status == status)
        query = apply_view_search(query, "contract", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "contract", sort_spec)

    if customer_id is not None:
        query = query.filter(Contract.customer_id == customer_id)
    if deal_id is not None:
        query = query.filter(Contract.deal_id == deal_id)
    return query


def _visible_export_columns(
    db: Session,
    ctx: TenantContext,
    entity_type: str,
    view_id: UUID | None,
) -> list[dict]:
    view = None
    if view_id is not None:
        view = get_view(db, ctx.tenant_id, view_id)
        if not view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, view)
    cols = resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, entity_type, view)
    return [c for c in cols if c.get("visible", True)]


def _model_has_column(entity, field_key: str) -> bool:
    try:
        return field_key in sa_inspect(type(entity)).columns.keys()
    except Exception:
        return False


def _raw_field_value(entity, field_key: str):
    if _model_has_column(entity, field_key):
        return getattr(entity, field_key, None)
    extra = getattr(entity, "extra_data", None) or {}
    if isinstance(extra, dict):
        return extra.get(field_key)
    return None


def _format_datetime(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    try:
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


def _format_cell(value, field_type: str | None, *, user_names: dict[str, str]) -> str:
    if value is None or value == "":
        return ""
    if field_type in ("datetime", "date"):
        return _format_datetime(value)
    if field_type in ("user_ref",) or field_type == "user_ref":
        key = str(value)
        return user_names.get(key) or key
    if isinstance(value, bool) or field_type == "checkbox":
        return "是" if value else "否"
    if isinstance(value, (list, tuple)):
        return "、".join(str(v) for v in value if v is not None and v != "")
    return str(value)


def _collect_user_ids(entities, columns: list[dict]) -> set[UUID]:
    ids: set[UUID] = set()
    user_keys = {c["field_key"] for c in columns if c.get("field_type") == "user_ref"}
    if not user_keys:
        return ids
    for entity in entities:
        for key in user_keys:
            raw = _raw_field_value(entity, key)
            if raw is None or raw == "":
                continue
            try:
                ids.add(raw if isinstance(raw, UUID) else UUID(str(raw)))
            except (TypeError, ValueError):
                continue
    return ids


def _load_user_names(db: Session, user_ids: set[UUID]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = db.query(User).filter(User.id.in_(list(user_ids))).all()
    out: dict[str, str] = {}
    for u in rows:
        name = (u.display_name or "").strip() or (u.phone or "").strip() or str(u.id)
        out[str(u.id)] = name
    return out


def _rows_from_entities(
    db: Session,
    entities: list,
    columns: list[dict],
) -> tuple[list[str], list[dict]]:
    headers = [c.get("label") or c["field_key"] for c in columns]
    # 防止重名表头覆盖：同名时追加 field_key
    seen: dict[str, int] = {}
    unique_headers: list[str] = []
    for i, h in enumerate(headers):
        if h not in seen:
            seen[h] = 0
            unique_headers.append(h)
        else:
            seen[h] += 1
            unique_headers.append(f"{h}({columns[i]['field_key']})")

    user_names = _load_user_names(db, _collect_user_ids(entities, columns))
    data: list[dict] = []
    for entity in entities:
        row: dict[str, str] = {}
        for col, header in zip(columns, unique_headers):
            raw = _raw_field_value(entity, col["field_key"])
            row[header] = _format_cell(raw, col.get("field_type"), user_names=user_names)
        data.append(row)
    return unique_headers, data


def _leads_table(db: Session, ctx: TenantContext, **filters) -> tuple[list[str], list[dict]]:
    view_id = filters.get("view_id")
    columns = _visible_export_columns(db, ctx, "lead", view_id)
    if not columns:
        raise HTTPException(status_code=400, detail="当前列表无可见列，请先在列设置中勾选")
    entities = _build_lead_query(db, ctx, **filters).limit(EXPORT_ROW_LIMIT).all()
    return _rows_from_entities(db, entities, columns)


def _customers_table(db: Session, ctx: TenantContext, **filters) -> tuple[list[str], list[dict]]:
    view_id = filters.get("view_id")
    columns = _visible_export_columns(db, ctx, "customer", view_id)
    if not columns:
        raise HTTPException(status_code=400, detail="当前列表无可见列，请先在列设置中勾选")
    entities = _build_customer_query(db, ctx, **filters).limit(EXPORT_ROW_LIMIT).all()
    return _rows_from_entities(db, entities, columns)


def _orders_table(db: Session, ctx: TenantContext, **filters) -> tuple[list[str], list[dict]]:
    view_id = filters.get("view_id")
    columns = _visible_export_columns(db, ctx, "order", view_id)
    if not columns:
        raise HTTPException(status_code=400, detail="当前列表无可见列，请先在列设置中勾选")
    entities = _build_order_query(db, ctx, **filters).limit(EXPORT_ROW_LIMIT).all()
    return _rows_from_entities(db, entities, columns)


def _contracts_table(db: Session, ctx: TenantContext, **filters) -> tuple[list[str], list[dict]]:
    view_id = filters.get("view_id")
    columns = _visible_export_columns(db, ctx, "contract", view_id)
    if not columns:
        raise HTTPException(status_code=400, detail="当前列表无可见列，请先在列设置中勾选")
    entities = _build_contract_query(db, ctx, **filters).limit(EXPORT_ROW_LIMIT).all()
    return _rows_from_entities(db, entities, columns)


def export_csv(db: Session, ctx: TenantContext, entity_type: str, **filters) -> tuple[str, bytes, int]:
    if entity_type == "lead":
        headers, data = _leads_table(db, ctx, **filters)
        filename = "leads.csv"
    elif entity_type == "customer":
        headers, data = _customers_table(db, ctx, **filters)
        filename = "customers.csv"
    elif entity_type == "order":
        headers, data = _orders_table(db, ctx, **filters)
        filename = "orders.csv"
    elif entity_type == "contract":
        headers, data = _contracts_table(db, ctx, **filters)
        filename = "contracts.csv"
    else:
        raise HTTPException(status_code=400, detail="仅支持 lead/customer/order/contract")
    row_count = len(data)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    if data:
        writer.writerows(data)
    return filename, buf.getvalue().encode("utf-8-sig"), row_count


def export_xlsx(db: Session, ctx: TenantContext, entity_type: str, **filters) -> tuple[str, bytes, int]:
    try:
        import openpyxl
    except ImportError as e:
        raise HTTPException(status_code=500, detail="需要 openpyxl") from e
    if entity_type == "lead":
        headers, data = _leads_table(db, ctx, **filters)
        filename = "leads.xlsx"
        sheet_name = "线索"
    elif entity_type == "customer":
        headers, data = _customers_table(db, ctx, **filters)
        filename = "customers.xlsx"
        sheet_name = "客户"
    elif entity_type == "order":
        headers, data = _orders_table(db, ctx, **filters)
        filename = "orders.xlsx"
        sheet_name = "订单"
    elif entity_type == "contract":
        headers, data = _contracts_table(db, ctx, **filters)
        filename = "contracts.xlsx"
        sheet_name = "合同"
    else:
        raise HTTPException(status_code=400, detail="仅支持 lead/customer/order/contract")
    row_count = len(data)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in data:
        ws.append([row.get(h, "") for h in headers])
    out = io.BytesIO()
    wb.save(out)
    return filename, out.getvalue(), row_count
