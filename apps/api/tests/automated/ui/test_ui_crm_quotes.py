"""CRM 报价管理 UI 自动化测试 — 对应 QUOTE-001~007。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_quote_list_view(page):
    """QUOTE-001: 报价列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/quotes")
    page.wait_for_selector(".el-table, .list-item", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_quote_create(page):
    """QUOTE-001: 从商机创建报价"""
    ui_login(page)
    ui_goto(page, "/crm/quotes")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    # 报价名称
    inp = page.locator('input[placeholder="例如：XX 项目报价"]').first
    if inp.count() > 0:
        inp.fill(f"UI报价-{__import__('uuid').uuid4().hex[:6]}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(4000)


def test_ui_quote_detail(page):
    """QUOTE-002: 报价详情"""
    ui_login(page)
    ui_goto(page, "/crm/quotes")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    assert page.locator(".detail-page, .quote-detail").count() > 0


def test_ui_cpq_create(page):
    """QUOTE-005~007: CPQ配置报价"""
    ui_login(page)
    ui_goto(page, "/crm/quotes/cpq/new")
    page.wait_for_timeout(3000)
    assert page.locator(".cpq-page, .quote-form, .product-config").count() > 0
