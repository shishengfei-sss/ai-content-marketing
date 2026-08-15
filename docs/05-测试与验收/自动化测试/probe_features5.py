import sys, json, time
sys.path.insert(0, ".")
from helpers import register
tok, phone, err = register("功能探针5租户")
import httpx
BASE="http://127.0.0.1:8000/api/v1"
H={"Authorization":f"Bearer {tok}"}
def call(method,path,json_body=None,files=None,data=None):
    h2=dict(H)
    if files or data: h2.pop("Content-Type",None)
    else: h2["Content-Type"]="application/json"
    r=httpx.request(method,BASE+path,headers=h2,json=json_body,files=files,data=data,timeout=30)
    try:b=r.json()
    except:b=r.text[:200]
    return r.status_code,b

# TENDER-002: set icp-config THEN lead THEN recalc
print("icp PUT:", call("PUT","/crm/icp-config",{"target_industries":["it"],"target_regions":["cn-bj"],"company_size_min":10,"company_size_max":500,"weight_industry":40,"weight_region":20,"weight_company_size":20,"weight_budget":10,"weight_urgency":10,"is_active":True})[0])
terr=call("GET","/crm/territories")[1][0]['id']
lc=call("POST","/crm/leads",{"company_name":"ICP2公司","contact_name":"王","mobile":"13900000003","industry":"it","source":"ad","territory_id":terr})
lid=lc[1]['id']
print("recalc:", call("POST", f"/crm/leads/{lid}/recalculate-score")[1].get("icp_score"))

# IMP-002: try PATCH with "mapping" key
csv="company_name,contact_name,mobile\n测试公司,张三,\n"
files={"file":("leads.csv",csv.encode(),"text/csv")}
r=httpx.post(BASE+"/crm/import/jobs",headers=H,data={"entity_type":"lead"},files=files,timeout=30)
jid=r.json().get("job_id"); mp=r.json().get("suggested_mapping")
print("\nPATCH mapping(key=mapping):", call("PATCH", f"/crm/import/jobs/{jid}", {"mapping": mp})[1].get("mapping"))
print("run after mapping:", call("POST", f"/crm/import/jobs/{jid}/run")[1])
time.sleep(1)
print("errors:", repr(call("GET", f"/crm/import/jobs/{jid}/errors")[1]))
