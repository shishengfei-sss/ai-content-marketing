"""精准复现 CRM-2a step_2a_5 的线索关联计数逻辑，打印真实返回码。"""
import os
import sys
import uuid

# 必须在 import app 之前设好数据库与 stub 环境变量
os.environ["DATABASE_URL"] = "sqlite:///./test_repro.db"
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("SMS_PROVIDER", "mock")
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

API_ROOT = os.path.dirname(os.path.abspath(__file__))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
PARENT = os.path.dirname(API_ROOT)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from sqlalchemy import inspect
from app.database import SessionLocal, engine
from app.models import Content, TenantMembership, User, TenantRole
from app.permissions import SYSTEM_ROLE_MARKETING
from app.services.auth_service import hash_password
from app.services.membership_service import get_membership
from tests.verify_crm_helpers import (
    CRM_TEST_PASSWORD,
    admin_token,
    ensure_crm_test_users,
    login,
    lead_body,
    req,
    sales_token,
    select_tenant,
)

MARKETING_PHONE = "13900001004"


def ensure_marketing_user(db):
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
        db.add(TenantMembership(user_id=user.id, tenant_id=tenant_id, role_id=role.id, is_active=True))
    else:
        membership.role_id = role.id
    db.commit()
    return base


def marketing_token():
    token = login(MARKETING_PHONE, CRM_TEST_PASSWORD)
    code, me = req("GET", "/auth/me", token=token)
    if me.get("need_select_tenant") and me.get("tenants"):
        return select_tenant(token, me["tenants"][0]["id"])
    return token


def main() -> None:
    db = SessionLocal()
    try:
        ctx = ensure_marketing_user(db)
    finally:
        db.close()

    mkt = marketing_token()
    sales_a = sales_token()

    code, camp = req("POST", "/crm/campaigns", token=mkt, body={"name": f"Phase验收-{uuid.uuid4().hex[:6]}"})
    print(f"[campaign create] code={code} id={camp.get('id')}")
    camp_id = camp["id"]

    r1 = req("POST", "/crm/leads", token=mkt, body=lead_body("活动线索A", campaign_id=camp_id))
    print(f"[lead A] code={r1[0]} body={r1[1]}")
    r2 = req("POST", "/crm/leads", token=mkt, body=lead_body("活动线索B", campaign_id=camp_id))
    print(f"[lead B] code={r2[0]} body={r2[1]}")

    code, detail = req("GET", f"/crm/campaigns/{camp_id}", token=mkt)
    print(f"[campaign detail] code={code} lead_count={detail.get('lead_count')} content_count={detail.get('content_count')}")

    # 直接查库确认 lead 的 tenant_id 与 campaign_id
    insp = inspect(engine)
    if insp.has_table("leads"):
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, tenant_id, campaign_id, company_name FROM leads WHERE campaign_id = :cid"),
                {"cid": str(camp_id)},
            ).fetchall()
            print(f"[db] leads with campaign_id={camp_id}: {len(rows)}")
            for r in rows:
                print("   ", dict(zip(["id", "tenant_id", "campaign_id", "company_name"], r)))
            # 取该 campaign 的 tenant
            camp_row = conn.execute(
                text("SELECT tenant_id FROM marketing_campaigns WHERE id = :cid"),
                {"cid": str(camp_id)},
            ).fetchone()
            print(f"[db] campaign tenant_id={camp_row[0] if camp_row else None}")


if __name__ == "__main__":
    main()
