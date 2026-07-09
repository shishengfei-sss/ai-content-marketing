"""CRM scope 单元测试（FR-CRM-SCOPE 并集）。"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.database import SessionLocal
from app.dependencies import TenantContext
from app.models import Tenant, TenantMembership, User
from app.models.crm import Lead, MembershipSalesProfile, SalesTerritory
from app.services.crm.crm_scope_service import (
    apply_lead_list_scope,
    can_view_lead,
    has_lead_list_permission,
)


def _ctx(*perms: str, user_id: uuid.UUID | None = None, membership_id: uuid.UUID | None = None) -> TenantContext:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    membership = MagicMock()
    membership.id = membership_id or uuid.uuid4()
    membership.role.permissions = [MagicMock(permission_code=p) for p in perms]
    return TenantContext(user=user, tenant_id=uuid.uuid4(), membership=membership)


def test_list_all_returns_all():
    ctx = _ctx("crm.lead.list_all")
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-test-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        owner = uuid.uuid4()
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="A",
                owner_user_id=owner,
                created_by_user_id=owner,
            )
        )
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="B",
                owner_user_id=uuid.uuid4(),
                created_by_user_id=owner,
            )
        )
        db.flush()
        q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.deleted_at.is_(None))
        q = apply_lead_list_scope(q, ctx, db)
        assert q.count() == 2
    finally:
        db.rollback()
        db.close()


def test_list_own_filters_owner():
    me = uuid.uuid4()
    ctx = _ctx("crm.lead.list_own", user_id=me)
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-own-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        db.add(Lead(tenant_id=tenant.id, company_name="Mine", owner_user_id=me, created_by_user_id=me))
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="Other",
                owner_user_id=uuid.uuid4(),
                created_by_user_id=me,
            )
        )
        db.flush()
        q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.deleted_at.is_(None))
        q = apply_lead_list_scope(q, ctx, db)
        assert q.count() == 1
        assert q.first().company_name == "Mine"
    finally:
        db.rollback()
        db.close()


def test_list_team_sees_subordinate():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-team-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        manager_user = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Mgr",
            role="user",
            is_active=True,
        )
        rep_user = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Rep",
            role="user",
            is_active=True,
        )
        db.add_all([manager_user, rep_user])
        db.flush()
        from app.models import TenantRole

        role = TenantRole(tenant_id=tenant.id, code="sales_manager", name="经理", is_system=True)
        db.add(role)
        db.flush()
        mgr_mem = TenantMembership(user_id=manager_user.id, tenant_id=tenant.id, role_id=role.id)
        rep_mem = TenantMembership(user_id=rep_user.id, tenant_id=tenant.id, role_id=role.id)
        db.add_all([mgr_mem, rep_mem])
        db.flush()
        db.add(
            MembershipSalesProfile(
                membership_id=rep_mem.id,
                reports_to_membership_id=mgr_mem.id,
            )
        )
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="RepLead",
                owner_user_id=rep_user.id,
                created_by_user_id=rep_user.id,
            )
        )
        db.flush()
        ctx = _ctx("crm.lead.list_team", user_id=manager_user.id, membership_id=mgr_mem.id)
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        ctx.membership.id = mgr_mem.id
        q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.deleted_at.is_(None))
        q = apply_lead_list_scope(q, ctx, db)
        assert q.count() == 1
        assert q.first().company_name == "RepLead"
    finally:
        db.rollback()
        db.close()


def test_list_territory_sees_territory_lead():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-terr-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        user = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Terr",
            role="user",
            is_active=True,
        )
        other = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Other",
            role="user",
            is_active=True,
        )
        db.add_all([user, other])
        db.flush()
        from app.models import TenantRole

        role = TenantRole(tenant_id=tenant.id, code="sales", name="销售", is_system=True)
        db.add(role)
        db.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, role_id=role.id)
        db.add(membership)
        db.flush()
        root = SalesTerritory(tenant_id=tenant.id, name="华东", code="east")
        child = SalesTerritory(tenant_id=tenant.id, name="上海", code="sh")
        db.add(root)
        db.flush()
        child.parent_id = root.id
        db.add(child)
        db.flush()
        db.add(MembershipSalesProfile(membership_id=membership.id, primary_territory_id=root.id))
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="ShLead",
                owner_user_id=other.id,
                territory_id=child.id,
                created_by_user_id=other.id,
            )
        )
        db.flush()
        ctx = _ctx("crm.lead.list_territory", user_id=user.id, membership_id=membership.id)
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        ctx.membership.id = membership.id
        q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.deleted_at.is_(None))
        q = apply_lead_list_scope(q, ctx, db)
        assert q.count() == 1
    finally:
        db.rollback()
        db.close()


def test_territory_union_without_team():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-u-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        user = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="U",
            role="user",
            is_active=True,
        )
        stranger = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="S",
            role="user",
            is_active=True,
        )
        db.add_all([user, stranger])
        db.flush()
        from app.models import TenantRole

        role = TenantRole(tenant_id=tenant.id, code="sales", name="销售", is_system=True)
        db.add(role)
        db.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, role_id=role.id)
        db.add(membership)
        db.flush()
        terr = SalesTerritory(tenant_id=tenant.id, name="华南", code="south")
        db.add(terr)
        db.flush()
        db.add(MembershipSalesProfile(membership_id=membership.id, primary_territory_id=terr.id))
        lead = Lead(
            tenant_id=tenant.id,
            company_name="TerrOnly",
            owner_user_id=stranger.id,
            territory_id=terr.id,
            created_by_user_id=stranger.id,
        )
        db.add(lead)
        db.flush()
        ctx = _ctx("crm.lead.list_territory", user_id=user.id, membership_id=membership.id)
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        ctx.membership.id = membership.id
        assert can_view_lead(ctx, db, stranger.id, terr.id) is True
    finally:
        db.rollback()
        db.close()


def test_no_territory_no_subordinate_only_own():
    me = uuid.uuid4()
    ctx = _ctx("crm.lead.list_team", "crm.lead.list_territory", user_id=me)
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"scope-edge-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        ctx = TenantContext(user=ctx.user, tenant_id=tenant.id, membership=ctx.membership)
        other = uuid.uuid4()
        db.add(Lead(tenant_id=tenant.id, company_name="Mine", owner_user_id=me, created_by_user_id=me))
        db.add(
            Lead(
                tenant_id=tenant.id,
                company_name="Other",
                owner_user_id=other,
                created_by_user_id=me,
            )
        )
        db.flush()
        q = db.query(Lead).filter(Lead.tenant_id == tenant.id, Lead.deleted_at.is_(None))
        q = apply_lead_list_scope(q, ctx, db)
        assert q.count() == 1
    finally:
        db.rollback()
        db.close()


def test_no_list_permission_empty():
    ctx = _ctx("crm.lead.view")
    assert has_lead_list_permission(ctx) is False


def test_has_list_own_permission():
    ctx = _ctx("crm.lead.list_own", "crm.lead.view")
    assert has_lead_list_permission(ctx) is True
