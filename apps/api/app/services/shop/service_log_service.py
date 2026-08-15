"""商家服务记录（P02-B-N / P02-B-R）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import User
from app.models.shop import ShopMerchantAccount, ShopMerchantServiceLog
from app.schemas.shop_platform import (
    MerchantServiceLogItem,
    MerchantServiceLogListResponse,
    RenewalRequestCreate,
    ServiceNoteCreate,
)
from app.services.platform_shop_service import user_has_platform_shop_permission
from app.services.shop.merchant_service import assert_can_read_merchant_tenant
from app.services.shop.onboarding_review_service import PURCHASE_MODES

MANUAL_SERVICE_LOG_TYPES: frozenset[str] = frozenset(
    {
        "note",
        "call",
        "visit",
        "wechat",
        "video",
        "email",
        "training",
        "complaint",
        "onboarding_assist",
        "other",
    }
)


def _get_merchant_for_tenant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if not merchant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商家不存在")
    return merchant


def _set_merchant_pending_renewal(db: Session, merchant_id: UUID, value: bool) -> None:
    updated = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.id, merchant_id))
        .update({"has_pending_renewal": value}, synchronize_session=False)
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="商家状态更新失败")


def _assert_no_pending_renewal(db: Session, merchant_id: UUID) -> None:
    pending = (
        db.query(ShopMerchantServiceLog)
        .filter(
            uuid_eq(ShopMerchantServiceLog.merchant_id, merchant_id),
            ShopMerchantServiceLog.type == "renewal_request",
            ShopMerchantServiceLog.status.in_(("pending", "processing")),
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有待处理续费申请")


def _to_log_item(log: ShopMerchantServiceLog) -> MerchantServiceLogItem:
    return MerchantServiceLogItem(
        id=log.id,
        type=log.type,
        status=log.status,
        content=log.content,
        payload_json=log.payload_json or {},
        operator_user_id=log.operator_user_id,
        operator_name=log.operator.display_name if log.operator else None,
        follow_up_at=log.follow_up_at,
        related_onboarding_id=log.related_onboarding_id,
        related_subscription_id=log.related_subscription_id,
        created_at=log.created_at,
        updated_at=log.updated_at,
    )


def create_service_note(
    db: Session,
    user: User,
    tenant_id: UUID,
    payload: ServiceNoteCreate,
) -> MerchantServiceLogItem:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    content = (payload.content or "").strip()
    if len(content) < 10:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请填写跟进内容（至少10字）")

    log_type = (payload.type or "call").strip()
    if log_type not in MANUAL_SERVICE_LOG_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="无效的跟进类型")

    merchant = _get_merchant_for_tenant(db, tenant_id)
    extra = dict(payload.payload_json or {})
    log = ShopMerchantServiceLog(
        merchant_id=merchant.id,
        tenant_id=tenant_id,
        type=log_type,
        status="logged",
        content=content,
        payload_json=extra,
        follow_up_at=payload.follow_up_at,
        operator_user_id=user.id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.id, log.id))
        .first()
    )
    return _to_log_item(log)


def create_renewal_request(
    db: Session,
    user: User,
    tenant_id: UUID,
    payload: RenewalRequestCreate,
) -> MerchantServiceLogItem:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    if user_has_platform_shop_permission(user, "platform.shop.subscription.manage"):
        pass  # 有订阅管理权限也可代提，通常直接进 P11

    if payload.purchase_mode not in PURCHASE_MODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="申请类型无效")
    if not payload.customer_confirmed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先与客户确认续费意向")
    if payload.quoted_amount_cents < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="金额不能为负")
    content = (payload.content or "").strip()
    if len(content) < 4:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请填写续费说明")
    # quoted_amount_cents 允许 0（赠送/免费续期）；0 或≠标价时由说明栏写明原因（已要求 ≥4 字）

    merchant = _get_merchant_for_tenant(db, tenant_id)
    if merchant.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅正常营业商家可申请续费")
    if merchant.plan_status not in ("expiring_soon", "expired") and not merchant.has_pending_renewal:
        # Phase1：即将到期/已到期才可申请；演示环境放宽为允许 active 但给出提示性校验
        if merchant.plan_status == "active" and merchant.benefits_until is None:
            pass
        elif merchant.plan_status == "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前套餐未到期，无需申请续费")

    _assert_no_pending_renewal(db, merchant.id)

    log = ShopMerchantServiceLog(
        merchant_id=merchant.id,
        tenant_id=tenant_id,
        type="renewal_request",
        status="pending",
        content=content,
        payload_json={
            "target_plan": payload.target_plan,
            "purchase_mode": payload.purchase_mode,
            "customer_confirmed": payload.customer_confirmed,
            "quoted_amount_cents": payload.quoted_amount_cents,
            "catalog_price_cents": payload.catalog_price_cents,
        },
        operator_user_id=user.id,
    )
    db.add(log)
    _set_merchant_pending_renewal(db, merchant.id, True)
    db.commit()
    db.refresh(log)
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.id, log.id))
        .first()
    )
    return _to_log_item(log)


def _get_renewal_log(
    db: Session,
    merchant: ShopMerchantAccount,
    service_log_id: UUID,
) -> ShopMerchantServiceLog:
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(
            uuid_eq(ShopMerchantServiceLog.id, service_log_id),
            uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id),
            ShopMerchantServiceLog.type == "renewal_request",
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="续费申请不存在")
    return log


def cancel_renewal_request(
    db: Session,
    user: User,
    tenant_id: UUID,
    service_log_id: UUID,
    *,
    note: str | None = None,
) -> MerchantServiceLogItem:
    if not user_has_platform_shop_permission(user, "platform.shop.subscription.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无订阅管理权限")

    merchant = _get_merchant_for_tenant(db, tenant_id)
    log = _get_renewal_log(db, merchant, service_log_id)
    if log.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="仅待处理可取消，请先退回待处理",
        )
    if log.status != "pending":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅待处理可取消")
    text = (note or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请填写取消原因")

    log.status = "cancelled"
    payload = dict(log.payload_json or {})
    payload["cancel_note"] = text
    log.payload_json = payload
    _set_merchant_pending_renewal(db, merchant.id, False)
    db.commit()
    db.refresh(log)
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.id, log.id))
        .first()
    )
    return _to_log_item(log)


def mark_renewal_processing(
    db: Session,
    user: User,
    tenant_id: UUID,
    service_log_id: UUID,
) -> MerchantServiceLogItem:
    """对照 #p11a-renewal 底栏「暂存处理中」。"""
    if not user_has_platform_shop_permission(user, "platform.shop.subscription.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无订阅管理权限")
    merchant = _get_merchant_for_tenant(db, tenant_id)
    log = _get_renewal_log(db, merchant, service_log_id)
    if log.status == "processing":
        return _to_log_item(log)
    if log.status != "pending":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅待处理可暂存为处理中")
    log.status = "processing"
    db.commit()
    db.refresh(log)
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.id, log.id))
        .first()
    )
    return _to_log_item(log)


def revert_renewal_pending(
    db: Session,
    user: User,
    tenant_id: UUID,
    service_log_id: UUID,
) -> MerchantServiceLogItem:
    """处理中退回待处理，之后才可取消申请。对照 #p11a-renewal。"""
    if not user_has_platform_shop_permission(user, "platform.shop.subscription.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无订阅管理权限")
    merchant = _get_merchant_for_tenant(db, tenant_id)
    log = _get_renewal_log(db, merchant, service_log_id)
    if log.status == "pending":
        return _to_log_item(log)
    if log.status != "processing":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅处理中可退回待处理")
    log.status = "pending"
    db.commit()
    db.refresh(log)
    log = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.id, log.id))
        .first()
    )
    return _to_log_item(log)


def list_service_logs(
    db: Session,
    user: User,
    tenant_id: UUID,
    *,
    type_filter: str | None = None,
    status_filter: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> MerchantServiceLogListResponse:
    assert_can_read_merchant_tenant(db, user, tenant_id)
    merchant = _get_merchant_for_tenant(db, tenant_id)
    query = (
        db.query(ShopMerchantServiceLog)
        .options(joinedload(ShopMerchantServiceLog.operator))
        .filter(uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id))
    )
    if type_filter:
        query = query.filter(ShopMerchantServiceLog.type == type_filter)
    else:
        query = query.filter(ShopMerchantServiceLog.type != "audit")
    if status_filter:
        query = query.filter(ShopMerchantServiceLog.status == status_filter)
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        query = query.filter(
            ShopMerchantServiceLog.content.ilike(like)
            | ShopMerchantServiceLog.operator.has(User.display_name.ilike(like))
        )
    total = query.count()
    rows = (
        query.order_by(ShopMerchantServiceLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return MerchantServiceLogListResponse(
        items=[_to_log_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )

