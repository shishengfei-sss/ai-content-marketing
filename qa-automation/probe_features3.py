import sys, json
sys.path.insert(0, ".")
from helpers import register
tok, phone, err = register("功能探针3租户")
import httpx
BASE = "http://127.0.0.1:8000/api/v1"
H = {"Authorization": f"Bearer {tok}"}
def call(method, path, json_body=None, files=None, data=None):
    h2=dict(H)
    if files or data: h2.pop("Content-Type",None)
    else: h2["Content-Type"]="application/json"
    r=httpx.request(method,BASE+path,headers=h2,json=json_body,files=files,data=data,timeout=30)
    try: b=r.json()
    except: b=r.text[:200]
    return r.status_code,b

o=json.load(open('openapi.json',encoding='utf-8'))
ij=o['paths'].get('/api/v1/crm/import/jobs/{job_id}',{})
print("job detail methods:", list(ij.keys()))
pv=o['paths'].get('/api/v1/crm/import/jobs/{job_id}/preview',{})
print("preview methods:", list(pv.keys()))

# create job
csv="company_name,contact_name,mobile\n测试公司,张三,\n"
files={"file":("leads.csv",csv.encode(),"text/csv")}
r=httpx.post(BASE+"/crm/import/jobs",headers=H,data={"entity_type":"lead"},files=files,timeout=30)
jid=r.json().get("job_id"); print("jid:",jid, "suggested:", r.json().get("suggested_mapping"))

# try preview with mapping
print("preview POST:", call("POST", f"/crm/import/jobs/{jid}/preview", {"column_mapping": r.json().get("suggested_mapping")}))
# maybe mapping needs PUT on job
print("job PUT mapping:", call("PUT", f"/crm/import/jobs/{jid}", {"column_mapping": r.json().get("suggested_mapping")}))
# run
print("run:", call("POST", f"/crm/import/jobs/{jid}/run"))
import time; time.sleep(1)
print("errors:", call("GET", f"/crm/import/jobs/{jid}/errors"))

print("\n=== RULE-002 PUT /crm/number-rules/lead suffix ===")
print(call("PUT","/crm/number-rules/lead",{"suffix":"084","enabled":True}))
print("list lead:", [x for x in call("GET","/crm/number-rules")[1] if x['entity_type']=='lead'])

print("\n=== TENDER-002 icp recalc ===")
# create lead matching target
lc=call("POST","/crm/leads",{"company_name":"ICP测试公司","contact_name":"李","mobile":"13900000001","industry":"it","source":"ad"})
print("lead create:", lc[0])
lid=lc[1].get("id") if isinstance(lc[1],dict) else None
print("recalc:", call("POST", f"/crm/leads/{lid}/recalculate-score"))
print("lead detail icp_score:", call("GET", f"/crm/leads/{lid}")[1].get("icp_score") if isinstance(call("GET", f"/crm/leads/{lid}")[1],dict) else "n/a")
