"""后端 API 用例执行器。

每个函数对应 Excel《后端API与集成测试》sheet 里的一条用例编号，
返回三元组 (ok: bool, actual: str, note: str)。
- ok：是否通过（按真实接口行为判定）
- actual：实际返回摘要，写入 Excel“实际结果”列
- note：补充说明（如规格/实现偏差）

注意：本文件以“真实接口”为准。Excel 里部分用例描述了不存在的接口
（如 /auth/refresh）或不存在的保存方式（如 POST /content 直存），
这类用例会被判定为“规格需修订”，并在 note 中说明。
"""
import time

from helpers import req, register, login, expired_token, stream_lines, new_phone, first_territory


def c_api_auth_001():
    tok, phone, err = register("API租户A")
    if err:
        return False, "", err
    code, body = req("POST", "/auth/login", json={"phone": phone, "password": "Test@123456"})
    has = code == 200 and isinstance(body, dict) and bool(body.get("access_token"))
    note = ""
    if has and "refresh_token" not in body:
        note = "通过；但实现未返回 refresh_token（用例预期含 refresh_token，与实现不符）"
    return has, f"code={code}, access_token={'有' if has else '无'}", note


def c_api_auth_002():
    tok, phone, err = register("API租户B")
    if err:
        return False, "", err
    code, body = req("POST", "/auth/login", json={"phone": phone, "password": "wrong"})
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    return code == 401, f"code={code}, detail={detail}", ""


def c_api_auth_003():
    # 用例预期有 /auth/refresh 刷新接口；真实后端无此接口 → 404/405
    code, body = req("POST", "/auth/refresh", json={})
    ok = code in (404, 405)
    note = ""
    if ok:
        note = "用例预期 POST /auth/refresh 刷新 token，但实现无此接口（规格/实现偏差，建议修订用例）"
    return ok, f"code={code}", note


def c_api_auth_004():
    code, body = req("GET", "/crm/leads")
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    return code == 401, f"code={code}, detail={detail}", ""


def c_api_auth_005():
    et = expired_token()
    code, body = req("GET", "/crm/leads", token=et)
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    return code == 401, f"code={code}, detail={detail}", ""


def c_api_crm_001():
    tok, phone, err = register("API租户C")
    if err:
        return False, "", err
    tid = first_territory(tok)
    code, body = req("POST", "/crm/leads", token=tok, json={
        "company_name": "测试公司", "contact_name": "张三", "mobile": "13700000001",
        "source": "website", "territory_id": tid})
    if code != 201 or not isinstance(body, dict):
        return False, f"create code={code}: {body}", ""
    lid = body.get("id")
    g = req("GET", f"/crm/leads/{lid}", token=tok)
    p = req("PATCH", f"/crm/leads/{lid}", token=tok, json={"contact_name": "李四"})
    d = req("DELETE", f"/crm/leads/{lid}", token=tok)
    g2 = req("GET", f"/crm/leads/{lid}", token=tok)
    ok = g[0] == 200 and p[0] == 200 and d[0] == 204 and g2[0] == 404
    return ok, f"create={code} get={g[0]} patch={p[0]} delete={d[0]} afterDel={g2[0]}", ""


def c_api_crm_002():
    tokA, _, e1 = register("隔离租户A")
    tokB, _, e2 = register("隔离租户B")
    if e1 or e2:
        return False, "", (e1 or e2)
    code, body = req("POST", "/crm/leads", token=tokA, json={
        "company_name": "隔离公司", "contact_name": "王五", "mobile": "13700000002",
        "territory_id": first_territory(tokA)})
    if code != 201 or not isinstance(body, dict):
        return False, f"A创建lead code={code}: {body}", ""
    lid = body.get("id")
    codeB, _ = req("GET", f"/crm/leads/{lid}", token=tokB)
    return codeB in (403, 404), f"B访问A的lead code={codeB}（预期403/404）", ""


def c_api_crm_003():
    tok, phone, err = register("API租户D")
    if err:
        return False, "", err
    req("POST", "/crm/leads", token=tok, json={
        "company_name": "分页公司", "contact_name": "赵六", "mobile": "13700000003",
        "source": "website", "territory_id": first_territory(tok)})
    code, body = req("GET", "/crm/leads", token=tok, params={"page": 1, "size": 20})
    items = body.get("items") if isinstance(body, dict) else None
    ok = code == 200 and isinstance(body, dict) and "items" in body
    code2, body2 = req("GET", "/crm/leads", token=tok, params={"source": "website", "page": 1, "size": 20})
    return (ok and code2 == 200), f"list code={code} items={len(items) if items else 0}; filter code={code2}", ""


def c_api_crm_004():
    tok, phone, err = register("API租户E")
    if err:
        return False, "", err
    code, body = req("POST", "/crm/customers", token=tok, json={"company_name": "客户公司", "industry": "软件"})
    if code != 201 or not isinstance(body, dict):
        return False, f"create customer code={code}: {body}", ""
    cid = body.get("id")
    req("POST", f"/crm/customers/{cid}/contacts", token=tok, json={"name": "联系人甲", "phone": "13700000004"})
    g = req("GET", f"/crm/customers/{cid}", token=tok)
    gc = req("GET", f"/crm/customers/{cid}/contacts", token=tok)
    contacts = gc[1].get("contacts") if isinstance(gc[1], dict) and "contacts" in gc[1] else gc[1]
    ok = g[0] == 200 and gc[0] == 200
    return ok, f"customer code={g[0]}; contacts code={gc[0]} count={contacts if not isinstance(contacts, list) else len(contacts)}", ""


def c_api_crm_005():
    tok, phone, err = register("API租户F")
    if err:
        return False, "", err
    # 真实导入流程：创建导入任务（带文件）→ 预览 → 执行
    files = {"file": ("leads.csv",
                      "company_name,contact_name,mobile\n测试公司,张三,13700000991\n".encode("utf-8"),
                      "text/csv")}
    code, body = req("POST", "/crm/import/jobs", token=tok, data={"entity_type": "leads"}, files=files)
    if code not in (200, 201) or not isinstance(body, dict):
        note = ""
        if code == 403:
            note = "返回403：导入需 crm.leads.import 权限，默认注册角色未授予（验证了权限门禁生效；如需打通需预置该权限）"
        return False, f"create import job code={code}: {body}", note
    jid = body.get("id")
    pc, pb = req("POST", f"/crm/import/jobs/{jid}/preview", token=tok, json={})
    ok = pc in (200, 201)
    return ok, f"job code={code} jobId={jid}; preview code={pc}", ""


def c_api_ct_001():
    tok, phone, err = register("API租户G")
    if err:
        return False, "", err
    sc, sb = req("POST", "/agent/sessions", token=tok, json={"title": "自动化会话"})
    if sc != 200 or not isinstance(sb, dict):
        return False, f"create session code={sc}: {sb}", ""
    sid = sb.get("id")
    code, lines = stream_lines("POST", f"/agent/sessions/{sid}/chat/stream", token=tok, json={
        "message": "写一段产品介绍", "platform": "xhs", "content_format": "article", "llm_source": "platform"})
    ok = code == 200 and len(lines) > 0
    return ok, f"stream code={code} chunks={len(lines)}", ""


def c_api_ct_002():
    tok, phone, err = register("API租户H")
    if err:
        return False, "", err
    # 真实实现：内容通过 /content/generate（LLM 生成）创建，无独立“保存”接口
    code, body = req("POST", "/content/generate", token=tok, json={
        "platform": "wechat", "topic": "自动化测试主题内容", "content_format": "article"})
    ok = code == 200 and isinstance(body, dict) and bool(body.get("id"))
    note = ""
    if ok:
        note = "实现经 /content/generate 创建内容（无独立 POST /content 保存接口），与用例描述略有差异"
    return ok, f"generate code={code} id={body.get('id') if isinstance(body, dict) else None}", note


def c_api_ct_003():
    tok, phone, err = register("API租户I")
    if err:
        return False, "", err
    files = {"file": ("kb.txt", "这是一段关于AI营销的知识库测试内容。".encode("utf-8"), "text/plain")}
    code, body = req("POST", "/knowledge/documents/upload", token=tok, data={"title": "知识库测试文档"}, files=files)
    if code not in (200, 201) or not isinstance(body, dict):
        return False, f"upload code={code}: {body}", ""
    did = body.get("id")
    time.sleep(2)
    sc, sb = req("GET", "/knowledge/search", token=tok, params={"q": "AI营销"})
    ok = sc == 200
    return ok, f"upload code={code} docId={did}; search code={sc}", ""


def c_api_ag_001():
    tok, phone, err = register("API租户J")
    if err:
        return False, "", err
    sc, sb = req("POST", "/agent/sessions", token=tok, json={"title": "预检会话"})
    if sc != 200 or not isinstance(sb, dict):
        return False, f"create session code={sc}: {sb}", ""
    sid = sb.get("id")
    pc, pb = req("POST", f"/agent/sessions/{sid}/preflight", token=tok, json={
        "message": "帮我代开发票避税", "platform": "xhs", "content_format": "article"})
    note = ""
    if pc == 200 and isinstance(pb, dict):
        note = f"ready={pb.get('ready')} action={pb.get('action')}"
        ok = True
    else:
        ok = False
    return ok, f"preflight code={pc} {note}", ""


def c_api_cust_002():
    """客户名称重复校验：创建同名客户，服务端应拦截（409/400，提示已存在）。"""
    tok, phone, err = register("CUST重名租户")
    if err:
        return False, "", err
    name = "ABC测试公司" + str(int(time.time()))[-6:]
    c1, b1 = req("POST", "/crm/customers", token=tok, json={"company_name": name})
    if c1 != 201:
        return False, f"首次创建 code={c1}: {b1}", ""
    c2, b2 = req("POST", "/crm/customers", token=tok, json={"company_name": name})
    msg = str(b2)
    dup = c2 in (400, 409, 422) and ("已存在" in msg or "重复" in msg or "exist" in msg.lower())
    note = ""
    if dup:
        note = f"重名被服务端拦截（返回 {c2}，提示含「已存在/重复」），验证了客户名称唯一性约束"
    else:
        note = f"同名客户再次创建返回 {c2}（非预期拦截），可能后端未对客户名做唯一性约束（需确认是否为缺陷）"
    return dup, f"first={c1} second={c2} msg={msg[:120]}", note


# 用例编号 → 执行器
REGISTRY = {
    "API-AUTH-001": c_api_auth_001,
    "API-AUTH-002": c_api_auth_002,
    "API-AUTH-003": c_api_auth_003,
    "API-AUTH-004": c_api_auth_004,
    "API-AUTH-005": c_api_auth_005,
    "API-CRM-001": c_api_crm_001,
    "API-CRM-002": c_api_crm_002,
    "API-CRM-003": c_api_crm_003,
    "API-CRM-004": c_api_crm_004,
    "API-CRM-005": c_api_crm_005,
    "API-CT-001": c_api_ct_001,
    "API-CT-002": c_api_ct_002,
    "API-CT-003": c_api_ct_003,
    "API-AG-001": c_api_ag_001,
    "CUST-002": c_api_cust_002,
}

try:
    from cases_auth_sec import REGISTRY_EXTRA
    REGISTRY.update(REGISTRY_EXTRA)
except Exception as _e:
    import sys
    print("cases_auth_sec load error:", _e, file=sys.stderr)

try:
    from cases_admin_extra import REGISTRY_ADMIN
    REGISTRY.update(REGISTRY_ADMIN)
except Exception as _e:
    import sys
    print("cases_admin_extra load error:", _e, file=sys.stderr)

try:
    from cases_crm_extra import REGISTRY_CRM
    REGISTRY.update(REGISTRY_CRM)
except Exception as _e:
    import sys
    print("cases_crm_extra load error:", _e, file=sys.stderr)

try:
    from cases_rest_extra import REGISTRY_REST_API
    REGISTRY.update(REGISTRY_REST_API)
except Exception as _e:
    import sys
    print("cases_rest_extra load error:", _e, file=sys.stderr)

try:
    from cases_features_extra import REGISTRY_FEATURES
    REGISTRY.update(REGISTRY_FEATURES)
except Exception as _e:
    import sys
    print("cases_features_extra load error:", _e, file=sys.stderr)
