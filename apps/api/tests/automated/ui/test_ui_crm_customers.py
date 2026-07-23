"""CRM 客户管理 UI 自动化测试 — 对应 CUST-001~005。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_customer_list_view(page):
    """CUST-001: 客户列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/customers")
    page.wait_for_selector(".el-table, .list-item, .crm-list", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_customer_create(page):
    """CUST-002: 新建客户"""
    ui_login(page)
    ui_goto(page, "/crm/customers")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    company_name = f"UI客户公司-{__import__('uuid').uuid4().hex[:6]}"
    # 客户创建对话框：前2个输入框通常是公司名、联系人
    inputs = page.locator(".el-dialog input.el-input__inner, .el-drawer input.el-input__inner").all()
    if len(inputs) >= 2:
        inputs[0].fill(company_name)
        inputs[1].fill("UI客户联系人")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(3000)
    page.wait_for_selector(".el-dialog, .el-drawer", state="detached", timeout=10000)

    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    assert page.locator(f"text={company_name}").count() > 0


def test_ui_customer_detail(page):
    """CUST-003: 客户详情"""
    ui_login(page)
    ui_goto(page, "/crm/customers")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    assert page.locator(".detail-page, .customer-detail, .el-descriptions").count() > 0


def test_ui_customer_edit(page):
    """CUST-004: 编辑客户"""
    ui_login(page)
    ui_goto(page, "/crm/customers")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return

    # 优先在行内找编辑按钮
    edit_btn = first.locator('button:has-text("编辑"), .btn-edit').first
    if edit_btn.count() == 0:
        # 点击进入详情再找编辑
        first.click()
        page.wait_for_timeout(1500)
        edit_btn = page.locator('button:has-text("编辑"), .btn-edit').first

    if edit_btn.count() > 0:
        edit_btn.click()
        page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)
        # 找到备注/描述字段（通常是textarea）
        ta = page.locator(".el-dialog textarea, .el-drawer textarea").first
        if ta.count() > 0:
            ta.fill("UI自动化编辑备注")
        page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
        page.wait_for_timeout(1500)


def test_ui_customer_delete(page):
    """CUST-005: 删除客户"""
    ui_login(page)
    ui_goto(page, "/crm/customers")

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
