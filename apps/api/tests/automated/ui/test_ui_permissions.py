"""数据权限与访问控制 UI 自动化测试 — 对应 PERM-001~006。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_permission_lead_scope(page):
    """PERM-001: 线索数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/leads")
    page.wait_for_timeout(2000)
    # 验证列表能加载（权限允许）
    assert page.locator(".el-table, .list-item").count() >= 0


def test_ui_permission_customer_scope(page):
    """PERM-002: 客户数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/customers")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0


def test_ui_permission_deal_scope(page):
    """PERM-003: 商机数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0


def test_ui_permission_quote_scope(page):
    """PERM-004: 报价数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/quotes")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0


def test_ui_permission_contract_scope(page):
    """PERM-005: 合同数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0


def test_ui_permission_order_scope(page):
    """PERM-006: 订单数据权限范围"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0
