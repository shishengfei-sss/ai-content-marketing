"""销售组织：地区树与成员档案。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import TenantMembership, TenantRole
from app.models.crm import MembershipSalesProfile, SalesTerritory
from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_SALES_MANAGER
from app.schemas.crm import SalesProfileUpdate, TerritoryCreate, TerritoryUpdate


def _uuid_key(value: UUID | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("-", "").lower()


def list_territories(db: Session, tenant_id: UUID) -> list[SalesTerritory]:
    return (
        db.query(SalesTerritory)
        .filter(SalesTerritory.tenant_id == tenant_id)
        .order_by(SalesTerritory.sort_order, SalesTerritory.name)
        .all()
    )


DEFAULT_TERRITORIES = [
    ("全国", "national", 0),
    ("华东", "east", 10),
    ("华南", "south", 20),
    ("华北", "north", 30),
    ("华中", "central", 40),
    ("西南", "southwest", 50),
    ("西北", "northwest", 60),
    ("东北", "northeast", 70),
]


def ensure_default_territories(db: Session, tenant_id: UUID) -> list[SalesTerritory]:
    """租户尚无销售地区时，补种常用大区，便于线索/客户归属地区可选。"""
    existing = list_territories(db, tenant_id)
    if existing:
        return existing
    rows: list[SalesTerritory] = []
    for name, code, sort_order in DEFAULT_TERRITORIES:
        row = SalesTerritory(
            tenant_id=tenant_id,
            name=name,
            code=code,
            sort_order=sort_order,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


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


def resolve_creator_org_snapshot(db: Session, ctx: TenantContext) -> tuple[UUID | None, UUID | None]:
    """创建人主地区 + 汇报上级 user_id（用于单据落库与区域/团队权限）。"""
    return resolve_owner_org_snapshot(db, ctx.tenant_id, ctx.user.id, membership_id=ctx.membership.id)


def resolve_owner_org_snapshot(
    db: Session,
    tenant_id: UUID,
    owner_user_id: UUID,
    *,
    membership_id: UUID | None = None,
) -> tuple[UUID | None, UUID | None]:
    """按负责人（或其 membership）解析主地区 + 汇报上级 user_id。"""
    membership: TenantMembership | None = None
    if membership_id is not None:
        membership = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.id, membership_id),
                uuid_eq(TenantMembership.tenant_id, tenant_id),
                TenantMembership.is_active.is_(True),
            )
            .first()
        )
    if membership is None:
        membership = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.user_id, owner_user_id),
                uuid_eq(TenantMembership.tenant_id, tenant_id),
                TenantMembership.is_active.is_(True),
            )
            .first()
        )
    if not membership:
        return None, None

    profile = (
        db.query(MembershipSalesProfile)
        .filter(uuid_eq(MembershipSalesProfile.membership_id, membership.id))
        .first()
    )
    territory_id = profile.primary_territory_id if profile else None
    manager_user_id: UUID | None = None
    if profile and profile.reports_to_membership_id:
        mgr = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.id, profile.reports_to_membership_id),
                uuid_eq(TenantMembership.tenant_id, tenant_id),
                TenantMembership.is_active.is_(True),
            )
            .first()
        )
        if mgr:
            manager_user_id = mgr.user_id
    return territory_id, manager_user_id


def apply_owner_org_snapshot(db: Session, tenant_id: UUID, owner_user_id: UUID) -> tuple[UUID | None, UUID | None]:
    """分配负责人后同步地区与汇报上级快照。"""
    return resolve_owner_org_snapshot(db, tenant_id, owner_user_id)


def apply_creator_org_defaults(
    db: Session,
    ctx: TenantContext,
    *,
    territory_id: UUID | None,
) -> tuple[UUID | None, UUID | None]:
    """请求未指定地区时回填创建人主地区；上级始终取创建人汇报线快照。"""
    snap_territory, snap_manager = resolve_creator_org_snapshot(db, ctx)
    return (territory_id if territory_id is not None else snap_territory), snap_manager


def get_assignable_owner_user_ids(db: Session, ctx: TenantContext) -> set[UUID]:
    """手动分配可选负责人：本人 + 汇报下属 + 同级销售经理；企业管理员可选全员。"""
    role_code = getattr(getattr(ctx.membership, "role", None), "code", None) or ""
    memberships = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role))
        .filter(
            uuid_eq(TenantMembership.tenant_id, ctx.tenant_id),
            TenantMembership.is_active.is_(True),
        )
        .all()
    )
    # SQLite UUID 存储格式不一，relationship join 可能落空，用 uuid_eq 回填
    for membership in memberships:
        if membership.role is None and membership.role_id is not None:
            membership.role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.id, membership.role_id))
                .first()
            )

    if role_code == SYSTEM_ROLE_ADMIN:
        return {m.user_id for m in memberships}

    allowed: set[UUID] = {ctx.user.id}
    allowed |= get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)

    profile_by_membership: dict[str, MembershipSalesProfile] = {}
    for profile in db.query(MembershipSalesProfile).all():
        profile_by_membership[_uuid_key(profile.membership_id) or ""] = profile

    my_profile = profile_by_membership.get(_uuid_key(ctx.membership.id) or "")
    my_reports_key = _uuid_key(my_profile.reports_to_membership_id if my_profile else None)

    for membership in memberships:
        if _uuid_key(membership.id) == _uuid_key(ctx.membership.id):
            continue
        code = (membership.role.code if membership.role else "") or ""
        if code != SYSTEM_ROLE_SALES_MANAGER:
            continue
        peer_profile = profile_by_membership.get(_uuid_key(membership.id) or "")
        peer_reports = peer_profile.reports_to_membership_id if peer_profile else None
        if _uuid_key(peer_reports) == my_reports_key:
            allowed.add(membership.user_id)
    return allowed


def assert_can_assign_owner(db: Session, ctx: TenantContext, target_user_id: UUID | None) -> None:
    if target_user_id is None:
        return
    allowed = get_assignable_owner_user_ids(db, ctx)
    allowed_keys = {_uuid_key(uid) for uid in allowed}
    if _uuid_key(target_user_id) not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能分配给下属或同级别销售经理",
        )


def list_assignable_owner_memberships(
    db: Session,
    ctx: TenantContext,
    *,
    include_user_id: UUID | None = None,
) -> list[TenantMembership]:
    allowed_keys = {_uuid_key(uid) for uid in get_assignable_owner_user_ids(db, ctx)}
    if include_user_id is not None:
        allowed_keys.add(_uuid_key(include_user_id))
    allowed_keys.discard(None)
    if not allowed_keys:
        return []

    rows = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.user), joinedload(TenantMembership.role))
        .filter(
            uuid_eq(TenantMembership.tenant_id, ctx.tenant_id),
            TenantMembership.is_active.is_(True),
        )
        .all()
    )
    result: list[TenantMembership] = []
    for membership in rows:
        if membership.role is None and membership.role_id is not None:
            membership.role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.id, membership.role_id))
                .first()
            )
        if _uuid_key(membership.user_id) in allowed_keys:
            result.append(membership)
    return sorted(
        result,
        key=lambda m: (
            ((m.user.display_name if m.user else None) or (m.user.phone if m.user else None) or "").lower(),
            str(m.user_id),
        ),
    )
