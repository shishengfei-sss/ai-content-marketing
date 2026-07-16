"""商机报表服务（v0.8 deal P1-05 销售漏斗）。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Deal, DealCloseAnalysis, DealStageLog, SalesPipeline, SalesPipelineStage
from app.services.crm.crm_scope_service import apply_deal_list_scope


def deal_funnel_report(
    db: Session,
    ctx: TenantContext,
    *,
    pipeline_id: UUID | None = None,
    owner_id: UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    tenant_id = ctx.tenant_id

    # 选定管道（缺省取默认管道）
    pipe_q = db.query(SalesPipeline).filter(SalesPipeline.tenant_id == tenant_id)
    if pipeline_id:
        pipe = pipe_q.filter(uuid_eq(SalesPipeline.id, pipeline_id)).first()
    else:
        pipe = pipe_q.filter(SalesPipeline.is_default.is_(True)).first() or pipe_q.first()
    if not pipe:
        return []

    stages = (
        db.query(SalesPipelineStage)
        .filter(uuid_eq(SalesPipelineStage.pipeline_id, pipe.id), SalesPipelineStage.tenant_id == tenant_id)
        .order_by(SalesPipelineStage.sort_order, SalesPipelineStage.id)
        .all()
    )
    if not stages:
        return []

    # 聚合每阶段的商机数与金额
    base = db.query(Deal).filter(Deal.tenant_id == tenant_id, Deal.deleted_at.is_(None))
    base = apply_deal_list_scope(base, ctx, db)
    if owner_id:
        base = base.filter(uuid_eq(Deal.owner_user_id, owner_id))
    if start_date:
        base = base.filter(Deal.created_at >= start_date)
    if end_date:
        base = base.filter(Deal.created_at < end_date)

    rows = (
        base.with_entities(Deal.stage_id, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0))
        .group_by(Deal.stage_id)
        .all()
    )
    stat_map = {row[0]: (int(row[1] or 0), float(row[2] or 0)) for row in rows}

    total_count = sum(c for c, _ in stat_map.values())
    result: list[dict] = []
    running = 0
    for idx, s in enumerate(stages):
        count, amount = stat_map.get(s.id, (0, 0.0))
        running += count
        # 转化率：当前阶段累计数 / 全部商机数
        conv = round(running / total_count * 100, 1) if total_count else 0.0
        # 阶段间转化率（前一阶段进入本阶段）
        if idx == 0:
            stage_conv = 100.0 if count else 0.0
        else:
            prev_count = result[idx - 1]["deal_count"]
            stage_conv = round(count / prev_count * 100, 1) if prev_count else 0.0
        result.append({
            "pipeline_id": str(pipe.id),
            "pipeline_name": pipe.name,
            "stage_id": str(s.id),
            "stage_name": s.name,
            "sort_order": s.sort_order,
            "probability": s.probability,
            "is_won_stage": s.is_won_stage,
            "is_lost_stage": s.is_lost_stage,
            "color": s.color,
            "deal_count": count,
            "amount": round(amount, 2),
            "conversion_rate": conv,
            "stage_conversion_rate": stage_conv,
            "max_stay_days": s.max_stay_days,
        })
    return result


def deal_forecast_report(
    db: Session,
    ctx: TenantContext,
    *,
    pipeline_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> dict:
    """收入预测：按阶段/负责人汇总金额与加权金额。"""
    tenant_id = ctx.tenant_id
    base = db.query(Deal).filter(
        Deal.tenant_id == tenant_id,
        Deal.deleted_at.is_(None),
        Deal.status.in_(("open", "in_progress")),
    )
    base = apply_deal_list_scope(base, ctx, db)
    if pipeline_id:
        base = base.filter(uuid_eq(Deal.pipeline_id, pipeline_id))
    if owner_id:
        base = base.filter(uuid_eq(Deal.owner_user_id, owner_id))

    deals = base.all()
    total_amount = 0.0
    weighted_amount = 0.0
    by_stage: dict[str, dict] = {}
    by_owner: dict[str, dict] = {}

    for d in deals:
        amt = float(d.amount or 0)
        prob = int(d.probability or 0)
        wgt = round(amt * prob / 100, 2)
        total_amount += amt
        weighted_amount += wgt
        sid = str(d.stage_id)
        by_stage.setdefault(sid, {"stage_id": sid, "deal_count": 0, "amount": 0.0, "weighted_amount": 0.0})
        by_stage[sid]["deal_count"] += 1
        by_stage[sid]["amount"] = round(by_stage[sid]["amount"] + amt, 2)
        by_stage[sid]["weighted_amount"] = round(by_stage[sid]["weighted_amount"] + wgt, 2)
        oid = str(d.owner_user_id)
        by_owner.setdefault(oid, {"owner_user_id": oid, "deal_count": 0, "amount": 0.0, "weighted_amount": 0.0})
        by_owner[oid]["deal_count"] += 1
        by_owner[oid]["amount"] = round(by_owner[oid]["amount"] + amt, 2)
        by_owner[oid]["weighted_amount"] = round(by_owner[oid]["weighted_amount"] + wgt, 2)

    return {
        "deal_count": len(deals),
        "total_amount": round(total_amount, 2),
        "weighted_amount": round(weighted_amount, 2),
        "by_stage": list(by_stage.values()),
        "by_owner": list(by_owner.values()),
    }


def deal_win_loss_report(
    db: Session,
    ctx: TenantContext,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """赢输分析汇总。"""
    tenant_id = ctx.tenant_id
    q = db.query(DealCloseAnalysis).filter(DealCloseAnalysis.tenant_id == tenant_id)
    if start_date:
        q = q.filter(DealCloseAnalysis.created_at >= start_date)
    if end_date:
        q = q.filter(DealCloseAnalysis.created_at < end_date)
    rows = q.order_by(DealCloseAnalysis.created_at.desc()).all()

    by_type: dict[str, int] = {"won": 0, "lost": 0, "abandoned": 0}
    by_reason: dict[str, int] = {}
    items = []
    for r in rows:
        by_type[r.close_type] = by_type.get(r.close_type, 0) + 1
        key = r.reason or "未填写"
        by_reason[key] = by_reason.get(key, 0) + 1
        items.append({
            "id": str(r.id),
            "deal_id": str(r.deal_id),
            "close_type": r.close_type,
            "reason": r.reason,
            "competitor": r.competitor,
            "detail": r.detail,
            "improvement": r.improvement,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {
        "total": len(rows),
        "by_type": by_type,
        "by_reason": [{"reason": k, "count": v} for k, v in sorted(by_reason.items(), key=lambda x: -x[1])],
        "items": items[:50],
    }


def deal_stage_duration_report(
    db: Session,
    ctx: TenantContext,
    *,
    pipeline_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> dict:
    """FR-DR-08：基于 deal_stage_logs 汇总各阶段平均/最大停留天数。"""
    tenant_id = ctx.tenant_id
    now = datetime.now(timezone.utc)

    pipe_q = db.query(SalesPipeline).filter(SalesPipeline.tenant_id == tenant_id)
    if pipeline_id:
        pipe = pipe_q.filter(uuid_eq(SalesPipeline.id, pipeline_id)).first()
    else:
        pipe = pipe_q.filter(SalesPipeline.is_default.is_(True)).first() or pipe_q.first()
    if not pipe:
        return {"pipeline_id": None, "pipeline_name": "", "stages": []}

    stages = (
        db.query(SalesPipelineStage)
        .filter(uuid_eq(SalesPipelineStage.pipeline_id, pipe.id), SalesPipelineStage.tenant_id == tenant_id)
        .order_by(SalesPipelineStage.sort_order, SalesPipelineStage.id)
        .all()
    )

    deal_q = db.query(Deal).filter(
        Deal.tenant_id == tenant_id,
        Deal.deleted_at.is_(None),
        uuid_eq(Deal.pipeline_id, pipe.id),
    )
    deal_q = apply_deal_list_scope(deal_q, ctx, db)
    if owner_id:
        deal_q = deal_q.filter(uuid_eq(Deal.owner_user_id, owner_id))
    deals = deal_q.all()
    if not deals:
        return {
            "pipeline_id": str(pipe.id),
            "pipeline_name": pipe.name,
            "stages": [
                {
                    "stage_id": str(s.id),
                    "stage_name": s.name,
                    "sort_order": s.sort_order,
                    "sample_count": 0,
                    "avg_days": 0.0,
                    "max_days": 0.0,
                    "max_stay_days": s.max_stay_days,
                    "over_sla_count": 0,
                }
                for s in stages
            ],
        }

    deal_ids = [d.id for d in deals]
    logs = (
        db.query(DealStageLog)
        .filter(DealStageLog.tenant_id == tenant_id, DealStageLog.deal_id.in_(deal_ids))
        .order_by(DealStageLog.deal_id, DealStageLog.changed_at)
        .all()
    )
    logs_by_deal: dict[UUID, list[DealStageLog]] = defaultdict(list)
    for log in logs:
        logs_by_deal[log.deal_id].append(log)

    stage_durations: dict[UUID, list[float]] = defaultdict(list)

    def _aware(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    for deal in deals:
        deal_logs = logs_by_deal.get(deal.id, [])
        if not deal_logs:
            start = _aware(deal.created_at) or now
            days = max(0.0, (now - start).total_seconds() / 86400)
            if deal.stage_id:
                stage_durations[deal.stage_id].append(days)
            continue

        for i, log in enumerate(deal_logs):
            start = _aware(log.changed_at) or now
            if i + 1 < len(deal_logs):
                end = _aware(deal_logs[i + 1].changed_at) or now
            else:
                end = now if deal.status == "open" else (_aware(deal.updated_at) or now)
            days = max(0.0, (end - start).total_seconds() / 86400)
            stage_durations[log.to_stage_id].append(days)

    result: list[dict] = []
    for s in stages:
        durs = stage_durations.get(s.id, [])
        avg = round(sum(durs) / len(durs), 1) if durs else 0.0
        max_d = round(max(durs), 1) if durs else 0.0
        sla = s.max_stay_days
        over = sum(1 for d in durs if sla and d > sla)
        result.append(
            {
                "stage_id": str(s.id),
                "stage_name": s.name,
                "sort_order": s.sort_order,
                "sample_count": len(durs),
                "avg_days": avg,
                "max_days": max_d,
                "max_stay_days": sla,
                "over_sla_count": over,
            }
        )

    return {"pipeline_id": str(pipe.id), "pipeline_name": pipe.name, "stages": result}
