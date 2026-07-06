"""企业信息与信用代码。"""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import Tenant

CREDIT_CODE_PATTERN = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$")
TENANT_NAME_TAKEN_DETAIL = "该公司名称已被使用，请联系管理员邀请加入"


def normalize_tenant_name(name: str) -> str:
    return name.strip()


def assert_tenant_name_available(
    db: Session,
    name: str,
    *,
    exclude_tenant_id=None,
) -> str:
    normalized = normalize_tenant_name(name)
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="公司名称至少 2 个字符")
    query = db.query(Tenant).filter(Tenant.name == normalized)
    if exclude_tenant_id is not None:
        query = query.filter(Tenant.id != exclude_tenant_id)
    if query.first():
        raise HTTPException(status_code=400, detail=TENANT_NAME_TAKEN_DETAIL)
    return normalized


def validate_credit_code(value: str | None) -> None:
    if value is None or value == "":
        return
    if len(value) != 18 or not CREDIT_CODE_PATTERN.match(value.upper()):
        raise HTTPException(status_code=422, detail="统一社会信用代码格式不正确")


def get_tenant_profile(db: Session, tenant_id) -> Tenant:
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="公司不存在")
    return tenant


def update_tenant_profile(
    db: Session,
    tenant_id,
    *,
    name: str | None = None,
    industry_code: str | None = None,
    credit_code: str | None = None,
) -> Tenant:
    tenant = get_tenant_profile(db, tenant_id)
    if credit_code is not None:
        validate_credit_code(credit_code)
        tenant.credit_code = credit_code.upper() if credit_code else None
    if name is not None:
        tenant.name = assert_tenant_name_available(
            db, name, exclude_tenant_id=tenant.id
        )
    if industry_code is not None:
        tenant.industry_code = industry_code
    db.commit()
    db.refresh(tenant)
    return tenant
