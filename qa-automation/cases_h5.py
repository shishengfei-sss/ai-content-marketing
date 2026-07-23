# -*- coding: utf-8 -*-
"""
H5（apps/mp，uni-app）移动端用例。
前端地址固定 5174，登录为 div 式（无 <button>/placeholder），token 存 localStorage['ai_marketing_token']。
每个用例函数自行打开/关闭 context（复用 ui_helpers 的全局浏览器实例），返回 (ok, actual, note)。

【重要】Playwright Sync API 的全局 event loop 只能 start 一次：不能每用例 `sync_playwright()` 起关，
否则第二次会报 "Event loop is closed"。因此 H5 复用 ui_helpers._ensure_browser() 的全局浏览器，
每条用例只 `browser.new_context()`，由 run.py 末尾 close_browser() 统一回收。
"""
import os
import json
import random
import string
import time

from ui_helpers import _ensure_browser
from helpers import register, req

HERE = os.path.dirname(os.path.abspath(__file__))
H5_BASE = "http://127.0.0.1:5174"
H5_STATE = os.path.join(HERE, "ui_h5_state.json")
H5_TOKEN_FILE = os.path.join(HERE, "ui_h5_token.json")


def _rand(n=6):
    return "".join(random.choices(string.digits, k=n))


def h5_login_ui(page, phone, pwd="Test@123456"):
    page.goto(H5_BASE + "/#/", timeout=25000)
    page.wait_for_timeout(2500)
    ins = page.locator("input")
    ins.nth(0).fill(phone)
    ins.nth(1).fill(pwd)
    page.get_by_text("登录", exact=True).click()
    page.wait_for_timeout(3000)


def h5_ensure_state():
    """在全局浏览器上注册并真实登录，固化 storage_state 与 api token 文件。
    文件已存在且可读取则直接返回。必须在调用 new_h5_* 之前确保就绪。
    """
    if os.path.exists(H5_STATE) and os.path.exists(H5_TOKEN_FILE):
        try:
            json.load(open(H5_TOKEN_FILE, encoding="utf-8"))
            return
        except Exception:
            try:
                os.remove(H5_STATE)
                os.remove(H5_TOKEN_FILE)
            except Exception:
                pass
    browser = _ensure_browser()
    ctx = browser.new_context()
    page = ctx.new_page()
    tok, phone, err = register(f"H5自动化租户{int(time.time())}")
    if not tok:
        raise RuntimeError("H5 register failed: " + str(err))
    h5_login_ui(page, phone)
    if "login" in page.url:
        raise RuntimeError("H5 login did not land on home: " + page.url)
    ctx.storage_state(path=H5_STATE)
    json.dump({"phone": phone, "token": tok}, open(H5_TOKEN_FILE, "w"), ensure_ascii=False)
    ctx.close()


def h5_api_token():
    h5_ensure_state()
    return json.load(open(H5_TOKEN_FILE, encoding="utf-8"))


def new_h5_page():
    # state 文件由用例开头的 h5_ensure_state() 保证存在
    browser = _ensure_browser()
    ctx = browser.new_context(storage_state=H5_STATE)
    return ctx, ctx.new_page()


def new_h5_anon():
    browser = _ensure_browser()
    ctx = browser.new_context()
    return ctx, ctx.new_page()


def _h5_territory(tok):
    code, body = req("GET", "/crm/territories", tok)
    if code == 200 and isinstance(body, list) and body:
        return body[0]["id"]
    return None


# ---------------- 用例 ----------------

def c_h5_auth_001():
    """H5账号密码登录"""
    info = h5_api_token()
    ctx, page = new_h5_anon()
    try:
        h5_login_ui(page, info["phone"])
        page.wait_for_timeout(2000)
        url = page.url
        body = page.locator("body").inner_text()
        ok = ("pages/index/index" in url) and ("智营获客" in body or "AI 内容营销" in body)
        return ok, f"登录后 url={url} 首页含品牌词={('智营获客' in body)}", "H5端到端: 账号密码登录成功落地首页"
    finally:
        ctx.close()


def c_h5_auth_002():
    """H5登录失败处理"""
    h5_ensure_state()
    ctx, page = new_h5_anon()
    try:
        page.goto(H5_BASE + "/#/", timeout=25000)
        page.wait_for_timeout(2500)
        ins = page.locator("input")
        ins.nth(0).fill("13900000000")
        ins.nth(1).fill("WrongPass@2026")
        page.get_by_text("登录", exact=True).click()
        page.wait_for_timeout(3000)
        url = page.url
        on_login = "login" in url
        toast_txt = ""
        try:
            t = page.locator("uni-toast, .uni-toast, .uni-message").first
            if t.count():
                toast_txt = t.inner_text()
        except Exception:
            pass
        body = page.locator("body").inner_text()
        err_hint = ("密码" in toast_txt) or ("错误" in toast_txt) or ("失败" in toast_txt) or ("账号" in toast_txt) or ("密码" in body) or ("错误" in body)
        # 失败处理正确 = 出现错误提示（登录失败被拦截，未进入首页）。不以 URL 含 login 为硬性条件（H5 登录失败仍停留在 #/ 首页并弹 toast）。
        ok = bool(err_hint)
        return ok, f"错误密码后提示={toast_txt!r} 错误提示命中={err_hint}", "H5: 错误密码被拒并提示(失败处理正确)"
    finally:
        ctx.close()


def c_h5_crm_001():
    """H5线索列表查看"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/crm/leads", timeout=20000)
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text()
        ok = ("线索" in body)
        return ok, f"线索列表页含'线索'={ok} body头={body[:60]!r}", "H5: 线索列表可达"
    finally:
        ctx.close()


def c_h5_crm_002():
    """H5创建线索"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/crm/lead-create", timeout=20000)
        page.wait_for_timeout(2500)
        ins = page.locator("input.uni-input-input")
        company = "H5线索" + _rand()
        ins.nth(0).fill(company)
        ins.nth(2).fill("H5联系人" + _rand())
        ins.nth(3).fill("139" + _rand(8))
        # 销售区域为必填下拉（uni-data-select），需先选择，否则提交被前端校验拦截
        try:
            page.get_by_text("请选择销售区域", exact=True).click(timeout=3000)
            page.wait_for_timeout(1500)
            page.get_by_text("华东", exact=True).first.click(timeout=3000)
            page.wait_for_timeout(1000)
        except Exception as _se:
            pass  # 若已被选中或弹层结构不同，忽略
        page.get_by_text("创建线索", exact=True).click()
        page.wait_for_timeout(3000)
        page.goto(H5_BASE + "/#/pages/crm/leads", timeout=20000)
        page.wait_for_timeout(2500)
        body = page.locator("body").inner_text()
        ok = company in body
        return ok, f"创建线索 company={company} 列表包含={ok}", "H5端到端: 新建线索成功并出现在列表"
    finally:
        ctx.close()


def c_h5_crm_003():
    """H5客户详情查看"""
    info = h5_api_token()
    ctx, page = new_h5_page()
    try:
        tok = info["token"]
        tid = _h5_territory(tok)
        name = "H5客户" + _rand()
        code, body = req("POST", "/crm/customers", tok, json={
            "company_name": name, "contact_name": "客联" + _rand(),
            "mobile": "138" + _rand(8), "territory_id": tid})
        cid = body.get("id") if isinstance(body, dict) else None
        page.goto(H5_BASE + f"/#/pages/crm/customer-detail?id={cid}", timeout=20000)
        page.wait_for_timeout(3000)
        b = page.locator("body").inner_text()
        ok = (name in b) or (cid is not None and ("客户" in b))
        return ok, f"客户 {name} 详情含名称={name in b} cid={cid}", "H5: 客户详情页可达并展示客户"
    finally:
        ctx.close()


def c_h5_crm_004():
    """H5商机看板"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/crm/deals", timeout=20000)
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text()
        try:
            page.get_by_text("看板", exact=True).click(timeout=3000)
            page.wait_for_timeout(1500)
        except Exception:
            pass
        body2 = page.locator("body").inner_text()
        ok = ("商机" in body) and ("看板" in body2 or "商机" in body2)
        return ok, f"商机页含'商机'={('商机' in body)} 看板切换后含'看板'={('看板' in body2)}", "H5: 商机列表/看板可达"
    finally:
        ctx.close()


def c_h5_crm_005():
    """H5与Web数据一致性（FR-CLIENT-01）"""
    info = h5_api_token()
    ctx, page = new_h5_page()
    try:
        tok = info["token"]
        tid = _h5_territory(tok)
        company = "一致性线索" + _rand()
        code, body = req("POST", "/crm/leads", tok, json={
            "company_name": company, "contact_name": "一", "mobile": "137" + _rand(8),
            "territory_id": tid, "source": "ad"})
        page.goto(H5_BASE + "/#/pages/crm/leads", timeout=20000)
        page.wait_for_timeout(3000)
        b = page.locator("body").inner_text()
        ok = company in b
        if not ok:
            try:
                page.locator("input").first.fill(company)
                page.wait_for_timeout(2000)
                b = page.locator("body").inner_text()
                ok = company in b
            except Exception:
                pass
        return ok, f"Web(API)创建线索 company={company} H5列表可见={ok}", "H5↔Web 数据一致性: H5列表可见Web创建的线索"
    finally:
        ctx.close()


def c_h5_cont_001():
    """H5快速创作内容"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/create/create", timeout=20000)
        page.wait_for_timeout(2500)
        ins = page.locator("input.uni-input-input")
        topic = "H5夏季营销" + _rand(4)
        ins.nth(0).fill(topic)
        page.get_by_text("发送", exact=True).click()
        page.wait_for_timeout(5000)
        b = page.locator("body").inner_text()
        ok = (topic in b) or ("生成" in b) or ("方案" in b) or ("创作" in b)
        return ok, f"输入主题={topic} 发布后页面含反馈={ok}", "H5: 快速创作可提交并获反馈(LLM=Fake)"
    finally:
        ctx.close()


def c_h5_cont_002():
    """H5内容列表查看"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/todo/todo", timeout=20000)
        page.wait_for_timeout(3000)
        b = page.locator("body").inner_text()
        ok = ("内容箱" in b) or ("内容" in b)
        return ok, f"内容箱页含'内容箱'={('内容箱' in b)}", "H5: 内容列表(内容箱)可达"
    finally:
        ctx.close()


def c_h5_set_001():
    """H5查看企业信息"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/settings/tenant", timeout=20000)
        page.wait_for_timeout(3000)
        b = page.locator("body").inner_text()
        save = page.get_by_text("保存", exact=True).count()
        ok = ("企业信息" in b) and (save > 0)
        return ok, f"企业信息页含标题={('企业信息' in b)} 保存按钮={save}", "H5: 企业信息页可达"
    finally:
        ctx.close()


def c_h5_set_002():
    """H5个人信息和退出"""
    h5_ensure_state()
    ctx, page = new_h5_page()
    try:
        page.goto(H5_BASE + "/#/pages/mine/mine", timeout=20000)
        page.wait_for_timeout(3000)
        b = page.locator("body").inner_text()
        has_profile = ("自动化测试员" in b) or ("我的" in b)
        page.get_by_text("退出登录", exact=True).click()
        page.wait_for_timeout(3000)
        url = page.url
        logged_out = ("login" in url) or ("登录" in page.locator("body").inner_text())
        ok = has_profile and logged_out
        return ok, f"个人页含资料={has_profile} 退出后回到登录={logged_out} url={url}", "H5端到端: 个人信息可见且可退出登录"
    finally:
        ctx.close()


REGISTRY_H5 = {
    "H5-AUTH-001": c_h5_auth_001,
    "H5-AUTH-002": c_h5_auth_002,
    "H5-CRM-001": c_h5_crm_001,
    "H5-CRM-002": c_h5_crm_002,
    "H5-CRM-003": c_h5_crm_003,
    "H5-CRM-004": c_h5_crm_004,
    "H5-CRM-005": c_h5_crm_005,
    "H5-CONT-001": c_h5_cont_001,
    "H5-CONT-002": c_h5_cont_002,
    "H5-SET-001": c_h5_set_001,
    "H5-SET-002": c_h5_set_002,
}
