"""P06 商户支付进件（平台端）。对照 06#p06-onboarding-list · #p06e · #p02b-payment。"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import Tenant, User
from app.models.shop import ShopMerchantAccount, ShopOnboardingApplication, ShopPaymentOnboarding
from app.services.shop.a15_payment_onboarding_service import (
    STATUS_APPROVED,
    STATUS_LABELS,
    STATUS_NOT_SUBMITTED,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    _entity_from_merchant,
    _get_or_create_row,
    _mask_account,
    _mask_sub_mch,
    _now,
)

logger = logging.getLogger(__name__)

SUB_MCH_RE = re.compile(r"^\d{8,12}$")
ENTITY_LABELS = {
    "personal": "个人",
    "individual_business": "个体",
    "enterprise": "企业",
}


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _meta(row: ShopPaymentOnboarding) -> dict[str, Any]:
    snap = _json_dict(row.entity_snapshot_json)
    return _json_dict(snap.get("_meta"))


def _write_meta(row: ShopPaymentOnboarding, meta: dict[str, Any]) -> None:
    snap = _json_dict(row.entity_snapshot_json)
    snap["_meta"] = meta
    row.entity_snapshot_json = snap


def _append_event(row: ShopPaymentOnboarding, event: str) -> None:
    meta = _meta(row)
    events = list(meta.get("timeline") or [])
    events.append({"at": _now().isoformat(), "event": event})
    meta["timeline"] = events
    meta["last_refresh_at"] = _now().isoformat()
    _write_meta(row, meta)


def _public_entity(row: ShopPaymentOnboarding | None, merchant: ShopMerchantAccount) -> dict[str, Any]:
    if row and row.entity_snapshot_json:
        ent = _json_dict(row.entity_snapshot_json)
        ent.pop("_meta", None)
        if ent.get("legal_name") or ent.get("entity_type"):
            return ent
    return _entity_from_merchant(merchant)


def _status_of(row: ShopPaymentOnboarding | None) -> str:
    if row is None:
        return STATUS_NOT_SUBMITTED
    return row.onboarding_status or STATUS_NOT_SUBMITTED


def _item(
    merchant: ShopMerchantAccount,
    row: ShopPaymentOnboarding | None,
    tenant: Tenant | None,
    manager: User | None,
    *,
    reveal: bool = False,
) -> dict[str, Any]:
    status = _status_of(row)
    entity = _public_entity(row, merchant)
    meta = _meta(row) if row else {}
    actions: list[str] = ["view_materials"]
    if status == STATUS_SUBMITTED:
        actions.extend(["refresh", "submit_wechat", "approve", "reject"])
    if status == STATUS_REJECTED:
        actions.extend(["refresh", "notify"])
    if status == STATUS_NOT_SUBMITTED:
        actions.append("remind")
    return {
        "tenant_id": str(merchant.tenant_id),
        "merchant_id": str(merchant.id),
        "merchant_name": merchant.display_name or merchant.legal_name or (tenant.name if tenant else ""),
        "tenant_name": tenant.name if tenant else "",
        "entity_type": merchant.entity_type,
        "entity_type_label": ENTITY_LABELS.get(merchant.entity_type, merchant.entity_type),
        "onboarding_status": status,
        "onboarding_status_label": STATUS_LABELS.get(status, status),
        "wx_sub_mch_id_masked": _mask_sub_mch(row.wx_sub_mch_id) if row and status == STATUS_APPROVED else None,
        "settlement_bank": row.settlement_bank if row else None,
        "settlement_account_masked": _mask_account(row.settlement_account) if row else None,
        "settlement_account": (row.settlement_account if reveal and row else None),
        "settlement_account_name": row.settlement_account_name if row else None,
        "submitted_at": _iso(row.submitted_at) if row else None,
        "approved_at": _iso(row.approved_at) if row else None,
        "account_manager_user_id": str(merchant.account_manager_user_id)
        if merchant.account_manager_user_id
        else None,
        "account_manager_name": (manager.display_name or manager.phone) if manager else None,
        "reject_reason": row.reject_reason if row and status == STATUS_REJECTED else None,
        "remark": row.remark if row else None,
        "mch_name": row.mch_name if row else None,
        "wx_apply_no": meta.get("wx_apply_no"),
        "last_refresh_at": meta.get("last_refresh_at"),
        "timeline": meta.get("timeline") or [],
        "entity": entity,
        "actions": actions,
    }


def _base_query(db: Session):
    return (
        db.query(ShopMerchantAccount, ShopPaymentOnboarding, Tenant, User)
        .outerjoin(
            ShopPaymentOnboarding,
            ShopPaymentOnboarding.tenant_id == ShopMerchantAccount.tenant_id,
        )
        .outerjoin(Tenant, Tenant.id == ShopMerchantAccount.tenant_id)
        .outerjoin(User, User.id == ShopMerchantAccount.account_manager_user_id)
        .filter(ShopMerchantAccount.status != "closed")
    )


def _apply_filters(
    query,
    *,
    status: str | None,
    q: str | None,
    entity_type: str | None,
    account_manager_user_id: str | None,
):
    if status:
        if status == STATUS_NOT_SUBMITTED:
            query = query.filter(
                or_(
                    ShopPaymentOnboarding.id.is_(None),
                    ShopPaymentOnboarding.onboarding_status == STATUS_NOT_SUBMITTED,
                )
            )
        else:
            query = query.filter(ShopPaymentOnboarding.onboarding_status == status)
    if entity_type:
        query = query.filter(ShopMerchantAccount.entity_type == entity_type)
    if account_manager_user_id == "none":
        query = query.filter(ShopMerchantAccount.account_manager_user_id.is_(None))
    elif account_manager_user_id:
        try:
            mid = UUID(account_manager_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="商家管家无效") from exc
        query = query.filter(uuid_eq(ShopMerchantAccount.account_manager_user_id, mid))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ShopMerchantAccount.display_name.ilike(like),
                ShopMerchantAccount.legal_name.ilike(like),
                Tenant.name.ilike(like),
                ShopPaymentOnboarding.wx_sub_mch_id.ilike(like),
            )
        )
    return query


def status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(ShopPaymentOnboarding.onboarding_status, func.count(ShopPaymentOnboarding.id))
        .join(
            ShopMerchantAccount,
            ShopMerchantAccount.tenant_id == ShopPaymentOnboarding.tenant_id,
        )
        .filter(ShopMerchantAccount.status != "closed")
        .group_by(ShopPaymentOnboarding.onboarding_status)
        .all()
    )
    by = {s: int(c) for s, c in rows}
    merchants = (
        db.query(func.count(ShopMerchantAccount.id))
        .filter(ShopMerchantAccount.status != "closed")
        .scalar()
        or 0
    )
    onboard_rows = sum(by.values())
    not_sub = int(by.get(STATUS_NOT_SUBMITTED, 0)) + max(0, int(merchants) - onboard_rows)
    return {
        "all": int(merchants),
        STATUS_NOT_SUBMITTED: not_sub,
        STATUS_SUBMITTED: int(by.get(STATUS_SUBMITTED, 0)),
        STATUS_REJECTED: int(by.get(STATUS_REJECTED, 0)),
        STATUS_APPROVED: int(by.get(STATUS_APPROVED, 0)),
    }


def list_onboardings(
    db: Session,
    *,
    status: str | None,
    q: str | None,
    entity_type: str | None,
    account_manager_user_id: str | None,
    sort_by: str | None,
    sort_dir: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    query = _apply_filters(
        _base_query(db),
        status=status,
        q=q,
        entity_type=entity_type,
        account_manager_user_id=account_manager_user_id,
    )
    total = query.count()
    col = ShopPaymentOnboarding.submitted_at
    if sort_by == "merchant":
        col = ShopMerchantAccount.display_name
    elif sort_by in ("submitted_at", "no", None, ""):
        col = ShopPaymentOnboarding.submitted_at
    order = col.asc() if (sort_dir or "").lower() == "asc" else col.desc()
    rows = (
        query.order_by(order, ShopMerchantAccount.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for m, o, t, u in rows:
        manager = u
        if manager is None and m.account_manager_user_id:
            manager = (
                db.query(User).filter(uuid_eq(User.id, m.account_manager_user_id)).first()
            )
        try:
            items.append(_item(m, o, t, manager))
        except Exception:
            logger.exception("payment onboarding list item failed tenant=%s", m.tenant_id)
            items.append(
                {
                    "tenant_id": str(m.tenant_id),
                    "merchant_id": str(m.id),
                    "merchant_name": m.display_name or m.legal_name or (t.name if t else ""),
                    "tenant_name": t.name if t else "",
                    "entity_type": m.entity_type,
                    "entity_type_label": ENTITY_LABELS.get(m.entity_type, m.entity_type),
                    "onboarding_status": STATUS_NOT_SUBMITTED,
                    "onboarding_status_label": STATUS_LABELS.get(STATUS_NOT_SUBMITTED, STATUS_NOT_SUBMITTED),
                    "wx_sub_mch_id_masked": None,
                    "settlement_bank": None,
                    "settlement_account_masked": None,
                    "settlement_account": None,
                    "settlement_account_name": None,
                    "submitted_at": None,
                    "approved_at": None,
                    "account_manager_user_id": str(m.account_manager_user_id)
                    if m.account_manager_user_id
                    else None,
                    "account_manager_name": (manager.display_name or manager.phone) if manager else None,
                    "reject_reason": None,
                    "remark": None,
                    "mch_name": None,
                    "wx_apply_no": None,
                    "last_refresh_at": None,
                    "timeline": [],
                    "entity": {},
                    "actions": ["view_materials"],
                }
            )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": status_counts(db),
        "account_managers": list_account_managers(db),
    }


def get_detail(db: Session, tenant_id: UUID, *, reveal: bool = False) -> dict[str, Any]:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if not merchant:
        raise HTTPException(status_code=404, detail="商家不存在")
    row = (
        db.query(ShopPaymentOnboarding)
        .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, tenant_id))
        .first()
    )
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    manager = None
    if merchant.account_manager_user_id:
        manager = db.query(User).filter(uuid_eq(User.id, merchant.account_manager_user_id)).first()
    item = _item(merchant, row, tenant, manager, reveal=reveal)
    files: dict[str, Any] = {}
    if merchant.onboarding_application_id:
        app_row = (
            db.query(ShopOnboardingApplication)
            .filter(uuid_eq(ShopOnboardingApplication.id, merchant.onboarding_application_id))
            .first()
        )
        if app_row:
            files = _json_dict(app_row.qualification_files)
    item["qualification_files"] = files
    return item


def list_account_managers(db: Session) -> list[dict[str, str]]:
    rows = (
        db.query(User)
        .join(ShopMerchantAccount, ShopMerchantAccount.account_manager_user_id == User.id)
        .filter(ShopMerchantAccount.status != "closed")
        .distinct()
        .all()
    )
    return [{"id": str(u.id), "name": (u.display_name or u.phone or "")} for u in rows]


def _require_row(db: Session, tenant_id: UUID) -> tuple[ShopMerchantAccount, ShopPaymentOnboarding]:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if not merchant:
        raise HTTPException(status_code=404, detail="商家不存在")
    row = (
        db.query(ShopPaymentOnboarding)
        .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, tenant_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=422, detail="商家尚未提交进件材料")
    return merchant, row


def submit_wechat(db: Session, tenant_id: UUID) -> dict[str, Any]:
    _, row = _require_row(db, tenant_id)
    if row.onboarding_status != STATUS_SUBMITTED:
        raise HTTPException(status_code=422, detail="仅审核中可代提微信")
    if not row.settlement_bank or not row.settlement_account:
        raise HTTPException(status_code=422, detail="材料不完整")
    apply_no = f"WX{_now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    meta = _meta(row)
    meta["wx_apply_no"] = apply_no
    _write_meta(row, meta)
    _append_event(row, f"平台代调微信进件 API · 申请单 {apply_no}")
    db.commit()
    return get_detail(db, tenant_id)


def refresh_status(db: Session, tenant_id: UUID) -> dict[str, Any]:
    _, row = _require_row(db, tenant_id)
    if row.onboarding_status not in (STATUS_SUBMITTED, STATUS_REJECTED):
        raise HTTPException(status_code=422, detail="当前状态不可刷新")
    _append_event(row, "刷新微信状态 · 仍审核中")
    db.commit()
    return get_detail(db, tenant_id)


def approve(db: Session, tenant_id: UUID, *, wx_sub_mch_id: str) -> dict[str, Any]:
    merchant, row = _require_row(db, tenant_id)
    if row.onboarding_status != STATUS_SUBMITTED:
        raise HTTPException(status_code=422, detail="仅审核中可开通")
    mch = re.sub(r"\s+", "", wx_sub_mch_id or "")
    if not SUB_MCH_RE.match(mch):
        raise HTTPException(status_code=422, detail="子商户号须为 8–12 位数字")
    row.onboarding_status = STATUS_APPROVED
    row.wx_sub_mch_id = mch
    row.mch_name = row.mch_name or merchant.legal_name or merchant.display_name
    row.approved_at = _now()
    row.reject_reason = None
    _append_event(row, f"微信审核通过 · 子商户号下发 {_mask_sub_mch(mch)}")
    db.commit()
    return get_detail(db, tenant_id)


def reject(db: Session, tenant_id: UUID, *, reason: str) -> dict[str, Any]:
    _, row = _require_row(db, tenant_id)
    if row.onboarding_status != STATUS_SUBMITTED:
        raise HTTPException(status_code=422, detail="仅审核中可驳回")
    text = (reason or "").strip()
    if len(text) < 4:
        raise HTTPException(status_code=422, detail="驳回原因至少 4 字")
    row.onboarding_status = STATUS_REJECTED
    row.reject_reason = text
    row.wx_sub_mch_id = None
    row.approved_at = None
    _append_event(row, f"已驳回：{text}")
    db.commit()
    return get_detail(db, tenant_id)


def reveal_sensitive(db: Session, tenant_id: UUID) -> dict[str, Any]:
    _, row = _require_row(db, tenant_id)
    _append_event(row, "查看结算账号明文")
    db.commit()
    return get_detail(db, tenant_id, reveal=True)


def notify_merchant(db: Session, tenant_id: UUID) -> dict[str, Any]:
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if not merchant:
        raise HTTPException(status_code=404, detail="商家不存在")
    row = (
        db.query(ShopPaymentOnboarding)
        .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, tenant_id))
        .first()
    )
    if not row:
        row = _get_or_create_row(db, tenant_id, merchant)
    if row.onboarding_status not in (STATUS_REJECTED, STATUS_NOT_SUBMITTED):
        raise HTTPException(status_code=422, detail="仅未提交或已驳回可通知商家")
    _append_event(row, "已通知商家补充材料")
    db.commit()
    return {"ok": True, "message": "已通知商家（可在支付与进件补充重提）"}


def export_csv(
    db: Session,
    *,
    status: str | None,
    q: str | None,
    entity_type: str | None,
    account_manager_user_id: str | None,
    sort_by: str | None = "submitted_at",
    sort_dir: str | None = "desc",
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_onboardings(
        db,
        status=status,
        q=q,
        entity_type=entity_type,
        account_manager_user_id=account_manager_user_id,
        sort_by=sort_by or "submitted_at",
        sort_dir=sort_dir or "desc",
        page=1,
        page_size=5000,
    )
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["商家", "主体", "进件状态", "子商户号", "结算账户", "最近提交", "商家管家"]
    col_map = {
        "merchant_name": ["商家"],
        "entity_type": ["主体"],
        "onboarding_status": ["进件状态"],
        "wx_sub_mch_id": ["子商户号"],
        "settlement": ["结算账户"],
        "submitted_at": ["最近提交"],
        "account_manager_name": ["商家管家"],
    }
    if columns:
        headers: list[str] = []
        seen: set[str] = set()
        for key in columns:
            for h in col_map.get(key, []):
                if h not in seen:
                    seen.add(h)
                    headers.append(h)
        headers = headers or default_headers
    else:
        headers = default_headers
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in data["items"]:
        values = {
            "商家": it.get("merchant_name") or "",
            "主体": it.get("entity_type_label") or "",
            "进件状态": it.get("onboarding_status_label") or "",
            "子商户号": it.get("wx_sub_mch_id_masked") or "",
            "结算账户": f"{it.get('settlement_bank') or ''} {it.get('settlement_account_masked') or ''}".strip(),
            "最近提交": (it.get("submitted_at") or "")[:16].replace("T", " "),
            "商家管家": it.get("account_manager_name") or "未分配",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_payment_onboarding_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import PaymentOnboardingExportRequest
    from app.services.shop import export_task_service

    body = body or PaymentOnboardingExportRequest()
    filters = {
        "status": body.status,
        "q": body.q,
        "entity_type": body.entity_type,
        "account_manager_user_id": body.account_manager_user_id,
        "sort_by": body.sort_by,
        "sort_dir": body.sort_dir,
        "columns": body.columns,
    }
    csv_text = export_csv(
        db,
        status=body.status,
        q=body.q,
        entity_type=body.entity_type,
        account_manager_user_id=body.account_manager_user_id,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="payment_onboarding",
        file_name="shop-payment-onboarding.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_payment_onboarding_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "payment_onboarding")


def read_payment_onboarding_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "payment_onboarding")


def channel_config(db: Session, base_url: str) -> dict[str, Any]:
    from app.services.shop import p06_channel_credential_service as cred

    return cred.channel_config(db, base_url)
