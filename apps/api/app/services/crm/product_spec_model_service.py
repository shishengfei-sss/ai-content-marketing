"""产品规格型号基础数据服务（v1.4）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Product, ProductSpecModel
from app.schemas.crm_deals import ProductSpecModelCreate, ProductSpecModelUpdate


def list_spec_models(
    db: Session, tenant_id: UUID, *, active_only: bool = False
) -> list[ProductSpecModel]:
    q = db.query(ProductSpecModel).filter(ProductSpecModel.tenant_id == tenant_id)
    if active_only:
        q = q.filter(ProductSpecModel.is_active.is_(True))
    return q.order_by(ProductSpecModel.sort_order.asc(), ProductSpecModel.name.asc()).all()


def get_spec_model(db: Session, tenant_id: UUID, spec_id: UUID) -> ProductSpecModel | None:
    return (
        db.query(ProductSpecModel)
        .filter(uuid_eq(ProductSpecModel.id, spec_id), ProductSpecModel.tenant_id == tenant_id)
        .first()
    )


def _check_name_unique(
    db: Session, tenant_id: UUID, name: str, exclude_id: UUID | None = None
) -> None:
    q = db.query(ProductSpecModel).filter(
        ProductSpecModel.tenant_id == tenant_id, ProductSpecModel.name == name
    )
    if exclude_id is not None:
        q = q.filter(ProductSpecModel.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="规格型号名称已存在")


def _check_code_unique(
    db: Session, tenant_id: UUID, code: str | None, exclude_id: UUID | None = None
) -> None:
    if not code:
        return
    q = db.query(ProductSpecModel).filter(
        ProductSpecModel.tenant_id == tenant_id, ProductSpecModel.code == code
    )
    if exclude_id is not None:
        q = q.filter(ProductSpecModel.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="规格型号编码已存在")


def create_spec_model(
    db: Session, ctx: TenantContext, data: ProductSpecModelCreate
) -> ProductSpecModel:
    name = data.name.strip()
    code = data.code.strip() if data.code else None
    _check_name_unique(db, ctx.tenant_id, name)
    _check_code_unique(db, ctx.tenant_id, code)
    row = ProductSpecModel(
        tenant_id=ctx.tenant_id,
        name=name,
        code=code,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_spec_model(
    db: Session, ctx: TenantContext, row: ProductSpecModel, data: ProductSpecModelUpdate
) -> ProductSpecModel:
    if data.name is not None:
        name = data.name.strip()
        if name != row.name:
            _check_name_unique(db, ctx.tenant_id, name, exclude_id=row.id)
            row.name = name
    if data.code is not None:
        code = data.code.strip() if data.code else None
        if code != row.code:
            _check_code_unique(db, ctx.tenant_id, code, exclude_id=row.id)
            row.code = code
    if data.description is not None:
        row.description = data.description
    if data.sort_order is not None:
        row.sort_order = data.sort_order
    if data.is_active is not None:
        row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return row


def _usage_count(db: Session, row: ProductSpecModel) -> int:
    return (
        db.query(Product)
        .filter(
            Product.tenant_id == row.tenant_id,
            uuid_eq(Product.spec_model_id, row.id),
            Product.deleted_at.is_(None),
        )
        .count()
    )


def delete_spec_model(db: Session, row: ProductSpecModel) -> None:
    if _usage_count(db, row) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="规格型号已被产品引用，无法删除，请改为停用",
        )
    db.delete(row)
    db.commit()


def assert_active_spec_model_id(db: Session, tenant_id: UUID, spec_model_id: UUID | None) -> None:
    if not spec_model_id:
        return
    row = get_spec_model(db, tenant_id, spec_model_id)
    if not row or not row.is_active:
        raise HTTPException(status_code=400, detail="请选择有效的规格型号")


def resolve_spec_model_id_by_name(db: Session, tenant_id: UUID, name: str) -> UUID:
    row = (
        db.query(ProductSpecModel)
        .filter(
            ProductSpecModel.tenant_id == tenant_id,
            ProductSpecModel.name == name.strip(),
            ProductSpecModel.is_active.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail=f"规格型号「{name}」不存在或已停用")
    return row.id
