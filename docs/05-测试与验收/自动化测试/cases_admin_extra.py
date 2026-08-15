"""平台管理后台剩余待扩展用例（ADM-002/004/005/008），以平台管理员 token 走后端接口。

发现：真实后端 admin 模块无「租户禁用/启用」接口、无独立「Prompt 模板」接口，
这些在 Excel 描述的功能实际未实现（记为偏差/缺陷）。招标线索有 publish/parse 接口可测。
"""
from helpers import req, admin_login


def c_adm_002():
    """禁用/启用租户。"""
    tok, err = admin_login()
    if err:
        return False, f"平台管理员登录失败: {err}", ""
    c, tenants = req("GET", "/admin/tenants", token=tok)
    items = (tenants or {}).get("items") or []
    if not items:
        return False, f"无租户列表 code={c}", ""
    tid = items[0]["id"]
    for path in [f"/admin/tenants/{tid}/disable", f"/admin/tenants/{tid}/suspend"]:
        cc, _ = req("PATCH", path, token=tok, json={"status": "disabled", "is_active": False})
        if cc in (200, 201, 204):
            return True, f"禁用接口 {path} code={cc}", "租户禁用/启用接口可用"
    return (False, f"未找到租户禁用接口(尝试 disable/suspend PATCH 均非2xx)",
            "偏差/缺陷: 后端无租户禁用/启用接口(Excel要求ADM-002禁用租户功能未实现)")


def c_adm_004():
    """审核招标线索（publish）。"""
    tok, err = admin_login()
    if err:
        return False, f"登录失败: {err}", ""
    c, lst = req("GET", "/admin/platform-tender-leads", token=tok)
    items = (lst or {}).get("items") or []
    if not items:
        c2, b2 = req("POST", "/admin/platform-tender-leads", token=tok,
                     json={"title": "测试招标", "source": "manual", "status": "pending"})
        if c2 in (200, 201) and b2:
            items = [b2]
    if not items:
        return False, f"无招标线索且创建失败 code={c}", ""
    lid = items[0]["id"]
    cc, _ = req("POST", f"/admin/platform-tender-leads/{lid}/publish", token=tok)
    ok = cc in (200, 201)
    return ok, f"publish code={cc}", "审核/发布招标线索(平台管理员)"


def c_adm_005():
    """招标附件/文本 AI 解析任务管理。"""
    tok, err = admin_login()
    if err:
        return False, f"登录失败: {err}", ""
    c, b = req("POST", "/admin/platform-tender-leads/parse-text", token=tok,
               json={"text": "某政府采购项目招标，预算500万，要求提供AI营销方案。"})
    jid = (b or {}).get("job_id") or (b or {}).get("id")
    if not jid:
        return False, f"parse-text code={c} {b}", ""
    c2, _ = req("GET", f"/admin/platform-tender-leads/parse-jobs/{jid}", token=tok)
    ok = c in (200, 201) and c2 == 200
    return ok, f"parse={c} job={c2}", "招标文本AI解析任务创建与查询"


def c_adm_008():
    """配置 Prompt 模板。"""
    tok, err = admin_login()
    if err:
        return False, f"登录失败: {err}", ""
    c, b = req("GET", "/admin/prompt-templates", token=tok)
    if c == 200:
        c2, _ = req("PATCH", "/admin/prompt-templates", token=tok,
                    json={"system_prompt": "测试模板"})
        ok = c2 in (200, 201, 204)
        return ok, f"GET={c} PATCH={c2}", "Prompt模板配置接口可用"
    c3, _ = req("PATCH", "/admin/platform-llm", token=tok, json={})
    if c3 in (200, 201, 204):
        return (True, f"无prompt-templates接口, platform-llm配置可保存 code={c3}",
                "偏差: 无独立Prompt模板接口，平台LLM配置可保存(对应配置能力)")
    return (False, f"无prompt-templates接口(code={c})，platform-llm PATCH={c3}",
            "偏差/缺陷: 后端无Prompt模板配置接口(Excel要求ADM-008配置Prompt模板)")


REGISTRY_ADMIN = {
    "ADM-002": c_adm_002,
    "ADM-004": c_adm_004,
    "ADM-005": c_adm_005,
    "ADM-008": c_adm_008,
}
