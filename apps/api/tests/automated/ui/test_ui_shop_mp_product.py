"""小程序商品详情 UI 自动化测试 — 对应 SHOP-MP-PROD-001~003。"""
from __future__ import annotations

import os

import pytest

from tests.seed_shop_demo import COURSE_NAME, seed

MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")


@pytest.fixture(scope="module")
def demo_shop():
    return seed(reset=False)


def _product_url(demo_shop: dict, product_id: str) -> str:
    return (
        f"{MP_BASE_URL}/#/pages/shop/product"
        f"?id={product_id}&tenant_id={demo_shop['tenant_id']}"
    )


def _course_id(demo_shop: dict) -> str:
    from tests.http_client import req

    code, data = req("GET", f"/mp/shop/store?shop_id={demo_shop['shop_id']}")
    if code != 200:
        raise RuntimeError(f"store {code} {data}")
    for p in data.get("products") or []:
        if p.get("name") == COURSE_NAME:
            return p["id"]
    raise RuntimeError("demo course not found")


def test_ui_shop_mp_product_detail(mobile_page, demo_shop):
    """SHOP-MP-PROD-001: 商品详情页。"""
    pid = _course_id(demo_shop)
    mobile_page.goto(_product_url(demo_shop, pid))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.locator(".name, .price").count() >= 1
    assert mobile_page.locator(".primary").count() >= 1


@pytest.mark.skip(reason="Phase1 无 SKU 规格")
def test_ui_shop_mp_product_sku(mobile_page, demo_shop):
    """SHOP-MP-PROD-002: SKU 选择（本阶段无规格）。"""
    pass


def test_ui_shop_mp_product_buy_cta(mobile_page, demo_shop):
    """SHOP-MP-PROD-003: 立即购买入口。"""
    pid = _course_id(demo_shop)
    mobile_page.goto(_product_url(demo_shop, pid))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    btn = mobile_page.locator(".primary").first
    assert btn.count() > 0
    btn.click()
    mobile_page.wait_for_timeout(1200)
    assert mobile_page.locator(".mobile-input, .section-title").count() >= 1


def test_ui_shop_mp_product_trial(mobile_page, demo_shop):
    """SHOP-MP-PROD-004: 未购点试看进 M08。对照 #m03 / #m08"""
    pid = _course_id(demo_shop)
    mobile_page.goto(_product_url(demo_shop, pid))
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    row = mobile_page.locator(".lesson-row", has_text="试看").first
    assert row.count() > 0
    row.click()
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.locator(".badge, .stage-title, .buy-cta").count() >= 1
