"""CRM 任务 API。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import CrmTask
from app.schemas.crm import TaskCreate, TaskListResponse, TaskOut, TaskUpdate, validate_task_priority
from app.services.crm.crm_scope_service import apply_task_list_scope, has_task_list_permission
from app.services.crm.task_service import create_task, require_task, soft_delete_task, update_task
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/tasks", tags=["crm-tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None, description="标题/备注关键词"),
    lead_id: UUID | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    campaign_id: UUID | None = Query(default=None),
    assignee_user_id: UUID | None = Query(default=None),
    due_from: datetime | None = Query(default=None, description="计划完成起始时间"),
    due_to: datetime | None = Query(default=None, description="计划完成结束时间"),
    due_today: bool = Query(default=False),
    due_this_week: bool = Query(default=False),
    overdue: bool = Query(default=False),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.task.list_own",
            "crm.task.list_team",
            "crm.task.list_territory",
            "crm.task.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_task_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    if priority:
        try:
            validate_task_priority(priority)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    query = db.query(CrmTask).filter(CrmTask.tenant_id == ctx.tenant_id, CrmTask.deleted_at.is_(None))
    query = apply_task_list_scope(query, ctx, db)
    if status:
        query = query.filter(CrmTask.status == status)
    elif due_today or due_this_week or overdue:
        query = query.filter(CrmTask.status.in_(("open", "in_progress", "on_hold")))
    if priority:
        query = query.filter(CrmTask.priority == priority)
    if lead_id:
        query = query.filter(CrmTask.lead_id == lead_id)
    if customer_id:
        query = query.filter(CrmTask.customer_id == customer_id)
    if campaign_id:
        query = query.filter(CrmTask.campaign_id == campaign_id)
    if assignee_user_id:
        query = query.filter(CrmTask.assignee_user_id == assignee_user_id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(CrmTask.title.ilike(like), CrmTask.description.ilike(like)))
    if due_from:
        query = query.filter(CrmTask.due_at >= due_from)
    if due_to:
        query = query.filter(CrmTask.due_at <= due_to)
    if due_today or due_this_week or overdue:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        week_end = today_start + timedelta(days=7)
        if due_today:
            query = query.filter(CrmTask.due_at >= today_start, CrmTask.due_at < today_end)
        if due_this_week:
            query = query.filter(CrmTask.due_at >= today_start, CrmTask.due_at < week_end)
        if overdue:
            query = query.filter(CrmTask.due_at < today_start)
    total = query.count()
    items = (
        query.order_by(CrmTask.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TaskListResponse(
        items=[TaskOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskOut, status_code=201)
def post_task(
    body: TaskCreate,
    ctx: TenantContext = Depends(require_permission("crm.task.create")),
    db: Session = Depends(get_db),
):
    task = create_task(db, ctx, body)
    return TaskOut.model_validate(task)


@router.get("/{task_id}", response_model=TaskOut)
def get_task_detail(
    task_id: UUID,
    ctx: TenantContext = Depends(require_any_permission("crm.task.list_own", "crm.task.list_all")),
    db: Session = Depends(get_db),
):
    task = require_task(db, ctx, task_id)
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: UUID,
    body: TaskUpdate,
    ctx: TenantContext = Depends(require_permission("crm.task.edit")),
    db: Session = Depends(get_db),
):
    task = require_task(db, ctx, task_id)
    task = update_task(db, ctx, task, body)
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.task.delete")),
    db: Session = Depends(get_db),
):
    task = require_task(db, ctx, task_id)
    soft_delete_task(db, task)
