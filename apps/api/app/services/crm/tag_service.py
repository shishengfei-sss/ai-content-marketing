"""标签与实体标签。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Customer, EntityTag, Tag


def list_tags(db: Session, tenant_id: UUID) -> list[Tag]:
    return db.query(Tag).filter(Tag.tenant_id == tenant_id).order_by(Tag.name.asc()).all()


def get_or_create_tag(
    db: Session,
    ctx: TenantContext,
    name: str,
    *,
    color: str | None = None,
    category: str | None = None,
    commit: bool = True,
) -> Tag:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名不能为空")
    tag = (
        db.query(Tag)
        .filter(Tag.tenant_id == ctx.tenant_id, Tag.name == name)
        .first()
    )
    if tag:
        if color is not None:
            tag.color = color
        if category is not None:
            tag.category = category
        if commit:
            db.commit()
            db.refresh(tag)
        return tag
    tag = Tag(tenant_id=ctx.tenant_id, name=name, color=color, category=category)
    db.add(tag)
    if commit:
        db.commit()
        db.refresh(tag)
    else:
        db.flush()
    return tag


def create_tag(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    color: str | None = None,
    category: str | None = None,
) -> Tag:
    exists = db.query(Tag).filter(Tag.tenant_id == ctx.tenant_id, Tag.name == name.strip()).first()
    if exists:
        raise HTTPException(status_code=409, detail="标签已存在")
    return get_or_create_tag(db, ctx, name, color=color, category=category)


def update_tag(
    db: Session,
    ctx: TenantContext,
    tag_id: UUID,
    *,
    name: str | None = None,
    color: str | None = None,
    category: str | None = None,
) -> Tag:
    tag = db.query(Tag).filter(uuid_eq(Tag.id, tag_id), Tag.tenant_id == ctx.tenant_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="标签名不能为空")
        dup = (
            db.query(Tag)
            .filter(Tag.tenant_id == ctx.tenant_id, Tag.name == new_name, Tag.id != tag.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="标签已存在")
        tag.name = new_name
    if color is not None:
        tag.color = color or None
    if category is not None:
        tag.category = category or None
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, ctx: TenantContext, tag_id: UUID) -> None:
    tag = db.query(Tag).filter(uuid_eq(Tag.id, tag_id), Tag.tenant_id == ctx.tenant_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    db.delete(tag)
    db.commit()


def list_entity_tags(
    db: Session, tenant_id: UUID, entity_type: str, entity_id: UUID
) -> list[tuple[EntityTag, Tag]]:
    rows = (
        db.query(EntityTag, Tag)
        .join(Tag, Tag.id == EntityTag.tag_id)
        .filter(
            EntityTag.tenant_id == tenant_id,
            EntityTag.entity_type == entity_type,
            uuid_eq(EntityTag.entity_id, entity_id),
        )
        .order_by(Tag.name.asc())
        .all()
    )
    return rows


def entity_tag_names(db: Session, tenant_id: UUID, entity_type: str, entity_id: UUID) -> list[str]:
    return [t.name for _, t in list_entity_tags(db, tenant_id, entity_type, entity_id)]


def bind_tag(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: UUID,
    tag_id: UUID | None = None,
    tag_name: str | None = None,
) -> EntityTag:
    # 标签字典在设置中维护；实体侧仅允许绑定已有 tag_id
    if tag_id is None:
        raise HTTPException(status_code=400, detail="请选择已有标签（标签请在设置 → 业务标签中维护）")
    tag = db.query(Tag).filter(uuid_eq(Tag.id, tag_id), Tag.tenant_id == ctx.tenant_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    existing = (
        db.query(EntityTag)
        .filter(
            EntityTag.tenant_id == ctx.tenant_id,
            EntityTag.entity_type == entity_type,
            uuid_eq(EntityTag.entity_id, entity_id),
            uuid_eq(EntityTag.tag_id, tag_id),
        )
        .first()
    )
    if existing:
        return existing
    row = EntityTag(
        tenant_id=ctx.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        tag_id=tag_id,
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    # 客户双写 JSON 列表以兼容旧前端
    if entity_type == "customer":
        cust = (
            db.query(Customer)
            .filter(uuid_eq(Customer.id, entity_id), Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if cust is not None:
            names = list(cust.tags or []) if isinstance(cust.tags, list) else []
            if tag.name not in names:
                names.append(tag.name)
                cust.tags = names
    db.commit()
    db.refresh(row)
    return row


def unbind_tag(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: UUID,
    tag_id: UUID,
) -> None:
    row = (
        db.query(EntityTag)
        .filter(
            EntityTag.tenant_id == ctx.tenant_id,
            EntityTag.entity_type == entity_type,
            uuid_eq(EntityTag.entity_id, entity_id),
            uuid_eq(EntityTag.tag_id, tag_id),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="实体标签不存在")
    tag = db.query(Tag).filter(uuid_eq(Tag.id, tag_id)).first()
    db.delete(row)
    if entity_type == "customer" and tag:
        cust = (
            db.query(Customer)
            .filter(uuid_eq(Customer.id, entity_id), Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if cust is not None and isinstance(cust.tags, list):
            cust.tags = [n for n in cust.tags if n != tag.name]
    db.commit()


def sync_customer_tag_names(
    db: Session, ctx: TenantContext, customer: Customer, names: list[str], *, commit: bool = True
) -> None:
    """按名称列表同步客户 entity_tags（创建时增补；缺失标签会写入字典）。"""
    for name in names:
        n = str(name).strip()
        if not n:
            continue
        tag = get_or_create_tag(db, ctx, n, commit=False)
        bind_tag(db, ctx, entity_type="customer", entity_id=customer.id, tag_id=tag.id)
    if not names and commit:
        db.commit()


def resolve_customer_tags(db: Session, customer: Customer) -> list[str]:
    names = entity_tag_names(db, customer.tenant_id, "customer", customer.id)
    if names:
        return names
    if isinstance(customer.tags, list):
        return [str(x) for x in customer.tags]
    return []
