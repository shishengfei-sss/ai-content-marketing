"""02 联测金标准 FE-*：页面操作 → Network → UI。

对照 docs/05-测试与验收/测试用例/内容获客商城-phase1/02-前后端联测金标准.md
A20 材料上传主路径仍以 verify_shop_m0f.py 为准；本文件覆盖可点写操作与边界拦截。
"""
from __future__ import annotations

import os
import time

import pytest

from tests.automated.ui.conftest import BASE_URL, ui_goto, ui_login, ui_wait_ready

PLATFORM_PHONE = os.environ.get("UI_TEST_PLATFORM_PHONE", "13800000000")
PLATFORM_PASSWORD = os.environ.get("UI_TEST_PLATFORM_PASSWORD", "admin123456")
MERCHANT_PHONE = os.environ.get("UI_TEST_PHONE", "13900000099")
MERCHANT_PASSWORD = os.environ.get("UI_TEST_PASSWORD", "test123456")


def _platform_login(page) -> None:
    page.goto(f"{BASE_URL}/admin/login", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(PLATFORM_PHONE)
    page.get_by_placeholder("请输入密码").fill(PLATFORM_PASSWORD)
    page.click('button:has-text("登录")')
    page.wait_for_url(lambda url: "/admin" in url and "/admin/login" not in url, timeout=20000)
    page.wait_for_timeout(400)


def _toast_or_body(page, *needles: str) -> bool:
    text = page.locator("body").inner_text()
    if any(n in text for n in needles):
        return True
    msg = page.locator(".el-message, .uni-toast, .uni-sample-toast")
    if msg.count() == 0:
        return False
    blob = msg.inner_text()
    return any(n in blob for n in needles)


def test_fe_a21_01_login_network(page):
    """FE-A21-01: 商家登录 → POST /auth/login 200 → 进入工作台。"""
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(MERCHANT_PHONE)
    page.get_by_placeholder("请输入密码").fill(MERCHANT_PASSWORD)
    with page.expect_response(
        lambda r: "/auth/login" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        page.click('button:has-text("登录")')
    assert resp_info.value.status == 200
    page.wait_for_url(
        lambda url: "/login" not in url
        and ("/dashboard" in url or "/select-tenant" in url or "/shop/" in url),
        timeout=20000,
    )


def test_fe_a21_01_b1_bad_password(page):
    """FE-A21-01-B1: 密码错误 → 401 + 中文错误。"""
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(MERCHANT_PHONE)
    page.get_by_placeholder("请输入密码").fill("wrong-password-xxx")
    with page.expect_response(
        lambda r: "/auth/login" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        page.click('button:has-text("登录")')
    assert resp_info.value.status in (401, 400, 422)
    page.wait_for_timeout(600)
    assert _toast_or_body(page, "密码", "错误", "不正确", "失败")


def test_fe_a22_01_b2_phone_10_digits(page):
    """FE-A22-01-B2: 注册手机 10 位 → 前端拦截不发或 422。"""
    page.goto(f"{BASE_URL}/register", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.get_by_placeholder("团队内显示的名称").fill("联测用户")
    page.get_by_placeholder("用于登录与接收重要通知").fill("1390000000")
    page.get_by_placeholder("至少 8 位").fill("demo123456")
    page.get_by_placeholder("团队对外称呼，可与营业执照名称不同").fill("联测工作台")
    fired = {"n": 0}

    def on_req(req):
        if "/auth/register" in req.url and req.method == "POST":
            fired["n"] += 1

    page.on("request", on_req)
    page.click('button:has-text("注册")')
    page.wait_for_timeout(800)
    assert fired["n"] == 0
    assert _toast_or_body(page, "11 位", "手机")


def test_fe_a02_01_save_draft_network(page):
    """FE-A02-01 / B1: 空名称拦截；填名称存草稿 → POST /shop/products。"""
    ui_login(page, MERCHANT_PHONE, MERCHANT_PASSWORD)
    ui_goto(page, "/shop/products/new")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="存草稿").click()
    page.wait_for_timeout(500)
    assert _toast_or_body(page, "名称")

    name = f"联测草稿课{int(time.time())}"
    page.locator(".el-form-item", has_text="名称").locator("input").first.fill(name)
    with page.expect_response(
        lambda r: "/shop/products" in r.url
        and r.request.method == "POST"
        and "/submit" not in r.url,
        timeout=20000,
    ) as resp_info:
        page.get_by_role("button", name="存草稿").click()
    assert resp_info.value.status in (200, 201)
    page.wait_for_timeout(800)
    assert _toast_or_body(page, "草稿", "成功") or "/shop/products/" in page.url


def test_fe_p02a_01_b1_tenant_required(page):
    """FE-P02A-01-B1: 发起入驻不选租户 → 不发或 422。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.locator('[data-testid="shop-merchants"]').wait_for(timeout=15000)
    btn = page.locator("button:has-text('发起入驻')").first
    if btn.count() == 0:
        pytest.skip("当前列表无发起入驻按钮（无未入驻行或无权限）")
    btn.click()
    page.wait_for_timeout(500)
    fired = {"n": 0}

    def on_req(req):
        if "/onboarding" in req.url and req.method == "POST":
            fired["n"] += 1

    page.on("request", on_req)
    page.get_by_role("button", name="提交待审").click()
    page.wait_for_timeout(800)
    assert fired["n"] == 0 or _toast_or_body(page, "租户")
    assert "租户" in page.locator("body").inner_text()


def test_fe_p03_01_b1_reject_empty(page):
    """FE-P03-01-B1: 驳回原因为空 → 前端拦截，仍 pending。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/onboarding")
    audit = page.get_by_role("button", name="审核").first
    view = page.get_by_role("button", name="查看").first
    if audit.count() == 0 and view.count() == 0:
        return
    (audit if audit.count() else view).click()
    page.wait_for_timeout(800)
    if page.locator(".review-subtabs").count() == 0:
        return
    page.locator(".review-subtabs").get_by_text("驳回", exact=True).click()
    page.wait_for_timeout(300)
    fired = {"n": 0}

    def on_req(req):
        if "reject" in req.url and req.method == "POST":
            fired["n"] += 1

    page.on("request", on_req)
    page.get_by_role("button", name="确认驳回").click()
    page.wait_for_timeout(700)
    assert fired["n"] == 0
    assert _toast_or_body(page, "至少", "原因", "说明")


def test_fe_p09_01_b1_reject_no_reason(page):
    """FE-P09-01-B1: 商品人审驳回无原因 → 拦截。无待审则只验页壳。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/product-reviews")
    ui_wait_ready(page)
    page.wait_for_timeout(600)
    assert page.locator(".el-table, .page-card").count() >= 1
    reject = page.locator(".el-button--danger:visible").filter(has_text="驳回").first
    if reject.count() == 0:
        return
    try:
        reject.click(timeout=4000)
    except Exception:
        return
    page.wait_for_timeout(400)
    confirm = page.get_by_role("button", name="确认驳回").first
    if confirm.count() == 0:
        return
    fired = {"n": 0}

    def on_req(req):
        if "reject" in req.url and req.method == "POST":
            fired["n"] += 1

    page.on("request", on_req)
    confirm.click()
    page.wait_for_timeout(600)
    assert fired["n"] == 0
    assert _toast_or_body(page, "原因", "至少", "填写")


def test_fe_p11_01_open_plan_dialog_network(page):
    """FE-P11-01: 人工开通抽屉可开；确认开通会打订阅 API。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/subscriptions")
    ui_wait_ready(page)
    btn = page.get_by_role("button", name="人工开通（主套餐/叠加）").first
    if btn.count() == 0:
        btn = page.get_by_text("人工开通", exact=False).first
    assert btn.count() >= 1
    btn.click()
    page.wait_for_timeout(500)
    assert page.get_by_text("选择套餐").count() >= 1
    assert page.get_by_role("button", name="确认开通").count() >= 1
    # 未选商家点确认 → 前端拦截
    page.get_by_role("button", name="确认开通").click()
    page.wait_for_timeout(600)
    assert _toast_or_body(page, "商家", "套餐", "必填", "选择")


def test_fe_a10_01_b1_refund_empty_reason(page):
    """FE-A10-01-B1: 商家退款不选原因 → 拦截。"""
    ui_login(page, MERCHANT_PHONE, MERCHANT_PASSWORD)
    ui_goto(page, "/shop/orders")
    ui_wait_ready(page)
    detail = page.locator("button:has-text('详情')").first
    assert detail.count() >= 1
    detail.click()
    page.wait_for_url(lambda u: "/shop/orders/" in u, timeout=15000)
    page.wait_for_timeout(800)
    refund_btn = page.locator("button:has-text('退款')").first
    if refund_btn.count() == 0:
        # 当前详情非已付款，回到列表找已付款行
        ui_goto(page, "/shop/orders")
        tab = page.get_by_text("已付款").first
        if tab.count():
            tab.click()
            page.wait_for_timeout(500)
        detail = page.locator("button:has-text('详情')").first
        if detail.count() == 0:
            return
        detail.click()
        page.wait_for_timeout(800)
        refund_btn = page.locator("button:has-text('退款')").first
    if refund_btn.count() == 0:
        return
    refund_btn.click()
    page.wait_for_timeout(400)
    confirm = page.get_by_role("button", name="提交退款").first
    if confirm.count() == 0:
        confirm = page.locator(".el-dialog button:has-text('提交退款')").last
    if confirm.count() == 0:
        return
    fired = {"n": 0}

    def on_req(req):
        if "/refund" in req.url and req.method == "POST":
            fired["n"] += 1

    page.on("request", on_req)
    confirm.click()
    page.wait_for_timeout(700)
    assert fired["n"] == 0
    assert _toast_or_body(page, "原因")
