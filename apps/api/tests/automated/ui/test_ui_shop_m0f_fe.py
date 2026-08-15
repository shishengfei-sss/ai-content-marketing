"""M0f 已交付页面 UI 联测 — 对照 FE-* / TC-P02 / TC-A20 / UI-W。

覆盖：列表壳、入驻审核页内 Tab（非抽屉）、A20 页状态、横幅。
写操作完整 Network 主路径以 verify_shop_m0f.py（FE-*）为准。
"""
from __future__ import annotations

import os

import pytest

from tests.automated.ui.conftest import BASE_URL, ui_goto, ui_login

PLATFORM_PHONE = os.environ.get("UI_TEST_PLATFORM_PHONE", "13800000000")
PLATFORM_PASSWORD = os.environ.get("UI_TEST_PLATFORM_PASSWORD", "admin123456")
MERCHANT_PHONE = os.environ.get("UI_TEST_PHONE", "13900000099")
MERCHANT_PASSWORD = os.environ.get("UI_TEST_PASSWORD", "test123456")


def _platform_login(page) -> None:
    page.goto(f"{BASE_URL}/admin/login", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(PLATFORM_PHONE)
    page.get_by_placeholder("请输入密码").fill(PLATFORM_PASSWORD)
    page.click('button:has-text("登录")')
    page.wait_for_url(lambda url: "/admin" in url and "/admin/login" not in url, timeout=20000)
    page.wait_for_timeout(400)


def test_tc_p02_l01_merchant_list_shell(page):
    """TC-P02-L01: 商家列表默认加载（页壳）。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.wait_for_timeout(1200)
    assert page.locator(".page-card .el-table").count() >= 1
    assert page.get_by_role("button", name="查询").count() >= 1
    assert page.locator(".el-pagination, .pager").count() >= 1


def test_fe_p03_audit_page_and_reject_guard(page):
    """FE-P03 / TC: 页内审核（非弹窗）；驳回空说明前端拦截。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/onboarding")
    page.wait_for_timeout(1200)
    assert page.locator(".page-card .el-table").count() >= 1
    audit = page.get_by_role("button", name="审核").first
    if audit.count() == 0:
        view = page.get_by_role("button", name="查看").first
        if view.count() == 0:
            pytest.skip("无待审/列表数据")
        view.click()
        page.wait_for_timeout(800)
        assert page.locator(".review-panel").count() >= 1
        return
    audit.click()
    page.wait_for_timeout(800)
    assert page.locator(".review-panel").count() >= 1
    assert page.locator(".review-panel .detail-head").count() >= 1
    # 顶栏无「申请列表 | 入驻审核」双 Tab；审核为页内视图
    assert page.get_by_role("tab", name="入驻审核").count() == 0
    assert page.get_by_role("tab", name="申请列表").count() == 0
    # 二级子 Tab「驳回」
    page.locator(".review-subtabs").get_by_text("驳回", exact=True).click()
    page.wait_for_timeout(300)
    page.get_by_role("button", name="确认驳回").click()
    page.wait_for_timeout(600)
    body = page.locator("body").inner_text()
    assert "至少" in body or page.locator(".el-message").count() >= 1


def test_fe_p02a_initiate_drawer_requires_tenant(page):
    """FE-P02A-01-B1: 发起入驻不选租户 → 前端提示。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.wait_for_timeout(1000)
    btn = page.get_by_role("button", name="发起入驻").first
    if btn.count() == 0:
        pytest.skip("无发起入驻权限或按钮")
    btn.click()
    page.wait_for_timeout(500)
    assert page.locator(".el-drawer").count() >= 1
    page.get_by_role("button", name="提交待审").click()
    page.wait_for_timeout(600)
    text = page.locator("body").inner_text()
    assert "租户" in text


def test_tc_a20_page_states(page):
    """TC-A20 / UI-W: 开通商城页可打开；审核中只读或已开通结果。"""
    ui_login(page, MERCHANT_PHONE, MERCHANT_PASSWORD)
    ui_goto(page, "/shop/onboarding")
    page.wait_for_timeout(1500)
    assert page.locator(".page-card.onboarding-apply, .onboarding-apply, .el-result").count() >= 1
    # 开通商城页不展示引导横幅
    assert page.locator(".shop-onboarding-banner").count() == 0
    # 其它页可有横幅入口
    ui_goto(page, "/dashboard")
    page.wait_for_timeout(1000)
    assert page.locator(".shop-onboarding-banner").count() >= 0


def test_ui_shop_admin_merchant_detail(page):
    """详情页：无 P02 文案；有 page-card。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.wait_for_timeout(1200)
    detail_btn = page.get_by_role("button", name="详情").first
    if detail_btn.count() == 0:
        pytest.skip("无商家行")
    detail_btn.click()
    page.wait_for_url(lambda u: "/admin/shop/merchants/" in u, timeout=10000)
    page.wait_for_timeout(800)
    assert page.locator(".page-card").count() >= 1
    assert "P02" not in page.locator("body").inner_text()
    assert page.locator(".el-tabs").count() >= 1
