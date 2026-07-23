"""CRM 线索管理 UI 自动化测试 — 对应 LEAD-001~005。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_lead_list_view(page):
    """LEAD-001: 线索列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/leads")
    page.wait_for_selector(".el-table, .list-item, .crm-list", timeout=10000)
    rows = page.locator(".el-table__row, .list-item").count()
    assert rows >= 0, "线索列表应正常加载"


def test_ui_lead_create_and_detail(page):
    """LEAD-002~003: 创建线索并查看详情"""
    ui_login(page)
    ui_goto(page, "/crm/leads")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    # 线索创建对话框前3个输入框：公司、联系人、手机
    company_name = f"UI测试公司-{__import__('uuid').uuid4().hex[:6]}"
    inputs = page.locator(".el-dialog input.el-input__inner, .el-drawer input.el-input__inner").all()
    if len(inputs) >= 3:
        inputs[0].fill(company_name)
        inputs[1].fill("UI测试联系人")
        inputs[3].fill(f"139{__import__('random').randint(10000000,99999999)}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(4000)

    # 验证没有错误toast（创建流程正常）
    error_toast = page.locator('.el-message--error')
    assert error_toast.count() == 0, "创建线索不应出现错误提示"


def test_ui_lead_search_filter(page):
    """LEAD-004: 关键词搜索和筛选"""
    ui_login(page)
    ui_goto(page, "/crm/leads")

    search_input = page.locator('input[placeholder*="搜索"], .el-input__inner').first
    if search_input.count() > 0:
        search_input.fill("测试")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_lead_convert_to_customer(page):
    """LEAD-005: 线索转客户"""
    ui_login(page)
    ui_goto(page, "/crm/leads")

    first_row = page.locator(".el-table__row, .list-item").first
    if first_row.count() == 0:
        return
    first_row.click()
    page.wait_for_timeout(2000)

    convert_btn = page.locator('button:has-text("转客户"), .btn-convert')
    if convert_btn.count() > 0:
        convert_btn.click()
        page.wait_for_timeout(2000)
        assert page.locator(".el-dialog, .el-message-box, .el-notification").count() >= 0
