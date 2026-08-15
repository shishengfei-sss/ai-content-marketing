"""Diagnostic: determine which app is on 5173 and what routes it serves (web app?)."""
import time
from playwright.sync_api import sync_playwright
from helpers import register
from config import TEST_PASSWORD

PORT = 5173
BASE = f"http://127.0.0.1:{PORT}"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
    ctx = b.new_context()
    pg = ctx.new_page()
    # register + login on 5173 (web style: placeholder + button)
    tok, phone, err = register(f"诊断web{int(time.time())}")
    print("register err:", err)
    pg.goto(BASE + "/login", timeout=20000)
    pg.wait_for_timeout(2500)
    print("login title:", pg.title())
    ph = pg.locator('input[placeholder="请输入手机号"]').count()
    btn = pg.locator('button:has-text("登录")').count()
    print(f"web-signature: phone-placeholder-inputs={ph} login-buttons={btn}")
    if ph and btn:
        pg.fill('input[placeholder="请输入手机号"]', phone)
        pg.fill('input[placeholder="请输入密码"]', TEST_PASSWORD)
        pg.click('button:has-text("登录")')
        pg.wait_for_timeout(4000)
        print("after login url:", pg.url)
        keys = pg.evaluate("Object.keys(localStorage)")
        print("localStorage keys:", keys)
    # check routes
    routes = ["/dashboard","/crm/leads","/crm/customers","/settings/crm-schema",
              "/settings/members","/agent","/analytics","/contents","/knowledge",
              "/admin/tenants","/admin/assistants"]
    for r in routes:
        try:
            pg.goto(BASE + r, timeout=15000)
            pg.wait_for_timeout(3000)
            redirected = "/login" in pg.url
            body = pg.locator("body").inner_text()
            print(f"  {r:24s} url={pg.url:50s} redirected={redirected} bodylen={len(body)}")
        except Exception as e:
            print(f"  {r:24s} ERR {e}")
    b.close()
