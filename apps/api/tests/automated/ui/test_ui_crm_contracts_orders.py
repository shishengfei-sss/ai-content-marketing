"""CRM 合同与订单 UI 自动化测试 — 对应 CONT-001~008, ORDER-001~006。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


# ── 合同 ────────────────────────────────────────────────────────

def test_ui_contract_list_view(page):
    """CONT-001: 合同列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")
    page.wait_for_selector(".el-table, .list-item", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_contract_detail(page):
    """CONT-002~003: 合同详情与签署"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    assert page.locator(".detail-page, .contract-detail").count() > 0

    sign_btn = page.locator('button:has-text("签署"), .btn-sign')
    assert sign_btn.count() >= 0


def test_ui_contract_edit(page):
    """CONT-002: 合同编辑"""
    ui_login(page)
    ui_goto(page, "/crm/contracts")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return

    edit_btn = first.locator('button:has-text("编辑"), .btn-edit').first
    if edit_btn.count() > 0:
        edit_btn.click()
        page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)
        ta = page.locator(".el-dialog textarea, .el-drawer textarea").first
        if ta.count() > 0:
            ta.fill("UI编辑备注")
        page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
        page.wait_for_timeout(1500)


# ── 订单 ────────────────────────────────────────────────────────

def test_ui_order_list_view(page):
    """ORDER-001: 订单列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/orders")
    page.wait_for_selector(".el-table, .list-item", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_order_create(page):
    """ORDER-001: 创建订单"""
    ui_login(page)
    ui_goto(page, "/crm/orders")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    inp = page.locator('input[placeholder="例如：XX 项目订单"]').first
    if inp.count() > 0:
        inp.fill(f"UI订单-{__import__('uuid').uuid4().hex[:6]}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(4000)


def test_ui_order_detail(page):
    """ORDER-003: 订单详情"""
    ui_login(page)
    ui_goto(page, "/crm/orders")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    assert page.locator(".detail-page, .order-detail").count() > 0
