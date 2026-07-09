"""销售组织：地区树与成员档案。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import TenantMembership
from app.models.crm import MembershipSalesProfile, SalesTerritory
from app.schemas.crm import SalesProfileUpdate, TerritoryCreate, TerritoryUpdate


def list_territories(db: Session, tenant_id: UUID) -> list[SalesTerritory]:
    return (
        db.query(SalesTerritory)
        .filter(SalesTerritory.tenant_id == tenant_id)
        .order_by(SalesTerritory.sort_order, SalesTerritory.name)
        .all()
    )


def get_territory(db: Session, tenant_id: UUID, territory_id: UUID) -> SalesTerritory | None:
    return (
        db.query(SalesTerritory)
        .filter(uuid_eq(SalesTerritory.id, territory_id), SalesTerritory.tenant_id == tenant_id)
        .first()
    )


def _assert_territory_no_cycle(
    db: Session, tenant_id: UUID, territory_id: UUID, new_parent_id: UUID | None
) -> None:
    if new_parent_id is None:
        return
    if new_parent_id == territory_id:
        raise HTTPException(status_code=422, detail="地区不能设为自己父节点")
    parent = get_territory(db, tenant_id, new_parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="父地区不存在")
    seen: set[UUID] = {territory_id}
    current_id: UUID | None = new_parent_id
    while current_id:
        if current_id in seen:
            raise HTTPException(status_code=422, detail="地区树不可成环")
        seen.add(current_id)
        row = get_territory(db, tenant_id, current_id)
        if not row:
            break
        current_id = row.parent_id


def _assert_membership_in_tenant(db: Session, tenant_id: UUID, membership_id: UUID) -> TenantMembership:
    membership = (
        db.query(TenantMembership)
        .filter(
            uuid_eq(TenantMembership.id, membership_id),
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="成员不存在")
    return membership


def create_territory(db: Session, ctx: TenantContext, data: TerritoryCreate) -> SalesTerritory:
    if data.parent_id:
        parent = get_territory(db, ctx.tenant_id, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="父地区不存在")
    if data.manager_membership_id:
        _assert_membership_in_tenant(db, ctx.tenant_id, data.manager_membership_id)
    territory = SalesTerritory(
        tenant_id=ctx.tenant_id,
        parent_id=data.parent_id,
        name=data.name.strip(),
        code=data.code,
        manager_membership_id=data.manager_membership_id,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(territory)
    db.flush()
    if territory.parent_id:
        _assert_territory_no_cycle(db, ctx.tenant_id, territory.id, territory.parent_id)
    db.commit()
    db.refresh(territory)
    return territory


def update_territory(
    db: Session, ctx: TenantContext, territory: SalesTerritory, data: TerritoryUpdate
) -> SalesTerritory:
    if data.parent_id is not None:
        _assert_territory_no_cycle(db, ctx.tenant_id, territory.id, data.parent_id)
        territory.parent_id = data.parent_id
    if data.name is not None:
        territory.name = data.name.strip()
    if data.code is not None:
        territory.code = data.code
    if data.manager_membership_id is not None:
        if data.manager_membership_id:
            _assert_membership_in_tenant(db, ctx.tenant_id, data.manager_membership_id)
        territory.manager_membership_id = data.manager_membership_id
    if data.sort_order is not None:
        territory.sort_order = data.sort_order
    if data.is_active is not None:
        territory.is_active = data.is_active
    db.commit()
    db.refresh(territory)
    return territory


def delete_territory(db: Session, territory: SalesTerritory) -> None:
    child = (
        db.query(SalesTerritory)
        .filter(SalesTerritory.parent_id == territory.id)
        .first()
    )
    if child:
        raise HTTPException(status_code=400, detail="存在子地区，无法删除")
    db.delete(territory)
    db.commit()


def _assert_reports_no_cycle(
    db: Session, tenant_id: UUID, membership_id: UUID, reports_to_id: UUID | None
) -> None:
    if reports_to_id is None:
        return
    if reports_to_id == membership_id:
        raise HTTPException(status_code=422, detail="不能汇报给自己")
    _assert_membership_in_tenant(db, tenant_id, reports_to_id)
    seen: set[UUID] = {membership_id}
    current_id: UUID | None = reports_to_id
    while current_id:
        if current_id in seen:
            raise HTTPException(status_code=422, detail="汇报关系不可成环")
        seen.add(current_id)
        profile = (
            db.query(MembershipSalesProfile)
            .filter(uuid_eq(MembershipSalesProfile.membership_id, current_id))
            .first()
        )
        if not profile or not profile.reports_to_membership_id:
            break
        current_id = profile.reports_to_membership_id


def list_sales_profiles(db: Session, tenant_id: UUID) -> list[dict]:
    rows = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.user), joinedload(TenantMembership.role))
        .filter(TenantMembership.tenant_id == tenant_id, TenantMembership.is_active.is_(True))
        .all()
    )
    out: list[dict] = []
    for m in rows:
        profile = (
            db.query(MembershipSalesProfile)
            .filter(uuid_eq(MembershipSalesProfile.membership_id, m.id))
            .first()
        )
        out.append(
            {
                "membership_id": m.id,
                "user_id": m.user_id,
                "display_name": m.user.display_name if m.user else None,
                "phone": m.user.phone if m.user else None,
                "role_name": m.role.name if m.role else None,
                "primary_territory_id": profile.primary_territory_id if profile else None,
                "reports_to_membership_id": profile.reports_to_membership_id if profile else None,
            }
        )
    return out


def upsert_sales_profile(
    db: Session, ctx: TenantContext, membership_id: UUID, data: SalesProfileUpdate
) -> MembershipSalesProfile:
    _assert_membership_in_tenant(db, ctx.tenant_id, membership_id)
    if data.primary_territory_id:
        terr = get_territory(db, ctx.tenant_id, data.primary_territory_id)
        if not terr:
            raise HTTPException(status_code=404, detail="主地区不存在")
    if data.reports_to_membership_id is not None:
        _assert_reports_no_cycle(db, ctx.tenant_id, membership_id, data.reports_to_membership_id)

    profile = (
        db.query(MembershipSalesProfile)
        .filter(uuid_eq(MembershipSalesProfile.membership_id, membership_id))
        .first()
    )
    if not profile:
        profile = MembershipSalesProfile(membership_id=membership_id)
        db.add(profile)
    if data.primary_territory_id is not None:
        profile.primary_territory_id = data.primary_territory_id
    if data.reports_to_membership_id is not None:
        profile.reports_to_membership_id = data.reports_to_membership_id
    db.commit()
    db.refresh(profile)
    return profile


def get_territory_subtree_ids(db: Session, tenant_id: UUID, root_id: UUID) -> set[UUID]:
    """返回 root 及其所有子地区 id。"""
    territories = list_territories(db, tenant_id)
    by_parent: dict[UUID | None, list[UUID]] = {}
    for t in territories:
        by_parent.setdefault(t.parent_id, []).append(t.id)
    result: set[UUID] = set()
    stack = [root_id]
    while stack:
        tid = stack.pop()
        if tid in result:
            continue
        result.add(tid)
        stack.extend(by_parent.get(tid, []))
    return result


def get_subordinate_user_ids(db: Session, tenant_id: UUID, manager_membership_id: UUID) -> set[UUID]:
    """汇报给 manager（含间接下级）的成员 user_id。"""
    profiles = (
        db.query(MembershipSalesProfile, TenantMembership)
        .join(TenantMembership, TenantMembership.id == MembershipSalesProfile.membership_id)
        .filter(TenantMembership.tenant_id == tenant_id, TenantMembership.is_active.is_(True))
        .all()
    )
    reports_map: dict[UUID, list[UUID]] = {}
    membership_to_user: dict[UUID, UUID] = {}
    for profile, membership in profiles:
        membership_to_user[membership.id] = membership.user_id
        if profile.reports_to_membership_id:
            reports_map.setdefault(profile.reports_to_membership_id, []).append(membership.id)

    result_users: set[UUID] = set()
    stack = list(reports_map.get(manager_membership_id, []))
    seen: set[UUID] = set()
    while stack:
        mid = stack.pop()
        if mid in seen:
            continue
        seen.add(mid)
        uid = membership_to_user.get(mid)
        if uid:
            result_users.add(uid)
        stack.extend(reports_map.get(mid, []))
    return result_users


def get_accessible_territory_ids(db: Session, tenant_id: UUID, membership_id: UUID) -> set[UUID]:
    """主地区子树 + 作为负责人的地区子树。"""
    accessible: set[UUID] = set()
    profile = (
        db.query(MembershipSalesProfile)
        .filter(uuid_eq(MembershipSalesProfile.membership_id, membership_id))
        .first()
    )
    if profile and profile.primary_territory_id:
        accessible |= get_territory_subtree_ids(db, tenant_id, profile.primary_territory_id)

    managed = (
        db.query(SalesTerritory)
        .filter(
            SalesTerritory.tenant_id == tenant_id,
            SalesTerritory.manager_membership_id == membership_id,
        )
        .all()
    )
    for t in managed:
        accessible |= get_territory_subtree_ids(db, tenant_id, t.id)
    return accessible
