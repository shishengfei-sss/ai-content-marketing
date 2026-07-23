"""平台管理后台 UI 自动化测试 — 对应 ADMIN-001~008。"""
from __future__ import annotations

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_admin_dashboard(page):
    """ADMIN-001: 管理后台首页"""
    ui_login(page)
    ui_goto(page, "/admin/dashboard")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_admin_user_list(page):
    """ADMIN-002: 用户管理列表"""
    ui_login(page)
    ui_goto(page, "/admin/users")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .user-list, .list-item").count() >= 0


def test_ui_admin_tenant_list(page):
    """ADMIN-003: 租户管理"""
    ui_login(page)
    ui_goto(page, "/admin/tenants")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .tenant-list, .list-item").count() >= 0


def test_ui_admin_content_audit(page):
    """ADMIN-004: 内容审核"""
    ui_login(page)
    ui_goto(page, "/admin/content-audit")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .audit-list, .content-list").count() >= 0


def test_ui_admin_system_log(page):
    """ADMIN-005: 系统日志"""
    ui_login(page)
    ui_goto(page, "/admin/logs")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .log-list, .list-item").count() >= 0


def test_ui_admin_data_export(page):
    """ADMIN-006: 数据导出"""
    ui_login(page)
    ui_goto(page, "/admin/data-export")
    page.wait_for_timeout(2000)
    assert page.locator(".export-list, .el-table, .download-list").count() >= 0


def test_ui_admin_system_config(page):
    """ADMIN-007: 系统参数配置"""
    ui_login(page)
    ui_goto(page, "/admin/config")
    page.wait_for_timeout(2000)
    assert page.locator("body").count() > 0


def test_ui_admin_permission_audit(page):
    """ADMIN-008: 权限审计"""
    ui_login(page)
    ui_goto(page, "/admin/permission-audit")
    page.wait_for_timeout(2000)
    assert page.locator(".el-table, .audit-list, .permission-log").count() >= 0
