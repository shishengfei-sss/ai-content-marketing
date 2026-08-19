"""02 金标准写库主路径：页面操作 → Network 写请求 → UI。

对照 docs/05-测试与验收/测试用例/内容获客商城-phase1/02-前后端联测金标准.md
隔离账号/商品/订单；不退演示课 DEMOPAID0001。
"""
from __future__ import annotations

import os
import re
import time
import uuid

import pytest

from tests.automated.ui.conftest import BASE_URL, ui_goto, ui_login, ui_wait_ready
from tests.automated.ui.gold_live import (
    MP_BASE_URL,
    PLATFORM_PASSWORD,
    PLATFORM_PHONE,
    create_draft_course,
    create_isolated_paid_order,
    merchant_token,
    register_workspace,
    submit_review_leave_pending,
    tiny_png_path,
)

MERCHANT_PHONE = os.environ.get("UI_TEST_PHONE", "13900000099")
MERCHANT_PASSWORD = os.environ.get("UI_TEST_PASSWORD", "test123456")

_STATE: dict = {}


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
    msg = page.locator(".el-message")
    if msg.count() == 0:
        return False
    blob = msg.inner_text()
    return any(n in blob for n in needles)


def _dropdown_items(page):
    vis = page.locator(".el-select-dropdown:visible .el-select-dropdown__item")
    if vis.count():
        return vis
    return page.locator(".el-select-dropdown__item")


def _pick_select(page, form_label: str, option_substr: str, *, typed: str | None = None, root=None) -> None:
    scope = root or page
    item = scope.locator(".el-form-item", has_text=form_label).first
    item.locator(".el-select").click()
    page.wait_for_timeout(400)
    if typed:
        inp = item.locator("input").first
        inp.click()
        inp.fill("")
        inp.press_sequentially(typed, delay=40)
        page.wait_for_timeout(600)
    opt = _dropdown_items(page).filter(has_text=option_substr)
    if opt.count() == 0:
        page.wait_for_timeout(800)
        opt = _dropdown_items(page).filter(has_text=option_substr)
    assert opt.count() >= 1, f"下拉无选项 {form_label}/{option_substr}"
    opt.first.click()
    page.wait_for_timeout(300)


def _upload_id_pair(page, root=None) -> None:
    png = tiny_png_path()
    scope = root or page
    inputs = scope.locator(".material-item input[type=file]")
    assert inputs.count() >= 2, "无身份证正反面上传框"
    inputs.nth(0).set_input_files(png)
    page.wait_for_timeout(900)
    inputs.nth(1).set_input_files(png)
    page.wait_for_timeout(900)
    assert scope.get_by_text("已上传").count() >= 2


def test_fe_a22_01_register_network(page):
    """FE-A22-01: 未占用手机注册 → POST /auth/register 200/201 → /dashboard 入驻引导，不进经营壳。"""
    phone = "137" + f"{int(time.time()) % 10**8:08d}"
    page.goto(f"{BASE_URL}/register", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.get_by_placeholder("团队内显示的名称").fill("金标注册用户")
    page.get_by_placeholder("用于登录与接收重要通知").fill(phone)
    page.get_by_placeholder("至少 8 位").fill("gold123456")
    page.get_by_placeholder("团队对外称呼，可与营业执照名称不同").fill(f"金标注册台{phone[-4:]}")
    with page.expect_response(
        lambda r: "/auth/register" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        page.click('button:has-text("注册")')
    assert resp_info.value.status in (200, 201)
    page.wait_for_url(lambda u: "/dashboard" in u, timeout=20000)
    assert "/shop/" not in page.url or "/shop/onboarding" in page.url
    body = page.locator("body").inner_text()
    assert "注册" in body or "入驻" in body or "开通内容获客" in body
    assert "经营壳" not in page.url


def test_fe_a20_01_onboarding_personal_upload(page):
    """FE-A20-01: 新商家个人主体 + 真上传身份证 → POST applications 200/201 → 审核中。"""
    acc = register_workspace(tag=uuid.uuid4().hex[:6])
    shop_name = f"金标自申店{acc['tag']}"
    _STATE["a20_shop"] = shop_name
    _STATE["a20_phone"] = acc["phone"]
    ui_login(page, acc["phone"], acc["password"])
    ui_goto(page, "/shop/onboarding")
    page.wait_for_timeout(800)
    page.locator(".el-radio-button__inner", has_text="个人").click()
    page.locator(".el-form-item", has_text="主体名称").locator("input").fill(f"金标个人{acc['tag']}")
    page.locator(".el-form-item", has_text="商家展示名").locator("input").fill(shop_name)
    page.locator(".el-form-item", has_text="经营联系人").locator("input").fill("金标联系人")
    page.locator(".el-form-item", has_text="联系电话").locator("input").fill(acc["phone"])
    page.locator(".el-form-item", has_text="身份证号").locator("input").fill("110101199001011234")
    _upload_id_pair(page)
    with page.expect_response(
        lambda r: "/onboarding/applications" in r.url
        and r.request.method == "POST"
        and "/admin/" not in r.url,
        timeout=25000,
    ) as resp_info:
        page.get_by_role("button", name="提交入驻申请").click()
    assert resp_info.value.status in (200, 201)
    page.wait_for_timeout(1000)
    body = page.locator("body").inner_text()
    assert "审核" in body or "提交成功" in body or "审核中" in body
    assert "假商户" not in body


def test_fe_p02a_01_initiate_onboarding(page):
    """FE-P02A-01: 平台帮客户开通 → 选租户+上传 → POST admin onboarding 201。"""
    acc = register_workspace(tag=uuid.uuid4().hex[:6])
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.locator('[data-testid="shop-merchants"]').wait_for(timeout=15000)
    btn = page.locator("button:has-text('帮客户开通商城')").first
    if btn.count() == 0:
        btn = page.locator("button:has-text('发起入驻')").first
    assert btn.count() >= 1
    btn.click()
    page.wait_for_timeout(600)
    drawer = page.locator(".el-drawer:visible")
    sel = drawer.locator(".el-select").first
    sel.click()
    page.wait_for_timeout(300)
    inp = drawer.locator(".el-select input").first
    inp.click()
    inp.fill("")
    inp.press_sequentially(acc["tenant_name"], delay=40)
    page.wait_for_timeout(900)
    opt = _dropdown_items(page).filter(has_text=acc["tenant_name"])
    assert opt.count() >= 1, f"租户候选无 {acc['tenant_name']}"
    opt.first.click()
    page.wait_for_timeout(400)
    drawer.locator(".el-radio-button__inner", has_text="个人").click()
    drawer.locator(".el-form-item", has_text="主体名称").locator("input").fill(f"金标代发{acc['tag']}")
    drawer.locator(".el-form-item", has_text="商家展示名").locator("input").fill(f"金标代发店{acc['tag']}")
    drawer.locator(".el-form-item", has_text="经营联系人").locator("input").fill("代发联系人")
    drawer.locator(".el-form-item", has_text="联系电话").locator("input").fill(acc["phone"])
    drawer.locator(".el-form-item", has_text="身份证号").locator("input").fill("110101199001011234")
    _upload_id_pair(page, drawer)
    with page.expect_response(
        lambda r: "/admin/shop/onboarding/applications" in r.url
        and r.request.method == "POST"
        and "/approve" not in r.url
        and "/reject" not in r.url,
        timeout=25000,
    ) as resp_info:
        page.get_by_role("button", name="提交待审").click()
    assert resp_info.value.status in (200, 201)
    page.wait_for_timeout(800)
    assert _toast_or_body(page, "待审核", "已提交", "审核")


def test_fe_p03_01_approve_onboarding(page):
    """FE-P03-01: 待审入驻 → 通过并开通 → POST approve 200。"""
    shop = _STATE.get("a20_shop")
    if not shop:
        pytest.skip("FE-A20-01 未产生待审单")
    _platform_login(page)
    ui_goto(page, "/admin/shop/onboarding")
    page.wait_for_timeout(600)
    tab = page.get_by_role("tab", name="待审").first
    if tab.count():
        tab.click()
        page.wait_for_timeout(400)
    search = page.get_by_placeholder("搜索商家名")
    search.fill(shop)
    search.press("Enter")
    page.wait_for_timeout(800)
    audit = page.get_by_role("button", name="审核").first
    assert audit.count() >= 1, f"待审列表无 {shop}"
    audit.click()
    page.wait_for_timeout(800)
    page.locator(".review-subtabs").get_by_text("通过并开通", exact=True).click()
    page.wait_for_timeout(500)
    with page.expect_response(
        lambda r: "/approve" in r.url and r.request.method == "POST", timeout=25000
    ) as resp_info:
        page.get_by_role("button", name="确认通过并开通").click()
    assert resp_info.value.status == 200
    page.wait_for_timeout(800)
    assert _toast_or_body(page, "已通过", "开通")


def test_fe_a02_01_s1_submit_review(page):
    """FE-A02-01-S1: 草稿点提交审核 → POST submit-review → pending_review。"""
    token = merchant_token()
    prod = create_draft_course(token)
    ui_login(page, MERCHANT_PHONE, MERCHANT_PASSWORD)
    ui_goto(page, f"/shop/products/{prod['id']}")
    page.wait_for_timeout(800)
    with page.expect_response(
        lambda r: "/submit-review" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        page.get_by_role("button", name="提交审核").click()
    assert resp_info.value.status in (200, 201)
    page.wait_for_timeout(800)
    body = page.locator("body").inner_text()
    assert "提交" in body or "审核" in body or "待审" in body


def test_fe_p09_01_approve_product_review(page):
    """FE-P09-01: 待审商品人审通过 → POST product-reviews/{id}/approve 200。"""
    token = merchant_token()
    prod = create_draft_course(token, name=f"金标待审课{uuid.uuid4().hex[:6]}")
    submit_review_leave_pending(token, prod["id"])
    _platform_login(page)
    ui_goto(page, "/admin/shop/product-reviews")
    ui_wait_ready(page)
    search = page.get_by_placeholder("搜索商品 / 商家")
    search.fill(prod["name"])
    search.press("Enter")
    page.wait_for_timeout(900)
    row = page.locator(".el-table__row", has_text=prod["name"]).first
    assert row.count() >= 1, f"商品待审无 {prod['name']}"
    row.get_by_role("button", name="审核").click()
    page.wait_for_timeout(900)
    panel = page.locator('[data-testid="shop-product-review-panel"]')
    note = panel.locator("textarea").first
    if note.count():
        note.fill("金标人审通过备注")
    with page.expect_response(
        lambda r: "/product-reviews/" in r.url
        and r.url.rstrip("/").endswith("/approve")
        and r.request.method == "POST",
        timeout=20000,
    ) as resp_info:
        page.evaluate(
            """() => {
              const panel = document.querySelector('[data-testid="shop-product-review-panel"]');
              const btn = [...(panel?.querySelectorAll('button') || [])]
                .find((b) => (b.textContent || '').trim() === '通过');
              btn?.click();
            }"""
        )
    assert resp_info.value.status == 200
    page.wait_for_timeout(700)
    assert _toast_or_body(page, "已通过")


def test_fe_p11_01_confirm_open_addon(page):
    """FE-P11-01: 人工开通叠加短信加购 → POST /admin/shop/subscriptions 200/201。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/subscriptions")
    ui_wait_ready(page)
    page.get_by_role("button", name="人工开通（主套餐/叠加）").click()
    page.wait_for_timeout(800)
    dlg = page.locator(".el-dialog").filter(has_text="人工开通").last
    _pick_select(page, "商家", "经营中", typed="经营中", root=dlg)
    dlg.locator(".el-radio").filter(has_text="叠加").click(force=True)
    page.wait_for_timeout(300)
    _pick_select(page, "选择套餐", "短信加购", root=dlg)
    page.wait_for_timeout(400)
    with page.expect_response(
        lambda r: r.request.method == "POST"
        and "/admin/shop/subscriptions" in r.url
        and "/export" not in r.url
        and "/replace" not in r.url
        and "/renew" not in r.url,
        timeout=20000,
    ) as resp_info:
        page.get_by_role("button", name="确认开通").click()
    assert resp_info.value.status in (200, 201, 409)
    page.wait_for_timeout(800)
    if resp_info.value.status in (200, 201):
        assert _toast_or_body(page, "开通成功", "成功")
    else:
        assert _toast_or_body(page, "叠加", "已开通", "失败", "冲突")


def test_fe_a10_01_merchant_refund(page):
    """FE-A10-01: 隔离已付单 → 商家选原因提交退款 → POST /shop/orders/{id}/refund 200。

    落地按钮文案为「提交退款」（非「同意」）；不消耗演示课。
    """
    paid = create_isolated_paid_order()
    ui_login(page, MERCHANT_PHONE, MERCHANT_PASSWORD)
    ui_goto(page, f"/shop/orders/{paid['order_id']}")
    page.wait_for_timeout(900)
    page.get_by_role("button", name="退款").click()
    page.wait_for_timeout(600)
    dlg = page.locator(".el-dialog").filter(has_text="发起退款").last
    _pick_select(page, "退款原因", "买家申请", root=dlg)
    with page.expect_response(
        lambda r: "/refund" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        page.get_by_role("button", name="提交退款").click()
    assert resp_info.value.status == 200
    page.wait_for_timeout(800)
    assert _toast_or_body(page, "退款成功", "已退", "成功")


def test_fe_m12_01_buyer_refund(mobile_page):
    """FE-M12-01: 隔离已付单 → 买家选原因提交申请 → POST mp refund 200/201。"""
    paid = create_isolated_paid_order()
    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/order-detail?id={paid['order_id']}"
        f"&tenant_id={paid['tenant_id']}&openid={paid['openid']}&action=refund"
    )
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1800)
    if mobile_page.get_by_text("申请退款").count() == 0:
        btn = mobile_page.get_by_text("申请退款").or_(mobile_page.locator(".btn.danger"))
        if btn.count():
            btn.first.click()
            mobile_page.wait_for_timeout(500)
    picker = mobile_page.locator(".picker").first
    if picker.count():
        picker.click()
        mobile_page.wait_for_timeout(600)
        done = mobile_page.locator(".uni-picker-action, .uni-picker-confirm").filter(
            has_text=re.compile("完成|确定")
        )
        if done.count() == 0:
            done = mobile_page.get_by_text("完成")
        if done.count():
            done.last.click(force=True)
            mobile_page.wait_for_timeout(300)
    with mobile_page.expect_response(
        lambda r: "/refund" in r.url and r.request.method == "POST", timeout=20000
    ) as resp_info:
        mobile_page.get_by_text("提交申请").first.click()
    assert resp_info.value.status in (200, 201)
    mobile_page.wait_for_timeout(800)
    body = mobile_page.locator("body").inner_text()
    assert "退款" in body or "已提交" in body or "进度" in body
