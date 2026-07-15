"""合同到期提醒 + 续约商机（v1.0 P1-D）。"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.crm import Contract, Deal, DealStageLog, DealTeamMember
from app.services.crm.notification_service import create_notification

logger = logging.getLogger(__name__)

EXPIRY_WINDOW_DAYS = 30


def _as_utc_date(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def create_renewal_deal_for_contract(db: Session, contract: Contract) -> Deal | None:
    """为合同创建续约商机（幂等：extra_data.renewal_deal_id）。无 TenantContext。"""
    extra = dict(contract.extra_data or {})
    existing = extra.get("renewal_deal_id")
    if existing:
        return db.query(Deal).filter(Deal.id == existing, Deal.tenant_id == contract.tenant_id).first()

    from app.services.crm.deal_service import _resolve_pipeline_and_stage

    pipeline_id, stage_id, probability = _resolve_pipeline_and_stage(
        db, contract.tenant_id, None, None
    )
    from app.services.crm.number_service import generate_number

    amount = float(contract.signed_amount if contract.signed_amount is not None else contract.amount or 0)
    deal = Deal(
        tenant_id=contract.tenant_id,
        deal_number=generate_number(db, contract.tenant_id, "deal"),
        title=f"{contract.title}（续约）",
        customer_id=contract.customer_id,
        contact_id=None,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        amount=amount,
        expected_close_date=None,
        probability=probability,
        status="open",
        source=None,
        description=f"由合同 {contract.contract_number} 到期提醒自动创建",
        next_step=None,
        deal_type="续约",
        priority="medium",
        competitor=None,
        contact_role=None,
        campaign_id=None,
        owner_user_id=contract.owner_user_id,
        territory_id=None,
        extra_data={"source_contract_id": str(contract.id)},
        created_by_user_id=contract.owner_user_id,
    )
    db.add(deal)
    db.flush()
    db.add(
        DealStageLog(
            tenant_id=contract.tenant_id,
            deal_id=deal.id,
            from_stage_id=None,
            to_stage_id=stage_id,
            changed_by_user_id=contract.owner_user_id,
            note="合同续约创建",
        )
    )
    db.add(
        DealTeamMember(
            tenant_id=contract.tenant_id,
            deal_id=deal.id,
            user_id=contract.owner_user_id,
            role="owner",
        )
    )
    extra["renewal_deal_id"] = str(deal.id)
    contract.extra_data = extra
    db.flush()
    return deal


def process_contract_expiry(
    db: Session,
    *,
    window_days: int = EXPIRY_WINDOW_DAYS,
    create_renewal: bool = True,
    batch_size: int = 100,
) -> dict[str, int]:
    """扫描即将到期/已过期合同：发通知、可选建续约商机、标记 expired。"""
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=window_days)
    notified = 0
    renewed = 0
    expired = 0

    rows = (
        db.query(Contract)
        .filter(
            Contract.deleted_at.is_(None),
            Contract.end_date.isnot(None),
            Contract.status.in_(("signed", "executing", "expired")),
        )
        .order_by(Contract.end_date.asc())
        .limit(batch_size * 5)
        .all()
    )

    for contract in rows:
        end_d = _as_utc_date(contract.end_date)
        if end_d is None:
            continue
        extra = dict(contract.extra_data or {})

        # 已过期 → 标记状态
        if end_d < today and contract.status in ("signed", "executing"):
            contract.status = "expired"
            expired += 1

        # 窗口内或已过期未通知
        in_window = today <= end_d <= horizon or end_d < today
        if not in_window:
            continue
        last_notified = extra.get("expiry_notified_on")
        if last_notified == today.isoformat():
            continue

        days_left = (end_d - today).days
        if days_left >= 0:
            title = f"合同即将到期：{contract.title}"
            body = f"{contract.contract_number} 将于 {end_d.isoformat()} 到期（剩 {days_left} 天）"
        else:
            title = f"合同已过期：{contract.title}"
            body = f"{contract.contract_number} 已于 {end_d.isoformat()} 过期（{abs(days_left)} 天）"

        create_notification(
            db,
            tenant_id=contract.tenant_id,
            user_id=contract.owner_user_id,
            title=title,
            body=body,
            category="contract_expiry",
            entity_type="contract",
            entity_id=contract.id,
            commit=False,
        )
        extra["expiry_notified_on"] = today.isoformat()
        contract.extra_data = extra
        notified += 1

        if create_renewal and not extra.get("renewal_deal_id"):
            deal = create_renewal_deal_for_contract(db, contract)
            if deal:
                renewed += 1

    if notified or renewed or expired:
        db.commit()
        logger.info(
            "Contract expiry job: notified=%s renewed=%s expired=%s",
            notified,
            renewed,
            expired,
        )
    return {"notified": notified, "renewed": renewed, "expired": expired}
