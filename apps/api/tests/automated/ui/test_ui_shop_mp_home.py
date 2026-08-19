"""小程序商城首页 UI 自动化测试 — 对应 SHOP-MP-HOME-001~003。"""
from __future__ import annotations

import os

import pytest

from tests.automated.ui.conftest import BASE_URL
from tests.seed_shop_demo import seed

MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")


@pytest.fixture(scope="module")
def demo_shop():
    return seed(reset=False)


def _home_url(demo_shop: dict) -> str:
    return (
        f"{MP_BASE_URL}/#/pages/shop/home"
        f"?shop_id={demo_shop['shop_id']}&tenant_id={demo_shop['tenant_id']}"
    )


def test_ui_shop_mp_home_load(mobile_page, demo_shop):
    """SHOP-MP-HOME-001: 店首页加载。"""
    mobile_page.goto(_home_url(demo_shop))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.locator(".product-card, .hero-name").count() >= 1


def test_ui_shop_mp_home_category(mobile_page, demo_shop):
    """SHOP-MP-HOME-002: 商品分类切换。"""
    mobile_page.goto(_home_url(demo_shop))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    tab = mobile_page.locator(".type-tab", has_text="课程").first
    if tab.count() > 0:
        tab.click()
        mobile_page.wait_for_timeout(800)
    assert mobile_page.locator(".product-list, .hint").count() >= 1


def test_ui_shop_mp_home_search(mobile_page, demo_shop):
    """SHOP-MP-HOME-003: 搜索商品。"""
    mobile_page.goto(_home_url(demo_shop))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    search = mobile_page.locator(".search-input input, input[placeholder*='搜索']").first
    assert search.count() > 0
    search.fill("演示")
    mobile_page.locator(".search-btn").first.click()
    mobile_page.wait_for_timeout(1000)
    assert mobile_page.locator(".product-card, .hint, .empty").count() >= 1


def test_ui_shop_mp_home_sort(mobile_page, demo_shop):
    """SHOP-MP-HOME-004: 排序 Chip（综合/价格/销量）。对照 #m02"""
    mobile_page.goto(_home_url(demo_shop))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    for label in ("综合", "价格升序", "价格降序", "销量"):
        tab = mobile_page.locator(".sort-tab", has_text=label).first
        assert tab.count() > 0, label
    mobile_page.locator(".sort-tab", has_text="销量").first.click()
    mobile_page.wait_for_timeout(800)
    assert mobile_page.locator(".product-card, .empty").count() >= 1


def test_ui_shop_mp_home_tabbar_mine(mobile_page, demo_shop):
    """SHOP-MP-HOME-005: 底栏为首页/已购/我的。对照 #m02 #m15"""
    from tests.seed_shop_demo import BUYER_OPENID

    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/home"
        f"?shop_id={demo_shop['shop_id']}&tenant_id={demo_shop['tenant_id']}&openid={BUYER_OPENID}"
    )
    mobile_page.wait_for_timeout(1500)
    nav = mobile_page.locator(".bottom-nav")
    assert nav.get_by_text("首页").count() >= 1
    assert nav.get_by_text("已购").count() >= 1
    assert nav.get_by_text("我的").count() >= 1
    nav.get_by_text("我的").click()
    mobile_page.wait_for_timeout(1200)
    assert mobile_page.get_by_text("我的订单").count() >= 1
    assert mobile_page.get_by_text("已购内容").count() >= 1
