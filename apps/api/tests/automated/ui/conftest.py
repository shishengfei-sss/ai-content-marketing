"""UI 自动化测试公共 fixture（Playwright）。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# 前端地址
BASE_URL = os.environ.get("UI_TEST_BASE_URL", "http://localhost:5173")
# 测试账号
ADMIN_PHONE = os.environ.get("UI_TEST_PHONE", "13900000099")
ADMIN_PASSWORD = os.environ.get("UI_TEST_PASSWORD", "test123456")

SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.set_default_timeout(15000)
    yield page
    page.close()


@pytest.fixture
def mobile_page(browser):
    """模拟移动端 viewport。"""
    page = browser.new_page(
        viewport={"width": 375, "height": 812},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    )
    page.set_default_timeout(15000)
    yield page
    page.close()


# ── 公共工具 ────────────────────────────────────────────────────

def ui_login(page, phone: str = ADMIN_PHONE, password: str = ADMIN_PASSWORD) -> None:
    """通过 UI 登录到工作台。"""
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # 密码登录模式
    password_tab = page.locator("text=密码登录")
    if password_tab.count() > 0:
        password_tab.click()

    page.fill('input[placeholder*="手机"], input[name="phone"], input[type="text"]', phone)
    page.fill('input[placeholder*="密码"], input[name="password"], input[type="password"]', password)

    # Element Plus 按钮
    page.click('button:has-text("登录")')

    # 等待登录成功跳转（dashboard 或 select-tenant）
    page.wait_for_url(lambda url: "/dashboard" in url or "/select-tenant" in url, timeout=15000)

    # 如果有租户选择，选第一个
    if "/select-tenant" in page.url:
        page.wait_for_selector(".tenant-item, .el-card, .tenant-card", timeout=10000)
        first_tenant = page.locator(".tenant-item, .tenant-card").first
        if first_tenant.count() > 0:
            first_tenant.click()
            page.wait_for_url(lambda url: "/dashboard" in url, timeout=10000)

    page.wait_for_load_state("networkidle")


def ui_goto(page, path: str) -> None:
    """导航到指定路径，确保页面加载完成。"""
    page.goto(f"{BASE_URL}{path}")
    page.wait_for_load_state("networkidle")


def screenshot_on_failure(page, name: str) -> None:
    """失败后截图。"""
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=path, full_page=True)
