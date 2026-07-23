"""CRM 数据导入 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.crm_import import (
    ImportJobCreateOut,
    ImportJobListResponse,
    ImportJobOut,
    ImportJobPatch,
    ImportPreviewOut,
    ImportPreviewRow,
)
from app.services.crm.import_service import (
    build_errors_csv,
    build_import_template,
    create_import_job,
    get_job,
    list_import_jobs,
    preview_job,
    run_import,
    update_job_mapping,
)
from app.services.membership_service import ensure_product_import_permission

router = APIRouter(prefix="/import", tags=["crm-import"])

_ENTITY_ALIASES = {
    "leads": "lead",
    "customers": "customer",
    "products": "product",
}


def _normalize_entity_type(entity_type: str) -> str:
    key = (entity_type or "").strip().lower()
    return _ENTITY_ALIASES.get(key, key)


def _require_import_perm(ctx: TenantContext, entity_type: str, db: Session | None = None) -> None:
    entity_type = _normalize_entity_type(entity_type)
    if entity_type == "product" and db is not None:
        ensure_product_import_permission(db, ctx.membership)
    perm = f"crm.{entity_type}.import"
    codes = {p.permission_code for p in ctx.membership.role.permissions}
    if perm in codes:
        return
    # 存量租户：有产品管理权即可导入（兼容未种子 crm.product.import）
    if entity_type in ("product", "product_spec_model") and "crm.product.manage" in codes:
        return
    raise HTTPException(status_code=403, detail="无导入权限")


@router.get("/template/{entity_type}")
def download_template(
    entity_type: str,
    format: str = Query(default="xlsx", description="xlsx | csv"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    entity_type = _normalize_entity_type(entity_type)
    _require_import_perm(ctx, entity_type, db)
    content, media_type, filename = build_import_template(
        db, ctx.tenant_id, entity_type, fmt=format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/jobs", response_model=ImportJobCreateOut, status_code=201)
async def upload_import_job(
    entity_type: str = Form(...),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    entity_type = _normalize_entity_type(entity_type)
    _require_import_perm(ctx, entity_type, db)
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大")
    job, columns, suggested = create_import_job(db, ctx, entity_type, file.filename or "upload.csv", raw)
    return ImportJobCreateOut(job_id=job.id, columns=columns, suggested_mapping=suggested)


@router.patch("/jobs/{job_id}", response_model=ImportJobOut)
def patch_import_job(
    job_id: UUID,
    body: ImportJobPatch,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    job = get_job(db, ctx.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if job.created_by_user_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="无权修改该任务")
    opts = body.options.model_dump() if body.options else None
    job = update_job_mapping(db, job, body.mapping, opts)
    return ImportJobOut.model_validate(job)


@router.post("/jobs/{job_id}/preview", response_model=ImportPreviewOut)
def post_preview(
    job_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    job = get_job(db, ctx.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if not job.mapping:
        raise HTTPException(status_code=400, detail="请先配置列映射")
    result = preview_job(db, ctx, job)
    return ImportPreviewOut(
        job_id=job.id,
        preview_rows=[ImportPreviewRow(**r) for r in result["preview_rows"]],
        error_count=result["error_count"],
        ok_count=result["ok_count"],
    )


@router.post("/jobs/{job_id}/run", response_model=ImportJobOut)
def post_run(
    job_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    job = get_job(db, ctx.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if not job.mapping:
        raise HTTPException(status_code=400, detail="请先配置列映射")
    job = run_import(db, ctx, job)
    return ImportJobOut.model_validate(job)


@router.get("/jobs", response_model=ImportJobListResponse)
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    entity_type: str | None = Query(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    items, total = list_import_jobs(db, ctx, page=page, page_size=page_size, entity_type=entity_type)
    return ImportJobListResponse(
        items=[ImportJobOut.model_validate(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/{job_id}", response_model=ImportJobOut)
def get_import_job(
    job_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    job = get_job(db, ctx.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return ImportJobOut.model_validate(job)


@router.get("/jobs/{job_id}/errors")
def get_import_errors(
    job_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    job = get_job(db, ctx.tenant_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    content = build_errors_csv(db, job)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="import_errors_{job_id}.csv"'},
    )
