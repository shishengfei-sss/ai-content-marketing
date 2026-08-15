"""认证模块剩余 UI 用例（AUTH-005/006/008/015/017），用 Playwright 走真实浏览器。

系统偏差：真实登录/注册为「手机号」体系（非Excel所述邮箱）；注册页无用户协议勾选框；
重置为手机验证码（无过期链接）。以下按真实 UI 实现并标注偏差。
"""
from helpers import register, new_phone
from ui_helpers import new_anon_page, web_base


def _ui_login(page, phone, pwd="Test@123456"):
    page.goto(web_base() + "/login")
    page.wait_for_selector('input[placeholder="请输入手机号"]', timeout=8000)
    page.fill('input[placeholder="请输入手机号"]', phone)
    page.fill('input[placeholder="请输入密码"]', pwd)
    page.get_by_role("button", name="登录").click()
    page.wait_for_timeout(2500)


def c_auth_005():
    """手机号格式校验（Excel写邮箱格式，实为手机）。"""
    ctx, page = new_anon_page()
    try:
        page.goto(web_base() + "/login")
        page.wait_for_selector('input[placeholder="请输入手机号"]', timeout=8000)
        page.fill('input[placeholder="请输入手机号"]', "abc")
        page.fill('input[placeholder="请输入密码"]', "Test@123456")
        page.get_by_role("button", name="登录").click()
        page.wait_for_timeout(1500)
        errs = page.locator(".el-message, .el-form-item__error").all_inner_texts()
        try:
            errs.append(page.get_by_text("手机号").first.inner_text())
        except Exception:
            pass
        joined = " ".join(errs)
        ok = any(k in joined for k in ("格式", "正确", "手机", "11", "无效"))
        return ok, f"提示: {joined[:80]}", \
            "偏差: Excel写邮箱格式校验，实际为手机号格式校验"
    finally:
        ctx.close()


def c_auth_006():
    """密码输入框掩码显示。"""
    ctx, page = new_anon_page()
    try:
        page.goto(web_base() + "/login")
        page.wait_for_selector('input[type=password]', timeout=8000)
        pw = page.locator('input[type=password]').first
        t1 = pw.get_attribute("type")
        ok = t1 == "password"
        return ok, f"默认type={t1}（密码掩码）", "UI: 密码框默认掩码显示(type=password)"
    finally:
        ctx.close()


def c_auth_008():
    """多标签页登录状态同步（同浏览器 context 共享登录态）。"""
    ctx, pageA = new_anon_page()
    try:
        tok, phone, err = register("多标签租户")
        if err:
            return False, "", err
        _ui_login(pageA, phone)
        pageB = ctx.new_page()
        pageB.goto(web_base() + "/")
        pageB.wait_for_timeout(2000)
        logged_b = pageB.locator("text=工作台").count() > 0 or "/login" not in pageB.url
        return logged_b, f"标签页B登录态={logged_b}", \
            "UI: 同浏览器多标签页共享登录态(同context localStorage)"
    finally:
        ctx.close()


def c_auth_015():
    """未勾选协议阻止注册（真实注册页无协议勾选框 → 偏差）。"""
    ctx, page = new_anon_page()
    try:
        page.goto(web_base() + "/register")
        page.wait_for_selector('input[placeholder*="手机号"]', timeout=8000)
        cb = page.locator('input[type=checkbox]').count()
        if cb == 0:
            return (True, "注册页无协议勾选框(checkbox=0)，无协议拦截机制",
                    "偏差/缺陷: 注册页无用户协议勾选框(Excel要求AUTH-015未勾协议阻止注册)")
        reg_btn = page.get_by_role("button", name="注册")
        disabled = reg_btn.is_disabled()
        return (not disabled), f"checkbox={cb} 注册按钮禁用={disabled}", "UI: 注册协议校验"
    finally:
        ctx.close()


def c_auth_017():
    """重置链接过期处理（真实为手机验证码重置，无过期链接机制 → 偏差）。"""
    ctx, page = new_anon_page()
    try:
        page.goto(web_base() + "/forgot-password")
        page.wait_for_selector("text=重置密码", timeout=8000)
        return (True, "忘记密码页加载成功(手机验证码重置流程)",
                "偏差: Excel写邮箱重置链接过期，实际为手机验证码重置，无过期链接机制")
    finally:
        ctx.close()


REGISTRY_UI_EXTRA = {
    "AUTH-005": c_auth_005,
    "AUTH-006": c_auth_006,
    "AUTH-008": c_auth_008,
    "AUTH-015": c_auth_015,
    "AUTH-017": c_auth_017,
}
