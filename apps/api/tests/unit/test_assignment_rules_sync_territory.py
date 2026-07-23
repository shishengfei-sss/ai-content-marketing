"""自动分配规则改负责人后应同步销售区域，避免原地区人员仍可见。"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.database import SessionLocal
from app.dependencies import TenantContext
from app.models import Tenant, TenantMembership, TenantRole, User
from app.models.crm import AssignmentRule, Lead, MembershipSalesProfile, SalesTerritory
from app.services.crm.assignment_service import apply_assignment_rules
from app.services.crm.crm_scope_service import can_view_lead


def _ctx(user: User, membership: TenantMembership, tenant_id) -> TenantContext:
    ctx_user = MagicMock()
    ctx_user.id = user.id
    mem = MagicMock()
    mem.id = membership.id
    role = MagicMock()
    role.code = "sales"
    role.permissions = [
        MagicMock(permission_code=p)
        for p in ("crm.lead.list_own", "crm.lead.list_territory", "crm.lead.create")
    ]
    mem.role = role
    return TenantContext(user=ctx_user, tenant_id=tenant_id, membership=mem)


def test_assignment_rules_sync_territory_hides_from_creator_region():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"asn-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()

        role = TenantRole(tenant_id=tenant.id, code="sales", name="销售", is_system=True)
        db.add(role)
        db.flush()

        east = SalesTerritory(tenant_id=tenant.id, name="华东", code=f"e-{uuid.uuid4().hex[:4]}")
        south = SalesTerritory(tenant_id=tenant.id, name="华南", code=f"s-{uuid.uuid4().hex[:4]}")
        db.add_all([east, south])
        db.flush()

        def add_user(name: str, territory_id):
            u = User(
                phone=f"13{uuid.uuid4().int % 10**9:09d}",
                hashed_password="x",
                display_name=name,
                role="user",
                is_active=True,
            )
            db.add(u)
            db.flush()
            m = TenantMembership(user_id=u.id, tenant_id=tenant.id, role_id=role.id, is_active=True)
            db.add(m)
            db.flush()
            db.add(
                MembershipSalesProfile(
                    membership_id=m.id,
                    primary_territory_id=territory_id,
                )
            )
            db.flush()
            return u, m

        east_u, east_m = add_user("EastSales", east.id)
        south_u, _ = add_user("SouthSales", south.id)

        db.add(
            AssignmentRule(
                tenant_id=tenant.id,
                name="固定给华南",
                condition_json={"field": "source", "operator": "contains", "value": ""},
                assign_type="fixed_user",
                target_id=south_u.id,
                priority=0,
                is_active=True,
            )
        )
        db.flush()

        lead = Lead(
            tenant_id=tenant.id,
            company_name="分配后应不可见",
            source="官网",
            owner_user_id=east_u.id,
            territory_id=east.id,
            manager_user_id=None,
            created_by_user_id=east_u.id,
        )
        db.add(lead)
        db.flush()

        ctx = _ctx(east_u, east_m, tenant.id)
        apply_assignment_rules(db, ctx, lead)
        db.flush()

        assert lead.owner_user_id == south_u.id
        assert lead.territory_id == south.id

        assert (
            can_view_lead(
                ctx,
                db,
                lead.owner_user_id,
                lead.territory_id,
                created_by_user_id=lead.created_by_user_id,
                manager_user_id=lead.manager_user_id,
            )
            is False
        )
    finally:
        db.rollback()
        db.close()
