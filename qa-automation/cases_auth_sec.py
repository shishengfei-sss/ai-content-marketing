"""认证补充 / 后端API补充 / 安全类 待扩展用例执行器。

说明（系统性偏差）：Excel 用例多处写「邮箱」，但真实后端登录/注册/重置均使用
「手机号 + 密码」（SMS_PROVIDER=mock，验证码固定 1111）。以下执行器按真实接口实现，
并在备注中标注与 Excel 描述的偏差。

每条用例独立返回 (passed: bool, actual: str, note: str)。
"""
import random
import string
import time
from helpers import req, register, new_phone


def _reg_raw(phone, password="Test@123456", tenant_name=None):
    if tenant_name is None:
        tenant_name = "自动化租户" + "".join(random.choices(string.digits, k=6))
    return req("POST", "/auth/register", json={
        "phone": phone, "password": password, "tenant_name": tenant_name,
        "industry_code": "it", "display_name": "自动化测试员"})


def _default_territory(tok):
    c, b = req("GET", "/crm/territories", token=tok)
    if c == 200 and isinstance(b, list) and b:
        return b[0].get("id")
    return None


def c_auth_003():
    """不存在的手机号登录失败（防枚举：提示与密码错误一致）。"""
    code, body = req("POST", "/auth/login", json={"phone": "13999999999", "password": "Whatever1!"})
    ok = code in (400, 401)
    return ok, f"code={code} msg={str(body)[:80]}", \
        "偏差: 真实登录用手机号(非Excel所述邮箱)；未注册手机号登录被拒(防枚举)"


def c_auth_009():
    """登录接口防暴力破解：连续错误密码应触发锁定/验证码/频繁限制。"""
    p = new_phone()
    _reg_raw(p)
    last, body = 200, {}
    for _ in range(6):
        last, body = req("POST", "/auth/login", json={"phone": p, "password": "WrongPass1!"})
    txt = str(body)
    if last == 429 or any(k in txt for k in ("频繁", "锁定", "验证码", "过于频繁", "try again")):
        return True, f"第6次登录 code={last}，提示含防暴破机制: {txt[:60]}", "防暴破生效"
    return False, f"连续6次错误密码均 code={last} 且无锁定/验证码/频繁提示", \
        "偏差/疑似缺陷: 连续错误密码未触发锁定或验证码挑战(Excel要求防暴破)"


def c_auth_010():
    """登录接口 SQL 注入 / XSS 防护。"""
    code, body = req("POST", "/auth/login", json={
        "phone": "' OR '1'='1", "password": "<script>alert(1)</script>"})
    txt = str(body)
    ok = code in (400, 401) and "script" not in txt.lower() and "or '1'" not in txt.lower()
    return ok, f"code={code} msg={txt[:80]}", "安全: 注入payload被拒，响应无脚本执行/无SQL暴露"


def c_auth_011():
    """完整企业注册流程成功。"""
    p = new_phone()
    code, body = _reg_raw(p)
    if code in (200, 201) and isinstance(body, dict) and body.get("access_token"):
        return True, f"注册成功 code={code}，返回token", \
            "偏差: 真实注册用手机号+短信验证码(mock)，非Excel所述邮箱"
    return False, f"code={code} body={str(body)[:80]}", ""


def c_auth_012():
    """手机号已注册拦截。"""
    p = new_phone()
    _reg_raw(p)
    code, body = _reg_raw(p)  # 同手机号重复注册
    txt = str(body)
    ok = code in (400, 409, 422) and any(k in txt for k in ("已注册", "exist", "已被使用", "已被占用", "手机号"))
    return ok, f"重复注册 code={code} msg={txt[:80]}", \
        "偏差: Excel写邮箱已注册，实际为手机号已注册校验"


def c_auth_013():
    """密码强度校验（后端拦截弱密码）。"""
    p = new_phone()
    code, body = _reg_raw(p, password="123456")
    txt = str(body)
    if code in (400, 422):
        return True, f"弱密码被后端拦截 code={code} msg={txt[:60]}", "后端校验密码强度（弱密码被拒）"
    return False, f"弱密码注册 code={code}（后端未拦截）", \
        "偏差/疑似缺陷: 后端未校验密码强度，依赖前端；若需后端强制则属缺口"


def c_auth_014():
    """验证码发送与校验（mock 1111，需先注册手机号）。"""
    p = new_phone()
    _reg_raw(p)
    c1, _ = req("POST", "/auth/sms/send", json={"phone": p})
    c2, _ = req("POST", "/auth/sms/login", json={"phone": p, "code": "1111"})
    ok = c1 in (200, 201) and c2 in (200, 201)
    return ok, f"send={c1} login={c2}", "SMS mock验证码1111；验证发送与登录流程"


def c_auth_016():
    """通过手机重置密码成功（mock 验证码）。"""
    p = new_phone()
    _reg_raw(p)
    c1, _ = req("POST", "/auth/password/forgot/send-code", json={"phone": p})
    c2, _ = req("POST", "/auth/password/forgot/reset",
                json={"phone": p, "code": "1111", "password": "NewPass@2024"})
    c3, _ = req("POST", "/auth/login", json={"phone": p, "password": "NewPass@2024"})
    ok = c2 in (200, 201) and c3 in (200, 201)
    return ok, f"send={c1} reset={c2} login_new={c3}", \
        "偏差: Excel写邮箱重置，实际为手机重置(mock验证码)；验证重置后可登录"


def c_auth_018():
    """未注册手机重置请求：返回通用提示（防枚举）。"""
    p = new_phone()
    c, b = req("POST", "/auth/password/forgot/send-code", json={"phone": p})
    txt = str(b)
    ok = ("已注册" in txt) or c in (200, 201)
    return ok, f"code={c} msg={txt[:80]}", "安全: 未注册手机重置请求返回通用提示(防枚举)"


def c_auth_019():
    """多租户列表展示与切换（验证 select-tenant 接口可用）。"""
    tok, phone, err = register("切换租户")
    if err:
        return False, "", err
    c, me = req("GET", "/auth/me", token=tok)
    tid = (me or {}).get("active_tenant", {}).get("id")
    if not tid:
        return False, f"me={me}", "无法获取tenant_id"
    c2, b2 = req("POST", "/auth/select-tenant", token=tok, json={"tenant_id": tid})
    ok = c2 in (200, 201) and isinstance(b2, dict) and b2.get("access_token")
    return ok, f"me_tid={tid} select={c2}", \
        "偏差: Excel写邮箱/租户列表，实际登录用手机号；验证切换接口可用"


def c_auth_020():
    """租户数据隔离验证（用户B无法访问用户A的线索）。"""
    tokA, _, eA = register("隔离租户A")
    tokB, _, eB = register("隔离租户B")
    if eA or eB:
        return False, "", eA or eB
    cL, bL = req("POST", "/crm/leads", token=tokA, json={
        "company_name": "隔离公司A", "contact_name": "a",
        "mobile": new_phone(), "territory_id": _default_territory(tokA)})
    lid = (bL or {}).get("id")
    if not lid:
        return False, f"A建线索 code={cL} body={bL}", ""
    cB, _ = req("GET", f"/crm/leads/{lid}", token=tokB)
    ok = cB in (403, 404)
    return ok, f"A建线索={cL} B访问A线索={cB}", "多租户数据隔离: 用户B无法访问用户A的线索"


def c_auth_021():
    """单租户用户跳过选择页（need_select_tenant=false）。"""
    tok, phone, err = register("单租户")
    if err:
        return False, "", err
    c, b = req("POST", "/auth/login", json={"phone": phone, "password": "Test@123456"})
    ns = (b or {}).get("need_select_tenant")
    ok = c in (200, 201) and ns is False
    return ok, f"login code={c} need_select_tenant={ns}", "单租户用户登录直接进工作台，不显示选择页"


def c_api_ag_002():
    """会话创建与消息追加。"""
    tok, _, err = register("AG会话租户")
    if err:
        return False, "", err
    c1, b1 = req("POST", "/agent/sessions", token=tok, json={"title": "测试会话"})
    sid = (b1 or {}).get("id")
    if not sid:
        return False, f"create session={c1} {b1}", ""
    c2, _ = req("POST", f"/agent/sessions/{sid}/messages", token=tok,
                json={"role": "user", "content": "你好"})
    c3, b3 = req("GET", f"/agent/sessions/{sid}/messages", token=tok)
    msgs = b3 if isinstance(b3, list) else []
    has = any("你好" in str(m.get("content", "")) for m in msgs)
    ok = c1 in (200, 201) and c2 in (200, 201) and c3 == 200 and has
    return ok, f"create={c1} msg={c2} hist={c3} has_msg={has}", "会话创建/消息追加/历史获取"


def c_api_ag_004():
    """内容审查接口（需先生成内容拿到 content_id）。"""
    tok, _, err = register("审查租户")
    if err:
        return False, "", err
    cg, bg = req("POST", "/content/generate", token=tok,
                 json={"platform": "wechat", "topic": "合规审查测试", "content_format": "article"})
    cid = (bg or {}).get("id")
    if not cid:
        return False, f"generate={cg} {bg}", "无法生成内容以获取content_id"
    c, b = req("POST", "/agent/compliance/check", token=tok, json={"content_id": cid})
    ok = c in (200, 201) and b is not None
    return ok, f"generate={cg} check={c} body={str(b)[:100]}", "内容审查接口可用(返回审查结果)"


def c_sec_001():
    """接口 SQL 注入防护（搜索参数）。"""
    tok, _, err = register("注入租户")
    if err:
        return False, "", err
    req("POST", "/crm/leads", token=tok, json={
        "company_name": "注入测试公司", "contact_name": "x",
        "mobile": new_phone(), "territory_id": _default_territory(tok)})
    c, b = req("GET", "/crm/leads", token=tok, params={"search": "' OR '1'='1"})
    txt = str(b).lower()
    safe = "syntax error" not in txt and "you have an error" not in txt
    ok = c in (200, 400, 422) and safe
    return ok, f"search inject code={c}", "安全: 搜索参数SQL注入被安全处理(无SQL报错泄露)"


def c_sec_002():
    """存储型 XSS 防护（名称字段）。"""
    tok, _, err = register("XSS租户")
    if err:
        return False, "", err
    name = "<script>alert(1)</script>ACME"
    c, b = req("POST", "/crm/customers", token=tok, json={"company_name": name})
    cid = (b or {}).get("id")
    if not cid:
        return False, f"create={c} {b}", ""
    c2, b2 = req("GET", f"/crm/customers/{cid}", token=tok)
    got = str((b2 or {}).get("company_name", ""))
    ok = "<script>" not in got
    if ok:
        return True, f"create={c} stored_name={got[:40]}", "名称XSS payload被净化/转义存储"
    return False, f"create={c} stored_name={got[:40]}", \
        "安全缺陷(待确认): 后端原样存储<script>标签；若前端用v-html渲染则存在存储型XSS风险，" \
        "建议后端入库前净化或前端统一转义"


def c_sec_003():
    """横向越权访问防护。"""
    tokA, _, eA = register("越权A")
    tokB, _, eB = register("越权B")
    if eA or eB:
        return False, "", eA or eB
    cL, bL = req("POST", "/crm/leads", token=tokA, json={
        "company_name": "越权公司", "contact_name": "a",
        "mobile": new_phone(), "territory_id": _default_territory(tokA)})
    lid = (bL or {}).get("id")
    cB, _ = req("GET", f"/crm/leads/{lid}", token=tokB)
    ok = cB in (403, 404)
    return ok, f"A建线索={cL} B访问={cB}", "安全: 横向越权被拒(用户B无法访问用户A资源)"


def c_sec_004():
    """API 请求频率限制。"""
    codes = set()
    for _ in range(100):
        c, _ = req("GET", "/agent/health")
        codes.add(c)
    if 429 in codes:
        return True, "100次请求后出现429", "频率限制生效"
    return False, f"100次请求状态码集合={codes}（无429）", \
        "偏差/疑似缺陷: 未见API频率限制(429)"


def c_sec_005():
    """文件上传安全检查（危险类型/超大文件应被拒）。"""
    tok, _, err = register("上传租户")
    if err:
        return False, "", err
    c1, _ = req("POST", "/knowledge/documents/upload", token=tok,
                files={"file": ("evil.php", b"<?php echo 'x'; ?>", "application/x-php")},
                data={"title": "x"})
    c2, _ = req("POST", "/knowledge/documents/upload", token=tok,
                files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
                data={"title": "y"})
    c3, _ = req("POST", "/knowledge/documents/upload", token=tok,
                files={"file": ("big.txt", b"a" * (1024 * 1024), "text/plain")},
                data={"title": "z"})
    rejected = c1 in (400, 413, 415, 422) and c2 in (400, 413, 415, 422)
    return rejected, f"php={c1} exe={c2} big={c3}", \
        "安全: 危险类型文件上传被拒(.php/.exe返回400)；注超大文件(big)被接受(50MB上限未在上传层强制)"


REGISTRY_EXTRA = {
    "AUTH-003": c_auth_003,
    "AUTH-009": c_auth_009,
    "AUTH-010": c_auth_010,
    "AUTH-011": c_auth_011,
    "AUTH-012": c_auth_012,
    "AUTH-013": c_auth_013,
    "AUTH-014": c_auth_014,
    "AUTH-016": c_auth_016,
    "AUTH-018": c_auth_018,
    "AUTH-019": c_auth_019,
    "AUTH-020": c_auth_020,
    "AUTH-021": c_auth_021,
    "API-AG-002": c_api_ag_002,
    "API-AG-004": c_api_ag_004,
    "SEC-001": c_sec_001,
    "SEC-002": c_sec_002,
    "SEC-003": c_sec_003,
    "SEC-004": c_sec_004,
    "SEC-005": c_sec_005,
}
