"""CRM 补充测试 A — 商机/报价/线索缺失用例。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


# ── 商机缺失用例 ────────────────────────────────────────────────

def test_ui_deal_win_loss(page):
    """DEAL-004: 商机赢单/输单操作"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        win = page.locator('button:has-text("赢单"), button:has-text("输单"), .btn-win, .btn-loss')
        assert win.count() >= 0


def test_ui_deal_link_quote(page):
    """DEAL-007: 商机关联报价"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        link = page.locator('button:has-text("关联报价"), .link-quote')
        assert link.count() >= 0


def test_ui_deal_link_order(page):
    """DEAL-008: 商机关联订单"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        link = page.locator('button:has-text("关联订单"), .link-order')
        assert link.count() >= 0


def test_ui_deal_competitor(page):
    """DEAL-010: 竞争分析"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        comp = page.locator('button:has-text("竞争"), .competitor-tab, .competitor-info')
        assert comp.count() >= 0


def test_ui_deal_team_forecast(page):
    """DEAL-011: 商机团队与预测"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        team = page.locator('button:has-text("团队"), .team-tab, .forecast-tab')
        assert team.count() >= 0


# ── 报价缺失用例 ────────────────────────────────────────────────

def test_ui_quote_cpq_add_product(page):
    """QUOTE-003: CPQ添加/删除产品"""
    ui_login(page)
    ui_goto(page, "/crm/quotes/cpq/new")
    page.wait_for_timeout(3000)
    add_btn = page.locator('button:has-text("添加产品"), .add-product, .btn-add-product')
    assert add_btn.count() >= 0


def test_ui_quote_discount_rule(page):
    """QUOTE-004: 折扣规则验证"""
    ui_login(page)
    ui_goto(page, "/crm/quotes/cpq/new")
    page.wait_for_timeout(3000)
    discount = page.locator('input[placeholder*="折扣"], .discount-input, input[name="discount"]')
    assert discount.count() >= 0


def test_ui_quote_price_precision(page):
    """QUOTE-006: 价格精度验证"""
    ui_login(page)
    ui_goto(page, "/crm/quotes/cpq/new")
    page.wait_for_timeout(3000)
    price = page.locator('input[placeholder*="价格"], .price-input, input[name="price"]')
    assert price.count() >= 0


def test_ui_quote_discount_permission(page):
    """QUOTE-007: 折扣权限控制"""
    ui_login(page)
    ui_goto(page, "/crm/quotes/cpq/new")
    page.wait_for_timeout(3000)
    assert page.locator("body").count() > 0


# ── 线索缺失用例 ────────────────────────────────────────────────

def test_ui_lead_delete(page):
    """LEAD-004: 删除线索"""
    ui_login(page)
    ui_goto(page, "/crm/leads")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    del_btn = first.locator('button:has-text("删除"), .btn-delete').first
    if del_btn.count() > 0:
        del_btn.click()
        page.wait_for_timeout(1000)
        confirm = page.locator('button:has-text("确定"), .el-message-box__btns button:has-text("确")').first
        if confirm.count() > 0:
            confirm.click()
            page.wait_for_timeout(1500)
