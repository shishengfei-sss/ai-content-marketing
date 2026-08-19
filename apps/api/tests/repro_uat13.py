import os, sys, uuid
os.environ["DATABASE_URL"]="sqlite:///./test_repro2.db"
os.environ.setdefault("LLM_PROVIDER","fake"); os.environ.setdefault("SMS_PROVIDER","mock")
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM","1"); os.environ["VERIFY_LIVE_API"]="0"
API=os.path.dirname(os.path.abspath(__file__))
for p in (API, os.path.dirname(API)):
    if p not in sys.path: sys.path.insert(0,p)
from app.database import SessionLocal, engine
from sqlalchemy import text
from tests.verify_crm_helpers import (SALES_A_PHONE, ensure_crm_test_users, sales_token, lead_body, req)
db=SessionLocal(); ctx=ensure_crm_test_users(db); db.close()
tenant_id=ctx["tenant_id"]
sales_a=sales_token(SALES_A_PHONE, tenant_id)
tag=uuid.uuid4().hex[:6]
code,lead=req("POST","/crm/leads",token=sales_a,body=lead_body(f"UAT13-{tag}",mobile=f"139{int(tag,16)%100000000:08d}"))
print(f"[uat13 lead create] code={code}")
print(f"  detail={lead}")
# 查 SALES_A 默认销售区域 (membership_sales_profiles)
with engine.connect() as c:
    u=c.execute(text("SELECT id FROM users WHERE phone=:p"),{"p":SALES_A_PHONE}).fetchone()
    if u:
        uid=str(u[0])
        m=c.execute(text("SELECT primary_territory_id FROM membership_sales_profiles WHERE user_id=:u AND tenant_id=:t"),{"u":uid,"t":str(tenant_id)}).fetchone()
        print(f"  SALES_A primary_territory_id in tenant {tenant_id}: {m[0] if m else None}")
