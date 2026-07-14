"""跨模块：商机 → 客户价值/时间线 Hook。"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import CrmActivity, Customer, Deal, SalesPipelineStage


def apply_deal_won_to_customer(db: Session, ctx: TenantContext, deal: Deal) -> None:
    """赢单幂等更新客户 total_revenue / last_deal_date，并写跟进。

    幂等：同一 deal 仅累加一次（用 extra_data._won_revenue_applied deal_id 集合）。
    """
    if not deal.customer_id:
        return
    customer = (
        db.query(Customer)
        .filter(uuid_eq(Customer.id, deal.customer_id), Customer.tenant_id == ctx.tenant_id, Customer.deleted_at.is_(None))
        .first()
    )
    if not customer:
        return
    extra = dict(customer.extra_data or {})
    applied = set(extra.get("_won_revenue_deal_ids") or [])
    deal_key = str(deal.id)
    if deal_key in applied:
        return
    amount = Decimal(str(deal.amount or 0))
    current = Decimal(str(customer.total_revenue or 0))
    customer.total_revenue = current + amount
    customer.last_deal_date = date.today()
    applied.add(deal_key)
    extra["_won_revenue_deal_ids"] = list(applied)
    customer.extra_data = extra
    db.add(
        CrmActivity(
            tenant_id=ctx.tenant_id,
            customer_id=customer.id,
            deal_id=deal.id,
            activity_type="other",
            subject="成交商机",
            content=f"成交商机「{deal.title}」¥{amount}",
            entity_type="customer",
            entity_id=str(customer.id),
            created_by_user_id=ctx.user.id,
        )
    )
    if customer.owner_user_id and customer.owner_user_id != ctx.user.id:
        from app.services.crm.notification_service import create_notification

        create_notification(
            db,
            tenant_id=ctx.tenant_id,
            user_id=customer.owner_user_id,
            title="客户商机已赢单",
            body=f"「{customer.company_name}」关联商机「{deal.title}」已赢单 ¥{amount}",
            category="deal_won",
            entity_type="customer",
            entity_id=customer.id,
            commit=False,
        )


def apply_deal_stage_progress_to_customer(
    db: Session,
    ctx: TenantContext,
    deal: Deal,
    *,
    to_stage: SalesPipelineStage,
) -> None:
    """阶段推进写入客户时间线。"""
    if not deal.customer_id:
        return
    db.add(
        CrmActivity(
            tenant_id=ctx.tenant_id,
            customer_id=deal.customer_id,
            deal_id=deal.id,
            activity_type="other",
            subject="商机推进",
            content=f"商机「{deal.title}」推进到【{to_stage.name}】",
            entity_type="customer",
            entity_id=str(deal.customer_id),
            created_by_user_id=ctx.user.id,
        )
    )
