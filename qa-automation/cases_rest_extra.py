"""CPQ/招标/交易、系统设置、回归 三张 sheet 待扩展用例的批量自动覆盖。

对每条待扩展用例，按关键词映射到：
- 普通 CRM 资源 API 列表（/crm/{res}）—— 验证资源接口可用
- 平台管理员资源 API 列表（/admin/{res}）—— 招标/租户类
- UI 页面可达冒烟（/settings、/contents、/knowledge、/create、/agent、/analytics）

这是「资源/页面可达」一级冒烟覆盖；深层配置/创建/编辑交互需进一步 E2E 扩展，
已在备注标明。普通用例共用一个租户 token，admin 用例共用一个平台管理员 token。
"""
import json
import os
from helpers import req, register, admin_login
from ui_helpers import new_logged_page, web_base

HERE = os.path.dirname(os.path.abspath(__file__))
_cases = json.load(open(os.path.join(HERE, "all_cases.json"), encoding="utf-8"))
TARGET = ["CPQ、招标线索与交易报表", "系统设置与管理", "回归测试与已知Bug验证"]
rest = [c for c in _cases if c["sheet"] in TARGET and not c["done"]]

# 关键词(长优先) -> 普通 CRM 资源
API_RES = [
    ("营销活动", "campaigns"), ("回款", "payments"), ("联系人", "customers"),
    ("客户", "customers"), ("商机", "deals"), ("报价", "quotes"), ("合同", "contracts"),
    ("产品", "products"), ("订单", "orders"), ("任务", "tasks"), ("活动", "tasks"),
    ("线索", "leads"),
]
# 关键词 -> 平台管理员资源
ADMIN_RES = [("招标", "platform-tender-leads"), ("租户", "tenants")]
# 关键词(长优先) -> UI 路由
UI_ROUTE = [
    ("表单字段", "settings/crm-schema"), ("成员", "settings/members"),
    ("权限", "settings/members"), ("角色", "settings/members"),
    ("品牌", "settings"), ("通知", "settings"), ("企业", "settings"),
    ("设置", "settings"), ("分析", "analytics"), ("报表", "analytics"),
    ("漏斗", "analytics"), ("内容", "contents"), ("知识库", "knowledge"),
    ("创作", "create"), ("顾问", "agent"), ("AI", "agent"),
]

_SHARED = {}


def _tok():
    if "tok" not in _SHARED:
        t, _, e = register("REST自动覆盖")
        _SHARED["tok"] = t
        _SHARED["err"] = e
    return _SHARED.get("tok"), _SHARED.get("err")


def _admin_tok():
    if "atok" not in _SHARED:
        t, e = admin_login()
        _SHARED["atok"] = t
        _SHARED["aerr"] = e
    return _SHARED.get("atok"), _SHARED.get("aerr")


def _match(text):
    for kw, res in ADMIN_RES:
        if kw in text:
            return ("admin", res)
    for kw, res in API_RES:
        if kw in text:
            return ("api", res)
    for kw, route in UI_ROUTE:
        if kw in text:
            return ("ui", route)
    return None


def make_api(res, admin=False):
    def run():
        if admin:
            tok, err = _admin_tok()
            path = f"/admin/{res}"
        else:
            tok, err = _tok()
            path = f"/crm/{res}"
        if err:
            return False, "", err
        c, b = req("GET", path, token=tok)
        ok = c == 200 and b is not None
        return ok, f"GET {path} code={c}", f"自动覆盖(API): {res}资源接口可用(深层交互需E2E扩展)"
    return run


def make_ui(route):
    def run():
        ctx, page = new_logged_page()
        try:
            page.goto(web_base() + "/" + route.lstrip("/"))
            page.wait_for_timeout(3000)
            # 关键：必须确认没有被鉴权守卫踢回登录页（否则只是登录页的 <form> 误判为通过）
            redirected = "/login" in page.url
            notfound = "No match found" in page.content()
            has = page.locator(".el-table, .el-card, h1, h2, .page-title, .el-empty, table, form, .el-tabs, .el-menu").count() > 0
            body_len = len(page.locator("body").inner_text())
            ok = (not redirected) and (not notfound) and (has or body_len > 50)
            return ok, f"route=/{route} redirected={redirected} 元素={has} body={body_len} url={page.url}", \
                f"自动覆盖(UI冒烟): /{route}页面可达(深层交互需E2E扩展)"
        finally:
            ctx.close()
    return run


REGISTRY_REST_API = {}
REGISTRY_REST_UI = {}
skipped = []
for c in rest:
    text = f"{c['submodule']} {c['feature']} {c['title']}"
    m = _match(text)
    if not m:
        skipped.append(c["id"])
        continue
    kind, target = m
    if kind == "api":
        REGISTRY_REST_API[c["id"]] = make_api(target, admin=False)
    elif kind == "admin":
        REGISTRY_REST_API[c["id"]] = make_api(target, admin=True)
    else:
        REGISTRY_REST_UI[c["id"]] = make_ui(target)
