"""P12 短信管理。对照 06#p12 · #p12-signatures · #p12-templates · #p12-assign · #p12-logs。"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import (
    PlatformChannelCredential,
    PlatformSmsSignature,
    PlatformSmsTemplate,
    ShopMerchantAccount,
    ShopSmsLog,
    ShopTenantSettings,
)
from app.services.crypto import decrypt_api_key, encrypt_api_key
from app.services.shop import a18_service
from app.services.shop.a15_sms_settings_service import _ensure_settings, _usage_block
from app.services.shop.entitlement_service import TZ_SH, UNLIMITED

SIG_INNER_RE = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9]{2,12}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_]{4,64}$")
CHANNEL_SMS_ALIYUN = "sms_aliyun"

STATUS_LABELS = {
    "pending": "审核中",
    "approved": "已通过",
    "rejected": "已驳回",
    "withdrawn": "已撤回",
}
PURPOSE_LABELS = {
    "claim_link": "领权",
    "notify": "平台通知",
    "test": "测试",
}
LOG_TYPE_PURPOSE = {
    "claim_link": "claim",
    "claim_link_test": "test",
}
LOG_PURPOSE_LABELS = {
    "claim": "领权",
    "test": "测试",
    "notify": "平台通知",
}
LOG_STATUS_LABELS = {
    "sent": "成功",
    "failed": "失败",
    "sending": "发送中",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_signature(raw: str) -> str:
    text = (raw or "").strip().replace(" ", "")
    if text.startswith("【") and text.endswith("】") and len(text) >= 4:
        inner = text[1:-1]
    else:
        inner = text.strip("【】")
    if not SIG_INNER_RE.match(inner):
        raise HTTPException(status_code=422, detail="签名含非法字符")
    return f"【{inner}】"


def _uuid_in(column, ids: list) -> Any | None:
    if not ids:
        return None
    return or_(*[uuid_eq(column, tid) for tid in ids])


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount | None:
    return (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )


def _merchant_name(db: Session, tenant_id: UUID | None) -> str | None:
    if not tenant_id:
        return None
    m = _merchant(db, tenant_id)
    if m:
        return m.display_name or m.legal_name
    t = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    return t.name if t else None


def _sig_item(db: Session, row: PlatformSmsSignature) -> dict[str, Any]:
    actions: list[str] = ["view"]
    if row.status == "pending":
        actions.extend(["sync", "withdraw", "approve", "reject"])
    if row.status == "rejected":
        actions.append("resubmit")
    if row.status == "approved":
        actions.append("assign")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id) if row.tenant_id else None,
        "merchant_name": _merchant_name(db, row.tenant_id) or "未分配",
        "name": row.name,
        "content": row.content,
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "remark": row.remark,
        "reject_reason": row.reject_reason if row.status == "rejected" else None,
        "qualification_files": row.qualification_files or {},
        "provider_sig_id": row.provider_sig_id,
        "applied_at": row.created_at.isoformat() if row.created_at else None,
        "actions": actions,
    }


def list_signatures(
    db: Session,
    *,
    q: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = db.query(PlatformSmsSignature)
    if status:
        query = query.filter(PlatformSmsSignature.status == status)
    if q:
        like = f"%{q.strip()}%"
        merchants = (
            db.query(ShopMerchantAccount.tenant_id)
            .filter(
                or_(
                    ShopMerchantAccount.display_name.ilike(like),
                    ShopMerchantAccount.legal_name.ilike(like),
                )
            )
            .all()
        )
        tids = [r[0] for r in merchants]
        conds = [PlatformSmsSignature.content.ilike(like), PlatformSmsSignature.name.ilike(like)]
        extra = _uuid_in(PlatformSmsSignature.tenant_id, tids)
        if extra is not None:
            conds.append(extra)
        query = query.filter(or_(*conds))
    total = query.count()
    rows = (
        query.order_by(PlatformSmsSignature.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_sig_item(db, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_signature(db: Session, sig_id: UUID) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    return _sig_item(db, row)


def create_signature(
    db: Session,
    *,
    tenant_id: UUID,
    content: str,
    remark: str | None,
    qualification_files: dict | None,
) -> dict[str, Any]:
    merchant = _merchant(db, tenant_id)
    if not merchant or merchant.status == "closed":
        raise HTTPException(status_code=422, detail="请选择关联商家")
    normalized = _normalize_signature(content)
    pending = (
        db.query(PlatformSmsSignature)
        .filter(
            uuid_eq(PlatformSmsSignature.tenant_id, tenant_id),
            PlatformSmsSignature.status == "pending",
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=422, detail="该商家已有审核中的签名申请")
    row = PlatformSmsSignature(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=normalized,
        content=normalized,
        status="pending",
        remark=(remark or "").strip() or None,
        qualification_files=qualification_files or {},
        provider_sig_id=f"mock_{uuid.uuid4().hex[:10]}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _sig_item(db, row)


def sync_signature(db: Session, sig_id: UUID) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    if row.status not in ("pending", "rejected"):
        raise HTTPException(status_code=422, detail="当前状态不可同步")
    db.commit()
    return _sig_item(db, row)


def withdraw_signature(db: Session, sig_id: UUID) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    if row.status != "pending":
        raise HTTPException(status_code=422, detail="仅审核中可撤回")
    row.status = "withdrawn"
    db.commit()
    db.refresh(row)
    return _sig_item(db, row)


def approve_signature(db: Session, sig_id: UUID) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    if row.status != "pending":
        raise HTTPException(status_code=422, detail="仅审核中可通过")
    row.status = "approved"
    row.reject_reason = None
    db.commit()
    db.refresh(row)
    return _sig_item(db, row)


def reject_signature(db: Session, sig_id: UUID, *, reason: str) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    if row.status != "pending":
        raise HTTPException(status_code=422, detail="仅审核中可驳回")
    text = (reason or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="驳回原因至少 4 字")
    row.status = "rejected"
    row.reject_reason = text
    db.commit()
    db.refresh(row)
    return _sig_item(db, row)


def resubmit_signature(
    db: Session,
    sig_id: UUID,
    *,
    content: str | None,
    remark: str | None,
    qualification_files: dict | None = None,
) -> dict[str, Any]:
    row = db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sig_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="签名不存在")
    if row.status != "rejected":
        raise HTTPException(status_code=422, detail="仅已驳回可重新提交")
    other = (
        db.query(PlatformSmsSignature)
        .filter(
            uuid_eq(PlatformSmsSignature.tenant_id, row.tenant_id),
            PlatformSmsSignature.status == "pending",
            PlatformSmsSignature.id != row.id,
        )
        .first()
    )
    if other:
        raise HTTPException(status_code=422, detail="该商家已有审核中的签名申请")
    if content:
        row.content = _normalize_signature(content)
        row.name = row.content
    if remark is not None:
        row.remark = remark.strip() or None
    if qualification_files is not None:
        row.qualification_files = qualification_files or {}
    row.status = "pending"
    row.reject_reason = None
    row.provider_sig_id = f"mock_{uuid.uuid4().hex[:10]}"
    db.commit()
    db.refresh(row)
    return _sig_item(db, row)


def _tpl_item(row: PlatformSmsTemplate) -> dict[str, Any]:
    actions = ["edit"]
    if row.status == "approved" and row.purpose == "claim_link":
        actions.append("set_default")
    if row.status == "pending":
        actions.extend(["approve", "sync"])
    return {
        "id": str(row.id),
        "name": row.name,
        "template_code": row.template_code,
        "purpose": row.purpose,
        "purpose_label": PURPOSE_LABELS.get(row.purpose, row.purpose),
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "is_default_claim": bool(row.is_default_claim),
        "content_preview": row.content_preview,
        "actions": actions,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_templates(
    db: Session,
    *,
    purpose: str | None,
    status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = db.query(PlatformSmsTemplate)
    if purpose:
        query = query.filter(PlatformSmsTemplate.purpose == purpose)
    if status:
        query = query.filter(PlatformSmsTemplate.status == status)
    total = query.count()
    rows = (
        query.order_by(
            PlatformSmsTemplate.is_default_claim.desc(),
            PlatformSmsTemplate.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_tpl_item(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_template(
    db: Session,
    *,
    name: str,
    template_code: str,
    purpose: str,
    content_preview: str | None,
    is_default_claim: bool,
) -> dict[str, Any]:
    title = (name or "").strip()
    code = (template_code or "").strip()
    if not title or len(title) > 100:
        raise HTTPException(status_code=422, detail="请填写模板名称")
    if not CODE_RE.match(code):
        raise HTTPException(status_code=422, detail="供应商 Template Code 格式无效")
    if purpose not in PURPOSE_LABELS:
        raise HTTPException(status_code=422, detail="用途无效")
    exists = (
        db.query(PlatformSmsTemplate).filter(PlatformSmsTemplate.template_code == code).first()
    )
    if exists:
        raise HTTPException(status_code=422, detail="Code 已存在")
    row = PlatformSmsTemplate(
        id=uuid.uuid4(),
        name=title,
        template_code=code,
        purpose=purpose,
        status="approved",
        content_preview=(content_preview or "").strip() or None,
        is_default_claim=False,
    )
    db.add(row)
    try:
        db.flush()
        if is_default_claim:
            _set_default_claim(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Code 已存在") from None
    db.refresh(row)
    return _tpl_item(row)


def update_template(
    db: Session,
    tpl_id: UUID,
    *,
    name: str | None,
    content_preview: str | None,
) -> dict[str, Any]:
    row = db.query(PlatformSmsTemplate).filter(uuid_eq(PlatformSmsTemplate.id, tpl_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    if name is not None:
        title = name.strip()
        if not title:
            raise HTTPException(status_code=422, detail="请填写模板名称")
        row.name = title
    if content_preview is not None:
        row.content_preview = content_preview.strip() or None
    db.commit()
    db.refresh(row)
    return _tpl_item(row)


def _set_default_claim(db: Session, row: PlatformSmsTemplate) -> None:
    if row.purpose != "claim_link":
        raise HTTPException(status_code=422, detail="仅领权模板可设为默认")
    if row.status != "approved":
        raise HTTPException(status_code=422, detail="模板未通过审核")
    db.query(PlatformSmsTemplate).filter(PlatformSmsTemplate.is_default_claim.is_(True)).update(
        {PlatformSmsTemplate.is_default_claim: False}
    )
    row.is_default_claim = True


def set_default_claim(db: Session, tpl_id: UUID) -> dict[str, Any]:
    row = db.query(PlatformSmsTemplate).filter(uuid_eq(PlatformSmsTemplate.id, tpl_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    _set_default_claim(db, row)
    db.commit()
    db.refresh(row)
    return _tpl_item(row)


def merchant_options(db: Session) -> list[dict[str, str]]:
    rows = (
        db.query(ShopMerchantAccount, Tenant)
        .outerjoin(Tenant, Tenant.id == ShopMerchantAccount.tenant_id)
        .filter(ShopMerchantAccount.status != "closed")
        .order_by(ShopMerchantAccount.display_name.asc())
        .all()
    )
    out = []
    for m, t in rows:
        out.append(
            {
                "tenant_id": str(m.tenant_id),
                "name": m.display_name or m.legal_name or (t.name if t else ""),
            }
        )
    return out


def approved_signatures_for(db: Session, tenant_id: UUID) -> list[dict[str, str]]:
    rows = (
        db.query(PlatformSmsSignature)
        .filter(
            uuid_eq(PlatformSmsSignature.tenant_id, tenant_id),
            PlatformSmsSignature.status == "approved",
        )
        .order_by(PlatformSmsSignature.created_at.desc())
        .all()
    )
    return [{"id": str(r.id), "content": r.content} for r in rows]


def approved_claim_templates(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(PlatformSmsTemplate)
        .filter(
            PlatformSmsTemplate.purpose == "claim_link",
            PlatformSmsTemplate.status == "approved",
        )
        .order_by(PlatformSmsTemplate.is_default_claim.desc(), PlatformSmsTemplate.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "template_code": r.template_code,
            "is_default_claim": bool(r.is_default_claim),
        }
        for r in rows
    ]


def _assign_status(sig: PlatformSmsSignature | None, tpl: PlatformSmsTemplate | None) -> str:
    if sig is None or tpl is None:
        return "unassigned"
    if sig.status == "pending":
        return "signature_pending"
    if sig.status == "approved" and tpl.status == "approved":
        return "assigned"
    return "unassigned"


def list_assignments(
    db: Session,
    *,
    q: str | None,
    assign_status: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = (
        db.query(ShopMerchantAccount, ShopTenantSettings, Tenant)
        .outerjoin(ShopTenantSettings, ShopTenantSettings.tenant_id == ShopMerchantAccount.tenant_id)
        .outerjoin(Tenant, Tenant.id == ShopMerchantAccount.tenant_id)
        .filter(ShopMerchantAccount.status != "closed")
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ShopMerchantAccount.display_name.ilike(like),
                ShopMerchantAccount.legal_name.ilike(like),
                Tenant.name.ilike(like),
            )
        )
    rows = query.order_by(ShopMerchantAccount.created_at.desc()).all()
    items = []
    for m, settings, t in rows:
        sig = None
        tpl = None
        if settings and settings.sms_signature_id:
            sig = (
                db.query(PlatformSmsSignature)
                .filter(uuid_eq(PlatformSmsSignature.id, settings.sms_signature_id))
                .first()
            )
        if settings and settings.claim_template_id:
            tpl = (
                db.query(PlatformSmsTemplate)
                .filter(uuid_eq(PlatformSmsTemplate.id, settings.claim_template_id))
                .first()
            )
        st = _assign_status(sig, tpl)
        if assign_status and st != assign_status:
            continue
        usage = _usage_block(db, m.tenant_id)["claim_sms_month"]
        lim = usage["limit"]
        lim_disp = "不限" if lim in (None, "unlimited", UNLIMITED) else lim
        actions = ["assign"] if st != "signature_pending" else []
        if st == "assigned":
            actions = ["edit"]
        items.append(
            {
                "tenant_id": str(m.tenant_id),
                "merchant_name": m.display_name or m.legal_name or (t.name if t else ""),
                "sms_signature_id": str(sig.id) if sig else None,
                "sms_signature": sig.content if sig else None,
                "sms_signature_status": sig.status if sig else None,
                "sms_signature_status_label": STATUS_LABELS.get(sig.status, "") if sig else "未分配",
                "claim_template_id": str(tpl.id) if tpl else None,
                "claim_template_name": tpl.name if tpl else None,
                "assign_status": st,
                "month_used": int(usage["used"] or 0),
                "month_limit": lim_disp,
                "actions": actions,
            }
        )
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def assign_sms(
    db: Session,
    *,
    tenant_id: UUID,
    sms_signature_id: UUID,
    claim_template_id: UUID,
) -> dict[str, Any]:
    merchant = _merchant(db, tenant_id)
    if not merchant or merchant.status == "closed":
        raise HTTPException(status_code=422, detail="商家不存在")
    sig = (
        db.query(PlatformSmsSignature).filter(uuid_eq(PlatformSmsSignature.id, sms_signature_id)).first()
    )
    tpl = (
        db.query(PlatformSmsTemplate).filter(uuid_eq(PlatformSmsTemplate.id, claim_template_id)).first()
    )
    if not sig or sig.status != "approved":
        raise HTTPException(status_code=422, detail="签名未通过审核")
    if sig.tenant_id and str(sig.tenant_id) != str(tenant_id):
        raise HTTPException(status_code=422, detail="签名未通过审核")
    if not tpl or tpl.status != "approved" or tpl.purpose != "claim_link":
        raise HTTPException(status_code=422, detail="模板未通过审核")
    row = _ensure_settings(db, tenant_id)
    row.sms_signature_id = sig.id
    row.claim_template_id = tpl.id
    db.commit()
    data = list_assignments(db, q=None, assign_status=None, page=1, page_size=5000)
    hit = next((x for x in data["items"] if x["tenant_id"] == str(tenant_id)), None)
    return hit or {"tenant_id": str(tenant_id), "assign_status": "assigned"}


def _mask_mobile(mobile: str | None) -> str | None:
    if not mobile:
        return None
    d = re.sub(r"\D", "", mobile)
    if len(d) < 7:
        return "****"
    return f"{d[:3]}****{d[-4:]}"


def _log_purpose(log_type: str) -> str:
    return LOG_TYPE_PURPOSE.get(log_type, "notify")


def _log_item(db: Session, row: ShopSmsLog, *, reveal: bool = False) -> dict[str, Any]:
    purpose = _log_purpose(row.type)
    settings = (
        db.query(ShopTenantSettings).filter(uuid_eq(ShopTenantSettings.tenant_id, row.tenant_id)).first()
    )
    sig_content = None
    tpl_name = None
    tpl_code = None
    if settings and settings.sms_signature_id:
        sig = (
            db.query(PlatformSmsSignature)
            .filter(uuid_eq(PlatformSmsSignature.id, settings.sms_signature_id))
            .first()
        )
        sig_content = sig.content if sig else None
    if settings and settings.claim_template_id:
        tpl = (
            db.query(PlatformSmsTemplate)
            .filter(uuid_eq(PlatformSmsTemplate.id, settings.claim_template_id))
            .first()
        )
        tpl_name = tpl.name if tpl else None
        tpl_code = tpl.template_code if tpl else None
    actions = ["view"]
    if row.status == "failed" and purpose == "claim":
        actions.append("retry")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "merchant_name": _merchant_name(db, row.tenant_id),
        "sent_at": (row.sent_at or row.created_at).isoformat() if (row.sent_at or row.created_at) else None,
        "purpose": purpose,
        "purpose_label": LOG_PURPOSE_LABELS.get(purpose, purpose),
        "sms_signature": sig_content,
        "template_name": tpl_name,
        "template_code": tpl_code,
        "mobile_masked": _mask_mobile(row.buyer_mobile),
        "mobile": row.buyer_mobile if reveal else None,
        "status": row.status,
        "status_label": LOG_STATUS_LABELS.get(row.status, row.status),
        "provider_msg_id": row.provider_msg_id,
        "content": row.content,
        "type": row.type,
        "trigger_source": None,
        "related_order_no": None,
        "quota_note": "占用套餐额度 1 条" if purpose == "claim" else None,
        "actions": actions,
    }


def list_logs(
    db: Session,
    *,
    purpose: str | None,
    status: str | None,
    q: str | None,
    range_key: str | None,
    date_from: str | None,
    date_until: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = db.query(ShopSmsLog)
    now = _now()
    if range_key == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(ShopSmsLog.created_at >= start)
    elif range_key == "7d":
        query = query.filter(ShopSmsLog.created_at >= now - timedelta(days=7))
    elif range_key == "30d":
        query = query.filter(ShopSmsLog.created_at >= now - timedelta(days=30))
    elif range_key == "custom":
        if date_from:
            query = query.filter(ShopSmsLog.created_at >= datetime.fromisoformat(date_from))
        if date_until:
            query = query.filter(ShopSmsLog.created_at <= datetime.fromisoformat(date_until))
    if purpose == "claim":
        query = query.filter(ShopSmsLog.type == "claim_link")
    elif purpose == "test":
        query = query.filter(ShopSmsLog.type == "claim_link_test")
    elif purpose == "notify":
        query = query.filter(~ShopSmsLog.type.in_(("claim_link", "claim_link_test")))
    if status:
        query = query.filter(ShopSmsLog.status == status)
    if q:
        like = f"%{q.strip()}%"
        merchants = (
            db.query(ShopMerchantAccount.tenant_id)
            .filter(
                or_(
                    ShopMerchantAccount.display_name.ilike(like),
                    ShopMerchantAccount.legal_name.ilike(like),
                )
            )
            .all()
        )
        tids = [r[0] for r in merchants]
        conds = [ShopSmsLog.buyer_mobile.ilike(like), ShopSmsLog.content.ilike(like)]
        extra = _uuid_in(ShopSmsLog.tenant_id, tids)
        if extra is not None:
            conds.append(extra)
        query = query.filter(or_(*conds))
    total = query.count()
    rows = (
        query.order_by(ShopSmsLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_log_item(db, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_log(db: Session, log_id: UUID, *, reveal: bool = False) -> dict[str, Any]:
    row = db.query(ShopSmsLog).filter(uuid_eq(ShopSmsLog.id, log_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _log_item(db, row, reveal=reveal)


def retry_log(db: Session, log_id: UUID) -> dict[str, Any]:
    row = db.query(ShopSmsLog).filter(uuid_eq(ShopSmsLog.id, log_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if row.status != "failed" or row.type != "claim_link":
        raise HTTPException(status_code=422, detail="不可重试")
    rem = _usage_block(db, row.tenant_id)["claim_sms_month"]
    lim = rem["limit"]
    if lim not in (None, "unlimited", UNLIMITED):
        try:
            if int(rem["used"] or 0) >= int(lim):
                raise HTTPException(status_code=422, detail="额度不足")
        except (TypeError, ValueError):
            pass
    clone = ShopSmsLog(
        id=uuid.uuid4(),
        tenant_id=row.tenant_id,
        shop_id=row.shop_id,
        buyer_mobile=row.buyer_mobile,
        type=row.type,
        content=row.content,
        status="sent",
        provider_msg_id=f"retry_{uuid.uuid4().hex[:12]}",
        sent_at=_now(),
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return _log_item(db, clone)


def export_logs_csv(
    db: Session,
    *,
    purpose: str | None,
    status: str | None,
    q: str | None,
    range_key: str | None,
    date_from: str | None,
    date_until: str | None,
) -> str:
    key = range_key or "30d"
    if key == "custom":
        if not date_from or not date_until:
            raise HTTPException(status_code=422, detail="导出范围过大")
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_until)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="导出范围过大") from exc
        if (end - start).days > 31:
            raise HTTPException(status_code=422, detail="导出范围过大")
    data = list_logs(
        db,
        purpose=purpose,
        status=status,
        q=q,
        range_key=key,
        date_from=date_from,
        date_until=date_until,
        page=1,
        page_size=5000,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["发送时间", "商家", "用途", "签名", "模板", "接收手机", "状态", "关联单号"])
    for it in data["items"]:
        w.writerow(
            [
                (it.get("sent_at") or "")[:16].replace("T", " "),
                it.get("merchant_name") or "",
                it.get("purpose_label") or "",
                it.get("sms_signature") or "",
                it.get("template_name") or "",
                it.get("mobile_masked") or "",
                it.get("status_label") or "",
                it.get("related_order_no") or "",
            ]
        )
    return buf.getvalue()


def create_sms_log_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SmsLogExportRequest
    from app.services.shop import export_task_service

    body = body or SmsLogExportRequest()
    filters = {
        "purpose": body.purpose,
        "status": body.status,
        "q": body.q,
        "range_key": body.range_key,
        "date_from": body.date_from,
        "date_until": body.date_until,
    }
    csv_text = export_logs_csv(
        db,
        purpose=body.purpose,
        status=body.status,
        q=body.q,
        range_key=body.range_key,
        date_from=body.date_from,
        date_until=body.date_until,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="sms_logs",
        file_name="shop-sms-logs.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_sms_log_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "sms_logs")


def read_sms_log_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "sms_logs")


def _csv_headers(default: list[str], col_map: dict[str, list[str]], columns: list[str] | None) -> list[str]:
    if not columns:
        return default
    headers: list[str] = []
    seen: set[str] = set()
    for key in columns:
        for h in col_map.get(key, []):
            if h not in seen:
                seen.add(h)
                headers.append(h)
    return headers or default


def export_signatures_csv(
    db: Session,
    *,
    q: str | None,
    status: str | None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_signatures(db, q=q, status=status, page=1, page_size=5000)
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    headers = _csv_headers(
        ["签名", "关联商家", "供应商审核", "申请时间"],
        {
            "content": ["签名"],
            "merchant_name": ["关联商家"],
            "status": ["供应商审核"],
            "applied_at": ["申请时间"],
        },
        columns,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in data["items"]:
        values = {
            "签名": it.get("content") or "",
            "关联商家": it.get("merchant_name") or "",
            "供应商审核": it.get("status_label") or "",
            "申请时间": (it.get("applied_at") or "")[:16].replace("T", " "),
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def export_templates_csv(
    db: Session,
    *,
    purpose: str | None,
    status: str | None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_templates(db, purpose=purpose, status=status, page=1, page_size=5000)
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    headers = _csv_headers(
        ["模板名称", "供应商 Code", "用途", "审核状态", "内容摘要"],
        {
            "name": ["模板名称"],
            "code": ["供应商 Code"],
            "template_code": ["供应商 Code"],
            "purpose": ["用途"],
            "status": ["审核状态"],
            "preview": ["内容摘要"],
            "content_preview": ["内容摘要"],
        },
        columns,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in data["items"]:
        values = {
            "模板名称": it.get("name") or "",
            "供应商 Code": it.get("template_code") or "",
            "用途": it.get("purpose_label") or "",
            "审核状态": it.get("status_label") or "",
            "内容摘要": it.get("content_preview") or "",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def export_assignments_csv(
    db: Session,
    *,
    q: str | None,
    assign_status: str | None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_assignments(db, q=q, assign_status=assign_status, page=1, page_size=5000)
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    headers = _csv_headers(
        ["商家", "领权签名", "领权模板", "本月已发"],
        {
            "merchant_name": ["商家"],
            "sms_signature": ["领权签名"],
            "claim_template": ["领权模板"],
            "claim_template_name": ["领权模板"],
            "month": ["本月已发"],
            "month_used": ["本月已发"],
        },
        columns,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in data["items"]:
        values = {
            "商家": it.get("merchant_name") or "",
            "领权签名": it.get("sms_signature") or "",
            "领权模板": it.get("claim_template_name") or "",
            "本月已发": f"{it.get('month_used')} / {it.get('month_limit')}",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def _persist_sms_export(db: Session, user: User, *, resource: str, file_name: str, csv_text: str, filters: dict):
    from app.services.shop import export_task_service

    return export_task_service.persist_csv_for_user(
        db, user, resource=resource, file_name=file_name, csv_text=csv_text, filters=filters
    )


def create_signature_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SmsSignatureExportRequest

    body = body or SmsSignatureExportRequest()
    csv_text = export_signatures_csv(
        db, q=body.q, status=body.status, columns=body.columns, raise_too_many=True
    )
    return _persist_sms_export(
        db,
        user,
        resource="sms_signatures",
        file_name="shop-sms-signatures.csv",
        csv_text=csv_text,
        filters={"q": body.q, "status": body.status, "columns": body.columns},
    )


def get_signature_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "sms_signatures")


def read_signature_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "sms_signatures")


def create_template_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SmsTemplateExportRequest

    body = body or SmsTemplateExportRequest()
    csv_text = export_templates_csv(
        db,
        purpose=body.purpose,
        status=body.status,
        columns=body.columns,
        raise_too_many=True,
    )
    return _persist_sms_export(
        db,
        user,
        resource="sms_templates",
        file_name="shop-sms-templates.csv",
        csv_text=csv_text,
        filters={"purpose": body.purpose, "status": body.status, "columns": body.columns},
    )


def get_template_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "sms_templates")


def read_template_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "sms_templates")


def create_assignment_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SmsAssignmentExportRequest

    body = body or SmsAssignmentExportRequest()
    csv_text = export_assignments_csv(
        db,
        q=body.q,
        assign_status=body.assign_status,
        columns=body.columns,
        raise_too_many=True,
    )
    return _persist_sms_export(
        db,
        user,
        resource="sms_assignments",
        file_name="shop-sms-assignments.csv",
        csv_text=csv_text,
        filters={"q": body.q, "assign_status": body.assign_status, "columns": body.columns},
    )


def get_assignment_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "sms_assignments")


def read_assignment_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "sms_assignments")


def _sms_cred_row(db: Session) -> PlatformChannelCredential | None:
    return (
        db.query(PlatformChannelCredential)
        .filter(PlatformChannelCredential.channel == CHANNEL_SMS_ALIYUN)
        .first()
    )


def _sms_secrets(row: PlatformChannelCredential | None) -> dict:
    if not row or not row.secret_enc:
        return {}
    try:
        return json.loads(decrypt_api_key(row.secret_enc) or "{}")
    except Exception:
        return {}


def _mask_access_key(value: str | None) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= 4:
        return "•" * len(s)
    return s[:4] + "•" * max(8, len(s) - 4)


def _sms_operator_name(user: User) -> str:
    return (user.display_name or "").strip() or (user.phone or "平台管理员")


def _connectivity_label(row: PlatformChannelCredential | None) -> str:
    if not row or row.last_tested_at is None:
        return "未测试"
    when = row.last_tested_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    local = when.astimezone(TZ_SH).strftime("%Y-%m-%d %H:%M")
    badge = "通过" if row.last_test_ok else "失败"
    return f"上次测试 {badge}（{local}）"


def channel_config(db: Session) -> dict[str, Any]:
    """对照 #p12-channel。凭据加密落 platform_channel_credentials.channel=sms_aliyun。"""
    row = _sms_cred_row(db)
    secrets = _sms_secrets(row)
    pub = dict((row.public_json if row else None) or {})
    configured = bool(secrets.get("access_key_id") and secrets.get("access_key_secret"))
    sig = pub.get("default_notify_signature") or "【智营获客】"
    return {
        "credentials_persist": True,
        "configured": configured,
        "access_key_id_masked": pub.get("access_key_id_masked") or _mask_access_key(secrets.get("access_key_id")),
        "default_notify_signature": sig,
        "last_test_at": row.last_tested_at.isoformat() if row and row.last_tested_at else None,
        "last_test_ok": row.last_test_ok if row else None,
        "connectivity_label": _connectivity_label(row),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by_name": pub.get("updated_by_name"),
    }


def save_channel_config(
    db: Session,
    user: User,
    *,
    access_key_id: str | None,
    access_key_secret: str | None,
    default_notify_signature: str | None,
) -> dict[str, Any]:
    incoming_key = (access_key_id or "").strip() if access_key_id is not None else ""
    row = _sms_cred_row(db)
    secrets = _sms_secrets(row)
    if access_key_id is not None and not incoming_key:
        raise HTTPException(status_code=422, detail="AccessKey ID 不能为空")
    key = incoming_key or (secrets.get("access_key_id") or "").strip()
    if not key:
        raise HTTPException(status_code=422, detail="AccessKey ID 不能为空")
    if len(key) < 8:
        raise HTTPException(status_code=422, detail="AccessKey ID 不能为空")
    if not row:
        row = PlatformChannelCredential(id=uuid4(), channel=CHANNEL_SMS_ALIYUN, public_json={})
        db.add(row)
        db.flush()
        secrets = _sms_secrets(row)
    secret = (access_key_secret or "").strip()
    if access_key_secret is not None and not secret and not secrets.get("access_key_secret"):
        raise HTTPException(status_code=422, detail="AccessKey Secret 不能为空")
    if secret:
        secrets["access_key_secret"] = secret
    elif not secrets.get("access_key_secret"):
        raise HTTPException(status_code=422, detail="AccessKey Secret 不能为空")
    secrets["access_key_id"] = key
    row.secret_enc = encrypt_api_key(json.dumps(secrets, ensure_ascii=False))
    sig_raw = (default_notify_signature or "").strip() or "【智营获客】"
    sig = _normalize_signature(sig_raw)
    pub = dict(row.public_json or {})
    pub.update(
        {
            "access_key_id_masked": _mask_access_key(key),
            "default_notify_signature": sig,
            "updated_by_name": _sms_operator_name(user),
        }
    )
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return channel_config(db)


def test_channel_config(db: Session, user: User) -> dict[str, Any]:
    """凭据完备性探测，不调阿里云开放接口。对照 #p12-channel 连通性测试。"""
    row = _sms_cred_row(db)
    secrets = _sms_secrets(row)
    if not secrets.get("access_key_id") or not secrets.get("access_key_secret"):
        raise HTTPException(status_code=422, detail="请先保存")
    ok = True
    row.last_tested_at = datetime.now(TZ_SH)
    row.last_test_ok = ok
    row.updated_by = user.id
    db.commit()
    return channel_config(db)
