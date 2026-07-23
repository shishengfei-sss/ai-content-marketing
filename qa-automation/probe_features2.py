import sys, json, io
sys.path.insert(0, ".")
from helpers import register

tok, phone, err = register("功能探针2租户")
print("tok?", bool(tok))
import httpx
BASE = "http://127.0.0.1:8000/api/v1"
H = {"Authorization": f"Bearer {tok}"}

def call(method, path, json_body=None, files=None):
    h2 = dict(H)
    if files: h2.pop("Content-Type", None)
    else: h2["Content-Type"]="application/json"
    r = httpx.request(method, BASE+path, headers=h2, json=json_body, files=files, timeout=30)
    try: body=r.json()
    except: body=r.text[:200]
    return r.status_code, body

# valid user id
me = call("GET","/auth/me")[1]
uid = me.get("id") or (me.get("active_tenant",{}) and None)
print("me id:", me.get("id"), "keys:", list(me.keys())[:8])

print("\n=== RULE-003 fixed (fixed_user + valid uid) ===")
print(call("POST","/crm/assignment-rules", {"name":"规则A","assign_type":"fixed_user","target_id":me.get("id"),"priority":10,"is_active":True}))

print("\n=== ICP-001 weights sum 100 ===")
print(call("PUT","/crm/icp-config", {"target_industries":["it"],"target_regions":["cn-bj"],"company_size_min":10,"company_size_max":500,"weight_industry":40,"weight_region":20,"weight_company_size":20,"weight_budget":10,"weight_urgency":10,"is_active":True}))

print("\n=== RULE-002 GET /crm/number-rules (list, suffix persists) ===")
print(call("GET","/crm/number-rules"))

print("\n=== PIPE-002 update stage ===")
pc = call("POST","/crm/pipelines", {"name":"管道B","stages":[{"name":"S1","sort_order":1,"probability":20}]})
pid = pc[1].get("id"); sid = pc[1]["stages"][0]["id"]
print("pid,sid:", pid, sid)
for m in ("PATCH","PUT"):
    print(m, call(m, f"/crm/pipelines/{pid}/stages/{sid}", {"sort_order":5,"probability":90}))

print("\n=== TENDER-002 search icp match endpoints ===")
o=json.load(open('openapi.json',encoding='utf-8'))
for pp in o['paths']:
    if any(k in pp.lower() for k in ['icp','match','fit','score']):
        print("  ",pp, list(o['paths'][pp].keys()))

print("\n=== IMP-002 multipart import (csv with bad row) ===")
csv = "company_name,contact_name,mobile\n测试公司,张三,\n"  # missing mobile -> error row
files={"file":("leads.csv", csv.encode("utf-8"), "text/csv")}
r = httpx.post(BASE+"/crm/import/jobs", headers=H, data={"entity_type":"lead"}, files=files, timeout=30)
print("create job:", r.status_code, r.text[:300])
try:
    jid = r.json().get("id") or r.json().get("job_id")
    print("job id:", jid)
    if jid:
        print("run:", call("POST", f"/crm/import/jobs/{jid}/run"))
        print("errors:", call("GET", f"/crm/import/jobs/{jid}/errors"))
except Exception as e:
    print("imp err:", e)
