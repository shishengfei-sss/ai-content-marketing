"""商家控制台 UI 自动化测试 — 对应 SHOP-MCH-001~005。"""
from __future__ import annotations

import pytest

from tests.automated.ui.conftest import ui_login, ui_goto


def test_ui_shop_merchant_console_home(page):
    """SHOP-MCH-001 / A01: 交易看板。对照 #a01。"""
    ui_login(page)
    ui_goto(page, "/shop/overview")
    page.get_by_role("heading", name="交易看板").wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "成交额" in body
    assert "待核销" in body
    assert "最近订单" in body
    assert page.locator('[data-testid="shop-dashboard-container"]').count() >= 1
    assert page.get_by_text("今日").count() >= 1
    assert page.get_by_text("近7日").count() >= 1
    assert page.get_by_text("近30日").count() >= 1
    page.get_by_text("近7日").first.click()
    page.wait_for_timeout(800)
    assert page.locator('[data-testid="chart-revenue-trend"]').count() >= 1
    page.locator('[data-testid="shop-current-store"]').wait_for(timeout=15000)
    chrome = page.locator('[data-testid="shop-current-store"]').inner_text()
    assert "当前店铺" in chrome


def test_ui_shop_merchant_onboarding_a20(page):
    """SHOP-MCH-M0f / TC-A20: A20 开通商城入驻页。"""
    ui_login(page)
    ui_goto(page, "/shop/onboarding")
    page.wait_for_timeout(1500)
    assert page.locator(".page-card.onboarding-apply, .onboarding-apply, .el-result, .el-alert").count() >= 1


def test_ui_shop_merchant_channel_settings(page):
    """SHOP-MCH-A23 / TC-A23-F01: 公域对接设置。对照 #a23。"""
    ui_login(page)
    ui_goto(page, "/shop/channel-settings")
    page.wait_for_timeout(1500)
    body = page.locator("body").inner_text()
    assert "公域对接" in body
    assert "选链路" in body or "成交链路" in body
    assert "路径 A" in body
    assert "外部店铺 ID" in body
    assert page.get_by_text("保存绑店").count() >= 1
    assert page.get_by_text("发送测试").count() >= 1
    assert page.get_by_text("保存对接设置").count() >= 1
    assert page.get_by_placeholder("请填写外部店铺 ID").count() >= 1


def test_ui_shop_merchant_subscription_a18(page):
    """SHOP-MCH-A18: 套餐信息。对照 #a18。"""
    ui_login(page)
    ui_goto(page, "/shop/subscription")
    page.get_by_text("套餐信息").first.wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "合并后可用额度" in body or "主套餐" in body or "怎么用您的套餐" in body
    assert page.get_by_text("申请升级 / 加购").count() >= 1 or "申请升级" in body


def test_ui_shop_merchant_shop_settings(page):
    """SHOP-MCH-002 / A19: 单店设置。对照 #a19。"""
    ui_login(page)
    ui_goto(page, "/shop/store-settings")
    page.get_by_role("heading", name="单店设置").wait_for(timeout=15000)
    assert page.get_by_text("本店展示").count() >= 1
    assert page.get_by_text("店铺名称（对外）").count() >= 1
    assert page.get_by_text("保存本店展示").count() >= 1
    page.get_by_role("tab", name="退款默认").click()
    page.wait_for_timeout(400)
    assert page.get_by_text("保存退款默认").count() >= 1
    assert page.get_by_text("随时可退").count() >= 1


def test_ui_shop_merchant_settings_hub(page):
    """SHOP-MCH-ASET: 设置中心。对照 #a-settings。"""
    ui_login(page)
    ui_goto(page, "/shop/settings")
    page.get_by_role("heading", name="设置").wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "支付与进件" in body
    assert "单店设置" in body
    assert "角色与成员" in body or "套餐信息" in body
    assert page.get_by_text("我的账号").count() >= 1


def test_ui_shop_merchant_payment_a15(page):
    """SHOP-MCH-A15: 支付与进件。对照 #a15。"""
    ui_login(page)
    ui_goto(page, "/shop/payment")
    page.get_by_role("heading", name="支付与进件").wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "商家做什么" in body or "进件材料" in body
    assert "证书" in body or "回调" in body
    assert page.get_by_text("支付与进件").count() >= 1
    # 状态矩阵按钮：未提交/驳回可见提交；已开通可见测试
    has_submit = page.get_by_text("提交进件材料").count() >= 1 or page.get_by_text("补充材料").count() >= 1
    has_test = page.get_by_text("测试 0.01 元").count() >= 1
    has_view = page.get_by_text("查看进件材料").count() >= 1
    assert has_submit or has_test or has_view, body[:600]


def test_ui_shop_merchant_sms_a15s(page):
    """SHOP-MCH-A15S: 短信与领权。对照 #a15-sms。"""
    ui_login(page)
    ui_goto(page, "/shop/sms-settings")
    page.get_by_role("heading", name="短信与领权").wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "短信签名" in body
    assert "领权过期天数" in body or "领权链接域名" in body
    assert page.get_by_text("保存领权参数").count() >= 1
    assert page.get_by_text("短信 / 领权").count() >= 1


def test_ui_shop_merchant_buyers(page):
    """SHOP-MCH-A11: 买家列表完备。对照 #a11 / #a11-select-spec。"""
    ui_login(page)
    ui_goto(page, "/shop/buyers")
    page.locator('[data-testid="shop-buyers"]').wait_for(timeout=15000)
    root = page.locator('[data-testid="shop-buyers"]')
    body = root.inner_text()
    for col in (
        "手机",
        "昵称",
        "账号状态",
        "来源店铺",
        "订单数",
        "权益数",
        "累计消费",
        "注册渠道",
        "最近下单",
        "注册时间",
    ):
        assert col in body, col
    assert "全部买家" in body
    assert "近 7 日新注册" in body
    assert "有权益" in body
    assert "已封禁" in body
    assert page.get_by_placeholder("手机 / 昵称").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    page.get_by_text("高级筛选").first.click()
    page.wait_for_timeout(300)
    assert page.get_by_placeholder("订单数 ≥").count() >= 1
    assert page.get_by_placeholder("权益数 ≥").count() >= 1
    assert page.get_by_placeholder("注册起").count() >= 1
    assert page.get_by_placeholder("最近下单起").count() >= 1
    page.get_by_text("列设置").first.click()
    page.wait_for_timeout(300)
    dlg = page.locator(".el-dialog").last
    dlg_text = dlg.inner_text()
    assert "首单时间" in dlg_text
    assert "buyer_id（技术）" in dlg_text
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("选中行").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    chrome = page.locator("body").inner_text()
    assert "同步到 CRM" not in chrome
    assert "升级为客户" not in chrome


def test_ui_shop_merchant_buyer_detail(page):
    """SHOP-MCH-A11A: 买家详情五 Tab 默认列。对照 #a11a。"""
    ui_login(page)
    ui_goto(page, "/shop/buyers")
    page.locator('[data-testid="shop-buyers"]').wait_for(timeout=15000)
    detail_btn = page.locator('[data-testid="shop-buyers"] button:has-text("详情")').first
    if detail_btn.count() == 0:
        pytest.skip("无买家行，跳过详情列断言")
    detail_btn.click()
    page.locator('[data-testid="shop-buyer-detail"]').wait_for(timeout=15000)
    root = page.locator('[data-testid="shop-buyer-detail"]')
    body = root.inner_text()
    for name in ("订单", "权益", "预约", "开票", "学习进度"):
        assert name in body, name
    assert "来源店铺" in body
    for col in ("单号", "商品", "店铺", "渠道", "金额", "状态", "下单时间", "操作"):
        assert col in body, col
    page.get_by_role("tab", name="权益").click()
    page.wait_for_timeout(400)
    ents = root.inner_text()
    for col in ("商品", "类型", "店铺", "状态", "次数", "来源订单", "开通时间", "到期"):
        assert col in ents, col
    page.get_by_role("tab", name="开票").click()
    page.wait_for_timeout(400)
    inv = root.inner_text()
    for col in ("申请单", "订单", "抬头", "类型", "税号", "金额", "申请时间", "状态"):
        assert col in inv, col
    page.get_by_role("tab", name="学习进度").click()
    page.wait_for_timeout(400)
    learn = root.inner_text()
    for col in ("专栏", "店铺", "权益状态", "进度", "已学/总讲", "最近学习", "最近课时"):
        assert col in learn, col
    chrome = page.locator("body").inner_text()
    assert "A11-A" not in chrome
    assert "同步到 CRM" not in chrome


def test_ui_shop_merchant_bookings(page):
    """SHOP-MCH-A07A: 预约名单只读。对照 #a07a / #a11a-bookings / #m10-cancel-policy。"""
    ui_login(page)
    ui_goto(page, "/shop/bookings")
    page.locator('[data-testid="shop-bookings"]').wait_for(timeout=15000)
    body = page.locator('[data-testid="shop-bookings"]').inner_text()
    assert "服务" in body
    assert "预约号" in body
    assert page.get_by_placeholder("预约日期").count() >= 1 or page.locator('[placeholder="预约日期"]').count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    assert page.get_by_text("到店标记").count() == 0
    assert page.locator("button:has-text('到店')").count() == 0
    chrome = page.locator("body").inner_text()
    assert "expired_unredeemed" not in chrome
    assert "slot_closed" not in chrome


def test_ui_shop_merchant_verifications(page):
    """SHOP-MCH-A08: 核销记录列表完备。对照 #a08-log / #a08-log-select-spec。"""
    ui_login(page)
    ui_goto(page, "/shop/verifications")
    page.locator('[data-testid="shop-verifications"]').wait_for(timeout=15000)
    root = page.locator('[data-testid="shop-verifications"]')
    assert "到店核销" in root.inner_text()
    page.get_by_text("核销记录").first.click()
    page.wait_for_timeout(500)
    body = root.inner_text()
    for col in ("核销时间", "核销码", "买家", "商品", "预约时段", "操作人"):
        assert col in body, col
    assert page.get_by_placeholder("核销码 / 买家手机").count() >= 1
    assert page.get_by_text("近7天").count() >= 1
    assert page.get_by_text("今日").count() >= 1
    assert page.locator(".el-select__placeholder").filter(has_text="操作人").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    page.get_by_text("列设置").first.click()
    page.wait_for_timeout(300)
    dlg = page.locator(".el-dialog").last
    assert "扣次" in dlg.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_merchant_clerk_shell(page):
    """SHOP-MCH-A08-C: 店员登录仅见核销台。对照 #a08-clerk。"""
    from tests.verify_shop_a08 import CLERK_PASSWORD, CLERK_PHONE, _ensure_clerk
    from tests.verify_shop_a14 import _ensure_merchant

    merchant, tenant_id = _ensure_merchant()
    _ensure_clerk(merchant, tenant_id)
    ui_login(page, CLERK_PHONE, CLERK_PASSWORD)
    page.locator('[data-testid="shop-clerk-shell"]').wait_for(timeout=20000)
    page.locator('[data-testid="shop-verifications"]').wait_for(timeout=10000)
    assert "/shop/verifications" in page.url
    side = page.locator(".app-sidebar").inner_text()
    assert "核销台" in side
    assert "预约管理" not in side
    assert "商品管理" not in side
    assert "工作台" not in side
    ui_goto(page, "/shop/bookings")
    page.wait_for_timeout(800)
    assert "/shop/verifications" in page.url
    ui_goto(page, "/shop/redemptions")
    page.locator('[data-testid="shop-verifications"]').wait_for(timeout=10000)


def test_ui_shop_merchant_stores_a17(page):
    """SHOP-MCH-A17: 店铺管理列表。对照 #a17。"""
    ui_login(page)
    ui_goto(page, "/shop/stores")
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    assert "我的店铺" in body or "新建店铺" in body, body[:500]
    assert page.get_by_text("店铺短码").count() >= 1 or "店铺短码" in body
    assert "全部店铺" in body or page.get_by_text("全部店铺").count() >= 1
    assert "待开业" in body or page.get_by_text("待开业").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.locator('[data-testid="shop-current-store"]').wait_for(timeout=10000)
    assert "当前店铺" in page.locator('[data-testid="shop-current-store"]').inner_text()


def test_ui_shop_merchant_roles_a16(page):
    """SHOP-MCH-004 / A16: 角色与成员。对照 #a16。"""
    ui_login(page)
    ui_goto(page, "/shop/roles-members")
    page.get_by_role("heading", name="角色与成员").wait_for(timeout=15000)
    body = page.locator("body").inner_text()
    assert "内置角色" in body
    assert "店铺管理员" in body or "shop_admin" in body
    assert page.get_by_text("分配成员").count() >= 1
    assert page.get_by_text("权限矩阵").count() >= 1


@pytest.mark.skip(reason="店员在 A16 角色与成员分配（已测 SHOP-MCH-004）；无独立 /shop/staff")
def test_ui_shop_merchant_staff(page):
    """历史 SHOP-MCH-003：独立店员页未规划。"""
    ui_login(page)
    ui_goto(page, "/shop/staff")


@pytest.mark.skip(reason="站内信本批不接；无商家消息通知页")
def test_ui_shop_merchant_notifications(page):
    """历史 SHOP-MCH-005：消息通知本批不接。"""
    ui_login(page)
    ui_goto(page, "/shop/notifications")
