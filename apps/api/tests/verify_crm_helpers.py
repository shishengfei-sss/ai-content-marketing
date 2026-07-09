"""CRM 验收共享工具（verify_crm_*.py）。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from uuid import UUID

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy.orm import Session

from app.models import TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_EDITOR, SYSTEM_ROLE_SALES
from app.services.auth_service import hash_password
from app.services.membership_service import get_membership
from tests.http_client import check, req, reset_test_client

ADMIN_PHONE = "13900000099"
ADMIN_PASSWORD = "test123456"
EDITOR_PHONE = "13900008888"
EDITOR_PASSWORD = "Test123456"
SALES_A_PHONE = "13900001001"
SALES_B_PHONE = "13900001002"
CRM_TEST_PASSWORD = "Test123456"


def lead_body(company_name: str, **extra) -> dict:
    """构造满足 LeadCreate 必填项的线索请求体。"""
    import uuid as _uuid

    tag = _uuid.uuid4().hex[:8]
    mobile = extra.pop("mobile", None) or f"139{int(tag, 16) % 100000000:08d}"
    contact_name = extra.pop("contact_name", "测试联系人")
    return {
        "company_name": company_name,
        "contact_name": contact_name,
        "mobile": mobile,
        **extra,
    }


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def select_tenant(token: str, tenant_id: str) -> str:
    code, data = req("POST", "/auth/select-tenant", token=token, body={"tenant_id": tenant_id})
    assert code == 200, data
    return data["access_token"]


def admin_token() -> str:
    return login(ADMIN_PHONE, ADMIN_PASSWORD)


def editor_token() -> str:
    token = login(EDITOR_PHONE, EDITOR_PASSWORD)
    code, me = req("GET", "/auth/me", token=token)
    tenant_b = me["tenants"][1]["id"]
    return select_tenant(token, tenant_b)


def _get_role_id(db: Session, tenant_id: UUID, code: str) -> UUID:
    role = db.query(TenantRole).filter(TenantRole.tenant_id == tenant_id, TenantRole.code == code).first()
    if not role:
        raise RuntimeError(f"role {code} not found for tenant {tenant_id}")
    return role.id


def ensure_crm_test_users(db: Session, admin_user_phone: str = ADMIN_PHONE) -> dict[str, str]:
    """确保 admin 租户下有 sales A/B 测试账号，返回 phone -> user_id。"""
    admin_user = db.query(User).filter(User.phone == admin_user_phone).first()
    if not admin_user or not admin_user.tenant_id:
        raise RuntimeError("admin test user missing tenant")
    tenant_id = admin_user.tenant_id
    sales_role_id = _get_role_id(db, tenant_id, SYSTEM_ROLE_SALES)
    out: dict[str, str] = {"tenant_id": str(tenant_id), "admin_user_id": str(admin_user.id)}

    for phone, name in ((SALES_A_PHONE, "销售A"), (SALES_B_PHONE, "销售B")):
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            user = User(
                phone=phone,
                hashed_password=hash_password(CRM_TEST_PASSWORD),
                display_name=name,
                role="user",
                is_active=True,
            )
            db.add(user)
            db.flush()
        user.tenant_id = tenant_id
        # 测试账号仅保留 admin 公司 membership，避免 /me 脏数据
        for m in list(db.query(TenantMembership).filter(TenantMembership.user_id == user.id).all()):
            if m.tenant_id != tenant_id:
                db.delete(m)
        membership = get_membership(db, user.id, tenant_id)
        if not membership:
            db.add(
                TenantMembership(
                    user_id=user.id,
                    tenant_id=tenant_id,
                    role_id=sales_role_id,
                    is_active=True,
                )
            )
        else:
            membership.role_id = sales_role_id
            membership.is_active = True
        out[phone] = str(user.id)
    db.commit()
    reset_test_client()
    return out


def sales_token(phone: str = SALES_A_PHONE, tenant_id: str | None = None) -> str:
    token = login(phone, CRM_TEST_PASSWORD)
    if tenant_id:
        return select_tenant(token, tenant_id)
    code, me = req("GET", "/auth/me", token=token)
    if me.get("need_select_tenant") and me.get("tenants"):
        return select_tenant(token, me["tenants"][0]["id"])
    if not me.get("active_tenant") and me.get("tenants"):
        return select_tenant(token, me["tenants"][0]["id"])
    return token


def run_pytest(test_path: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
    return r.returncode == 0


def check_files(results: list[bool], label: str, paths: list[Path]) -> None:
    missing = [str(p) for p in paths if not p.is_file()]
    results.append(check(f"{label} 文件存在", len(missing) == 0, ", ".join(missing) or "ok"))


def run_step_parser(step_choices: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=step_choices)
    return parser.parse_args()


def finish_phase(phase: str, results: list[bool]) -> int:
    passed = all(results) if results else False
    print(f"\n=== CRM-{phase}", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1
