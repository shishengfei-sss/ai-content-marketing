"""销售管道与阶段服务（v0.7 CRM-2）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Deal, SalesPipeline, SalesPipelineStage
from app.schemas.crm_deals import (
    PipelineCreate,
    PipelineStageCreate,
    PipelineStageUpdate,
    PipelineUpdate,
)


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def list_pipelines(db: Session, tenant_id: UUID, include_inactive: bool = False) -> list[SalesPipeline]:
    q = db.query(SalesPipeline).filter(SalesPipeline.tenant_id == tenant_id)
    if not include_inactive:
        q = q.filter(SalesPipeline.is_active.is_(True))
    pipes = q.order_by(SalesPipeline.is_default.desc(), SalesPipeline.created_at).all()
    # 预加载阶段
    for p in pipes:
        _ = p.stages if hasattr(p, "stages") else None  # noqa: B018
    return pipes


def get_pipeline(db: Session, tenant_id: UUID, pipeline_id: UUID) -> SalesPipeline | None:
    return (
        db.query(SalesPipeline)
        .filter(uuid_eq(SalesPipeline.id, pipeline_id), SalesPipeline.tenant_id == tenant_id)
        .first()
    )


def get_default_pipeline(db: Session, tenant_id: UUID) -> SalesPipeline | None:
    return (
        db.query(SalesPipeline)
        .filter(SalesPipeline.tenant_id == tenant_id, SalesPipeline.is_default.is_(True))
        .first()
    )


def list_stages(db: Session, tenant_id: UUID, pipeline_id: UUID) -> list[SalesPipelineStage]:
    return (
        db.query(SalesPipelineStage)
        .filter(
            SalesPipelineStage.tenant_id == tenant_id,
            uuid_eq(SalesPipelineStage.pipeline_id, pipeline_id),
        )
        .order_by(SalesPipelineStage.sort_order, SalesPipelineStage.created_at)
        .all()
    )


def get_stage(db: Session, tenant_id: UUID, stage_id: UUID) -> SalesPipelineStage | None:
    return (
        db.query(SalesPipelineStage)
        .filter(
            uuid_eq(SalesPipelineStage.id, stage_id),
            SalesPipelineStage.tenant_id == tenant_id,
        )
        .first()
    )


def get_first_stage(db: Session, tenant_id: UUID, pipeline_id: UUID) -> SalesPipelineStage | None:
    return (
        db.query(SalesPipelineStage)
        .filter(
            SalesPipelineStage.tenant_id == tenant_id,
            uuid_eq(SalesPipelineStage.pipeline_id, pipeline_id),
            SalesPipelineStage.is_active.is_(True),
        )
        .order_by(SalesPipelineStage.sort_order, SalesPipelineStage.created_at)
        .first()
    )


def _reset_default_pipeline(db: Session, tenant_id: UUID, exclude_id: UUID | None) -> None:
    """将租户内其它管道 is_default 置为 False，保证仅 1 个默认。"""
    q = db.query(SalesPipeline).filter(
        SalesPipeline.tenant_id == tenant_id,
        SalesPipeline.is_default.is_(True),
    )
    if exclude_id is not None:
        q = q.filter(SalesPipeline.id != exclude_id)
    for p in q.all():
        p.is_default = False


def create_pipeline(
    db: Session, ctx: TenantContext, data: PipelineCreate
) -> SalesPipeline:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    if data.is_default:
        _reset_default_pipeline(db, ctx.tenant_id, exclude_id=None)
    pipeline = SalesPipeline(
        tenant_id=ctx.tenant_id,
        name=data.name,
        is_default=data.is_default,
        is_active=data.is_active,
    )
    db.add(pipeline)
    db.flush()
    for idx, s in enumerate(data.stages or []):
        stage = SalesPipelineStage(
            tenant_id=ctx.tenant_id,
            pipeline_id=pipeline.id,
            name=s.name,
            sort_order=s.sort_order if s.sort_order is not None else idx * 10,
            probability=s.probability,
            is_won_stage=s.is_won_stage,
            is_lost_stage=s.is_lost_stage,
            is_closed_stage=s.is_closed_stage,
            color=s.color,
            max_stay_days=s.max_stay_days,
            is_active=s.is_active,
        )
        db.add(stage)
    db.commit()
    db.refresh(pipeline)
    return pipeline


def update_pipeline(
    db: Session, ctx: TenantContext, pipeline: SalesPipeline, data: PipelineUpdate
) -> SalesPipeline:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    if data.name is not None:
        pipeline.name = data.name
    if data.is_active is not None:
        pipeline.is_active = data.is_active
    if data.is_default is True and not pipeline.is_default:
        _reset_default_pipeline(db, ctx.tenant_id, exclude_id=pipeline.id)
        pipeline.is_default = True
    elif data.is_default is False:
        pipeline.is_default = False
    db.commit()
    db.refresh(pipeline)
    return pipeline


def delete_pipeline(db: Session, ctx: TenantContext, pipeline: SalesPipeline) -> None:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    # 检查是否有商机在用
    in_use = (
        db.query(Deal)
        .filter(uuid_eq(Deal.pipeline_id, pipeline.id), Deal.deleted_at.is_(None))
        .count()
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"管道下有 {in_use} 个商机，无法删除（请改为停用）",
        )
    db.query(SalesPipelineStage).filter(
        uuid_eq(SalesPipelineStage.pipeline_id, pipeline.id)
    ).delete()
    db.delete(pipeline)
    db.commit()


def create_stage(
    db: Session, ctx: TenantContext, pipeline: SalesPipeline, data: PipelineStageCreate
) -> SalesPipelineStage:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    stage = SalesPipelineStage(
        tenant_id=ctx.tenant_id,
        pipeline_id=pipeline.id,
        name=data.name,
        sort_order=data.sort_order,
        probability=data.probability,
        is_won_stage=data.is_won_stage,
        is_lost_stage=data.is_lost_stage,
        is_closed_stage=data.is_closed_stage,
        color=data.color,
        max_stay_days=data.max_stay_days,
        is_active=data.is_active,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session,
    ctx: TenantContext,
    stage: SalesPipelineStage,
    data: PipelineStageUpdate,
) -> SalesPipelineStage:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    values: dict = {}
    if data.name is not None:
        values["name"] = data.name
    if data.sort_order is not None:
        values["sort_order"] = data.sort_order
    if data.probability is not None:
        values["probability"] = data.probability
    if data.is_won_stage is not None:
        values["is_won_stage"] = data.is_won_stage
    if data.is_lost_stage is not None:
        values["is_lost_stage"] = data.is_lost_stage
    if data.is_closed_stage is not None:
        values["is_closed_stage"] = data.is_closed_stage
    if data.color is not None:
        values["color"] = data.color
    if "max_stay_days" in data.model_fields_set:
        values["max_stay_days"] = data.max_stay_days
    if data.is_active is not None:
        values["is_active"] = data.is_active
    if not values:
        return stage
    stage_id = stage.id
    tenant_id = stage.tenant_id
    db.execute(
        update(SalesPipelineStage)
        .where(uuid_eq(SalesPipelineStage.id, stage_id))
        .values(**values)
    )
    db.commit()
    db.expire(stage)
    refreshed = get_stage(db, tenant_id, stage_id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="管道阶段不存在")
    return refreshed


def delete_stage(db: Session, ctx: TenantContext, stage: SalesPipelineStage) -> None:
    if "crm.pipeline.manage" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理销售管道")
    in_use = (
        db.query(Deal)
        .filter(uuid_eq(Deal.stage_id, stage.id), Deal.deleted_at.is_(None))
        .count()
    )
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"阶段下有 {in_use} 个商机，无法删除（请改为停用）",
        )
    db.delete(stage)
    db.commit()


def require_pipeline(db: Session, tenant_id: UUID, pipeline_id: UUID) -> SalesPipeline:
    p = get_pipeline(db, tenant_id, pipeline_id)
    if not p:
        raise HTTPException(status_code=404, detail="销售管道不存在")
    return p


def require_stage(db: Session, tenant_id: UUID, stage_id: UUID) -> SalesPipelineStage:
    s = get_stage(db, tenant_id, stage_id)
    if not s:
        raise HTTPException(status_code=404, detail="管道阶段不存在")
    return s
