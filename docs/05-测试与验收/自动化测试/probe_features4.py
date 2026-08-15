import sys, json, time
sys.path.insert(0, ".")
from helpers import register
tok, phone, err = register("功能探针4租户")
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

# IMP-002 PATCH mapping flow
csv="company_name,contact_name,mobile\n测试公司,张三,\n"
files={"file":("leads.csv",csv.encode(),"text/csv")}
r=httpx.post(BASE+"/crm/import/jobs",headers=H,data={"entity_type":"lead"},files=files,timeout=30)
jid=r.json().get("job_id"); mp=r.json().get("suggested_mapping")
print("jid:",jid)
print("PATCH mapping:", call("PATCH", f"/crm/import/jobs/{jid}", {"column_mapping": mp}))
print("run:", call("POST", f"/crm/import/jobs/{jid}/run"))
time.sleep(1.5)
print("errors:", call("GET", f"/crm/import/jobs/{jid}/errors"))

# TENDER-002 lead create with territory
terr=call("GET","/crm/territories")[1]
print("territories type:", type(terr), (terr if not isinstance(terr,(list,dict)) else (terr[:1] if isinstance(terr,list) else list(terr.keys()))))
tid = terr[0]['id'] if isinstance(terr,list) and terr else (terr.get('items',[{}])[0].get('id') if isinstance(terr,dict) else None)
print("tid:", tid)
lc=call("POST","/crm/leads",{"company_name":"ICP测试公司","contact_name":"李","mobile":"13900000002","industry":"it","source":"ad","territory_id":tid})
print("lead create:", lc[0], str(lc[1])[:200])
lid = lc[1].get('id') if isinstance(lc[1],dict) else None
if lid:
    print("recalc:", call("POST", f"/crm/leads/{lid}/recalculate-score")[1])
    det=call("GET", f"/crm/leads/{lid}")[1]
    print("icp_score:", det.get("icp_score") if isinstance(det,dict) else det)
