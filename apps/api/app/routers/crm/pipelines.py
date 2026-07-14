"""销售管道与阶段 API（v0.7 CRM-2）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    PipelineCreate,
    PipelineOut,
    PipelineStageCreate,
    PipelineStageOut,
    PipelineStageUpdate,
    PipelineUpdate,
)
from app.services.crm.pipeline_service import (
    create_pipeline,
    create_stage,
    delete_pipeline,
    delete_stage,
    list_pipelines,
    list_stages,
    require_pipeline,
    require_stage,
    update_pipeline,
    update_stage,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/pipelines", tags=["crm-pipelines"])


def _pipeline_to_out(pipe, db: Session) -> PipelineOut:
    stages = list_stages(db, pipe.tenant_id, pipe.id)
    return PipelineOut(
        id=pipe.id,
        tenant_id=pipe.tenant_id,
        name=pipe.name,
        is_default=pipe.is_default,
        is_active=pipe.is_active,
        created_at=pipe.created_at,
        updated_at=pipe.updated_at,
        stages=[PipelineStageOut.model_validate(s) for s in stages],
    )


@router.get("", response_model=list[PipelineOut])
def list_pipelines_endpoint(
    ctx: TenantContext = Depends(
        require_permission("crm.deal.list_own")  # 任一 deal list 权限即可读管道
    ),
    db: Session = Depends(get_db),
):
    pipes = list_pipelines(db, ctx.tenant_id)
    return [_pipeline_to_out(p, db) for p in pipes]


@router.post("", response_model=PipelineOut, status_code=201)
def create_pipeline_endpoint(
    body: PipelineCreate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = create_pipeline(db, ctx, body)
    return _pipeline_to_out(pipe, db)


@router.patch("/{pipeline_id}", response_model=PipelineOut)
def update_pipeline_endpoint(
    pipeline_id: UUID,
    body: PipelineUpdate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = require_pipeline(db, ctx.tenant_id, pipeline_id)
    pipe = update_pipeline(db, ctx, pipe, body)
    return _pipeline_to_out(pipe, db)


@router.delete("/{pipeline_id}", status_code=204)
def delete_pipeline_endpoint(
    pipeline_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = require_pipeline(db, ctx.tenant_id, pipeline_id)
    delete_pipeline(db, ctx, pipe)


@router.post("/{pipeline_id}/stages", response_model=PipelineStageOut, status_code=201)
def create_stage_endpoint(
    pipeline_id: UUID,
    body: PipelineStageCreate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = require_pipeline(db, ctx.tenant_id, pipeline_id)
    stage = create_stage(db, ctx, pipe, body)
    return PipelineStageOut.model_validate(stage)


@router.patch("/{pipeline_id}/stages/{stage_id}", response_model=PipelineStageOut)
def update_stage_endpoint(
    pipeline_id: UUID,
    stage_id: UUID,
    body: PipelineStageUpdate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = require_pipeline(db, ctx.tenant_id, pipeline_id)
    stage = require_stage(db, ctx.tenant_id, stage_id)
    if stage.pipeline_id != pipe.id:
        raise HTTPException(status_code=400, detail="阶段不属于该管道")
    stage = update_stage(db, ctx, stage, body)
    return PipelineStageOut.model_validate(stage)


@router.delete("/{pipeline_id}/stages/{stage_id}", status_code=204)
def delete_stage_endpoint(
    pipeline_id: UUID,
    stage_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    pipe = require_pipeline(db, ctx.tenant_id, pipeline_id)
    stage = require_stage(db, ctx.tenant_id, stage_id)
    if stage.pipeline_id != pipe.id:
        raise HTTPException(status_code=400, detail="阶段不属于该管道")
    delete_stage(db, ctx, stage)
