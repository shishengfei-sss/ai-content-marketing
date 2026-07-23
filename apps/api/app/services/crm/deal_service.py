"""商机服务（v0.7 CRM-2）。

CRUD + 阶段推进 + 关闭赢单/输单 + 阶段日志 + 转订单。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import (
    Contract,
    Deal,
    DealCloseAnalysis,
    DealLineItem,
    DealStageLog,
    DealTeamMember,
    Order,
    Quote,
    SalesPipelineStage,
)
from app.schemas.crm_deals import (
    DealBatchUpdate,
    DealClose,
    DealCreate,
    DealOut,
    DealStageChange,
    DealUpdate,
    QuoteCreate,
    QuoteLineCreate,
)
from app.services.crm.crm_scope_service import assert_can_mutate_deal, assert_can_view_deal
from app.services.crm.number_service import generate_number
from app.services.crm.pipeline_service import (
    get_default_pipeline,
    get_first_stage,
    get_pipeline,
    get_stage,
    require_pipeline,
    require_stage,
)
from app.services.crm.quote_service import create_quote
from app.services.crm.schema_service import validate_extra_data
from app.services.crm.sales_org_service import apply_creator_org_defaults, apply_owner_org_snapshot, assert_can_assign_owner, get_territory
from app.services.crm.tax_engine import TaxLineIn, compute_tax_lines


def _assert_deal_open(deal: Deal) -> None:
    if deal.status in ("won", "lost", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已关闭的商机不可编辑",
        )


def _assert_deal_convertible(deal: Deal) -> None:
    """转订单：进行中/赢单可转；输单/放弃禁止。"""
    if deal.status in ("lost", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"已{ {'lost': '输单', 'abandoned': '放弃'}[deal.status] }商机不可转订单",
        )


def _assert_deal_quoteable(deal: Deal) -> None:
    """生成报价：进行中/赢单可；输单/放弃禁止。"""
    if deal.status in ("lost", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已关闭（输单/放弃）的商机不可生成报价",
        )


def _first_open_stage(db: Session, tenant_id: UUID, pipeline_id: UUID) -> SalesPipelineStage | None:
    """管道内第一个非终态阶段（用于重开）。"""
    return (
        db.query(SalesPipelineStage)
        .filter(
            SalesPipelineStage.tenant_id == tenant_id,
            uuid_eq(SalesPipelineStage.pipeline_id, pipeline_id),
            SalesPipelineStage.is_active.is_(True),
            SalesPipelineStage.is_won_stage.is_(False),
            SalesPipelineStage.is_lost_stage.is_(False),
            SalesPipelineStage.is_closed_stage.is_(False),
        )
        .order_by(SalesPipelineStage.sort_order, SalesPipelineStage.created_at)
        .first()
    )


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def _stage_entered_map(db: Session, tenant_id: UUID, deals: list[Deal]) -> dict[UUID, datetime]:
    """取各商机进入当前阶段的最近时间。"""
    from sqlalchemy import func

    if not deals:
        return {}
    deal_ids = [d.id for d in deals]
    rows = (
        db.query(DealStageLog.deal_id, DealStageLog.to_stage_id, func.max(DealStageLog.changed_at))
        .filter(DealStageLog.tenant_id == tenant_id, DealStageLog.deal_id.in_(deal_ids))
        .group_by(DealStageLog.deal_id, DealStageLog.to_stage_id)
        .all()
    )
    keyed: dict[tuple[UUID, UUID], datetime] = {(r[0], r[1]): r[2] for r in rows}
    result: dict[UUID, datetime] = {}
    for d in deals:
        entered = keyed.get((d.id, d.stage_id))
        result[d.id] = entered or d.created_at
    return result


def enrich_deals_stage_stay(db: Session, tenant_id: UUID, deals: list[Deal]) -> list[DealOut]:
    if not deals:
        return []
    stage_ids = list({d.stage_id for d in deals})
    stages = (
        db.query(SalesPipelineStage)
        .filter(SalesPipelineStage.tenant_id == tenant_id, SalesPipelineStage.id.in_(stage_ids))
        .all()
    )
    max_map = {s.id: s.max_stay_days for s in stages}
    entered_map = _stage_entered_map(db, tenant_id, deals)
    now = datetime.now(timezone.utc)
    outs: list[DealOut] = []
    for d in deals:
        out = DealOut.model_validate(d)
        entered = entered_map.get(d.id) or d.created_at
        if entered.tzinfo is None:
            entered = entered.replace(tzinfo=timezone.utc)
        stay = max(0, (now - entered).days)
        max_days = max_map.get(d.stage_id)
        out.stage_stay_days = stay
        out.stage_max_stay_days = max_days
        out.is_stage_overdue = bool(max_days and stay > max_days)
        outs.append(out)
    return outs


def deal_to_out(db: Session, tenant_id: UUID, deal: Deal) -> DealOut:
    return enrich_deals_stage_stay(db, tenant_id, [deal])[0]


def _replace_lines(db: Session, deal: Deal, lines) -> None:
    """写入商机明细：共用价税引擎（行未税 + 税额尾差），无头折。"""
    db.query(DealLineItem).filter(DealLineItem.deal_id == deal.id).delete(synchronize_session=False)
    engine_in = [
        TaxLineIn(
            unit_price=ln.unit_price,
            quantity=ln.quantity,
            discount_rate=ln.discount_percent or 0,
            tax_rate=ln.tax_rate,
        )
        for ln in lines
    ]
    result = compute_tax_lines(engine_in, header_discount_rate=None)
    for i, (ln, out) in enumerate(zip(lines, result.lines)):
        db.add(
            DealLineItem(
                tenant_id=deal.tenant_id,
                deal_id=deal.id,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                product_id=ln.product_id,
                product_name=ln.product_name or "",
                description=ln.description,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_percent=ln.discount_percent or 0,
                tax_rate=float(out.tax_rate) if out.tax_rate is not None else ln.tax_rate,
                tax_amount=float(out.tax_amount),
                subtotal=float(out.line_total),
            )
        )
    db.flush()


def _load_deal_lines(db: Session, deal_id: UUID) -> list[DealLineItem]:
    return (
        db.query(DealLineItem)
        .filter(DealLineItem.deal_id == deal_id)
        .order_by(DealLineItem.sort_order, DealLineItem.id)
        .all()
    )


def _recompute_amount_from_lines(db: Session, deal: Deal) -> float:
    total = 0.0
    for line in _load_deal_lines(db, deal.id):
        total += float(line.subtotal)
    return round(total, 2)


def get_deal(db: Session, tenant_id: UUID, deal_id: UUID) -> Deal | None:
    return (
        db.query(Deal)
        .filter(uuid_eq(Deal.id, deal_id), Deal.tenant_id == tenant_id, Deal.deleted_at.is_(None))
        .first()
    )


def require_deal(db: Session, ctx: TenantContext, deal_id: UUID) -> Deal:
    deal = get_deal(db, ctx.tenant_id, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="商机不存在")
    try:
        assert_can_view_deal(
            ctx,
            db,
            deal.owner_user_id,
            deal.territory_id,
            created_by_user_id=deal.created_by_user_id,
            manager_user_id=getattr(deal, "manager_user_id", None),
        )
    except HTTPException as exc:
        if exc.status_code == 403 and _is_deal_team_member(db, ctx, deal.id):
            pass
        else:
            raise
    return deal


def _is_deal_team_member(db: Session, ctx: TenantContext, deal_id: UUID) -> bool:
    from app.models.crm import DealTeamMember

    return (
        db.query(DealTeamMember)
        .filter(
            DealTeamMember.tenant_id == ctx.tenant_id,
            uuid_eq(DealTeamMember.deal_id, deal_id),
            uuid_eq(DealTeamMember.user_id, ctx.user.id),
        )
        .first()
        is not None
    )


def _resolve_pipeline_and_stage(
    db: Session, tenant_id: UUID, pipeline_id: UUID | None, stage_id: UUID | None
) -> tuple[UUID, UUID, int]:
    """返回 (pipeline_id, stage_id, probability)。"""
    if pipeline_id is None:
        pipe = get_default_pipeline(db, tenant_id)
        if not pipe:
            raise HTTPException(status_code=400, detail="租户尚无默认销售管道")
        pipeline_id = pipe.id
    else:
        pipe = get_pipeline(db, tenant_id, pipeline_id)
        if not pipe:
            raise HTTPException(status_code=404, detail="销售管道不存在")
    if stage_id is None:
        stage = get_first_stage(db, tenant_id, pipeline_id)
        if not stage:
            raise HTTPException(status_code=400, detail="管道下无可用阶段")
        stage_id = stage.id
        probability = stage.probability
    else:
        stage = get_stage(db, tenant_id, stage_id)
        if not stage:
            raise HTTPException(status_code=404, detail="管道阶段不存在")
        if stage.pipeline_id != pipeline_id:
            raise HTTPException(status_code=400, detail="阶段不属于该管道")
        probability = stage.probability
    return pipeline_id, stage_id, probability


def create_deal(db: Session, ctx: TenantContext, data: DealCreate, *, commit: bool = True) -> Deal:
    extra = validate_extra_data(db, ctx.tenant_id, "deal", data.extra_data, is_create=True)
    if data.territory_id is not None and not get_territory(db, ctx.tenant_id, data.territory_id):
        raise HTTPException(status_code=404, detail="地区不存在")
    territory_id, manager_user_id = apply_creator_org_defaults(db, ctx, territory_id=data.territory_id)
    pipeline_id, stage_id, default_prob = _resolve_pipeline_and_stage(
        db, ctx.tenant_id, data.pipeline_id, data.stage_id
    )
    probability = data.probability if data.probability is not None else default_prob
    # assign 权限校验
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.deal.assign" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        assert_can_assign_owner(db, ctx, data.owner_user_id)
        owner_user_id = data.owner_user_id
    deal = Deal(
        tenant_id=ctx.tenant_id,
        deal_number=generate_number(db, ctx.tenant_id, "deal"),
        title=data.title.strip(),
        customer_id=data.customer_id,
        contact_id=data.contact_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        amount=data.amount,
        expected_close_date=data.expected_close_date,
        probability=probability,
        status=data.status,
        source=data.source,
        description=data.description,
        next_step=data.next_step,
        deal_type=data.deal_type,
        priority=data.priority or "medium",
        competitor=data.competitor,
        contact_role=data.contact_role,
        campaign_id=data.campaign_id,
        owner_user_id=owner_user_id,
        territory_id=territory_id,
        manager_user_id=manager_user_id,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(deal)
    db.flush()
    # 明细行
    if data.lines:
        _replace_lines(db, deal, data.lines)
        deal.amount = _recompute_amount_from_lines(db, deal)
    # 写入首条阶段日志（from_stage=None）
    db.add(
        DealStageLog(
            tenant_id=ctx.tenant_id,
            deal_id=deal.id,
            from_stage_id=None,
            to_stage_id=stage_id,
            changed_by_user_id=ctx.user.id,
            note="商机创建",
        )
    )
    # 写入负责人为团队成员（role=owner）
    db.add(
        DealTeamMember(
            tenant_id=ctx.tenant_id,
            deal_id=deal.id,
            user_id=owner_user_id,
            role="owner",
        )
    )
    from app.services.crm.entity_team_service import ensure_deal_owner_synced

    ensure_deal_owner_synced(db, ctx, deal.id, owner_user_id)
    if commit:
        db.commit()
        db.refresh(deal)
    return deal


def update_deal(db: Session, ctx: TenantContext, deal: Deal, data: DealUpdate) -> Deal:
    perms = _perm_set(ctx)
    # 除分配负责人外，其它字段变更仅负责人可操作
    mutate_keys = set(data.model_fields_set) - {"owner_user_id"}
    if mutate_keys or (data.owner_user_id is not None and data.owner_user_id != deal.owner_user_id):
        _assert_deal_open(deal)
    if mutate_keys:
        assert_can_mutate_deal(ctx, deal)

    if data.owner_user_id is not None and data.owner_user_id != deal.owner_user_id:
        if "crm.deal.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        assert_can_assign_owner(db, ctx, data.owner_user_id)
        deal.owner_user_id = data.owner_user_id
        snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, data.owner_user_id)
        if data.territory_id is None:
            deal.territory_id = snap_territory
        deal.manager_user_id = snap_manager
        # 同步团队中的 owner 角色
        for row in (
            db.query(DealTeamMember)
            .filter(
                DealTeamMember.tenant_id == ctx.tenant_id,
                uuid_eq(DealTeamMember.deal_id, deal.id),
                DealTeamMember.role == "owner",
            )
            .all()
        ):
            if row.user_id != data.owner_user_id:
                row.role = "member"
        existing_new = (
            db.query(DealTeamMember)
            .filter(
                DealTeamMember.tenant_id == ctx.tenant_id,
                uuid_eq(DealTeamMember.deal_id, deal.id),
                uuid_eq(DealTeamMember.user_id, data.owner_user_id),
            )
            .first()
        )
        if existing_new:
            existing_new.role = "owner"
        else:
            db.add(
                DealTeamMember(
                    tenant_id=ctx.tenant_id,
                    deal_id=deal.id,
                    user_id=data.owner_user_id,
                    role="owner",
                )
            )
        from app.services.crm.entity_team_service import ensure_deal_owner_synced

        ensure_deal_owner_synced(db, ctx, deal.id, data.owner_user_id)
    if data.title is not None:
        deal.title = data.title.strip()
    if data.customer_id is not None:
        deal.customer_id = data.customer_id
    if data.contact_id is not None:
        deal.contact_id = data.contact_id
    if data.pipeline_id is not None:
        # 切换管道时若未提供 stage，则取新管道第一阶段
        require_pipeline(db, ctx.tenant_id, data.pipeline_id)
        if data.stage_id is None:
            first = get_first_stage(db, ctx.tenant_id, data.pipeline_id)
            if first:
                deal.stage_id = first.id
                deal.probability = first.probability
        deal.pipeline_id = data.pipeline_id
    if data.stage_id is not None:
        # 切换阶段走 stage_change 路径，但允许直接 PATCH（也写日志）
        new_stage = require_stage(db, ctx.tenant_id, data.stage_id)
        if new_stage.pipeline_id != deal.pipeline_id:
            raise HTTPException(status_code=400, detail="阶段不属于当前管道")
        if new_stage.id != deal.stage_id:
            db.add(
                DealStageLog(
                    tenant_id=ctx.tenant_id,
                    deal_id=deal.id,
                    from_stage_id=deal.stage_id,
                    to_stage_id=new_stage.id,
                    changed_by_user_id=ctx.user.id,
                )
            )
            deal.stage_id = new_stage.id
            deal.probability = new_stage.probability
    if data.amount is not None:
        deal.amount = data.amount
    if data.expected_close_date is not None:
        deal.expected_close_date = data.expected_close_date
    if data.probability is not None:
        deal.probability = data.probability
    if data.status is not None:
        deal.status = data.status
    if data.source is not None:
        deal.source = data.source
    if data.description is not None:
        deal.description = data.description
    if data.next_step is not None:
        deal.next_step = data.next_step
    if data.deal_type is not None:
        deal.deal_type = data.deal_type
    if data.priority is not None:
        deal.priority = data.priority
    if data.competitor is not None:
        deal.competitor = data.competitor
    if data.contact_role is not None:
        deal.contact_role = data.contact_role
    if data.campaign_id is not None:
        deal.campaign_id = data.campaign_id
    if data.territory_id is not None:
        if not get_territory(db, ctx.tenant_id, data.territory_id):
            raise HTTPException(status_code=404, detail="地区不存在")
        deal.territory_id = data.territory_id
    if data.extra_data is not None:
        merged = dict(deal.extra_data or {})
        merged.update(data.extra_data)
        deal.extra_data = validate_extra_data(db, ctx.tenant_id, "deal", merged)
    if data.lines is not None:
        _replace_lines(db, deal, data.lines)
        deal.amount = _recompute_amount_from_lines(db, deal)
    db.commit()
    db.refresh(deal)
    return deal


def change_stage(
    db: Session, ctx: TenantContext, deal: Deal, data: DealStageChange
) -> Deal:
    assert_can_mutate_deal(ctx, deal)
    _assert_deal_open(deal)
    if deal.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"商机已 {deal.status}，不可改阶段",
        )
    new_stage = require_stage(db, ctx.tenant_id, data.stage_id)
    if new_stage.pipeline_id != deal.pipeline_id:
        raise HTTPException(status_code=400, detail="阶段不属于当前管道")
    if new_stage.id == deal.stage_id:
        return deal  # 幂等
    db.add(
        DealStageLog(
            tenant_id=ctx.tenant_id,
            deal_id=deal.id,
            from_stage_id=deal.stage_id,
            to_stage_id=new_stage.id,
            changed_by_user_id=ctx.user.id,
            note=data.note,
        )
    )
    deal.stage_id = new_stage.id
    deal.probability = new_stage.probability
    from app.services.crm.customer_deal_hooks import apply_deal_stage_progress_to_customer, apply_deal_won_to_customer

    apply_deal_stage_progress_to_customer(db, ctx, deal, to_stage=new_stage)
    # 若进入赢单/输单终态阶段，自动调用 close_deal
    if new_stage.is_won_stage:
        _close_deal_internal(db, ctx, deal, status_value="won", amount=float(deal.amount))
        apply_deal_won_to_customer(db, ctx, deal)
    elif new_stage.is_lost_stage:
        _close_deal_internal(
            db, ctx, deal, status_value="lost", amount=None, loss_reason=data.note
        )
    db.commit()
    db.refresh(deal)
    return deal


def _close_deal_internal(
    db: Session,
    ctx: TenantContext,
    deal: Deal,
    *,
    status_value: str,
    amount: float | None,
    loss_reason: str | None = None,
    reason: str | None = None,
    competitor: str | None = None,
    detail: str | None = None,
    improvement: str | None = None,
) -> None:
    """内部关闭逻辑（不 commit，由调用方控制事务）。"""
    if status_value not in ("won", "lost", "abandoned"):
        raise HTTPException(status_code=400, detail=f"不支持的关闭状态: {status_value}")
    if status_value == "won" and amount is None:
        raise HTTPException(status_code=400, detail="赢单必填实际金额")
    if status_value == "lost" and not (loss_reason or reason):
        raise HTTPException(status_code=400, detail="输单必填输单原因")
    deal.status = status_value
    deal.closed_at = datetime.now(timezone.utc)
    if amount is not None:
        deal.amount = amount
    final_reason = reason or loss_reason
    if final_reason is not None:
        deal.loss_reason = final_reason
    if competitor:
        deal.competitor = competitor
    db.add(
        DealCloseAnalysis(
            tenant_id=ctx.tenant_id,
            deal_id=deal.id,
            close_type=status_value,
            reason=final_reason,
            competitor=competitor or deal.competitor,
            detail=detail,
            improvement=improvement,
        )
    )


def close_deal(db: Session, ctx: TenantContext, deal: Deal, data: DealClose) -> Deal:
    assert_can_mutate_deal(ctx, deal)
    if deal.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"商机已 {deal.status}，不可再次关闭",
        )
    if "crm.deal.close" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限关闭商机")
    _close_deal_internal(
        db,
        ctx,
        deal,
        status_value=data.status,
        amount=data.amount,
        loss_reason=data.loss_reason,
        reason=data.reason,
        competitor=data.competitor,
        detail=data.detail,
        improvement=data.improvement,
    )
    if data.status == "won":
        from app.services.crm.customer_deal_hooks import apply_deal_won_to_customer

        apply_deal_won_to_customer(db, ctx, deal)
    db.commit()
    db.refresh(deal)
    return deal


def reopen_deal(db: Session, ctx: TenantContext, deal: Deal) -> Deal:
    """主管重开已关闭商机：status→open，回退到管道首个非终态阶段。"""
    if "crm.deal.reopen" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限重开商机")
    if deal.status not in ("won", "lost", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仅已关闭的商机可重开",
        )
    open_stage = _first_open_stage(db, ctx.tenant_id, deal.pipeline_id)
    if not open_stage:
        raise HTTPException(status_code=400, detail="管道无可用的进行中阶段，无法重开")
    from_stage_id = deal.stage_id
    deal.status = "open"
    deal.closed_at = None
    if open_stage.id != deal.stage_id:
        deal.stage_id = open_stage.id
        deal.probability = open_stage.probability
    db.add(
        DealStageLog(
            tenant_id=ctx.tenant_id,
            deal_id=deal.id,
            from_stage_id=from_stage_id,
            to_stage_id=deal.stage_id,
            changed_by_user_id=ctx.user.id,
            note="重开商机",
        )
    )
    db.commit()
    db.refresh(deal)
    return deal


def list_stage_logs(
    db: Session, tenant_id: UUID, deal_id: UUID
) -> list[DealStageLog]:
    return (
        db.query(DealStageLog)
        .filter(
            DealStageLog.tenant_id == tenant_id,
            uuid_eq(DealStageLog.deal_id, deal_id),
        )
        .order_by(DealStageLog.changed_at)
        .all()
    )


def soft_delete_deal(db: Session, ctx: TenantContext, deal: Deal) -> None:
    assert_can_mutate_deal(ctx, deal)
    if deal.status in ("won", "lost", "abandoned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已关闭的商机不可删除，请保留记录",
        )
    related = []
    if (
        db.query(Quote.id)
        .filter(Quote.deal_id == deal.id, Quote.deleted_at.is_(None))
        .first()
    ):
        related.append("报价")
    if (
        db.query(Contract.id)
        .filter(Contract.deal_id == deal.id, Contract.deleted_at.is_(None))
        .first()
    ):
        related.append("合同")
    if (
        db.query(Order.id)
        .filter(Order.deal_id == deal.id, Order.deleted_at.is_(None))
        .first()
    ):
        related.append("订单")
    if related:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"商机已关联{'/'.join(related)}，不可删除",
        )
    deal.deleted_at = datetime.now(timezone.utc)
    db.commit()


def _generate_order_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "order")


def generate_quote_from_deal(db: Session, ctx: TenantContext, deal: Deal) -> Quote:
    """商机明细 → 一键生成报价单（草稿）。进行中/赢单可生成；输单/放弃不可。"""
    if "crm.quote.edit" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限创建报价单")
    _assert_deal_quoteable(deal)
    lines = _load_deal_lines(db, deal.id)
    quote_lines = [
        QuoteLineCreate(
            product_id=ln.product_id,
            name=ln.product_name or "明细",
            unit=ln.unit,
            quantity=float(ln.quantity),
            unit_price=float(ln.unit_price),
            discount_rate=float(ln.discount_percent or 0),
            tax_rate=float(ln.tax_rate) if ln.tax_rate is not None else None,
            tax_amount=float(ln.tax_amount) if ln.tax_amount is not None else None,
            line_total=float(ln.subtotal),
            sort_order=ln.sort_order,
        )
        for ln in lines
    ]
    data = QuoteCreate(
        deal_id=deal.id,
        customer_id=deal.customer_id,
        contact_id=deal.contact_id,
        subject=f"{deal.title} - 报价",
        lines=quote_lines,
        owner_user_id=deal.owner_user_id,
    )
    return create_quote(db, ctx, data)


def convert_deal_to_order(db: Session, ctx: TenantContext, deal: Deal) -> Order:
    """商机转订单（最短路径）。

    生成 draft 订单：source=deal, amount=deal.amount, 无明细。
    业务规则 BR-ORDER-01：customer_id 必填（来自商机）。
    进行中/赢单可转；输单/放弃不可。
    """
    perms = _perm_set(ctx)
    if not ({"crm.order.convert", "crm.order.create", "crm.deal.convert"} & perms):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限转订单")
    _assert_deal_convertible(deal)
    order = Order(
        tenant_id=ctx.tenant_id,
        order_number=_generate_order_number(db, ctx.tenant_id),
        title=f"由商机「{deal.title}」生成",
        customer_id=deal.customer_id,
        contact_id=deal.contact_id,
        deal_id=deal.id,
        quote_id=None,
        contract_id=None,
        source="deal",
        order_date=datetime.now(timezone.utc),
        amount=float(deal.amount),
        status="draft",
        owner_user_id=deal.owner_user_id,
        territory_id=deal.territory_id,
        extra_data={},
        created_by_user_id=ctx.user.id,
    )
    db.add(order)
    db.flush()
    # 标记商机的 converted_order_id（一对多，仅记最近一次；订单可重复生成）
    deal.converted_order_id = order.id
    db.commit()
    db.refresh(order)
    return order


# ============================================================
# v0.8 P1-06 多人协作团队
# ============================================================

def list_team_members(db: Session, ctx: TenantContext, deal: Deal) -> list[DealTeamMember]:
    return (
        db.query(DealTeamMember)
        .filter(DealTeamMember.tenant_id == ctx.tenant_id, uuid_eq(DealTeamMember.deal_id, deal.id))
        .order_by(DealTeamMember.joined_at)
        .all()
    )


def add_team_member(db: Session, ctx: TenantContext, deal: Deal, user_id: UUID, role: str = "member") -> DealTeamMember:
    if "crm.deal.edit" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理商机团队")
    _assert_deal_open(deal)
    assert_can_mutate_deal(ctx, deal)
    from app.models import User

    user = db.query(User).filter(User.id == user_id, User.tenant_id == ctx.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = (
        db.query(DealTeamMember)
        .filter(
            DealTeamMember.tenant_id == ctx.tenant_id,
            uuid_eq(DealTeamMember.deal_id, deal.id),
            uuid_eq(DealTeamMember.user_id, user_id),
        )
        .first()
    )
    if existing:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing
    member = DealTeamMember(
        tenant_id=ctx.tenant_id,
        deal_id=deal.id,
        user_id=user_id,
        role=role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_team_member(db: Session, ctx: TenantContext, deal: Deal, member_id: UUID) -> None:
    if "crm.deal.edit" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理商机团队")
    _assert_deal_open(deal)
    assert_can_mutate_deal(ctx, deal)
    member = (
        db.query(DealTeamMember)
        .filter(DealTeamMember.tenant_id == ctx.tenant_id, DealTeamMember.id == member_id)
        .first()
    )
    if not member or str(member.deal_id) != str(deal.id):
        raise HTTPException(status_code=404, detail="团队成员不存在")
    if member.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不可移除负责人")
    db.delete(member)
    db.commit()


def clone_deal(db: Session, ctx: TenantContext, deal: Deal) -> Deal:
    """一键复制商机（重置阶段/状态，保留明细与客户信息）。"""
    if "crm.deal.create" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限创建商机")
    first_stage = get_first_stage(db, ctx.tenant_id, deal.pipeline_id)
    if not first_stage:
        raise HTTPException(status_code=400, detail="管道无可用阶段")
    from app.schemas.crm_deals import DealLineItemCreate

    lines = _load_deal_lines(db, deal.id)
    data = DealCreate(
        title=f"{deal.title} (复制)",
        customer_id=deal.customer_id,
        contact_id=deal.contact_id,
        pipeline_id=deal.pipeline_id,
        stage_id=first_stage.id,
        amount=float(deal.amount),
        expected_close_date=deal.expected_close_date,
        probability=first_stage.probability,
        status="open",
        source=deal.source,
        description=deal.description,
        next_step=deal.next_step,
        deal_type=deal.deal_type,
        priority=deal.priority,
        competitor=deal.competitor,
        contact_role=deal.contact_role,
        campaign_id=deal.campaign_id,
        territory_id=deal.territory_id,
        lines=[
            DealLineItemCreate(
                product_id=ln.product_id,
                product_name=ln.product_name,
                description=ln.description,
                unit=ln.unit,
                quantity=float(ln.quantity),
                unit_price=float(ln.unit_price),
                discount_percent=float(ln.discount_percent or 0),
                tax_rate=float(ln.tax_rate) if ln.tax_rate is not None else None,
                tax_amount=float(ln.tax_amount) if ln.tax_amount is not None else None,
                subtotal=float(ln.subtotal),
                sort_order=ln.sort_order,
            )
            for ln in lines
        ],
    )
    return create_deal(db, ctx, data)


def batch_update_deals(db: Session, ctx: TenantContext, data: DealBatchUpdate) -> int:
    if "crm.deal.edit" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限编辑商机")
    updated = 0
    for deal_id in data.deal_ids:
        deal = get_deal(db, ctx.tenant_id, deal_id)
        if not deal:
            continue
        try:
            require_deal(db, ctx, deal_id)
        except HTTPException:
            continue
        patch_fields: dict = {}
        if "owner_user_id" in data.model_fields_set and data.owner_user_id is not None:
            patch_fields["owner_user_id"] = data.owner_user_id
        if "stage_id" in data.model_fields_set and data.stage_id is not None:
            patch_fields["stage_id"] = data.stage_id
        if "status" in data.model_fields_set and data.status is not None:
            patch_fields["status"] = data.status
        if not patch_fields:
            continue
        try:
            update_deal(db, ctx, deal, DealUpdate(**patch_fields))
            updated += 1
        except HTTPException:
            continue
    return updated
