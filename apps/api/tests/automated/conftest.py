"""pytest conftest — 自动化测试公共 fixture。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.models import Tenant, TenantMembership, User
from app.services.auth_service import hash_password
from app.services.membership_service import get_membership, list_active_memberships, seed_tenant_roles

from tests.http_client import check, req, reset_test_client

# ── 测试账号常量（与 verify_crm_helpers 保持一致）──
ADMIN_PHONE = "13900000099"
ADMIN_PASSWORD = "test123456"


# ── fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_session():
    """整个测试会话共享一个 db，每个用例自行 rollback。"""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="session")
def admin_token_fixture() -> str:
    """admin 账号登录 token。"""
    code, data = req("POST", "/auth/login", body={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    assert code == 200, f"admin login failed: {data}"
    return data["access_token"]


@pytest.fixture(scope="session")
def sales_token_fixture() -> str:
    """sales_a 登录 token。"""
    from tests.verify_crm_helpers import SALES_A_PHONE, CRM_TEST_PASSWORD, ensure_crm_test_users
    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    code, data = req("POST", "/auth/login", body={"phone": SALES_A_PHONE, "password": CRM_TEST_PASSWORD})
    assert code == 200, f"sales_a login failed: {data}"
    token = data["access_token"]
    code, me = req("GET", "/auth/me", token=token)
    if me.get("need_select_tenant") and me.get("tenants"):
        from tests.verify_crm_helpers import select_tenant
        token = select_tenant(token, me["tenants"][0]["id"])
    return token


@pytest.fixture(scope="session")
def second_tenant_token() -> str:
    """创建一个独立租户及其管理员，返回 token，用于多租户隔离测试。"""
    db = SessionLocal()
    try:
        phone = f"13{uuid4().int % 10**9:09d}"
        password = f"Test{uuid4().hex[:8]}"
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name="隔离租户Admin",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        tenant = Tenant(name=f"隔离租户-{uuid4().hex[:8]}", industry_code="finance")
        db.add(tenant)
        db.flush()
        admin_role, _ = seed_tenant_roles(db, tenant.id)
        db.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, role_id=admin_role.id, is_active=True))
        user.tenant_id = tenant.id
        db.commit()
        tenant_id = str(tenant.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, f"second tenant login failed: {data}"
    return data["access_token"]
