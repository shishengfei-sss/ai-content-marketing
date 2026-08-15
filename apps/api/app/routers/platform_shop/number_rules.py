"""P08-F / P04-E 平台业务编码规则 API。对照 06#p08f · #p04e。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_platform_admin
from app.models import User
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import platform_number_service

router = APIRouter(prefix="/number-rules", tags=["platform-shop-number-rules"])


class PlatformNumberRuleUpdate(BaseModel):
    prefix: str | None = None
    suffix: str | None = None
    date_format: str | None = None
    seq_width: int | None = Field(default=None, ge=1, le=8)
    reset_period: str | None = None
    inherit_parent_code: bool | None = None
    separator: str | None = None
    enabled: bool | None = None


class PlatformNumberPreviewRequest(BaseModel):
    parent_id: UUID | None = None
    prefix: str | None = None
    date_format: str | None = None
    seq_width: int | None = Field(default=None, ge=1, le=8)
    reset_period: str | None = None
    suffix: str | None = None


@router.get("")
def list_number_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    """P08-F：全部实体规则。fee.manage 可读（P04 预览）。"""
    return {"items": platform_number_service.list_rules(db)}


@router.post("/reset-defaults")
def reset_defaults(
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    from app.services.platform_shop_service import assert_can_manage_shop_accounts

    assert_can_manage_shop_accounts(user)
    items = platform_number_service.reset_all_defaults(db, user)
    return {"items": items}


@router.get("/{entity_type}")
def get_number_rule(
    entity_type: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    rule = platform_number_service.get_rule(db, entity_type)
    return platform_number_service.rule_to_dict(rule)


@router.put("/{entity_type}")
def put_number_rule(
    entity_type: str,
    body: PlatformNumberRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    """保存规则。Phase1：须平台超管（对齐 PRD platform.user.manage）。"""
    from app.services.platform_shop_service import assert_can_manage_shop_accounts

    assert_can_manage_shop_accounts(user)
    return platform_number_service.update_rule(
        db,
        user,
        entity_type,
        prefix=body.prefix,
        suffix=body.suffix,
        date_format=body.date_format,
        seq_width=body.seq_width,
        reset_period=body.reset_period,
        inherit_parent_code=body.inherit_parent_code,
        separator=body.separator,
        enabled=body.enabled,
    )


@router.post("/{entity_type}/preview")
def preview_number_rule(
    entity_type: str,
    body: PlatformNumberPreviewRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    parent_id = body.parent_id if body else None
    return platform_number_service.preview_number(
        db,
        entity_type,
        parent_id=parent_id,
        prefix=body.prefix if body else None,
        date_format=body.date_format if body else None,
        seq_width=body.seq_width if body else None,
        reset_period=body.reset_period if body else None,
        suffix=body.suffix if body else None,
    )
