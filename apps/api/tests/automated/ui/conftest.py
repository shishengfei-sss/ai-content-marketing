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


def _launch_chromium(playwright):
    return playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])


@pytest.fixture(scope="session")
def _browser():
    """会话级浏览器；中途崩溃则在 page fixture 里重拉。

    禁止 ``taskkill /IM chrome-headless-shell.exe``：会误杀同机其它 Playwright。
    """
    import threading

    playwright = sync_playwright().start()
    state = {"browser": _launch_chromium(playwright)}

    def ensure(force: bool = False):
        browser = state["browser"]
        if force or browser is None or not browser.is_connected():
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            state["browser"] = _launch_chromium(playwright)
        return state["browser"]

    state["ensure"] = ensure
    try:
        yield state
    finally:
        def _close():
            try:
                b = state.get("browser")
                if b is not None:
                    b.close()
            except Exception:
                pass
            try:
                playwright.stop()
            except Exception:
                pass

        t = threading.Thread(target=_close, daemon=True)
        t.start()
        t.join(timeout=8)


def _new_page(browser_state, **context_kwargs):
    browser = browser_state["ensure"]()
    try:
        context = browser.new_context(**context_kwargs)
    except Exception:
        browser = browser_state["ensure"](force=True)
        context = browser.new_context(**context_kwargs)
    pg = context.new_page()
    pg.set_default_timeout(15000)
    return context, pg


@pytest.fixture
def page(_browser):
    """每个用例独立 context/page。"""
    context, pg = _new_page(_browser, viewport={"width": 1280, "height": 900})
    try:
        yield pg
    finally:
        try:
            context.close()
        except Exception:
            pass


@pytest.fixture
def mobile_page(_browser):
    """模拟移动端 viewport。"""
    context, pg = _new_page(
        _browser,
        viewport={"width": 375, "height": 812},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    )
    try:
        yield pg
    finally:
        try:
            context.close()
        except Exception:
            pass


# ── 公共工具 ────────────────────────────────────────────────────

def ui_login(page, phone: str = ADMIN_PHONE, password: str = ADMIN_PASSWORD) -> None:
    """通过 UI 登录到工作台。"""
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(500)

    # 默认密码登录；若界面是验证码模式再切回
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()

    page.get_by_placeholder("请输入手机号").fill(phone)
    page.get_by_placeholder("请输入密码").fill(password)
    page.click('button:has-text("登录")')

    # 等待登录成功跳转（工作台 / 选租户 / 商城页）
    page.wait_for_url(
        lambda url: (
            "/login" not in url
            and (
                "/dashboard" in url
                or "/select-tenant" in url
                or "/shop/" in url
            )
        ),
        timeout=20000,
    )

    # 如果有租户选择，选第一个
    if "/select-tenant" in page.url:
        page.wait_for_selector(".tenant-item, .el-card, .tenant-card", timeout=10000)
        first_tenant = page.locator(".tenant-item, .tenant-card").first
        if first_tenant.count() > 0:
            first_tenant.click()
            page.wait_for_url(
                lambda url: "/dashboard" in url or "/shop/" in url,
                timeout=10000,
            )

    page.wait_for_timeout(500)


def ui_wait_ready(page, timeout: int = 8000) -> None:
    """等 Element Plus loading 遮罩消失，避免挡住工具栏点击。"""
    try:
        page.locator(".el-loading-mask").first.wait_for(state="hidden", timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(200)


def ui_goto(page, path: str) -> None:
    """导航到指定路径，确保页面加载完成。"""
    page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    ui_wait_ready(page)


def screenshot_on_failure(page, name: str) -> None:
    """失败后截图。"""
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=path, full_page=True)
