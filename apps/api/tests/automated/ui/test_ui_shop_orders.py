"""订单管理 UI — 对照 PRD #a09/#a10/#a12。已落地页去 skip。"""
from __future__ import annotations

import pytest

from tests.automated.ui.conftest import ui_goto, ui_login


def test_ui_shop_orders_list(page):
    """SHOP-ORD-001: 订单列表页（A09）。对照 PRD #a09 默认列与工具栏。"""
    ui_login(page)
    ui_goto(page, "/shop/orders")
    page.wait_for_selector(".el-table", timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.locator(".status-tabs, .tabs, .tab").count() >= 1 or page.get_by_text("全部订单").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    for label in ("单号", "商品", "买家", "金额", "渠道", "状态", "下单时间"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_orders_detail(page):
    """SHOP-ORD-002 / A10: 订单详情（行内查看 → 详情页）。"""
    ui_login(page)
    ui_goto(page, "/shop/orders")
    page.wait_for_selector(".el-table", timeout=15000)
    detail_btn = page.locator("button:has-text('详情')").first
    if detail_btn.count() > 0:
        detail_btn.click()
        page.wait_for_timeout(1500)
        assert "/shop/orders/" in page.url
        assert page.locator(".el-descriptions, .order-detail, .page-card, .el-card").count() >= 1
    else:
        # 无数据时至少列表空态可渲染
        assert page.locator(".el-table, .el-empty").count() >= 1


def test_ui_shop_orders_entitlements(page):
    """SHOP-ORD-004 / A12: 权益列表完备。对照 #a12 / #a12-select-spec。"""
    ui_login(page)
    ui_goto(page, "/shop/entitlements")
    page.locator('[data-testid="shop-entitlements"]').wait_for(timeout=15000)
    root = page.locator('[data-testid="shop-entitlements"]')
    body = root.inner_text()
    assert "全部权益" in body
    for col in ("买家", "商品", "类型", "状态", "次数", "订单", "开通时间", "到期时间"):
        assert col in body, col
    assert page.get_by_placeholder("手机 / 订单号").count() >= 1
    assert page.locator(".el-select__placeholder").filter(has_text="类型").count() >= 1
    assert page.locator(".el-select__placeholder").filter(has_text="状态").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    page.get_by_text("高级筛选").first.click()
    page.wait_for_timeout(300)
    assert page.get_by_placeholder("开通起").count() >= 1
    assert page.get_by_placeholder("到期起").count() >= 1
    page.get_by_text("列设置").first.click()
    page.wait_for_timeout(300)
    dlg = page.locator(".el-dialog").last
    assert "店铺" in dlg.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


@pytest.mark.skip(reason="Phase1 内容商品无物流发货流；履约为权益/核销")
def test_ui_shop_orders_ship(page):
    """历史 SHOP-ORD-003：发货不适用。"""
    ui_login(page)
    ui_goto(page, "/shop/orders")


@pytest.mark.skip(reason="无独立售后列表页；退款在 A09/A10 行内弹窗（对照 #a09b）")
def test_ui_shop_orders_after_sale(page):
    """历史 SHOP-ORD-005：独立售后页未规划。"""
    ui_login(page)
    ui_goto(page, "/shop/orders")
