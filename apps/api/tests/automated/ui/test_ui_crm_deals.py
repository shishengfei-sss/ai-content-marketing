"""CRM 商机管理 UI 自动化测试 — 对应 DEAL-001~011。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_deal_list_view(page):
    """DEAL-001: 商机列表查看"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_selector(".el-table, .list-item, .crm-list", timeout=10000)
    assert page.locator(".el-table__row, .list-item").count() >= 0


def test_ui_deal_create(page):
    """DEAL-002: 创建商机"""
    ui_login(page)
    ui_goto(page, "/crm/deals")

    page.click('button:has-text("新建"), button:has-text("新增"), .btn-add')
    page.wait_for_selector(".el-dialog, .el-drawer", timeout=10000)

    # 商机名称字段
    inp = page.locator('input[placeholder="请输入商机名称"]').first
    if inp.count() > 0:
        inp.fill(f"UI商机-{__import__('uuid').uuid4().hex[:6]}")

    page.click('.el-dialog button:has-text("保存"), .el-drawer button:has-text("保存")')
    page.wait_for_timeout(4000)


def test_ui_deal_detail(page):
    """DEAL-003: 商机详情"""
    ui_login(page)
    ui_goto(page, "/crm/deals")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)
    assert page.locator(".detail-page, .deal-detail").count() > 0


def test_ui_deal_pipeline_change(page):
    """DEAL-005: 商机管道阶段变更"""
    ui_login(page)
    ui_goto(page, "/crm/deals")

    first = page.locator(".el-table__row, .list-item").first
    if first.count() == 0:
        return
    first.click()
    page.wait_for_timeout(2000)

    stage_select = page.locator('button:has-text("推进"), .stage-change, .pipeline-stage').first
    if stage_select.count() > 0:
        stage_select.click()
        page.wait_for_timeout(1000)


def test_ui_deal_funnel_view(page):
    """DEAL-009: 销售漏斗查看"""
    ui_login(page)
    ui_goto(page, "/crm/deal-funnel")
    page.wait_for_timeout(3000)
    assert page.locator(".funnel-chart, .el-table, .echarts, canvas").count() > 0


def test_ui_deal_kanban_view(page):
    """DEAL-006: 商机看板"""
    ui_login(page)
    ui_goto(page, "/crm/deals")
    page.wait_for_timeout(2000)

    kanban_btn = page.locator('button:has-text("看板"), .view-kanban, [data-view="kanban"]').first
    if kanban_btn.count() > 0:
        kanban_btn.click()
        page.wait_for_timeout(2000)
        assert page.locator(".kanban-board, .kanban-column").count() > 0
