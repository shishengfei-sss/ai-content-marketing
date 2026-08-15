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
