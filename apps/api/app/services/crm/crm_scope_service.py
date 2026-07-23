"""CRM 数据可见范围（list_own / list_team / list_territory / list_all 并集）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.dependencies import TenantContext
from app.models.crm import Customer, CrmTask, Deal, Lead, MarketingCampaign
from app.services.crm.sales_org_service import get_accessible_territory_ids, get_subordinate_user_ids


def _uuid_key(value: UUID | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("-", "").lower()


def _territory_in_clause(column, territory_ids: set[UUID]):
    """SQLite UUID 格式不一，避免直接 IN 比较失效或误匹配。"""
    from app.database import uuid_eq

    ids = [tid for tid in territory_ids if tid is not None]
    if not ids:
        return column.is_(None)  # 无地区可访问时不额外放行
    return or_(*[uuid_eq(column, tid) for tid in ids])


def _territory_accessible(territory_id: UUID | None, territory_ids: set[UUID]) -> bool:
    if territory_id is None or not territory_ids:
        return False
    key = _uuid_key(territory_id)
    return any(_uuid_key(tid) == key for tid in territory_ids)


def _perm_set(ctx: TenantContext, db: Session | None = None) -> set[str]:
    """读取成员角色权限；commit/expire 后 role 可能被 SQLite UUID 格式问题懒加载为空。"""
    membership = ctx.membership
    role = membership.role
    if role is None:
        from sqlalchemy.orm import object_session

        from app.services.membership_service import ensure_membership_role

        session = db or object_session(membership)
        if session is not None:
            role = ensure_membership_role(session, membership)
    if role is None:
        return set()
    return {p.permission_code for p in role.permissions}


def _append_team_scope_parts(
    parts: list,
    *,
    db: Session,
    ctx: TenantContext,
    owner_col,
    created_by_col=None,
    manager_col=None,
    extra_owner_cols: list | None = None,
) -> None:
    """上级可见：下级负责人/创建人 + 创建时落库的汇报上级快照。"""
    subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
    if subordinate_ids:
        parts.append(owner_col.in_(subordinate_ids))
        if created_by_col is not None:
            parts.append(created_by_col.in_(subordinate_ids))
        for col in extra_owner_cols or []:
            parts.append(col.in_(subordinate_ids))
    if manager_col is not None:
        parts.append(manager_col == ctx.user.id)


def _team_can_view(
    *,
    db: Session,
    ctx: TenantContext,
    owner_user_id: UUID | None,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
    extra_user_ids: list[UUID] | None = None,
) -> bool:
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
    if not subordinate_ids:
        return False
    if owner_user_id is not None and owner_user_id in subordinate_ids:
        return True
    if created_by_user_id is not None and created_by_user_id in subordinate_ids:
        return True
    for uid in extra_user_ids or []:
        if uid in subordinate_ids:
            return True
    return False


def has_lead_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.lead.list_own",
                "crm.lead.list_team",
                "crm.lead.list_territory",
                "crm.lead.list_all",
            }
        )
    )


def has_customer_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.customer.list_own",
                "crm.customer.list_team",
                "crm.customer.list_territory",
                "crm.customer.list_all",
            }
        )
    )


def _lead_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.lead.list_all" in perms:
        return None
    if not perms.intersection({"crm.lead.list_own", "crm.lead.list_team", "crm.lead.list_territory"}):
        return Lead.id.is_(None)
    # 与 FR-CRM-SCOPE 对齐：本人负责人 / 汇报上级快照 / 下属负责人 / 可访问地区
    # 不按 created_by 扩大范围，否则分配给其他区后原经理仍因「下属创建过」可见
    parts = [Lead.owner_user_id == ctx.user.id, Lead.manager_user_id == ctx.user.id]
    if "crm.lead.list_team" in perms:
        _append_team_scope_parts(
            parts,
            db=db,
            ctx=ctx,
            owner_col=Lead.owner_user_id,
            created_by_col=None,
            manager_col=None,
        )
    if "crm.lead.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(_territory_in_clause(Lead.territory_id, territory_ids))
    return or_(*parts)


def apply_lead_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _lead_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def _customer_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.customer.list_all" in perms:
        return None
    if not perms.intersection({"crm.customer.list_own", "crm.customer.list_team", "crm.customer.list_territory"}):
        return Customer.id.is_(None)
    parts = [Customer.owner_user_id == ctx.user.id, Customer.manager_user_id == ctx.user.id]
    if "crm.customer.list_team" in perms:
        _append_team_scope_parts(
            parts,
            db=db,
            ctx=ctx,
            owner_col=Customer.owner_user_id,
            created_by_col=None,
        )
    if "crm.customer.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(_territory_in_clause(Customer.territory_id, territory_ids))
    return or_(*parts)


def apply_customer_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _customer_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_lead(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID | None,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
    pool_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.lead.list_all" in perms:
        return True
    # 公海待认领：无负责人，与公海列表可见范围一致（list_* / edit）
    if pool_id is not None and owner_user_id is None:
        return has_lead_list_permission(ctx) or "crm.lead.edit" in perms
    list_perms = {"crm.lead.list_own", "crm.lead.list_team", "crm.lead.list_territory"}
    if not perms.intersection(list_perms):
        return False
    if owner_user_id is not None and owner_user_id == ctx.user.id:
        return True
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    if "crm.lead.list_team" in perms and _team_can_view(
        db=db,
        ctx=ctx,
        owner_user_id=owner_user_id,
        created_by_user_id=None,
        manager_user_id=manager_user_id,
    ):
        return True
    if "crm.lead.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if _territory_accessible(territory_id, territory_ids):
            return True
    return False


def can_view_customer(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID | None,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
    pool_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.customer.list_all" in perms:
        return True
    if pool_id is not None and owner_user_id is None:
        return has_customer_list_permission(ctx) or "crm.customer.edit" in perms
    list_perms = {"crm.customer.list_own", "crm.customer.list_team", "crm.customer.list_territory"}
    if not perms.intersection(list_perms):
        return False
    if owner_user_id is not None and owner_user_id == ctx.user.id:
        return True
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    if "crm.customer.list_team" in perms and _team_can_view(
        db=db,
        ctx=ctx,
        owner_user_id=owner_user_id,
        created_by_user_id=None,
        manager_user_id=manager_user_id,
    ):
        return True
    if "crm.customer.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if _territory_accessible(territory_id, territory_ids):
            return True
    return False


def assert_can_view_lead(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID | None,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
    pool_id: UUID | None = None,
) -> None:
    if not can_view_lead(
        ctx,
        db,
        owner_user_id,
        territory_id,
        created_by_user_id=created_by_user_id,
        manager_user_id=manager_user_id,
        pool_id=pool_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该线索")


def assert_can_mutate_lead(ctx: TenantContext, lead) -> None:
    """编辑 / 删除 / 转化 / 退回公海：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(lead, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="公海线索不可直接操作，请先认领",
        )
    if str(lead.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅负责人可编辑、删除、转化或退回公海",
        )


def assert_can_mutate_customer(ctx: TenantContext, customer) -> None:
    """编辑 / 删除 / 退回公海：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(customer, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="公海客户不可直接操作，请先认领或分配负责人",
        )
    if str(customer.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅负责人可编辑、删除或退回公海",
        )


def assert_can_mutate_deal(ctx: TenantContext, deal) -> None:
    """编辑 / 删除 / 改阶段 / 关闭：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(deal, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="商机无负责人，请先分配负责人",
        )
    if str(deal.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅商机负责人可编辑这些操作",
        )


def assert_can_mutate_quote(ctx: TenantContext, quote) -> None:
    """编辑 / 删除 / 发送 / 接受 / 转订单：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(quote, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="报价无负责人，请先分配负责人",
        )
    if str(quote.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅报价负责人可编辑这些操作",
        )


def assert_can_mutate_contract(ctx: TenantContext, contract) -> None:
    """编辑 / 删除 / 签署 / 转订单：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(contract, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="合同无负责人，请先分配负责人",
        )
    if str(contract.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅合同负责人可编辑这些操作",
        )


def assert_can_mutate_order(ctx: TenantContext, order) -> None:
    """编辑 / 删除 / 确认 / 提交 / 取消 / 修订：仅当前负责人可操作（分配负责人除外；审批人除外）。"""
    if getattr(order, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="订单无负责人，请先分配负责人",
        )
    if str(order.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅订单负责人可编辑这些操作",
        )


def assert_can_mutate_payment(ctx: TenantContext, payment) -> None:
    """编辑 / 删除 / 确认 / 冲销：仅当前负责人可操作（分配负责人除外）。"""
    if getattr(payment, "owner_user_id", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="回款无负责人，请先分配负责人",
        )
    if str(payment.owner_user_id).replace("-", "").lower() != str(ctx.user.id).replace("-", "").lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅回款负责人可编辑这些操作",
        )


def assert_can_view_customer(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID | None,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
    pool_id: UUID | None = None,
) -> None:
    if not can_view_customer(
        ctx,
        db,
        owner_user_id,
        territory_id,
        created_by_user_id=created_by_user_id,
        manager_user_id=manager_user_id,
        pool_id=pool_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该客户")


def has_task_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.task.list_own",
                "crm.task.list_team",
                "crm.task.list_territory",
                "crm.task.list_all",
            }
        )
    )


def _task_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.task.list_all" in perms:
        return None
    if not perms.intersection({"crm.task.list_own", "crm.task.list_team", "crm.task.list_territory"}):
        return CrmTask.id.is_(None)
    parts = [
        CrmTask.assignee_user_id == ctx.user.id,
        CrmTask.owner_user_id == ctx.user.id,
        CrmTask.manager_user_id == ctx.user.id,
    ]
    if "crm.task.list_team" in perms:
        _append_team_scope_parts(
            parts,
            db=db,
            ctx=ctx,
            owner_col=CrmTask.owner_user_id,
            extra_owner_cols=[CrmTask.assignee_user_id],
        )
    if "crm.task.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(CrmTask.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_task_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _task_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_task(
    ctx: TenantContext,
    db: Session,
    assignee_user_id: UUID,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
    *,
    manager_user_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.task.list_all" in perms:
        return True
    list_perms = {"crm.task.list_own", "crm.task.list_team", "crm.task.list_territory"}
    if not perms.intersection(list_perms):
        return False
    if assignee_user_id == ctx.user.id or owner_user_id == ctx.user.id:
        return True
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    if "crm.task.list_team" in perms and _team_can_view(
        db=db,
        ctx=ctx,
        owner_user_id=owner_user_id,
        extra_user_ids=[assignee_user_id],
        manager_user_id=manager_user_id,
    ):
        return True
    if "crm.task.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def assert_can_view_task(ctx: TenantContext, db: Session, task: CrmTask) -> None:
    if not can_view_task(
        ctx,
        db,
        task.assignee_user_id,
        task.owner_user_id,
        task.territory_id,
        manager_user_id=getattr(task, "manager_user_id", None),
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该任务")


def has_campaign_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.campaign.list_own",
                "crm.campaign.list_team",
                "crm.campaign.list_territory",
                "crm.campaign.list_all",
            }
        )
    )


def _campaign_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.campaign.list_all" in perms:
        return None
    if not perms.intersection(
        {"crm.campaign.list_own", "crm.campaign.list_team", "crm.campaign.list_territory"}
    ):
        return MarketingCampaign.id.is_(None)
    parts = [
        MarketingCampaign.owner_user_id == ctx.user.id,
        MarketingCampaign.manager_user_id == ctx.user.id,
    ]
    if "crm.campaign.list_team" in perms:
        _append_team_scope_parts(
            parts,
            db=db,
            ctx=ctx,
            owner_col=MarketingCampaign.owner_user_id,
        )
    if "crm.campaign.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(MarketingCampaign.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_campaign_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _campaign_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_campaign(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
    *,
    manager_user_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.campaign.list_all" in perms:
        return True
    list_perms = {
        "crm.campaign.list_own",
        "crm.campaign.list_team",
        "crm.campaign.list_territory",
        "crm.campaign.view",
    }
    if not perms.intersection(list_perms):
        return False
    if owner_user_id == ctx.user.id:
        return True
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    if "crm.campaign.list_team" in perms and _team_can_view(
        db=db, ctx=ctx, owner_user_id=owner_user_id, manager_user_id=manager_user_id
    ):
        return True
    if "crm.campaign.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def assert_can_view_campaign(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
    *,
    manager_user_id: UUID | None = None,
) -> None:
    if not can_view_campaign(
        ctx, db, owner_user_id, territory_id, manager_user_id=manager_user_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该活动")


# ============================================================
# v0.7 商机 scope（owner_user_id + territory_id 并集规则）
# ============================================================


def has_deal_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.deal.list_own",
                "crm.deal.list_team",
                "crm.deal.list_territory",
                "crm.deal.list_all",
            }
        )
    )


def _deal_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.deal.list_all" in perms:
        return None
    if not perms.intersection(
        {"crm.deal.list_own", "crm.deal.list_team", "crm.deal.list_territory"}
    ):
        return Deal.id.is_(None)
    parts = [Deal.owner_user_id == ctx.user.id, Deal.manager_user_id == ctx.user.id]
    if "crm.deal.list_team" in perms:
        _append_team_scope_parts(
            parts,
            db=db,
            ctx=ctx,
            owner_col=Deal.owner_user_id,
            created_by_col=None,
        )
    if "crm.deal.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(_territory_in_clause(Deal.territory_id, territory_ids))
    return or_(*parts)


def apply_deal_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _deal_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_deal(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.deal.list_all" in perms:
        return True
    list_perms = {"crm.deal.list_own", "crm.deal.list_team", "crm.deal.list_territory"}
    if not perms.intersection(list_perms):
        return False
    if owner_user_id == ctx.user.id:
        return True
    if manager_user_id is not None and manager_user_id == ctx.user.id:
        return True
    if "crm.deal.list_team" in perms and _team_can_view(
        db=db,
        ctx=ctx,
        owner_user_id=owner_user_id,
        created_by_user_id=None,
        manager_user_id=manager_user_id,
    ):
        return True
    if "crm.deal.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if _territory_accessible(territory_id, territory_ids):
            return True
    return False


def assert_can_view_deal(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
    *,
    created_by_user_id: UUID | None = None,
    manager_user_id: UUID | None = None,
) -> None:
    if not can_view_deal(
        ctx,
        db,
        owner_user_id,
        territory_id,
        created_by_user_id=created_by_user_id,
        manager_user_id=manager_user_id,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该商机")


# ============================================================
# v0.7 交易类实体通用 scope（quote / contract / order / payment）
# 仅按 owner_user_id + list_team + list_all 控制可见性
# ============================================================


def _build_owner_scoped_visibility(model, own_perm: str, team_perm: str, all_perm: str):
    def _filter(db: Session, ctx: TenantContext, perms: set[str]):
        if all_perm in perms:
            return None
        if not perms.intersection({own_perm, team_perm}):
            return model.id.is_(None)
        parts = [model.owner_user_id == ctx.user.id]
        if team_perm in perms:
            subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
            if subordinate_ids:
                parts.append(model.owner_user_id.in_(subordinate_ids))
            if hasattr(model, "manager_user_id"):
                parts.append(model.manager_user_id == ctx.user.id)
        elif hasattr(model, "manager_user_id"):
            parts.append(model.manager_user_id == ctx.user.id)
        return or_(*parts)

    return _filter


def _build_owner_scoped_can_view(own_perm: str, team_perm: str, all_perm: str):
    def _can_view(
        ctx: TenantContext,
        db: Session,
        owner_user_id: UUID,
        *,
        created_by_user_id: UUID | None = None,
        manager_user_id: UUID | None = None,
    ) -> bool:
        perms = _perm_set(ctx)
        if all_perm in perms:
            return True
        if not perms.intersection({own_perm, team_perm}):
            return False
        if owner_user_id == ctx.user.id:
            return True
        if manager_user_id is not None and manager_user_id == ctx.user.id:
            return True
        if team_perm in perms and _team_can_view(
            db=db,
            ctx=ctx,
            owner_user_id=owner_user_id,
            created_by_user_id=None,
            manager_user_id=manager_user_id,
        ):
            return True
        return False

    return _can_view


def _build_has_list_perm(own_perm: str, team_perm: str, all_perm: str):
    def _has(ctx: TenantContext) -> bool:
        return bool(_perm_set(ctx).intersection({own_perm, team_perm, all_perm}))

    return _has


from app.models.crm import Contract, Order, Payment, Quote  # noqa: E402

has_quote_list_permission = _build_has_list_perm(
    "crm.quote.list_own", "crm.quote.list_team", "crm.quote.list_all"
)
has_contract_list_permission = _build_has_list_perm(
    "crm.contract.list_own", "crm.contract.list_team", "crm.contract.list_all"
)
has_order_list_permission = _build_has_list_perm(
    "crm.order.list_own", "crm.order.list_team", "crm.order.list_all"
)
has_payment_list_permission = _build_has_list_perm(
    "crm.payment.list_own", "crm.payment.list_team", "crm.payment.list_all"
)

_quote_visibility_filter = _build_owner_scoped_visibility(
    Quote, "crm.quote.list_own", "crm.quote.list_team", "crm.quote.list_all"
)
_contract_visibility_filter = _build_owner_scoped_visibility(
    Contract, "crm.contract.list_own", "crm.contract.list_team", "crm.contract.list_all"
)
_order_visibility_filter = _build_owner_scoped_visibility(
    Order, "crm.order.list_own", "crm.order.list_team", "crm.order.list_all"
)
_payment_visibility_filter = _build_owner_scoped_visibility(
    Payment, "crm.payment.list_own", "crm.payment.list_team", "crm.payment.list_all"
)


def apply_quote_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    clause = _quote_visibility_filter(db, ctx, _perm_set(ctx))
    return query if clause is None else query.filter(clause)


def apply_contract_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    clause = _contract_visibility_filter(db, ctx, _perm_set(ctx))
    return query if clause is None else query.filter(clause)


def apply_order_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    clause = _order_visibility_filter(db, ctx, _perm_set(ctx))
    return query if clause is None else query.filter(clause)


def apply_payment_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    clause = _payment_visibility_filter(db, ctx, _perm_set(ctx))
    return query if clause is None else query.filter(clause)


can_view_quote = _build_owner_scoped_can_view(
    "crm.quote.list_own", "crm.quote.list_team", "crm.quote.list_all"
)
can_view_contract = _build_owner_scoped_can_view(
    "crm.contract.list_own", "crm.contract.list_team", "crm.contract.list_all"
)
can_view_order = _build_owner_scoped_can_view(
    "crm.order.list_own", "crm.order.list_team", "crm.order.list_all"
)
can_view_payment = _build_owner_scoped_can_view(
    "crm.payment.list_own", "crm.payment.list_team", "crm.payment.list_all"
)


def assert_can_view_quote(ctx: TenantContext, db: Session, owner_user_id: UUID) -> None:
    if not can_view_quote(ctx, db, owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该报价")


def assert_can_view_contract(ctx: TenantContext, db: Session, owner_user_id: UUID) -> None:
    if not can_view_contract(ctx, db, owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该合同")


def assert_can_view_order(ctx: TenantContext, db: Session, owner_user_id: UUID) -> None:
    if not can_view_order(ctx, db, owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该订单")


def assert_can_view_payment(ctx: TenantContext, db: Session, owner_user_id: UUID) -> None:
    if not can_view_payment(ctx, db, owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该回款")
