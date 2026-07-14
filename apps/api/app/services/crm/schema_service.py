"""CRM 字段 Schema 与用户列偏好服务。"""
from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.crm import (
    ENTITY_TYPES,
    PROTECTED_FIELD_KEYS,
    EntityFieldDefinition,
    UserEntityViewPreference,
    is_list_locked_field,
)
from app.services.crm.schema_seeds import ENTITY_SEED_MAP

FIELD_TYPES = frozenset(
    {
        "text",
        "textarea",
        "number",
        "currency",
        "date",
        "datetime",
        "select",
        "multiselect",
        "phone",
        "email",
        "url",
        "checkbox",
        "user_ref",
        "territory_ref",
        "ref",
    }
)

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def serialize_field_definition(row: EntityFieldDefinition):
    from app.schemas.crm_schema import FieldDefinitionOut

    base = FieldDefinitionOut.model_validate(row)
    return base.model_copy(update={"list_locked": is_list_locked_field(row.entity_type, row.field_key)})


def normalize_list_column(
    entity_type: str,
    field_key: str,
    *,
    visible: bool,
    width: int | None,
    order: int,
) -> dict:
    locked = is_list_locked_field(entity_type, field_key)
    return {
        "field_key": field_key,
        "visible": True if locked else visible,
        "width": width,
        "order": order,
    }


def list_column_out(
    entity_type: str,
    field: EntityFieldDefinition,
    *,
    visible: bool,
    width: int | None,
    order: int,
) -> dict:
    locked = is_list_locked_field(entity_type, field.field_key)
    return {
        "field_key": field.field_key,
        "label": field.label,
        "field_type": field.field_type,
        "visible": True if locked else visible,
        "width": width,
        "order": order,
        "list_locked": locked,
    }


def validate_entity_type(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的 entity_type: {entity_type}")


def _normalize_seed(raw: dict) -> dict:
    return {
        "field_key": raw["field_key"],
        "label": raw["label"],
        "field_type": raw["field_type"],
        "is_system": raw.get("is_system", True),
        "is_required": raw.get("is_required", False),
        "is_unique": raw.get("is_unique", False),
        "options": raw.get("options", []),
        "default_value": raw.get("default_value"),
        "placeholder": raw.get("placeholder"),
        "sort_order": raw.get("sort_order", 0),
        "show_in_list_default": raw.get("show_in_list_default", False),
        "list_width": raw.get("list_width"),
        "is_active": True,
        "validation": raw.get("validation", {}),
        "storage": raw.get("storage", "seed"),
    }


def _sync_seed_field_metadata(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    fields: list[EntityFieldDefinition],
) -> None:
    """存量租户：同步系统种子字段的 label / sort_order / is_required 等元数据。"""
    seeds = {_normalize_seed(raw)["field_key"]: _normalize_seed(raw) for raw in ENTITY_SEED_MAP.get(entity_type, [])}
    changed = False
    sync_keys = ("label", "sort_order", "is_required", "field_type", "options", "placeholder", "show_in_list_default")
    for row in fields:
        if row.field_key not in seeds:
            continue
        seed = seeds[row.field_key]
        for key in sync_keys:
            new_val = seed.get(key)
            if getattr(row, key) != new_val:
                setattr(row, key, new_val)
                changed = True
    if changed:
        db.commit()


def ensure_entity_schema(db: Session, tenant_id: UUID, entity_type: str) -> list[EntityFieldDefinition]:
    validate_entity_type(entity_type)
    existing = (
        db.query(EntityFieldDefinition)
        .filter(
            EntityFieldDefinition.tenant_id == tenant_id,
            EntityFieldDefinition.entity_type == entity_type,
        )
        .count()
    )
    if existing:
        fields = list_active_fields(db, tenant_id, entity_type, include_inactive=True)
        _sync_seed_field_metadata(db, tenant_id, entity_type, fields)
        # 补种种子中存在但租户尚未拥有的字段（如 v0.8 新增编号字段）
        existing_keys = {f.field_key for f in fields}
        seeds = ENTITY_SEED_MAP.get(entity_type, [])
        for raw in seeds:
            data = _normalize_seed(raw)
            if data["field_key"] in existing_keys:
                continue
            row = EntityFieldDefinition(tenant_id=tenant_id, entity_type=entity_type, **data)
            db.add(row)
            fields.append(row)
        db.commit()
        for f in fields:
            db.refresh(f)
        return fields

    seeds = ENTITY_SEED_MAP.get(entity_type, [])
    created: list[EntityFieldDefinition] = []
    for raw in seeds:
        data = _normalize_seed(raw)
        row = EntityFieldDefinition(tenant_id=tenant_id, entity_type=entity_type, **data)
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


def list_active_fields(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    *,
    include_inactive: bool = False,
) -> list[EntityFieldDefinition]:
    validate_entity_type(entity_type)
    q = db.query(EntityFieldDefinition).filter(
        EntityFieldDefinition.tenant_id == tenant_id,
        EntityFieldDefinition.entity_type == entity_type,
    )
    if not include_inactive:
        q = q.filter(EntityFieldDefinition.is_active.is_(True))
    return q.order_by(EntityFieldDefinition.sort_order, EntityFieldDefinition.field_key).all()


def get_field(
    db: Session, tenant_id: UUID, entity_type: str, field_key: str
) -> EntityFieldDefinition | None:
    return (
        db.query(EntityFieldDefinition)
        .filter(
            EntityFieldDefinition.tenant_id == tenant_id,
            EntityFieldDefinition.entity_type == entity_type,
            EntityFieldDefinition.field_key == field_key,
        )
        .first()
    )


def create_custom_field(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    *,
    field_key: str,
    label: str,
    field_type: str,
    is_required: bool = False,
    options: list | None = None,
    show_in_list_default: bool = False,
    sort_order: int = 500,
    placeholder: str | None = None,
) -> EntityFieldDefinition:
    validate_entity_type(entity_type)
    ensure_entity_schema(db, tenant_id, entity_type)

    if not field_key.startswith("cf_"):
        raise HTTPException(status_code=400, detail="自定义字段 field_key 必须以 cf_ 开头")
    if field_type not in FIELD_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的 field_type: {field_type}")
    if get_field(db, tenant_id, entity_type, field_key):
        raise HTTPException(status_code=409, detail="字段已存在")

    row = EntityFieldDefinition(
        tenant_id=tenant_id,
        entity_type=entity_type,
        field_key=field_key,
        label=label,
        field_type=field_type,
        is_system=False,
        is_required=is_required,
        options=options or [],
        show_in_list_default=show_in_list_default,
        sort_order=sort_order,
        storage="extra",
        is_active=True,
        placeholder=placeholder,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_field_definition(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    field_key: str,
    *,
    label: str | None = None,
    is_required: bool | None = None,
    options: list | None = None,
    show_in_list_default: bool | None = None,
    sort_order: int | None = None,
    placeholder: str | None = None,
    list_width: int | None = None,
) -> EntityFieldDefinition:
    row = get_field(db, tenant_id, entity_type, field_key)
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="字段不存在")
    if label is not None:
        row.label = label
    if is_required is not None:
        row.is_required = is_required
    if options is not None:
        row.options = options
    if show_in_list_default is not None:
        row.show_in_list_default = show_in_list_default
    if sort_order is not None:
        row.sort_order = sort_order
    if placeholder is not None:
        row.placeholder = placeholder
    if list_width is not None:
        row.list_width = list_width
    db.commit()
    db.refresh(row)
    return row


def soft_delete_field(db: Session, tenant_id: UUID, entity_type: str, field_key: str) -> None:
    row = get_field(db, tenant_id, entity_type, field_key)
    if not row:
        raise HTTPException(status_code=404, detail="字段不存在")
    if row.is_system or field_key in PROTECTED_FIELD_KEYS:
        raise HTTPException(status_code=403, detail="系统字段不可删除")
    row.is_active = False
    db.commit()


def _validate_field_value(field: EntityFieldDefinition, value) -> None:
    if value is None or value == "":
        return
    ft = field.field_type
    if ft == "phone" and isinstance(value, str) and not _PHONE_RE.match(value.strip()):
        raise HTTPException(status_code=422, detail=f"字段 {field.label} 手机格式无效")
    if ft == "email" and isinstance(value, str) and not _EMAIL_RE.match(value.strip()):
        raise HTTPException(status_code=422, detail=f"字段 {field.label} 邮箱格式无效")
    if ft == "select" and field.options and value not in field.options:
        raise HTTPException(status_code=422, detail=f"字段 {field.label} 选项无效")
    if ft == "multiselect":
        if not isinstance(value, list):
            raise HTTPException(status_code=422, detail=f"字段 {field.label} 须为数组")
        if field.options:
            invalid = [v for v in value if v not in field.options]
            if invalid:
                raise HTTPException(status_code=422, detail=f"字段 {field.label} 选项无效")


def validate_extra_data(
    db: Session,
    tenant_id: UUID,
    entity_type: str,
    extra_data: dict | None,
    *,
    is_create: bool = False,
) -> dict:
    ensure_entity_schema(db, tenant_id, entity_type)
    data = dict(extra_data or {})
    fields = list_active_fields(db, tenant_id, entity_type)
    field_map = {f.field_key: f for f in fields if f.storage in ("seed", "extra")}

    for key in data:
        if key not in field_map:
            if key.startswith("cf_"):
                raise HTTPException(status_code=422, detail=f"未知自定义字段: {key}")
            continue
        _validate_field_value(field_map[key], data[key])

    for field in fields:
        if field.storage not in ("seed", "extra"):
            continue
        if field.is_required and is_create and field.field_key not in data:
            if field.default_value is None:
                raise HTTPException(status_code=422, detail=f"字段 {field.label} 为必填")
    return data


def resolve_list_columns(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    entity_type: str,
) -> list[dict]:
    ensure_entity_schema(db, tenant_id, entity_type)
    fields = list_active_fields(db, tenant_id, entity_type)
    field_map = {f.field_key: f for f in fields}

    pref = (
        db.query(UserEntityViewPreference)
        .filter(
            UserEntityViewPreference.tenant_id == tenant_id,
            UserEntityViewPreference.user_id == user_id,
            UserEntityViewPreference.entity_type == entity_type,
            UserEntityViewPreference.view_kind == "list",
        )
        .first()
    )

    if pref and pref.columns:
        cols: list[dict] = []
        for i, col in enumerate(pref.columns):
            key = col.get("field_key")
            if not key or key not in field_map:
                continue
            f = field_map[key]
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

    defaults = [f for f in fields if f.show_in_list_default]
    return [
        list_column_out(
            entity_type,
            f,
            visible=True,
            width=f.list_width,
            order=f.sort_order,
        )
        for f in sorted(defaults, key=lambda x: x.sort_order)
    ]


def get_view_preference(
    db: Session, tenant_id: UUID, user_id: UUID, entity_type: str
) -> UserEntityViewPreference | None:
    validate_entity_type(entity_type)
    return (
        db.query(UserEntityViewPreference)
        .filter(
            UserEntityViewPreference.tenant_id == tenant_id,
            UserEntityViewPreference.user_id == user_id,
            UserEntityViewPreference.entity_type == entity_type,
            UserEntityViewPreference.view_kind == "list",
        )
        .first()
    )


def save_view_preference(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    entity_type: str,
    columns: list[dict],
) -> UserEntityViewPreference:
    validate_entity_type(entity_type)
    ensure_entity_schema(db, tenant_id, entity_type)
    fields = list_active_fields(db, tenant_id, entity_type)
    allowed = {f.field_key for f in fields}

    normalized: list[dict] = []
    for i, col in enumerate(columns):
        key = col.get("field_key")
        if not key or key not in allowed:
            raise HTTPException(status_code=400, detail=f"列 {key} 不在 Schema 中")
        normalized.append(
            {
                "field_key": key,
                "visible": True
                if is_list_locked_field(entity_type, key)
                else bool(col.get("visible", True)),
                "width": col.get("width"),
                "order": col.get("order", i),
            }
        )

    pref = get_view_preference(db, tenant_id, user_id, entity_type)
    if pref:
        pref.columns = normalized
        pref.updated_at = datetime.now().astimezone()
    else:
        pref = UserEntityViewPreference(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            view_kind="list",
            columns=normalized,
        )
        db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref
