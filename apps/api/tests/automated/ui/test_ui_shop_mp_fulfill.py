"""买家履约页 UI。对照 M05/M07–M10b/M12–M14。"""
from __future__ import annotations

import os

import pytest

from tests.seed_shop_demo import BUYER_MOBILE, BUYER_OPENID, CLAIM_TOKEN, DIGITAL_NAME, seed

MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")


@pytest.fixture(scope="module")
def demo_shop():
    return seed(reset=False)


def _qs(demo_shop: dict, extra: str = "") -> str:
    q = f"tenant_id={demo_shop['tenant_id']}&openid={BUYER_OPENID}"
    return f"{q}&{extra}" if extra else q


def _goto(mobile_page, path: str, demo_shop: dict, extra: str = "") -> None:
    mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/{path}?{_qs(demo_shop, extra)}")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(2000)
    for _ in range(8):
        if mobile_page.get_by_text("加载中").count() == 0:
            break
        mobile_page.wait_for_timeout(400)


def _click_entitlement_action(mobile_page, demo_shop, chip: str, action: str):
    _goto(mobile_page, "entitlements", demo_shop)
    tab = mobile_page.locator(".chip", has_text=chip).first
    if tab.count() > 0:
        tab.click()
        mobile_page.wait_for_timeout(500)
    btn = mobile_page.get_by_text(action, exact=True).first
    if btn.count() == 0:
        btn = mobile_page.locator(".btn", has_text=action).first
    return btn


def test_ui_shop_mp_learn(mobile_page, demo_shop):
    """SHOP-MP-FUL-001 / M07: 课时目录。对照 #m07。"""
    btn = _click_entitlement_action(mobile_page, demo_shop, "课程", "继续学")
    if btn.count() == 0:
        pytest.skip("无课程已购")
    btn.click()
    mobile_page.wait_for_timeout(1500)
    body = mobile_page.locator("body").inner_text()
    assert "学习进度" in body or "课程目录" in body
    assert mobile_page.locator(".lesson, .head").count() >= 1


def test_ui_shop_mp_player(mobile_page, demo_shop):
    """SHOP-MP-FUL-002 / M08: 已购进播放器。对照 #m08。"""
    btn = _click_entitlement_action(mobile_page, demo_shop, "课程", "继续学")
    if btn.count() == 0:
        pytest.skip("无课程已购")
    btn.click()
    mobile_page.wait_for_timeout(1500)
    lesson = mobile_page.locator(".lesson").first
    if lesson.count() == 0:
        pytest.skip("无课时行")
    lesson.click()
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.locator(".stage-title, .play-btn").count() >= 1
    assert mobile_page.get_by_text("播放").count() >= 1 or mobile_page.get_by_text("暂停").count() >= 1


def test_ui_shop_mp_materials(mobile_page, demo_shop):
    """SHOP-MP-FUL-003 / M09: 资料领取。对照 #m09。"""
    btn = _click_entitlement_action(mobile_page, demo_shop, "资料", "领取")
    if btn.count() == 0:
        pytest.skip("无资料已购")
    btn.click()
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("资料领取").count() >= 1
    assert mobile_page.locator(".card, .empty").count() >= 1


def test_ui_shop_mp_booking(mobile_page, demo_shop):
    """SHOP-MP-FUL-004 / M10: 服务预约。对照 #m10。"""
    btn = _click_entitlement_action(mobile_page, demo_shop, "服务", "预约")
    if btn.count() == 0:
        pytest.skip("无服务已购")
    btn.click()
    mobile_page.wait_for_timeout(1500)
    body = mobile_page.locator("body").inner_text()
    assert "核销码" in body or "确认预约" in body or "预约" in body
    assert mobile_page.locator(".btn-primary, .empty").count() >= 1


def test_ui_shop_mp_verify_code(mobile_page, demo_shop):
    """SHOP-MP-FUL-005 / M10b: 核销码页。对照 #m10b。"""
    btn = _click_entitlement_action(mobile_page, demo_shop, "服务", "预约")
    if btn.count() == 0:
        pytest.skip("无服务已购")
    btn.click()
    mobile_page.wait_for_timeout(1500)
    code_btn = mobile_page.get_by_text("获取核销码").first
    if code_btn.count() == 0:
        pytest.skip("次数卡核销码入口未出（预约模式）")
    code_btn.click()
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("核销码").count() >= 1
    assert mobile_page.get_by_text("复制核销码").count() >= 1


def test_ui_shop_mp_bookings_list(mobile_page, demo_shop):
    """SHOP-MP-FUL-006 / M10: 我的预约列表。对照 #m10。"""
    _goto(mobile_page, "bookings", demo_shop)
    assert mobile_page.get_by_text("我的预约").count() >= 1
    assert mobile_page.locator(".card, .empty").count() >= 1


def test_ui_shop_mp_pay_result(mobile_page, demo_shop):
    """SHOP-MP-FUL-007 / M05: 支付结果页。对照 #m05。"""
    _goto(mobile_page, "pay-result", demo_shop, extra="status=paid")
    assert mobile_page.get_by_text("支付成功").count() >= 1
    assert mobile_page.get_by_text("查看已购").count() >= 1


def test_ui_shop_mp_order_detail(mobile_page, demo_shop):
    """SHOP-MP-FUL-008 / M12: 订单详情。对照 #m12。"""
    _goto(mobile_page, "orders", demo_shop)
    card = mobile_page.locator(".card").first
    if card.count() == 0:
        pytest.skip("无订单行")
    card.click()
    mobile_page.wait_for_timeout(1500)
    body = mobile_page.locator("body").inner_text()
    assert "实付" in body or "单号" in body
    assert mobile_page.locator(".badge, .actions").count() >= 1


def test_ui_shop_mp_invoice(mobile_page, demo_shop):
    """SHOP-MP-FUL-009 / M13: 申请开票页。对照 #m13。"""
    _goto(mobile_page, "orders", demo_shop)
    inv = mobile_page.get_by_text("申请开票").first
    if inv.count() == 0:
        inv = mobile_page.get_by_text("查看发票").first
    if inv.count() == 0:
        pytest.skip("无开票入口（需已付款订单）")
    inv.click()
    mobile_page.wait_for_timeout(1500)
    body = mobile_page.locator("body").inner_text()
    assert "开票" in body or "发票" in body
    assert mobile_page.locator(".input, .card, .seg-item").count() >= 1


def test_ui_shop_mp_claim(mobile_page, demo_shop):
    """SHOP-MP-FUL-010 / M14: 领权页三态壳。对照 #m14。"""
    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/claim?token={CLAIM_TOKEN}&tenant_id={demo_shop['tenant_id']}"
    )
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("领取课程").count() >= 1
    body = mobile_page.locator("body").inner_text()
    assert (
        "确认领取" in body
        or "领取成功" in body
        or "链接已失效" in body
        or "无法领取" in body
        or "链接无效" in body
    )


def test_fe_m03_01_checkout_pay_network(mobile_page, demo_shop):
    """FE-M03-01: 确认订单 → POST orders + pay → 支付成功页。"""
    from tests.http_client import req

    code, data = req("GET", f"/mp/shop/store?shop_id={demo_shop['shop_id']}")
    assert code == 200, data
    pid = None
    for p in data.get("products") or []:
        if p.get("name") == DIGITAL_NAME:
            pid = p["id"]
            break
    if not pid and data.get("products"):
        pid = data["products"][0]["id"]
    assert pid
    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/checkout"
        f"?product_id={pid}&tenant_id={demo_shop['tenant_id']}&openid={BUYER_OPENID}"
    )
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("应付金额").count() >= 1
    with mobile_page.expect_response(
        lambda r: "/mp/shop/orders" in r.url and r.request.method == "POST" and "/pay" not in r.url,
        timeout=25000,
    ) as create_info:
        mobile_page.locator(".primary").first.click()
    assert create_info.value.status in (200, 201)
    mobile_page.wait_for_timeout(2500)
    body = mobile_page.locator("body").inner_text()
    assert "支付成功" in body or "查看已购" in body or "支付处理中" in body


def test_fe_m12_01_b1_refund_no_reason(mobile_page, demo_shop):
    """FE-M12-01-B1: 申请退款不选原因 → toast 拦截。"""
    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/orders?tenant_id={demo_shop['tenant_id']}&openid={BUYER_OPENID}"
    )
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    refund = mobile_page.get_by_text("退款").first
    if refund.count() == 0:
        card = mobile_page.locator(".card").first
        if card.count() == 0:
            return
        card.click()
        mobile_page.wait_for_timeout(1200)
        refund = mobile_page.get_by_text("申请退款").first
    if refund.count() == 0:
        return
    refund.click()
    mobile_page.wait_for_timeout(500)
    submit = mobile_page.get_by_text("提交申请").first
    if submit.count() == 0:
        return
    fired = {"n": 0}

    def on_req(req):
        if "/refund" in req.url and req.method == "POST":
            fired["n"] += 1

    mobile_page.on("request", on_req)
    submit.click()
    mobile_page.wait_for_timeout(800)
    assert fired["n"] == 0


def test_fe_m14_01_claim_page_network(mobile_page, demo_shop):
    """FE-M14-01: 领权页加载 GET claim；pending 则可授权确认。"""
    with mobile_page.expect_response(
        lambda r: f"/mp/shop/claim/{CLAIM_TOKEN}" in r.url and r.request.method == "GET",
        timeout=20000,
    ) as get_info:
        mobile_page.goto(
            f"{MP_BASE_URL}/#/pages/shop/claim?token={CLAIM_TOKEN}&tenant_id={demo_shop['tenant_id']}"
        )
        mobile_page.wait_for_load_state("networkidle")
    assert get_info.value.status in (200, 404, 410)
    for _ in range(8):
        if mobile_page.get_by_text("加载中").count() == 0:
            break
        mobile_page.wait_for_timeout(400)
    body = mobile_page.locator("body").inner_text()
    assert "领取课程" in body
    if "确认领取" not in body:
        assert any(
            x in body
            for x in ("领取成功", "链接已失效", "无法领取", "链接无效")
        )
        return
    auth = mobile_page.get_by_text("授权").first
    if auth.count():
        auth.click()
        mobile_page.wait_for_timeout(400)
        inp = mobile_page.locator("input[placeholder*='购买手机号']").first
        if inp.count():
            inp.fill(BUYER_MOBILE)
            mobile_page.locator(".sheet-actions .btn-primary").first.click()
            mobile_page.wait_for_timeout(800)
    confirm = mobile_page.locator(".btn-primary", has_text="确认领取").first
    if confirm.count() == 0:
        return
    with mobile_page.expect_response(
        lambda r: f"/mp/shop/claim/{CLAIM_TOKEN}" in r.url and r.request.method == "POST",
        timeout=15000,
    ) as post_info:
        confirm.click()
    assert post_info.value.status in (200, 409, 410, 422)
    mobile_page.wait_for_timeout(800)
    body = mobile_page.locator("body").inner_text()
    assert "领取" in body or "已购" in body or "失败" in body or "过期" in body
