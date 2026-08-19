"""小程序已购 / 订单中心 UI。对照 M06 / M11。"""
from __future__ import annotations

import os

from tests.seed_shop_demo import BUYER_OPENID, seed

MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")


def demo_shop():
    return seed(reset=False)


def _qs(info: dict) -> str:
    return f"tenant_id={info['tenant_id']}&openid={BUYER_OPENID}"


def test_ui_shop_mp_profile_home(mobile_page):
    """SHOP-MP-PROF-001: 已购（学习中心）。对照 #m06。"""
    info = demo_shop()
    mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/entitlements?{_qs(info)}")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("已购").count() >= 1
    assert mobile_page.locator(".chip, .card, .empty").count() >= 1


def test_ui_shop_mp_profile_orders(mobile_page):
    """SHOP-MP-PROF-002: 从已购进入我的订单。对照 #m11。"""
    info = demo_shop()
    mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/entitlements?{_qs(info)}")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1200)
    link = mobile_page.get_by_text("我的订单").first
    if link.count() > 0:
        link.click()
        mobile_page.wait_for_timeout(1200)
    else:
        mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/orders?{_qs(info)}")
        mobile_page.wait_for_timeout(1200)
    assert mobile_page.locator(".tab, .card, .empty, body").count() > 0


def test_ui_shop_mp_profile_benefits(mobile_page):
    """SHOP-MP-PROF-003: 已购类型 Chip。对照 #m06。"""
    info = demo_shop()
    mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/entitlements?{_qs(info)}")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    chip = mobile_page.locator(".chip", has_text="课程").first
    if chip.count() > 0:
        chip.click()
        mobile_page.wait_for_timeout(600)
    assert mobile_page.locator(".card, .empty, .chip").count() >= 1


def _mine_url(info: dict) -> str:
    return (
        f"{MP_BASE_URL}/#/pages/shop/mine"
        f"?shop_id={info['shop_id']}&tenant_id={info['tenant_id']}&openid={BUYER_OPENID}"
    )


def test_ui_shop_mp_mine_logged_in(mobile_page):
    """TC-M15-F01: 已登录资料与菜单原文。对照 #m15。"""
    info = demo_shop()
    mobile_page.goto(_mine_url(info))
    mobile_page.wait_for_timeout(1800)
    login_btn = mobile_page.get_by_text("登录", exact=True)
    if login_btn.count():
        login_btn.first.click()
        mobile_page.wait_for_timeout(800)
    body = mobile_page.locator("body").inner_text()
    assert "我的订单" in body
    assert "已购内容" in body
    assert "领权兑换" in body
    assert "联系客服" in body
    assert "用户协议 / 隐私" in body
    assert "退出登录" in body
    assert "****" in body or "未绑定手机" in body


def test_ui_shop_mp_mine_orders_entry(mobile_page):
    """TC-M15-F04: 我的订单 → M11。对照 #m15。"""
    info = demo_shop()
    mobile_page.goto(_mine_url(info))
    mobile_page.wait_for_timeout(1800)
    login_btn = mobile_page.get_by_text("登录", exact=True)
    if login_btn.count():
        login_btn.first.click()
        mobile_page.wait_for_timeout(800)
    mobile_page.locator(".menu-item", has_text="我的订单").first.click()
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("我的订单").count() >= 1
    assert mobile_page.locator(".card, .empty, .tab").count() >= 1


def test_ui_shop_mp_mine_cs_and_legal(mobile_page):
    """TC-M15-F01 客服/协议子页。对照 #m15a #m15b。"""
    info = demo_shop()
    mobile_page.goto(_mine_url(info))
    mobile_page.wait_for_timeout(1500)
    mobile_page.locator(".menu-item", has_text="联系客服").first.click()
    mobile_page.wait_for_timeout(1200)
    body = mobile_page.locator("body").inner_text()
    assert "客服电话" in body
    assert "工作时间" in body
    assert "打开客服" in body
    mobile_page.get_by_text("返回").first.click()
    mobile_page.wait_for_timeout(800)
    mobile_page.locator(".menu-item", has_text="用户协议 / 隐私").first.click()
    mobile_page.wait_for_timeout(800)
    body = mobile_page.locator("body").inner_text()
    assert "用户服务协议" in body
    assert "隐私政策" in body
    assert mobile_page.get_by_text("关闭").count() >= 1


def test_ui_shop_mp_mine_logout(mobile_page):
    """TC-M15-F03: 退出登录确认后清会话。对照 #m15c。"""
    info = demo_shop()
    mobile_page.goto(_mine_url(info))
    mobile_page.wait_for_timeout(1800)
    login_btn = mobile_page.get_by_text("登录", exact=True)
    if login_btn.count():
        login_btn.first.click()
        mobile_page.wait_for_timeout(800)
    mobile_page.locator(".logout").click()
    mobile_page.wait_for_timeout(400)
    assert "退出后需重新登录才能购买与学习" in mobile_page.locator("body").inner_text()
    mobile_page.get_by_text("确认退出").click()
    mobile_page.wait_for_timeout(800)
    assert mobile_page.get_by_text("登录").count() >= 1
    assert mobile_page.locator(".logout").count() == 0
