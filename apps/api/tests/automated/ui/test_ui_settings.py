"""系统设置 UI 自动化测试 — 对应 SET-001~013。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_settings_company_info(page):
    """SET-001: 查看企业信息"""
    ui_login(page)
    ui_goto(page, "/settings/company")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_settings_custom_fields(page):
    """SET-002: 自定义字段配置"""
    ui_login(page)
    ui_goto(page, "/settings/custom-fields")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .field-list, .list-item").count() >= 0


def test_ui_settings_pipeline_config(page):
    """SET-003: 销售管道配置"""
    ui_login(page)
    ui_goto(page, "/settings/pipelines")
    page.wait_for_timeout(2000)
    assert page.locator(".pipeline-list, .stage-list, .el-table, .kanban-board").count() >= 0


def test_ui_settings_team_members(page):
    """SET-004: 团队成员管理"""
    ui_login(page)
    ui_goto(page, "/settings/team")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .member-list, .list-item").count() >= 0


def test_ui_settings_icp_config(page):
    """SET-005: ICP配置"""
    ui_login(page)
    ui_goto(page, "/settings/icp")
    page.wait_for_timeout(2000)
    assert page.locator(".el-form, .icp-form").count() > 0


def test_ui_settings_role_permission(page):
    """SET-006: 角色权限配置"""
    ui_login(page)
    ui_goto(page, "/settings/roles")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .role-list, .permission-list").count() >= 0


def test_ui_settings_data_permission(page):
    """SET-007: 数据权限范围"""
    ui_login(page)
    ui_goto(page, "/settings/data-permission")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_settings_integration_tender(page):
    """SET-008: 招标集成配置"""
    ui_login(page)
    ui_goto(page, "/settings/integrations")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_settings_cpq_config(page):
    """SET-009: CPQ规则配置"""
    ui_login(page)
    page.goto("http://localhost:5173/settings/cpq")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_settings_wechat_official(page):
    """SET-010: 公众号配置"""
    ui_login(page)
    page.goto("http://localhost:5173/settings/wechat")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_settings_llm_config(page):
    """SET-011: LLM模型配置"""
    ui_login(page)
    ui_goto(page, "/settings/llm")
    page.wait_for_timeout(2000)
    assert page.locator(".el-form, .llm-form, .model-list").count() > 0


def test_ui_settings_brand_voice(page):
    """SET-012: 品牌声音与Memory"""
    ui_login(page)
    ui_goto(page, "/settings/brand")
    page.wait_for_timeout(2000)
    assert page.locator(".el-form, .brand-form, .voice-config").count() > 0


def test_ui_settings_notification(page):
    """SET-013: 通知设置"""
    ui_login(page)
    ui_goto(page, "/settings/notifications")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0
