#!/usr/bin/env python3
"""CRM-2a 验收：营销活动（docs/v0.5-crm执行计划.md §6）。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.models import Content, TenantMembership, User
from app.permissions import SYSTEM_ROLE_MARKETING
from tests.alembic_head import is_at_expected_head
from tests.verify_crm_helpers import (
    admin_token,
    check,
    check_files,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    req,
    run_step_parser,
    sales_token,
)

MARKETING_PHONE = "13900001004"


def _ensure_marketing_user(db) -> None:
    from app.models import TenantRole
    from app.services.auth_service import hash_password
    from app.services.membership_service import get_membership

    base = ensure_crm_test_users(db)
    tenant_id = uuid.UUID(base["tenant_id"])
    role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_MARKETING)
        .first()
    )
    user = db.query(User).filter(User.phone == MARKETING_PHONE).first()
    if not user:
        user = User(
            phone=MARKETING_PHONE,
            hashed_password=hash_password("Test123456"),
            display_name="市场专员",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
    user.tenant_id = tenant_id
    membership = get_membership(db, user.id, tenant_id)
    if not membership:
        db.add(
            TenantMembership(user_id=user.id, tenant_id=tenant_id, role_id=role.id, is_active=True)
        )
    else:
        membership.role_id = role.id
    db.commit()


def marketing_token() -> str:
    from tests.verify_crm_helpers import CRM_TEST_PASSWORD, login, select_tenant

    token = login(MARKETING_PHONE, CRM_TEST_PASSWORD)
    code, me = req("GET", "/auth/me", token=token)
    if me.get("need_select_tenant") and me.get("tenants"):
        return select_tenant(token, me["tenants"][0]["id"])
    return token


def step_2a_1(results: list[bool]) -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("V2a-1-0 alembic", is_at_expected_head(out), out.strip()[:60]))
    insp = inspect(engine)
    for table in ("marketing_campaigns", "campaign_contents"):
        results.append(check(f"V2a-1-1 表 {table}", insp.has_table(table)))


def step_2a_2(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
        _ensure_marketing_user(db)
    finally:
        db.close()

    mkt = marketing_token()
    code, camp = req(
        "POST",
        "/crm/campaigns",
        token=mkt,
        body={"name": f"春季获客-{uuid.uuid4().hex[:6]}", "status": "active"},
    )
    results.append(check("V2a-2-1 marketing创建", code == 201, str(code)))

    code, _ = req(
        "POST",
        "/crm/campaigns",
        token=sales_token(),
        body={"name": "非法活动"},
    )
    results.append(check("V2a-2-2 sales不可创建403", code == 403, str(code)))

    results.append(check("V2a-2-3 活动ID", "id" in camp, str(camp.get("id"))))


def step_2a_3(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_marketing_user(db)
        mkt_user = db.query(User).filter(User.phone == MARKETING_PHONE).first()
        tenant_id = uuid.UUID(ctx["tenant_id"])
        contents = []
        for i in range(2):
            c = Content(
                tenant_id=tenant_id,
                author_id=mkt_user.id,
                platform="wechat",
                topic=f"活动文案{i}-{uuid.uuid4().hex[:4]}",
                body="test",
            )
            db.add(c)
            db.flush()
            contents.append(c)
        db.commit()
        content_ids = [str(c.id) for c in contents]
    finally:
        db.close()

    mkt = marketing_token()
    code, camp = req(
        "POST",
        "/crm/campaigns",
        token=mkt,
        body={"name": f"内容关联-{uuid.uuid4().hex[:6]}"},
    )
    camp_id = camp["id"]

    for cid in content_ids:
        code, _ = req(
            "POST",
            f"/crm/campaigns/{camp_id}/contents",
            token=mkt,
            body={"content_id": cid},
        )
        results.append(check("V2a-3-1 关联内容", code == 201, str(code)))

    code, detail = req("GET", f"/crm/campaigns/{camp_id}", token=mkt)
    results.append(check("V2a-3-2 content_count=2", detail.get("content_count") == 2, str(detail)))

    code, listed = req("GET", f"/content?campaign_id={camp_id}", token=mkt)
    results.append(check("V2a-3-3 内容库筛选", code == 200 and listed.get("total") == 2, str(listed)))


def step_2a_4(results: list[bool]) -> None:
    from app.schemas import ContentGenerateRequest

    fields = ContentGenerateRequest.model_fields
    results.append(check("V2a-4-1 generate含campaign_id", "campaign_id" in fields, str(fields.keys())))

    create_vue = WEB_SRC / "views" / "Create.vue"
    if create_vue.is_file():
        text = create_vue.read_text(encoding="utf-8")
        results.append(check("V2a-4-2 Create.vue", "campaign_id" in text or "campaign" in text.lower(), "Create.vue"))
    else:
        results.append(check("V2a-4-2 Create.vue", False, "missing"))


def step_2a_5(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
        _ensure_marketing_user(db)
    finally:
        db.close()

    mkt = marketing_token()
    sales_a = sales_token()

    code, camp = req(
        "POST",
        "/crm/campaigns",
        token=mkt,
        body={"name": f"Phase验收-{uuid.uuid4().hex[:6]}"},
    )
    results.append(check("V2a-5-1 marketing可建", code == 201, str(code)))
    code, _ = req("POST", "/crm/campaigns", token=sales_a, body={"name": "x"})
    results.append(check("V2a-5-1 sales不可建", code == 403, str(code)))

    camp_id = camp["id"]
    req(
        "POST",
        "/crm/leads",
        token=mkt,
        body=lead_body("活动线索A", campaign_id=camp_id),
    )
    req(
        "POST",
        "/crm/leads",
        token=mkt,
        body=lead_body("活动线索B", campaign_id=camp_id),
    )
    code, detail = req("GET", f"/crm/campaigns/{camp_id}", token=mkt)
    results.append(check("V2a-5-2 lead_count=2", detail.get("lead_count") == 2, str(detail)))

    db = SessionLocal()
    content_ids: list[str] = []
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_marketing_user(db)
        mkt_user = db.query(User).filter(User.phone == MARKETING_PHONE).first()
        tenant_id = uuid.UUID(ctx["tenant_id"])
        for i in range(2):
            c = Content(
                tenant_id=tenant_id,
                author_id=mkt_user.id,
                platform="wechat",
                topic=f"phase-{uuid.uuid4().hex[:6]}-{i}",
                body="b",
            )
            db.add(c)
            db.flush()
            content_ids.append(str(c.id))
        db.commit()
    finally:
        db.close()

    for cid in content_ids:
        req(
            "POST",
            f"/crm/campaigns/{camp_id}/contents",
            token=mkt,
            body={"content_id": cid},
        )

    code, detail2 = req("GET", f"/crm/campaigns/{camp_id}", token=mkt)
    results.append(check("V2a-5-3 content_count=2", detail2.get("content_count") == 2, str(detail2)))


STEPS = {
    "2a-1": step_2a_1,
    "2a-2": step_2a_2,
    "2a-3": step_2a_3,
    "2a-4": step_2a_4,
    "2a-5": step_2a_5,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    try:
        if args.step:
            STEPS[args.step](results)
        else:
            for key in STEPS:
                STEPS[key](results)
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    return finish_phase("2a", results)


if __name__ == "__main__":
    raise SystemExit(main())
