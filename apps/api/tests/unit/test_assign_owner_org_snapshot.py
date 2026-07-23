"""分配负责人后组织快照同步，避免原负责人跨区仍可见。"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.database import SessionLocal
from app.dependencies import TenantContext
from app.models import Tenant, TenantMembership, TenantRole, User
from app.models.crm import Lead, MembershipSalesProfile, SalesTerritory
from app.services.crm.crm_scope_service import can_view_lead
from app.services.crm.sales_org_service import apply_owner_org_snapshot


def _membership_ctx(user: User, membership: TenantMembership, tenant_id) -> TenantContext:
    ctx_user = MagicMock()
    ctx_user.id = user.id
    mem = MagicMock()
    mem.id = membership.id
    role = MagicMock()
    role.code = "sales_manager"
    role.permissions = [
        MagicMock(permission_code=p)
        for p in (
            "crm.lead.list_own",
            "crm.lead.list_team",
            "crm.lead.list_territory",
            "crm.lead.assign",
        )
    ]
    mem.role = role
    return TenantContext(user=ctx_user, tenant_id=tenant_id, membership=mem)


def test_assign_owner_snapshot_hides_from_previous_manager_territory():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"snap-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()

        role_mgr = TenantRole(tenant_id=tenant.id, code="sales_manager", name="销售经理", is_system=True)
        db.add(role_mgr)
        db.flush()

        east = SalesTerritory(tenant_id=tenant.id, name="华东", code=f"e-{uuid.uuid4().hex[:4]}")
        south = SalesTerritory(tenant_id=tenant.id, name="华南", code=f"s-{uuid.uuid4().hex[:4]}")
        db.add_all([east, south])
        db.flush()

        def add_mgr(name: str, territory_id):
            u = User(
                phone=f"13{uuid.uuid4().int % 10**9:09d}",
                hashed_password="x",
                display_name=name,
                role="user",
                is_active=True,
            )
            db.add(u)
            db.flush()
            m = TenantMembership(user_id=u.id, tenant_id=tenant.id, role_id=role_mgr.id, is_active=True)
            db.add(m)
            db.flush()
            db.add(
                MembershipSalesProfile(
                    membership_id=m.id,
                    primary_territory_id=territory_id,
                    reports_to_membership_id=None,
                )
            )
            db.flush()
            return u, m

        a_u, a_m = add_mgr("MgrEast", east.id)
        b_u, b_m = add_mgr("MgrSouth", south.id)

        lead = Lead(
            tenant_id=tenant.id,
            company_name="跨区线索",
            owner_user_id=a_u.id,
            territory_id=east.id,
            manager_user_id=None,
            created_by_user_id=a_u.id,
        )
        db.add(lead)
        db.flush()

        snap_t, snap_m = apply_owner_org_snapshot(db, tenant.id, b_u.id)
        assert snap_t == south.id
        lead.owner_user_id = b_u.id
        lead.territory_id = snap_t
        lead.manager_user_id = snap_m
        db.flush()

        ctx_a = _membership_ctx(a_u, a_m, tenant.id)
        ctx_b = _membership_ctx(b_u, b_m, tenant.id)

        assert (
            can_view_lead(
                ctx_a,
                db,
                lead.owner_user_id,
                lead.territory_id,
                created_by_user_id=lead.created_by_user_id,
                manager_user_id=lead.manager_user_id,
            )
            is False
        )
        assert (
            can_view_lead(
                ctx_b,
                db,
                lead.owner_user_id,
                lead.territory_id,
                created_by_user_id=lead.created_by_user_id,
                manager_user_id=lead.manager_user_id,
            )
            is True
        )
    finally:
        db.rollback()
        db.close()
