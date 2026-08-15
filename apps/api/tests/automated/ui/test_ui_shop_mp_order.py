"""小程序下单与订单 UI。对照 M04 / M11。Phase1 无私域购物车。"""
from __future__ import annotations

import os

import pytest

from tests.seed_shop_demo import BUYER_OPENID, COURSE_NAME, seed

MP_BASE_URL = os.environ.get("UI_TEST_MP_BASE_URL", "http://localhost:5174")


@pytest.fixture(scope="module")
def demo_shop():
    return seed(reset=False)


def _course_id(demo_shop: dict) -> str:
    from tests.http_client import req

    code, data = req("GET", f"/mp/shop/store?shop_id={demo_shop['shop_id']}")
    if code != 200:
        raise RuntimeError(f"store {code} {data}")
    for p in data.get("products") or []:
        if p.get("name") == COURSE_NAME:
            return p["id"]
    raise RuntimeError("demo course not found")


def _qs(demo_shop: dict, extra: str = "") -> str:
    q = f"tenant_id={demo_shop['tenant_id']}&openid={BUYER_OPENID}"
    return f"{q}&{extra}" if extra else q


@pytest.mark.skip(reason="Phase1 无私域购物车，下单走确认订单页 M04")
def test_ui_shop_mp_order_cart(mobile_page):
    """SHOP-MP-ORD-001: 购物车 — 本阶段无此页。"""
    raise AssertionError("unreachable")


def test_ui_shop_mp_order_checkout(mobile_page, demo_shop):
    """SHOP-MP-ORD-002: 确认订单页。对照 #m04。"""
    pid = _course_id(demo_shop)
    mobile_page.goto(
        f"{MP_BASE_URL}/#/pages/shop/checkout?product_id={pid}&{_qs(demo_shop)}"
    )
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("应付金额").count() >= 1
    assert mobile_page.locator(".primary").count() >= 1
    assert (
        mobile_page.get_by_text("确认支付").count() >= 1
        or mobile_page.get_by_text("确认领取").count() >= 1
    )


def test_ui_shop_mp_order_list(mobile_page, demo_shop):
    """SHOP-MP-ORD-003: 我的订单。对照 #m11。"""
    mobile_page.goto(f"{MP_BASE_URL}/#/pages/shop/orders?{_qs(demo_shop)}")
    mobile_page.wait_for_load_state("networkidle")
    mobile_page.wait_for_timeout(1500)
    assert mobile_page.get_by_text("我的订单").count() >= 1
    assert mobile_page.get_by_text("待付款").count() >= 1
    assert mobile_page.locator(".card, .empty, .tab").count() >= 1
