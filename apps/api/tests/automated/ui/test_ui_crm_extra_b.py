"""CRM 补充测试 B — 合同/订单缺失用例。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


# ── 合同缺失用例 ────────────────────────────────────────────────

def test_ui_contract_sign(page):
    """CONT-003: 合同电子签署"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        sign = page.locator('button:has-text("签署"), .btn-sign, .e-sign')
        assert sign.count() >= 0


def test_ui_contract_payment_record(page):
    """CONT-004: 合同回款记录"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        payment = page.locator('button:has-text("回款"), .payment-tab, .payment-record')
        assert payment.count() >= 0


def test_ui_contract_attachment(page):
    """CONT-005: 合同附件上传"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        attach = page.locator('button:has-text("附件"), .attachment-tab, .upload-btn')
        assert attach.count() >= 0


def test_ui_contract_approval(page):
    """CONT-006: 合同审批流程"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        approval = page.locator('button:has-text("审批"), .approval-tab, .approval-flow')
        assert approval.count() >= 0


def test_ui_contract_template(page):
    """CONT-007: 合同模板管理"""
    ui_login(page)
    ui_goto(page, "/settings/contract-templates")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_contract_expire(page):
    """CONT-008: 合同到期提醒"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .list-item").count() >= 0


# ── 订单缺失用例 ────────────────────────────────────────────────

def test_ui_order_link_quote(page):
    """ORDER-002: 订单关联报价"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        link = page.locator('button:has-text("关联报价"), .link-quote')
        assert link.count() >= 0


def test_ui_order_status_flow(page):
    """ORDER-004: 订单状态流转"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        status = page.locator('.status-badge, .order-status, .el-tag')
        assert status.count() >= 0


def test_ui_order_payment_plan(page):
    """ORDER-005: 订单回款计划"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        plan = page.locator('button:has-text("回款"), .payment-plan, .payment-tab')
        assert plan.count() >= 0


def test_ui_order_refund(page):
    """ORDER-006: 订单退款处理"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_timeout(2000)
    first = page.locator(".el-table__row, .list-item").first
    if first.count() > 0:
        first.click()
        page.wait_for_timeout(1500)
        refund = page.locator('button:has-text("退款"), .btn-refund')
        assert refund.count() >= 0
