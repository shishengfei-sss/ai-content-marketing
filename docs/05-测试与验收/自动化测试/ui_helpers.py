"""UI 自动化辅助：基于 Playwright 管理浏览器与登录态。

设计要点：
- 首次运行用一个测试账号（借后端 API 注册）在真实浏览器里登录一次，
  把 localStorage(token) 固化为 storage_state 文件，后续每条用例复用，
  避免重复注册/登录，且每条用例用全新 context 隔离状态。
- web_base() 自动探测 vite dev server 端口（5173/5174/...），不写死。
- 真实系统登录用「手机号 + 密码」，与 Excel 里写的「邮箱」不同（已在备注标注）。
"""
import json
import os
import time
import urllib.request

from playwright.sync_api import sync_playwright

from config import TEST_PASSWORD, PLATFORM_ADMIN_PHONE, PLATFORM_ADMIN_PASSWORD
from helpers import register

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "ui_state.json")
ACCOUNT_FILE = os.path.join(HERE, "ui_account.json")
# 平台管理员（platform_admin 角色）独立登录态：13800000000/admin123456
ADMIN_STATE_FILE = os.path.join(HERE, "ui_admin_state.json")

_playwright = None
_browser = None


def web_base():
    # 本机环境：5173 = apps/web（Vue3 前端，系统被测对象）；5174 = apps/mp（uni-app H5 移动端）。
    # 优先 5173（web）。不能只看 HTTP 200 —— 两个端口都返回 200，但需确认是真实 Vite 页面
    # （含 <!DOCTYPE / @vite/client），避免被空 200 的幽灵进程误导。
    if getattr(web_base, "_cached", None):
        return web_base._cached
    for port in (5173, 5174, 5175, 5176, 5177):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                if r.status == 200:
                    body = r.read(4096).decode("utf-8", "ignore")
                    if body.strip() and (
                        "<!DOCTYPE" in body or "/@vite/client" in body or "<html" in body
                    ):
                        web_base._cached = f"http://127.0.0.1:{port}"
                        return web_base._cached
        except Exception:
            pass
    web_base._cached = "http://127.0.0.1:5173"
    return web_base._cached


def _ensure_browser():
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
    return _browser


def setup_login_state():
    """注册一个测试账号并真实登录，固化 storage_state；已存在则直接复用。"""
    if os.path.exists(STATE_FILE):
        return STATE_FILE
    browser = _ensure_browser()
    tok, phone, err = register(f"UI自动化租户{int(time.time())}")
    if err:
        raise RuntimeError("UI 测试账号注册失败: " + str(err))
    pwd = TEST_PASSWORD
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(web_base() + "/login")
    page.fill('input[placeholder="请输入手机号"]', phone)
    page.fill('input[placeholder="请输入密码"]', pwd)
    page.click('button:has-text("登录")')
    try:
        page.wait_for_url("**/dashboard", timeout=20000)
    except Exception:
        # 极少数情况（如多租户需选租户）兜底处理
        if "select-tenant" in page.url:
            page.locator(".el-card, [class*='tenant']").first.click()
            page.wait_for_url("**/dashboard", timeout=10000)
        else:
            raise
    ctx.storage_state(path=STATE_FILE)
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump({"phone": phone, "password": pwd}, f)
    ctx.close()
    return STATE_FILE


def get_account():
    if not os.path.exists(ACCOUNT_FILE):
        setup_login_state()
    with open(ACCOUNT_FILE, encoding="utf-8") as f:
        return json.load(f)


def new_logged_page():
    """返回 (context, page)，page 已处于登录态。调用方负责 ctx.close()。"""
    browser = _ensure_browser()
    state = setup_login_state()
    ctx = browser.new_context(storage_state=state)
    return ctx, ctx.new_page()


def new_anon_page():
    """返回 (context, page)，未登录态，用于登录失败/校验类用例。"""
    browser = _ensure_browser()
    ctx = browser.new_context()
    return ctx, ctx.new_page()


def setup_admin_login_state():
    """以平台管理员(13800000000)登录，固化 storage_state；已存在则复用。"""
    if os.path.exists(ADMIN_STATE_FILE):
        return ADMIN_STATE_FILE
    browser = _ensure_browser()
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(web_base() + "/login")
    page.fill('input[placeholder="请输入手机号"]', PLATFORM_ADMIN_PHONE)
    page.fill('input[placeholder="请输入密码"]', PLATFORM_ADMIN_PASSWORD)
    page.click('button:has-text("登录")')
    try:
        page.wait_for_url("**/admin/**", timeout=20000)
    except Exception:
        # 兜底：平台管理员登录后由前端守卫直送 /admin
        if "select-tenant" in page.url:
            page.locator(".el-card, [class*='tenant']").first.click()
            page.wait_for_url("**/admin/**", timeout=10000)
        else:
            page.goto(web_base() + "/admin/tenants")
            page.wait_for_timeout(3000)
    ctx.storage_state(path=ADMIN_STATE_FILE)
    ctx.close()
    return ADMIN_STATE_FILE


def new_admin_page():
    """返回 (context, page)，page 已处于平台管理员登录态。调用方负责 ctx.close()。"""
    browser = _ensure_browser()
    state = setup_admin_login_state()
    ctx = browser.new_context(storage_state=state)
    return ctx, ctx.new_page()


def close_browser():
    global _playwright, _browser
    try:
        if _browser:
            _browser.close()
    finally:
        if _playwright:
            _playwright.stop()
        _browser = None
        _playwright = None
