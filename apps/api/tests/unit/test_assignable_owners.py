"""可分配负责人范围单元测试。"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.database import SessionLocal
from app.dependencies import TenantContext
from app.models import Tenant, TenantMembership, TenantRole, User
from app.models.crm import MembershipSalesProfile
from app.services.crm.sales_org_service import assert_can_assign_owner, get_assignable_owner_user_ids
from fastapi import HTTPException


def _ctx(role_code: str, user_id: uuid.UUID, membership_id: uuid.UUID, tenant_id: uuid.UUID) -> TenantContext:
    user = MagicMock()
    user.id = user_id
    membership = MagicMock()
    membership.id = membership_id
    membership.role = MagicMock()
    membership.role.code = role_code
    membership.role.permissions = []
    return TenantContext(user=user, tenant_id=tenant_id, membership=membership)


def test_assignable_includes_subordinates_and_peer_managers():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"assign-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()

        role_mgr = TenantRole(tenant_id=tenant.id, code="sales_manager", name="销售经理", is_system=True)
        role_sales = TenantRole(tenant_id=tenant.id, code="sales", name="销售", is_system=True)
        db.add_all([role_mgr, role_sales])
        db.flush()

        def add_user(name: str, role: TenantRole, reports_to: uuid.UUID | None = None):
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
                    reports_to_membership_id=reports_to,
                )
            )
            db.flush()
            return u, m

        boss_u, boss_m = add_user("Boss", role_mgr, None)
        mgr_a_u, mgr_a_m = add_user("MgrA", role_mgr, boss_m.id)
        mgr_b_u, mgr_b_m = add_user("MgrB", role_mgr, boss_m.id)
        sales_u, sales_m = add_user("Sales", role_sales, mgr_a_m.id)
        other_sales_u, _ = add_user("OtherSales", role_sales, mgr_b_m.id)

        ctx = _ctx("sales_manager", mgr_a_u.id, mgr_a_m.id, tenant.id)
        allowed = get_assignable_owner_user_ids(db, ctx)
        assert mgr_a_u.id in allowed
        assert sales_u.id in allowed
        assert mgr_b_u.id in allowed
        assert other_sales_u.id not in allowed
        assert boss_u.id not in allowed

        assert_can_assign_owner(db, ctx, sales_u.id)
        assert_can_assign_owner(db, ctx, mgr_b_u.id)
        try:
            assert_can_assign_owner(db, ctx, other_sales_u.id)
            assert False, "expected HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
    finally:
        db.rollback()
        db.close()


def test_admin_can_assign_anyone():
    db = SessionLocal()
    try:
        tenant = Tenant(name=f"assign-admin-{uuid.uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        role_admin = TenantRole(tenant_id=tenant.id, code="admin", name="管理员", is_system=True)
        role_sales = TenantRole(tenant_id=tenant.id, code="sales", name="销售", is_system=True)
        db.add_all([role_admin, role_sales])
        db.flush()

        admin_u = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Admin",
            role="user",
            is_active=True,
        )
        sales_u = User(
            phone=f"13{uuid.uuid4().int % 10**9:09d}",
            hashed_password="x",
            display_name="Sales",
            role="user",
            is_active=True,
        )
        db.add_all([admin_u, sales_u])
        db.flush()
        admin_m = TenantMembership(user_id=admin_u.id, tenant_id=tenant.id, role_id=role_admin.id, is_active=True)
        sales_m = TenantMembership(user_id=sales_u.id, tenant_id=tenant.id, role_id=role_sales.id, is_active=True)
        db.add_all([admin_m, sales_m])
        db.flush()

        ctx = _ctx("admin", admin_u.id, admin_m.id, tenant.id)
        allowed = get_assignable_owner_user_ids(db, ctx)
        assert sales_u.id in allowed
        assert admin_u.id in allowed
    finally:
        db.rollback()
        db.close()
