"""A15 支付与进件。对照 PRD 01#a15 · #a15a · §8.7.3。

商家仅提交材料与查看状态；证书/回调由平台 P06 维护，本模块不暴露。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import ShopMerchantAccount, ShopPaymentOnboarding

STATUS_NOT_SUBMITTED = "not_submitted"
STATUS_SUBMITTED = "submitted"
STATUS_REJECTED = "rejected"
STATUS_APPROVED = "approved"

STATUS_LABELS = {
    STATUS_NOT_SUBMITTED: "未提交",
    STATUS_SUBMITTED: "审核中",
    STATUS_REJECTED: "已驳回",
    STATUS_APPROVED: "已开通",
}

ENTITY_LABELS = {
    "personal": "个人",
    "individual_business": "个体工商户",
    "enterprise": "企业",
}

# 04 §通用 · 结算开户行常用列表（Phase1 静态；后续可平台配置）
SETTLEMENT_BANKS = [
    "招商银行",
    "工商银行",
    "建设银行",
    "农业银行",
    "中国银行",
    "交通银行",
    "民生银行",
    "兴业银行",
    "浦发银行",
    "中信银行",
    "光大银行",
    "平安银行",
    "广发银行",
    "华夏银行",
    "邮储银行",
    "北京银行",
    "上海银行",
    "其他银行",
]

ACCOUNT_RE = re.compile(r"^\d{8,32}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount | None:
    return (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )


def _require_onboarded_merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = _merchant(db, tenant_id)
    if not m or m.status not in ("active", "suspended"):
        raise HTTPException(status_code=422, detail="请先完成入驻")
    return m


def _get_or_create_row(
    db: Session, tenant_id: UUID, merchant: ShopMerchantAccount | None
) -> ShopPaymentOnboarding:
    row = (
        db.query(ShopPaymentOnboarding)
        .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, tenant_id))
        .first()
    )
    if row:
        return row
    row = ShopPaymentOnboarding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        merchant_id=merchant.id if merchant else None,
        onboarding_status=STATUS_NOT_SUBMITTED,
        entity_snapshot_json={},
    )
    db.add(row)
    db.flush()
    return row


def _mask_account(acc: str | None) -> str | None:
    if not acc:
        return None
    digits = re.sub(r"\s+", "", acc)
    if len(digits) <= 4:
        return "****"
    return f"{'*' * max(4, len(digits) - 4)}{digits[-4:]}"


def _mask_sub_mch(mid: str | None) -> str | None:
    if not mid:
        return None
    if len(mid) <= 4:
        return "****"
    return f"{mid[:2]}{'*' * (len(mid) - 4)}{mid[-2:]}"


def _entity_from_merchant(m: ShopMerchantAccount) -> dict[str, Any]:
    return {
        "entity_type": m.entity_type,
        "entity_type_label": ENTITY_LABELS.get(m.entity_type, m.entity_type),
        "legal_name": m.legal_name or "",
        "unified_social_credit_code": m.unified_social_credit_code or "",
        "legal_rep_name": m.legal_rep_name or "",
        "id_no": m.id_no or "",
    }


def _actions_for(status: str, can_write: bool) -> list[str]:
    actions: list[str] = []
    if status in (STATUS_NOT_SUBMITTED, STATUS_REJECTED) and can_write:
        actions.append("submit" if status == STATUS_NOT_SUBMITTED else "resubmit")
    if status in (STATUS_SUBMITTED, STATUS_APPROVED, STATUS_REJECTED):
        actions.append("view_materials")
    if status == STATUS_APPROVED and can_write:
        actions.append("test_payment")
    return actions


def get_payment_settings(db: Session, ctx: TenantContext, *, can_write: bool = True) -> dict[str, Any]:
    merchant = _merchant(db, ctx.tenant_id)
    if not merchant:
        return {
            "state": "not_onboarded",
            "onboarding_status": STATUS_NOT_SUBMITTED,
            "onboarding_status_label": STATUS_LABELS[STATUS_NOT_SUBMITTED],
            "can_submit": False,
            "actions": [],
            "entity": None,
            "settlement": None,
            "wx_sub_mch_id_masked": None,
            "mch_name": None,
            "reject_reason": None,
            "submitted_at": None,
            "approved_at": None,
            "banks": SETTLEMENT_BANKS,
            "hint": "请先完成入驻后再提交支付进件材料",
        }

    row = _get_or_create_row(db, ctx.tenant_id, merchant)
    status = row.onboarding_status or STATUS_NOT_SUBMITTED
    entity = dict(row.entity_snapshot_json or {}) if row.entity_snapshot_json else _entity_from_merchant(merchant)
    entity.pop("_meta", None)
    settlement = None
    if row.settlement_bank or row.settlement_account or row.settlement_account_name:
        settlement = {
            "settlement_bank": row.settlement_bank,
            "settlement_account_masked": _mask_account(row.settlement_account),
            "settlement_account_name": row.settlement_account_name,
            "remark": row.remark,
        }
    can_submit = status in (STATUS_NOT_SUBMITTED, STATUS_REJECTED) and merchant.status in (
        "active",
        "suspended",
    )
    return {
        "state": "onboarded",
        "onboarding_status": status,
        "onboarding_status_label": STATUS_LABELS.get(status, status),
        "can_submit": can_submit and can_write,
        "actions": _actions_for(status, can_write),
        "entity": entity,
        "settlement": settlement,
        "wx_sub_mch_id_masked": _mask_sub_mch(row.wx_sub_mch_id)
        if status == STATUS_APPROVED
        else None,
        "mch_name": row.mch_name if status == STATUS_APPROVED else (entity.get("legal_name") or None),
        "reject_reason": row.reject_reason if status == STATUS_REJECTED else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "banks": SETTLEMENT_BANKS,
        "hint": "提交进件材料后由平台代提微信子商户；证书与回调由平台统一维护，商家无需配置。",
    }


def submit_onboarding(
    db: Session,
    ctx: TenantContext,
    *,
    settlement_bank: str,
    settlement_account: str,
    settlement_account_name: str,
    remark: str | None = None,
) -> dict[str, Any]:
    merchant = _require_onboarded_merchant(db, ctx.tenant_id)
    row = _get_or_create_row(db, ctx.tenant_id, merchant)
    if row.onboarding_status not in (STATUS_NOT_SUBMITTED, STATUS_REJECTED):
        raise HTTPException(status_code=422, detail="当前状态不可提交")

    bank = (settlement_bank or "").strip()
    account = re.sub(r"\s+", "", settlement_account or "")
    name = (settlement_account_name or "").strip()
    if not bank:
        raise HTTPException(status_code=422, detail="请选择结算开户行")
    if bank not in SETTLEMENT_BANKS:
        raise HTTPException(status_code=422, detail="结算开户行不在可选列表中")
    if not ACCOUNT_RE.match(account):
        raise HTTPException(status_code=422, detail="结算账号须为 8–32 位数字")
    if not name or len(name) < 2 or len(name) > 200:
        raise HTTPException(status_code=422, detail="请填写开户名")

    snap = _entity_from_merchant(merchant)
    prev = dict(row.entity_snapshot_json or {})
    meta = dict(prev.get("_meta") or {})
    events = list(meta.get("timeline") or [])
    events.append({"at": _now().isoformat(), "event": "商家提交进件材料（A15）"})
    meta["timeline"] = events
    snap["_meta"] = meta
    row.merchant_id = merchant.id
    row.settlement_bank = bank
    row.settlement_account = account
    row.settlement_account_name = name
    row.remark = (remark or "").strip() or None
    row.entity_snapshot_json = snap
    row.mch_name = snap.get("legal_name") or merchant.display_name
    row.onboarding_status = STATUS_SUBMITTED
    row.reject_reason = None
    row.submitted_at = _now()
    row.submitted_by = ctx.user.id
    row.wx_sub_mch_id = None
    row.approved_at = None
    db.commit()
    db.refresh(row)
    return get_payment_settings(db, ctx, can_write=True)


def test_payment(db: Session, ctx: TenantContext) -> dict[str, Any]:
    merchant = _require_onboarded_merchant(db, ctx.tenant_id)
    row = _get_or_create_row(db, ctx.tenant_id, merchant)
    if row.onboarding_status != STATUS_APPROVED:
        raise HTTPException(status_code=422, detail="进件未开通")
    # Phase1：沙箱测试单，不污染生产对账
    return {
        "ok": True,
        "amount_cents": 1,
        "currency": "CNY",
        "mode": "sandbox",
        "wx_sub_mch_id_masked": _mask_sub_mch(row.wx_sub_mch_id),
        "message": "测试支付已发起（沙箱 0.01 元）",
    }


def force_approve_for_tests(
    db: Session,
    tenant_id: UUID,
    *,
    wx_sub_mch_id: str = "1600123456",
) -> ShopPaymentOnboarding:
    """仅供 verify / 联测：模拟平台审核通过。"""
    merchant = _merchant(db, tenant_id)
    if not merchant:
        raise HTTPException(status_code=404, detail="商家不存在")
    row = _get_or_create_row(db, tenant_id, merchant)
    if row.onboarding_status != STATUS_SUBMITTED:
        raise HTTPException(status_code=422, detail="仅审核中可开通")
    row.onboarding_status = STATUS_APPROVED
    row.wx_sub_mch_id = wx_sub_mch_id
    row.mch_name = row.mch_name or merchant.legal_name or merchant.display_name
    row.approved_at = _now()
    row.reject_reason = None
    db.commit()
    db.refresh(row)
    return row
