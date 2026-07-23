"""CRM 任务 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import CrmTask
from app.schemas.crm import TaskCreate, TaskUpdate, validate_task_priority, validate_task_status
from app.services.crm.crm_scope_service import assert_can_view_task
from app.services.crm.number_service import generate_number
from app.services.crm.sales_org_service import apply_creator_org_defaults, assert_can_assign_owner


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _apply_status_timestamps(task: CrmTask, old_status: str, new_status: str) -> None:
    if old_status == new_status:
        return
    now = _now()
    if new_status == "in_progress" and task.started_at is None:
        task.started_at = now
    if new_status == "done" and task.completed_at is None:
        task.completed_at = now


def get_task(db: Session, tenant_id: UUID, task_id: UUID) -> CrmTask | None:
    return (
        db.query(CrmTask)
        .filter(
            uuid_eq(CrmTask.id, task_id),
            CrmTask.tenant_id == tenant_id,
            CrmTask.deleted_at.is_(None),
        )
        .first()
    )


def create_task(db: Session, ctx: TenantContext, data: TaskCreate) -> CrmTask:
    validate_task_status(data.status)
    validate_task_priority(data.priority)
    assignee = data.assignee_user_id or ctx.user.id
    if assignee != ctx.user.id and "crm.task.assign" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限指派执行人")
    assert_can_assign_owner(db, ctx, assignee)
    started_at = data.started_at
    completed_at = data.completed_at
    if data.status == "in_progress" and started_at is None:
        started_at = _now()
    if data.status == "done" and completed_at is None:
        completed_at = _now()
    territory_id, manager_user_id = apply_creator_org_defaults(db, ctx, territory_id=data.territory_id)
    task = CrmTask(
        tenant_id=ctx.tenant_id,
        task_number=generate_number(db, ctx.tenant_id, "task"),
        title=data.title.strip(),
        description=data.description,
        status=data.status,
        priority=data.priority,
        planned_start_at=data.planned_start_at,
        started_at=started_at,
        due_at=data.due_at,
        completed_at=completed_at,
        assignee_user_id=assignee,
        owner_user_id=ctx.user.id,
        territory_id=territory_id,
        manager_user_id=manager_user_id,
        lead_id=data.lead_id,
        customer_id=data.customer_id,
        campaign_id=data.campaign_id,
        content_id=data.content_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _is_task_assignee(ctx: TenantContext, task: CrmTask) -> bool:
    return task.assignee_user_id is not None and task.assignee_user_id == ctx.user.id


def update_task(db: Session, ctx: TenantContext, task: CrmTask, data: TaskUpdate) -> CrmTask:
    if task.status in ("done", "cancelled"):
        raise HTTPException(status_code=400, detail="已完成或已取消的任务不可编辑")
    perms = _perm_set(ctx)
    # 非执行人：仅允许重新分配执行人（需 crm.task.assign）
    if not _is_task_assignee(ctx, task):
        fields = set(data.model_fields_set)
        if fields != {"assignee_user_id"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅任务执行人可编辑；非执行人仅可重新分配执行人",
            )
        if "crm.task.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限指派执行人")
        if data.assignee_user_id is None:
            raise HTTPException(status_code=400, detail="请选择任务执行人")
        assert_can_assign_owner(db, ctx, data.assignee_user_id)
        task.assignee_user_id = data.assignee_user_id
        db.commit()
        db.refresh(task)
        return task

    if data.assignee_user_id is not None and data.assignee_user_id != task.assignee_user_id:
        if "crm.task.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限指派执行人")
        assert_can_assign_owner(db, ctx, data.assignee_user_id)
        task.assignee_user_id = data.assignee_user_id
    if data.title is not None:
        task.title = data.title.strip()
    if data.description is not None:
        task.description = data.description
    if data.status is not None:
        validate_task_status(data.status)
        if data.status == "cancelled":
            # 待办与删除互斥：未开始请直接删除
            if task.status == "open":
                raise HTTPException(status_code=400, detail="待办任务请直接删除，不可取消")
            reason = (data.cancel_reason or "").strip()
            if not reason:
                raise HTTPException(status_code=400, detail="取消任务须填写取消原因")
            if len(reason) > 500:
                raise HTTPException(status_code=400, detail="取消原因不超过 500 字")
            task.cancel_reason = reason
        _apply_status_timestamps(task, task.status, data.status)
        task.status = data.status
    elif data.cancel_reason is not None:
        # 仅在取消时写入原因，非取消态不允许单独改
        raise HTTPException(status_code=400, detail="取消原因仅在取消任务时填写")
    if data.priority is not None:
        validate_task_priority(data.priority)
        task.priority = data.priority
    if data.planned_start_at is not None:
        task.planned_start_at = data.planned_start_at
    if data.started_at is not None:
        task.started_at = data.started_at
    if data.due_at is not None:
        task.due_at = data.due_at
    if data.completed_at is not None:
        task.completed_at = data.completed_at
    if data.territory_id is not None:
        task.territory_id = data.territory_id
    if "lead_id" in data.model_fields_set:
        task.lead_id = data.lead_id
    if "customer_id" in data.model_fields_set:
        task.customer_id = data.customer_id
    if "campaign_id" in data.model_fields_set:
        task.campaign_id = data.campaign_id
    db.commit()
    db.refresh(task)
    return task


def soft_delete_task(db: Session, ctx: TenantContext, task: CrmTask) -> None:
    if not _is_task_assignee(ctx, task):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅任务执行人可删除")
    if task.status != "open":
        raise HTTPException(status_code=400, detail="仅待办状态的任务可删除；已开始请取消或完成")
    task.deleted_at = _now()
    db.commit()


def require_task(db: Session, ctx: TenantContext, task_id: UUID) -> CrmTask:
    task = get_task(db, ctx.tenant_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    assert_can_view_task(ctx, db, task)
    return task
