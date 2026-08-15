"""P02-C/D/F 商家暂停 / 恢复 / 清退。对照 PRD §2.4.4 · §2.4.5 · §8.4。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import ShopMerchantAccount, ShopMerchantServiceLog, ShopOnboardingApplication, ShopStore
from app.schemas.shop_platform import MerchantCloseRequest, MerchantResumeRequest, MerchantSuspendRequest
from app.services.shop.merchant_service import get_platform_merchant_detail

SUSPEND_REASONS = frozenset({"violation", "arrears", "merchant_request", "other"})
CLOSE_REASONS = frozenset({"violation", "contract_end", "merchant_request", "fraud", "other"})


def _get_merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="商家不存在")
    return m


def _log_status_change(
    db: Session,
    merchant: ShopMerchantAccount,
    user: User,
    *,
    from_status: str,
    to_status: str,
    reason_code: str | None,
    reason_text: str | None,
) -> None:
    db.add(
        ShopMerchantServiceLog(
            merchant_id=merchant.id,
            tenant_id=merchant.tenant_id,
            type="status_change",
            status="logged",
            content=f"状态变更 {from_status} → {to_status}"
            + (f"：{reason_text}" if reason_text else ""),
            payload_json={
                "from": from_status,
                "to": to_status,
                "reason_code": reason_code,
                "reason_text": reason_text,
            },
            operator_user_id=user.id,
        )
    )


def _pause_all_stores(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id), ShopStore.status != "closed")
        .update({"status": "paused"}, synchronize_session=False)
    )


def _resume_paused_stores(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id), ShopStore.status == "paused")
        .update({"status": "active"}, synchronize_session=False)
    )


def suspend_merchant(db: Session, user: User, tenant_id: UUID, payload: MerchantSuspendRequest):
    merchant = _get_merchant(db, tenant_id)
    if merchant.status != "active":
        raise HTTPException(status_code=422, detail="仅正常营业商家可暂停")
    if payload.reason_code not in SUSPEND_REASONS:
        raise HTTPException(status_code=422, detail="暂停原因码无效")
    text = (payload.reason_text or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="请填写暂停原因（至少4字）")

    prev = merchant.status
    merchant.status = "suspended"
    merchant.suspended_at = datetime.now(timezone.utc)
    _pause_all_stores(db, tenant_id)
    operator_id = user.id
    _log_status_change(
        db, merchant, user, from_status=prev, to_status="suspended", reason_code=payload.reason_code, reason_text=text
    )
    from app.services.shop.audit_log_service import (
        ACTION_SUSPEND,
        SOURCE_MERCHANT_LIST,
        record_merchant_audit,
    )

    record_merchant_audit(
        db,
        tenant_id=tenant_id,
        merchant_id=merchant.id,
        action=ACTION_SUSPEND,
        summary=f"原因：{text}",
        source=SOURCE_MERCHANT_LIST,
        operator=user,
    )
    db.commit()
    return _detail_after_write(db, operator_id, tenant_id)


def resume_merchant(db: Session, user: User, tenant_id: UUID, payload: MerchantResumeRequest | None = None):
    merchant = _get_merchant(db, tenant_id)
    if merchant.status == "closed":
        raise HTTPException(status_code=422, detail="已清退不可恢复")
    if merchant.status != "suspended":
        raise HTTPException(status_code=422, detail="仅已暂停商家可恢复")
    prev = merchant.status
    merchant.status = "active"
    merchant.suspended_at = None
    _resume_paused_stores(db, tenant_id)
    note = (payload.note if payload else None) or "恢复营业资格"
    operator_id = user.id
    _log_status_change(
        db, merchant, user, from_status=prev, to_status="active", reason_code="resume", reason_text=note
    )
    from app.services.shop.audit_log_service import (
        ACTION_RESUME,
        SOURCE_MERCHANT_LIST,
        record_merchant_audit,
    )

    record_merchant_audit(
        db,
        tenant_id=tenant_id,
        merchant_id=merchant.id,
        action=ACTION_RESUME,
        summary=note,
        source=SOURCE_MERCHANT_LIST,
        operator=user,
    )
    db.commit()
    return _detail_after_write(db, operator_id, tenant_id)


def close_merchant(db: Session, user: User, tenant_id: UUID, payload: MerchantCloseRequest):
    merchant = _get_merchant(db, tenant_id)
    if merchant.status == "closed":
        raise HTTPException(status_code=409, detail="已清退")
    if merchant.status not in ("active", "suspended"):
        raise HTTPException(status_code=422, detail="当前状态不可清退")
    if not payload.ack_irreversible:
        raise HTTPException(status_code=422, detail="须确认不可恢复")
    if payload.reason_code not in CLOSE_REASONS:
        raise HTTPException(status_code=422, detail="清退原因码无效")
    text = (payload.reason_text or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="请填写清退说明（至少4字）")

    prev = merchant.status
    now = datetime.now(timezone.utc)
    merchant.status = "closed"
    merchant.closed_at = now
    merchant.closed_by = user.id
    merchant.close_reason_code = payload.reason_code
    merchant.close_reason_text = text
    merchant.has_pending_renewal = False
    _pause_all_stores(db, tenant_id)

    # 取消在途续费
    pending = (
        db.query(ShopMerchantServiceLog)
        .filter(
            uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id),
            ShopMerchantServiceLog.type == "renewal_request",
            ShopMerchantServiceLog.status.in_(("pending", "processing")),
        )
        .all()
    )
    for log in pending:
        log.status = "cancelled"
        payload_json = dict(log.payload_json or {})
        payload_json["cancel_reason"] = "merchant_closed"
        log.payload_json = payload_json

    # 在途入驻申请驳回/关闭
    apps = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.tenant_id, tenant_id),
            ShopOnboardingApplication.status == "pending",
        )
        .all()
    )
    for app in apps:
        app.status = "rejected"
        app.reject_code = "other"
        app.reject_reason = "商家已清退"

    operator_id = user.id
    _log_status_change(
        db, merchant, user, from_status=prev, to_status="closed", reason_code=payload.reason_code, reason_text=text
    )
    from app.services.shop.audit_log_service import (
        ACTION_CLOSE,
        SOURCE_MERCHANT_LIST,
        record_merchant_audit,
    )

    record_merchant_audit(
        db,
        tenant_id=tenant_id,
        merchant_id=merchant.id,
        action=ACTION_CLOSE,
        summary=f"原因：{text}",
        source=SOURCE_MERCHANT_LIST,
        operator=user,
    )
    db.commit()
    return _detail_after_write(db, operator_id, tenant_id)


def _detail_after_write(db: Session, operator_id: UUID, tenant_id: UUID):
    """commit 后重新加载 operator，避免 Session expire 导致 ObjectDeletedError。"""
    op = db.query(User).filter(uuid_eq(User.id, operator_id)).first()
    if not op:
        raise HTTPException(status_code=500, detail="操作人加载失败")
    return get_platform_merchant_detail(db, op, tenant_id)


def assert_merchant_not_blocked_for_trade(db: Session, tenant_id: UUID) -> None:
    """买家新购 / 交易闸（M2-3）：suspended/closed → 422。"""
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        return
    if m.status == "suspended":
        raise HTTPException(status_code=422, detail="暂停营业")
    if m.status == "closed":
        raise HTTPException(status_code=422, detail="商家已清退")
