"""Instrumented login probe: replicate setup_login_state step by step with logging."""
import sys, time, json
from playwright.sync_api import sync_playwright
from config import TEST_PASSWORD
from helpers import register
from ui_helpers import web_base

def log(s):
    print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)

base = web_base()
log(f"web_base = {base}")
with sync_playwright() as p:
    log("launching browser...")
    b = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
    log("browser launched")
    tok, phone, err = register(f"探针租户{int(time.time())}")
    log(f"register -> err={err} phone={phone} token?{bool(tok)}")
    if err:
        log("register failed, abort"); b.close(); sys.exit(1)
    ctx = b.new_context()
    page = ctx.new_page()
    log("goto /login")
    page.goto(base + "/login", timeout=20000)
    log("login page loaded; title=%s url=%s" % (page.title(), page.url))
    log("filling phone via input[type=number]")
    page.locator('input[type="number"]').fill(phone)
    log("filling password via input[type=password]")
    page.locator('input[type="password"]').fill(TEST_PASSWORD)
    log("clicking 登录 (text div)")
    page.get_by_text("登录", exact=True).click()
    log("clicked; waiting 6s for redirect")
    page.wait_for_timeout(6000)
    log(f"after login url={page.url}")
    # inspect localStorage keys
    keys = page.evaluate("Object.keys(localStorage)")
    log(f"localStorage keys = {keys}")
    tok_val = page.evaluate("localStorage.getItem('token')")
    log(f"localStorage['token'] present? {tok_val is not None} (len={len(tok_val) if tok_val else 0})")
    log("navigating to /crm/leads")
    page.goto(base + "/crm/leads", timeout=20000)
    page.wait_for_timeout(4000)
    log(f"/crm/leads url={page.url}")
    body = page.locator("body").inner_text()
    log(f"/crm/leads bodylen={len(body)} has_线索={'线索' in body}")
    b.close()
    log("DONE")
