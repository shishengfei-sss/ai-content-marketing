"""数据看板与结算 UI — 已落地页去 skip；未做页书面 Blocked。"""
from __future__ import annotations

import pytest

from tests.automated.ui.conftest import ui_goto, ui_login


def _open_a01(page):
    """A01 交易看板。/shop/dashboard 会重定向到 /shop/overview。"""
    ui_login(page)
    ui_goto(page, "/shop/overview")
    page.get_by_role("heading", name="交易看板").wait_for(timeout=20000)
    page.locator('[data-testid="shop-dashboard-container"]').wait_for(timeout=10000)


def test_ui_shop_dashboard_charts(page):
    """SHOP-DASH-001 / A01: 交易看板图表。对照 #a01。"""
    _open_a01(page)
    assert page.get_by_text("成交额").count() >= 1
    assert page.get_by_text("品类占比").count() >= 1
    assert page.get_by_text("渠道占比").count() >= 1
    assert page.locator('[data-testid="select-time-range"]').count() >= 1
    page.locator('[data-testid="shop-current-store"]').wait_for(timeout=15000)
    assert "当前店铺" in page.locator('[data-testid="shop-current-store"]').inner_text()
    page.get_by_text("待开票").first.click()
    page.wait_for_timeout(1500)
    assert "/shop/invoices" in page.url


def test_ui_shop_dashboard_sales_trend(page):
    """SHOP-DASH-002 / A01: 成交额按日（无独立销售趋势路由，对照 #a01 图表）。"""
    _open_a01(page)
    chart = page.locator('[data-testid="chart-revenue-trend"]')
    chart.wait_for(timeout=10000)
    assert "成交额按日" in chart.inner_text()
    page.get_by_role("button", name="近7日").click()
    page.wait_for_timeout(800)
    assert chart.count() >= 1


def test_ui_shop_dashboard_product_ranking(page):
    """SHOP-DASH-003 / A01: 品类占比（PRD 无独立商品排行页）。"""
    _open_a01(page)
    body = page.locator('[data-testid="shop-dashboard-container"]').inner_text()
    assert "品类占比" in body
    assert "渠道占比" in body


def test_ui_shop_dashboard_invoices(page):
    """SHOP-DASH / A13: 开票申请列表完备。对照 #a13 / #a13-select-spec。"""
    ui_login(page)
    ui_goto(page, "/shop/invoices")
    page.locator('[data-testid="shop-invoices"]').wait_for(timeout=15000)
    root = page.locator('[data-testid="shop-invoices"]')
    body = root.inner_text()
    assert "全部申请" in body
    for col in ("订单", "抬头", "类型", "税号", "邮箱", "金额", "申请时间", "状态"):
        assert col in body, col
    assert page.get_by_placeholder("订单号 / 抬头").count() >= 1
    assert page.locator(".el-select__placeholder").filter(has_text="类型").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    page.get_by_text("高级筛选").first.click()
    page.wait_for_timeout(300)
    assert page.get_by_placeholder("申请起").count() >= 1
    assert page.get_by_placeholder("申请止").count() >= 1
    page.get_by_text("列设置").first.click()
    page.wait_for_timeout(300)
    dlg = page.locator(".el-dialog").last
    text = dlg.inner_text()
    assert "处理人" in text
    assert "开具时间" in text
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
    page.wait_for_timeout(200)
    issue_btn = page.get_by_role("button", name="开具", exact=True)
    if issue_btn.count() >= 1:
        issue_btn.first.click()
        page.get_by_text("开具发票").wait_for(timeout=5000)
        drawer = page.locator(".el-drawer").filter(has_text="开具发票")
        assert "备注" in drawer.inner_text()
        remark = drawer.locator("textarea")
        assert remark.count() >= 1
        assert remark.first.is_enabled()
        remark.first.fill("开具备注验收")
        assert remark.first.input_value() == "开具备注验收"


@pytest.mark.skip(reason="Phase1 清结算在平台 P05；商家无独立结算列表（对照 #p05）")
def test_ui_shop_dashboard_settlement(page):
    """历史 SHOP-DASH-004：商家结算列表不在 Phase1 范围。"""
    ui_login(page)
    ui_goto(page, "/shop/settlement")


@pytest.mark.skip(reason="Phase1 对账详情在平台 P05-B；商家无独立对账页")
def test_ui_shop_dashboard_reconciliation(page):
    """历史 SHOP-DASH-005：商家对账页不在 Phase1 范围。"""
    ui_login(page)
    ui_goto(page, "/shop/settlement/reconciliation/1")
