#!/usr/bin/env python3
"""CRM-1b 验收：销售组织 + Scope 并集（docs/v0.5-crm执行计划.md §4）。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import inspect, text

from app.config import settings
from app.database import SessionLocal, engine
from app.models import TenantMembership, User
from app.permissions import SYSTEM_ROLE_SALES, SYSTEM_ROLE_SALES_MANAGER
from tests.alembic_head import is_at_expected_head
from tests.verify_crm_helpers import (
    SALES_A_PHONE,
    SALES_B_PHONE,
    admin_token,
    check,
    check_files,
    editor_token,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    req,
    run_pytest,
    run_step_parser,
    sales_token,
)

SALES_MGR_PHONE = "13900001003"


def _ensure_sales_manager(db) -> dict[str, str]:
    from app.models import TenantRole
    from app.services.auth_service import hash_password
    from app.services.membership_service import get_membership

    from app.services.auth_service import hash_password

    base = ensure_crm_test_users(db)
    tenant_id = base["tenant_id"]
    mgr_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == uuid.UUID(str(tenant_id)), TenantRole.code == SYSTEM_ROLE_SALES_MANAGER)
        .first()
    )
    if not mgr_role:
        raise RuntimeError("sales_manager role missing")
    user = db.query(User).filter(User.phone == SALES_MGR_PHONE).first()
    if not user:
        user = User(
            phone=SALES_MGR_PHONE,
            hashed_password=hash_password("Test123456"),
            display_name="销售经理",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
    user.tenant_id = uuid.UUID(tenant_id)
    membership = get_membership(db, user.id, uuid.UUID(tenant_id))
    if not membership:
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=uuid.UUID(tenant_id),
                role_id=mgr_role.id,
                is_active=True,
            )
        )
    else:
        membership.role_id = mgr_role.id
    db.commit()
    base["manager_user_id"] = str(user.id)
    base["manager_phone"] = SALES_MGR_PHONE
    return base


def step_1b_1(results: list[bool]) -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("V1b-1-0 alembic", is_at_expected_head(out), out.strip()[:80]))

    insp = inspect(engine)
    for table in ("sales_territories", "membership_sales_profile"):
        results.append(check(f"V1b-1-1 表 {table}", insp.has_table(table)))

    with engine.connect() as conn:
        cols = {c["name"]: c for c in insp.get_columns("sales_territories")}
        results.append(check("V1b-1-1 parent_id", "parent_id" in cols))
        results.append(check("V1b-1-1 manager_membership_id", "manager_membership_id" in cols))
        mgr_nullable = cols.get("manager_membership_id", {}).get("nullable", False)
        results.append(check("V1b-1-1 manager可空", mgr_nullable is True))

        pk = insp.get_pk_constraint("membership_sales_profile")
        results.append(check("V1b-1-2 membership_id唯一", pk.get("constrained_columns") == ["membership_id"]))


def step_1b_2(results: list[bool]) -> None:
    admin = admin_token()
    code, parent = req("POST", "/crm/territories", token=admin, body={"name": "华东", "code": "east"})
    results.append(check("V1b-2-1 创建父地区", code == 201, str(code)))
    parent_id = parent["id"]

    code, child = req(
        "POST",
        "/crm/territories",
        token=admin,
        body={"name": "上海", "code": "sh", "parent_id": parent_id},
    )
    results.append(check("V1b-2-1 创建子地区", code == 201, str(code)))

    code, _ = req(
        "PATCH",
        f"/crm/territories/{parent_id}",
        token=admin,
        body={"parent_id": child["id"]},
    )
    results.append(check("V1b-2-2 地区成环422", code == 422, str(code)))

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        mgr = _ensure_sales_manager(db)
        sales_a_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_A_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        mgr_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_MGR_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        assert sales_a_mid and mgr_mid
        code, _ = req(
            "PATCH",
            f"/crm/sales-profiles/{sales_a_mid.id}",
            token=admin,
            body={"reports_to_membership_id": str(mgr_mid.id)},
        )
        results.append(check("V1b-2-3 设置汇报", code == 200, str(code)))
        code, _ = req(
            "PATCH",
            f"/crm/sales-profiles/{mgr_mid.id}",
            token=admin,
            body={"reports_to_membership_id": str(sales_a_mid.id)},
        )
        results.append(check("V1b-2-3 汇报成环422", code == 422, str(code)))
    finally:
        db.close()

    code, _ = req("POST", "/crm/territories", token=sales_token(), body={"name": "非法"})
    results.append(check("V1b-2-4 sales无org.manage403", code == 403, str(code)))


def step_1b_3(results: list[bool]) -> None:
    results.append(check("V1b-3-4 unit test_crm_scope", run_pytest("tests/unit/test_crm_scope.py")))


def step_1b_4(results: list[bool]) -> None:
    check_files(
        results,
        "V1b-4-1 Web页面",
        [WEB_SRC / "views" / "SettingsCrmOrg.vue"],
    )
    router_text = (WEB_SRC / "router.js").read_text(encoding="utf-8")
    results.append(
        check(
            "V1b-4-1 路由",
            "SettingsCrmOrg" in router_text and "crm.org.manage" in router_text,
            "router.js",
        )
    )
    sales = sales_token()
    code, _ = req("GET", "/crm/territories", token=sales)
    results.append(check("V1b-4-2 sales不可见组织403", code == 403, str(code)))


def step_1b_5(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        mgr = _ensure_sales_manager(db)
        sales_a_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_A_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        mgr_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_MGR_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        assert sales_a_mid and mgr_mid
        req(
            "PATCH",
            f"/crm/sales-profiles/{sales_a_mid.id}",
            token=admin,
            body={"reports_to_membership_id": str(mgr_mid.id)},
        )
        sales_a = sales_token(SALES_A_PHONE)
        sales_b = sales_token(SALES_B_PHONE)
        mgr_token = sales_token(SALES_MGR_PHONE)

        code, lead = req(
            "POST",
            "/crm/leads",
            token=sales_a,
            body=lead_body(f"下级线索-{uuid.uuid4().hex[:6]}"),
        )
        results.append(check("V1b-5-0 A建线索", code == 201, str(code)))

        code, listed = req("GET", "/crm/leads", token=mgr_token)
        ids = [i["id"] for i in listed.get("items", [])]
        results.append(check("V1b-5-1 manager见下级", lead["id"] in ids, str(ids[:3])))

        code, b_list = req("GET", "/crm/leads", token=sales_b)
        b_ids = [i["id"] for i in b_list.get("items", [])]
        results.append(check("V1b-5-1 B不见A线索", lead["id"] not in b_ids, str(b_ids)))

        stranger = str(uuid.uuid4())
        code, tampered = req("GET", f"/crm/leads?owner_id={stranger}", token=mgr_token)
        tampered_ids = [i["id"] for i in tampered.get("items", [])]
        results.append(check("V1b-5-2 篡改owner_id不越权", len(tampered_ids) == 0, str(tampered_ids)))
    finally:
        db.close()


STEPS = {
    "1b-1": step_1b_1,
    "1b-2": step_1b_2,
    "1b-3": step_1b_3,
    "1b-4": step_1b_4,
    "1b-5": step_1b_5,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    try:
        if args.step:
            STEPS[args.step](results)
        else:
            for fn in STEPS.values():
                fn(results)
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    return finish_phase("1b", results)


if __name__ == "__main__":
    raise SystemExit(main())
