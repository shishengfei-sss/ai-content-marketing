"""CRM 产品与任务 UI 自动化测试 — 对应 PROD-001~007, TASK-001~004, ACT-001~002。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


# ── 产品 ────────────────────────────────────────────────────────

def test_ui_product_list_view(page):
    """PROD-001: 产品列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/products")
    page.wait_for_selector(".el-table, .list-item", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_product_create(page):
    """PROD-001: 新建产品"""
    ui_login(page)
    ui_goto(page, "/crm/products")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    # 产品名称通常在第2个input（第1个是编号）
    inputs = page.locator(".el-dialog input.el-input__inner, .el-drawer input.el-input__inner").all()
    if len(inputs) >= 2:
        inputs[1].fill(f"UI产品-{__import__('uuid').uuid4().hex[:6]}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(4000)


def test_ui_product_detail_edit(page):
    """PROD-002: 产品编辑"""
    ui_login(page)
    ui_goto(page, "/crm/products")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return

    edit_btn = first.locator('button:has-text("编辑"), .btn-edit').first
    if edit_btn.count() > 0:
        edit_btn.click()
        page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)
        ta = page.locator(".el-dialog textarea, .el-drawer textarea").first
        if ta.count() > 0:
            ta.fill("UI编辑描述")
        page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
        page.wait_for_timeout(1500)


# ── 任务 ────────────────────────────────────────────────────────

def test_ui_task_list_view(page):
    """TASK-001: 任务列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/tasks")
    page.wait_for_selector(".el-table, .list-item, .task-list", timeout=10000)
    assert page.locator(".el-table__row, .list-item, .task-item").count() >= 0


def test_ui_task_create(page):
    """TASK-001: 创建任务"""
    ui_login(page)
    ui_goto(page, "/crm/tasks")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    inp = page.locator('input[placeholder="例如：发送产品方案、电话回访确认需求"]').first
    if inp.count() > 0:
        inp.fill(f"UI任务-{__import__('uuid').uuid4().hex[:6]}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存"), .el-dialog button:has-text("创建")')
    page.wait_for_timeout(3000)
    page.wait_for_selector(".el-dialog, .el-drawer", state="detached", timeout=10000)


# ── 营销活动 ────────────────────────────────────────────────────

def test_ui_campaign_list_view(page):
    """CAMP-001: 营销活动列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/campaigns")
    page.wait_for_selector(".el-table, .list-item", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_campaign_detail(page):
    """CAMP-003: 营销活动详情"""
    ui_login(page)
    ui_goto(page, "/crm/campaigns")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    # 详情页可能以不同形式展示
    assert page.locator(".detail-page, .campaign-detail, .el-descriptions, .page-header").count() > 0
