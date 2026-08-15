import sys, json
sys.path.insert(0, ".")
from helpers import register

tok, phone, err = register("功能探针租户")
print("register err:", err, "tok?", bool(tok))
if not tok:
    raise SystemExit("no token")

import httpx
BASE = "http://127.0.0.1:8000/api/v1"
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

def call(method, path, json_body=None, files=None):
    if files:
        h2 = {k:v for k,v in H.items() if k!="Content-Type"}
        r = httpx.request(method, BASE+path, headers=h2, files=files, timeout=30)
    else:
        r = httpx.request(method, BASE+path, headers=H, json=json_body, timeout=30)
    try: body = r.json()
    except: body = r.text[:200]
    return r.status_code, body

print("\n=== IMP-001 GET /crm/import/jobs ===")
print(call("GET","/crm/import/jobs"))

print("\n=== import jobs POST contract (check content types) ===")
# peek openapi for this path
o=json.load(open('openapi.json',encoding='utf-8'))
ij=o['paths'].get('/api/v1/crm/import/jobs',{}).get('post',{})
print("requestBody content-types:", list(ij.get('requestBody',{}).get('content',{}).keys()))

print("\n=== RULE-001 POST /crm/number-rules ===")
print(call("POST","/crm/number-rules", {"entity_type":"lead","prefix":"LD","suffix":"X","seq_width":4,"enabled":True}))

print("\n=== RULE-002 GET /crm/number-rules/lead ===")
print(call("GET","/crm/number-rules/lead"))

print("\n=== RULE-003 POST /crm/assignment-rules ===")
print(call("POST","/crm/assignment-rules", {"name":"规则A","assign_type":"user","target_id":"00000000-0000-0000-0000-000000000001","priority":10,"is_active":True}))

print("\n=== ICP-001 PUT /crm/icp-config ===")
print(call("PUT","/crm/icp-config", {"target_industries":["it"],"target_regions":["cn-bj"],"company_size_min":10,"company_size_max":500,"weight_industry":2,"weight_region":1,"is_active":True}))

print("\n=== PIPE-001 POST /crm/pipelines ===")
sc = call("POST","/crm/pipelines", {"name":"标准管道","is_default":False,"is_active":True,"stages":[{"name":"初步接触","sort_order":1,"probability":10},{"name":"方案确认","sort_order":2,"probability":50}]})
print(sc)
pid = None
if isinstance(sc[1], dict):
    pid = sc[1].get('id') or sc[1].get('pipeline_id')
print("pipeline id:", pid)

print("\n=== API-AG-003 GET /assistants (persona) ===")
print(call("GET","/assistants"))

print("\n=== REG-P1-006 POST /crm/schema/lead/fields (select options) ===")
print(call("POST","/crm/schema/lead/fields", {"field_key":"f_source_sel","label":"来源选择","field_type":"select","options":["广告","转介绍"],"is_required":False}))

print("\n=== PERF-001 POST /content/proposals ===")
print(call("POST","/content/proposals", {"platform":"wechat","topic":"暑期营销","content_format":"article","proposal_count":3}))

print("\n=== REG-P0-001 GET /dashboard/stats & /analytics/lead-funnel ===")
print(call("GET","/dashboard/stats"))
print(call("GET","/analytics/lead-funnel"))

print("\n=== TENDER-002 ICP match: leads list icp_score? ===")
print(call("GET","/crm/leads?page=1&page_size=2"))
