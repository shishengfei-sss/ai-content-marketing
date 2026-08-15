"""P10 套餐配置 API。对照 PRD：06-平台端UI.html#p10。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import (
    PlanFeatureCreate,
    PlanFeatureDeactivateRequest,
    PlanFeatureOut,
    PlanFeatureUpdate,
    PlanTemplateCreate,
    PlanTemplateListResponse,
    PlanTemplateOut,
    PlanTemplateUpdate,
)
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop import plan_service

router = APIRouter(tags=["platform-shop-plans"])

_plan_read = require_platform_shop_any(
    "platform.shop.plan.manage",
    "platform.shop.subscription.manage",
    "platform.shop.subscription.read",
)


@router.get("/feature-dictionary")
def list_feature_dictionary(
    q: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    tree: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(_plan_read),
):
    return plan_service.list_features(
        db,
        q=q,
        node_type=node_type,
        is_active=is_active,
        parent_id=parent_id,
        tree=tree,
    )


@router.post("/feature-dictionary/preview-code")
def preview_feature_code(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.preview_feature_code(db)


@router.post("/feature-dictionary", response_model=PlanFeatureOut)
def create_feature_dictionary(
    body: PlanFeatureCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.create_feature(db, body, user)


@router.get("/feature-dictionary/{feature_id}", response_model=PlanFeatureOut)
def get_feature_dictionary(
    feature_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(_plan_read),
):
    return plan_service.get_feature(db, feature_id)


@router.patch("/feature-dictionary/{feature_id}", response_model=PlanFeatureOut)
def patch_feature_dictionary(
    feature_id: UUID,
    body: PlanFeatureUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.update_feature(db, feature_id, body, user)


@router.post("/feature-dictionary/{feature_id}/deactivate", response_model=PlanFeatureOut)
def deactivate_feature_dictionary(
    feature_id: UUID,
    body: PlanFeatureDeactivateRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    req = body or PlanFeatureDeactivateRequest()
    return plan_service.deactivate_feature(
        db, feature_id, user, remove_from_templates=req.remove_from_templates
    )


@router.post("/feature-dictionary/{feature_id}/activate", response_model=PlanFeatureOut)
def activate_feature_dictionary(
    feature_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.activate_feature(db, feature_id, user)


@router.get("/plan-templates", response_model=PlanTemplateListResponse)
def list_plan_templates(
    q: str | None = Query(default=None),
    plan_type: str | None = Query(default=None),
    published: bool | None = Query(default=None, description="true=已上架 is_public"),
    is_active: bool | None = Query(default=True),
    stackable: bool | None = Query(default=None),
    replace_group: str | None = Query(default=None),
    upgrade_from: str | None = Query(default=None),
    tenant_id: UUID | None = Query(default=None),
    purchase_mode: str | None = Query(default=None, description="stack | replace"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(_plan_read),
):
    items, total = plan_service.list_plan_templates(
        db,
        q=q,
        plan_type=plan_type,
        published=published,
        is_active=is_active,
        stackable=stackable,
        replace_group=replace_group,
        upgrade_from=upgrade_from,
        tenant_id=tenant_id,
        purchase_mode=purchase_mode,
        page=page,
        page_size=page_size,
    )
    return PlanTemplateListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/plan-templates/preview-code")
def preview_plan_code(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.preview_plan_code(db)


@router.post("/plan-templates", response_model=PlanTemplateOut)
def create_plan_template(
    body: PlanTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.create_plan_template(db, body, user)


@router.get("/plan-templates/{code}", response_model=PlanTemplateOut)
def get_plan_template(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(_plan_read),
):
    return plan_service.get_plan_template(db, code)


@router.patch("/plan-templates/{code}", response_model=PlanTemplateOut)
def patch_plan_template(
    code: str,
    body: PlanTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.update_plan_template(db, code, body, user)


@router.post("/plan-templates/{code}/publish", response_model=PlanTemplateOut)
def publish_plan_template(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.publish_plan_template(db, code, user)


@router.post("/plan-templates/{code}/unpublish", response_model=PlanTemplateOut)
def unpublish_plan_template(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.plan.manage")),
):
    return plan_service.unpublish_plan_template(db, code, user)
