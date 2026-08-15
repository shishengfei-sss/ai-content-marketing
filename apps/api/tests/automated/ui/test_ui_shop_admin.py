"""平台管理后台 — 商家管理模块 UI — SHOP-ADMIN / M0f 冒烟（选择器对齐 page-card）。"""
from __future__ import annotations

import os
import re

from tests.automated.ui.conftest import ui_goto

PLATFORM_PHONE = os.environ.get("UI_TEST_PLATFORM_PHONE", "13800000000")
PLATFORM_PASSWORD = os.environ.get("UI_TEST_PLATFORM_PASSWORD", "admin123456")


def _platform_login(page) -> None:
    from tests.automated.ui.conftest import BASE_URL

    page.goto(f"{BASE_URL}/admin/login", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    password_seg = page.locator(".el-segmented__item", has_text="密码登录")
    if password_seg.count() > 0:
        password_seg.first.click()
    page.get_by_placeholder("请输入手机号").fill(PLATFORM_PHONE)
    page.get_by_placeholder("请输入密码").fill(PLATFORM_PASSWORD)
    page.click('button:has-text("登录")')
    page.wait_for_url(lambda url: "/admin" in url and "/admin/login" not in url, timeout=20000)
    page.wait_for_timeout(500)


def test_ui_shop_admin_merchant_list(page):
    """SHOP-ADMIN-001 / TC-P02-L01 · TC-P02C: 商家列表与暂停/清退确认。对照 #p02-list / #p02c / #p02f。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.locator('[data-testid="shop-merchants"]').wait_for(timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.locator(".el-input, .el-select").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    assert page.get_by_placeholder("商家名 / 商家编码").count() >= 1
    assert page.get_by_text(re.compile(r"SH\d{12}")).count() >= 1
    pause_btn = page.locator("button:has-text('暂停')").first
    if pause_btn.count() >= 1:
        pause_btn.click()
        page.wait_for_timeout(400)
        for label in ("影响说明（只读）", "暂停原因", "说明"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.locator("button:has-text('确认暂停')").count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    close_btn = page.locator("button:has-text('清退')").first
    if close_btn.count() >= 1:
        close_btn.click()
        page.wait_for_timeout(400)
        for label in ("原因码", "说明", "影响（只读）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.get_by_text("我已知晓清退不可恢复", exact=False).count() >= 1
        assert page.locator("button:has-text('确认清退')").count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
    assert "即将开放" not in page.locator('[data-testid="shop-merchants"]').inner_text()
    chrome = page.locator('[data-testid="shop-merchants"]').inner_text()
    assert "P02-C" not in chrome and "P02-D" not in chrome and "P02-F" not in chrome
    assert page.get_by_placeholder("标签（字典未接）").count() == 0
    assign_btn = page.locator('[data-testid="shop-merchants"] .el-table button:has-text("分配管家")').first
    if assign_btn.count() >= 1:
        assign_btn.click()
        page.wait_for_timeout(400)
        for label in ("新管家", "确认分配", "影响说明（只读）", "当前管家（只读）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    assert page.locator('[data-testid="shop-batch-assign"]').count() >= 1
    page.locator('[data-testid="shop-batch-assign"]').click()
    page.wait_for_timeout(400)
    assert page.get_by_text("请先勾选商家", exact=False).count() >= 1 or page.locator(".el-message").count() >= 1
    tag_btn = page.locator("button:has-text('编辑标签')").first
    if tag_btn.count() >= 1:
        tag_btn.click()
        page.wait_for_timeout(400)
        for label in ("已选标签", "添加标签", "常用（点击添加）", "续费意向"):
            assert page.get_by_text(label, exact=False).count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_admin_merchant_audit(page):
    """SHOP-ADMIN-002 / TC-P03-L01: 入驻审核。对照 #p03-list / #p03-approve / #p03-reject。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/onboarding")
    page.locator('[data-testid="shop-onboarding"]').wait_for(timeout=15000)
    assert page.locator(".el-table").count() >= 1
    for label in ("全部申请", "待审", "已通过", "已驳回"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.get_by_placeholder("搜索商家名").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    assert page.locator("button:has-text('高级筛选')").count() >= 1
    for col in ("申请单号", "主体类型", "申请时间", "发起方式", "状态"):
        assert page.get_by_text(col, exact=False).count() >= 1
    review_btn = page.locator('[data-testid="shop-onboarding"] .el-table button:has-text("审核")').first
    view_btn = page.locator('[data-testid="shop-onboarding"] .el-table button:has-text("查看")').first
    if review_btn.count() >= 1:
        review_btn.click()
        page.get_by_role("tab", name="申请详情").wait_for(timeout=10000)
        for label in ("申请详情", "通过并开通", "驳回"):
            assert page.get_by_text(label, exact=False).count() >= 1
        page.get_by_role("tab", name="通过并开通").click()
        page.wait_for_timeout(400)
        for label in ("首开套餐", "生效起", "生效止", "分配商家管家", "将创建（只读）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.get_by_text("商家（正常）+ 订阅快照").count() >= 1
        assert page.locator("button:has-text('确认通过并开通')").count() >= 1
        page.get_by_role("tab", name="驳回").click()
        page.wait_for_timeout(400)
        assert page.get_by_text("驳回原因码", exact=False).count() >= 1
        assert page.locator("button:has-text('确认驳回')").count() >= 1
        page.get_by_role("tab", name="申请详情").click()
        page.wait_for_timeout(500)
        assert page.get_by_text("申请单号").count() >= 1
        review_txt = page.locator('[data-testid="shop-onboarding"]').inner_text()
        assert "OB" in review_txt
        import re as _re
        assert _re.search(r"OB\d{12}", review_txt), review_txt[:400]
        assert page.get_by_text("审核日志").count() >= 1
        assert page.locator('[data-testid="shop-onboarding-review-logs"]').count() >= 1
        assert page.get_by_text("明文揭露本批未接").count() == 0
        assert page.locator('[data-testid="btn-reveal-contact-mobile"]').count() >= 1
    elif view_btn.count() >= 1:
        view_btn.click()
        page.wait_for_timeout(800)
        assert page.get_by_text("申请详情", exact=False).count() >= 1 or page.get_by_text(
            "已审出申请仅可查阅详情"
        ).count() >= 1
        assert page.get_by_text("审核日志").count() >= 1
        assert page.get_by_text("明文揭露本批未接").count() == 0
    chrome = page.locator('[data-testid="shop-onboarding"]').inner_text()
    assert "#p03" not in chrome.lower()
    assert "明文揭露本批未接" not in chrome


def test_ui_shop_admin_merchant_detail(page):
    """SHOP-ADMIN-003 / TC-P02B-F01: 商家详情六 Tab 与写跟进栏位。对照 #p02b。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/merchants")
    page.wait_for_timeout(1500)
    ent_btn = page.locator("button:has-text('当前权益')").first
    if ent_btn.count() == 0:
        assert page.locator(".el-table, .el-empty").count() >= 1
        return
    ent_btn.click()
    page.locator('[data-testid="shop-merchant-detail"]').wait_for(timeout=15000)
    page.wait_for_timeout(500)
    for label in ("概览", "当前权益", "旗下店铺", "入驻材料", "支付进件", "服务记录", "操作日志"):
        assert page.get_by_role("tab", name=label).count() >= 1
    page.get_by_role("tab", name="当前权益").click()
    page.wait_for_timeout(800)
    assert page.get_by_text("生效中订阅").count() >= 1
    assert page.get_by_text("合并后有效权益").count() >= 1
    page.get_by_text("店铺与商品").first.wait_for(timeout=10000)
    assert page.get_by_text("分组 · 无合并值").count() >= 1
    assert page.get_by_text("领权短信 / 月").count() >= 1
    assert page.get_by_text("已用", exact=True).count() >= 1
    ent_chrome = page.locator('[data-testid="shop-merchant-detail"]').inner_text()
    assert "暂无计量接口" not in ent_chrome
    assert "用量分组折叠本批未做" not in ent_chrome
    page.get_by_role("tab", name="服务记录").click()
    page.wait_for_timeout(800)
    assert page.locator("button:has-text('写跟进')").count() >= 1
    page.locator("button:has-text('写跟进')").click()
    page.wait_for_timeout(500)
    for label in ("跟进类型", "跟进时间", "内容", "下次跟进"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator(".el-dialog button:has-text('保存')").count() >= 1
    page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
    page.wait_for_timeout(300)
    chrome = page.locator('[data-testid="shop-merchant-detail"]').inner_text()
    assert "P02-E" not in chrome and "本批未开放" not in chrome
    assert re.search(r"SH\d{12}", chrome)
    assert page.locator('[data-testid="shop-merchant-detail"] button:has-text("暂停")').count() == 0
    assert page.locator('[data-testid="shop-merchant-detail"] button:has-text("清退")').count() == 0
    page.get_by_role("tab", name="入驻材料").click()
    page.wait_for_timeout(500)
    assert page.get_by_text("OCR 识别快照").count() >= 1
    page.get_by_role("tab", name="操作日志").click()
    page.wait_for_timeout(500)
    page.locator('[data-testid="shop-merchant-audit"]').wait_for(timeout=5000)
    assert page.get_by_placeholder("全部动作").count() >= 1 or page.get_by_text("全部动作").count() >= 1
    assert page.get_by_placeholder("搜索操作人 / 摘要").count() >= 1
    for label in ("时间", "动作", "摘要", "操作人", "来源"):
        assert page.get_by_text(label, exact=False).count() >= 1
    chrome_audit = page.locator('[data-testid="shop-merchant-detail"]').inner_text()
    assert "无独立审计表" not in chrome_audit
    page.get_by_role("tab", name="概览").click()
    page.wait_for_timeout(300)
    assert page.get_by_text("本月 GMV").count() >= 1
    eye = page.locator('[data-testid="btn-reveal-contact-mobile"]')
    if eye.count() >= 1:
        eye.first.click()
        page.wait_for_timeout(400)
    if page.locator("button:has-text('分配管家')").count() >= 1:
        page.locator("button:has-text('分配管家')").first.click()
        page.wait_for_timeout(400)
        assert page.get_by_text("确认分配", exact=False).count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()


def test_ui_shop_admin_categories(page):
    """SHOP-ADMIN-P04 / TC-P04-L01: 类目与费率列表。对照 #p04 / #p04d / #p04c。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/categories")
    page.locator('[data-testid="shop-categories"]').wait_for(timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.get_by_text("+ 新增类目").count() >= 1
    for label in ("类目", "类目编码", "平台费率", "需资质", "状态"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    assert page.locator("button:has-text('高级筛选')").count() >= 1
    assert page.get_by_placeholder("搜索类目名").count() >= 1
    assert (
        page.locator("button:has-text('启用（需审批）')").count()
        + page.locator("button:has-text('审批启用')").count()
    ) >= 1
    disable_btn = page.locator(".el-table__fixed-right button:has-text('禁用')").first
    if disable_btn.count() >= 1:
        disable_btn.click()
        page.get_by_text("影响说明（只读）").wait_for(timeout=10000)
        for label in ("影响说明（只读）", "告警（只读）", "原因类型", "说明"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.locator("button:has-text('确认禁用')").count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    page.locator("button:has-text('+ 新增类目')").click()
    page.wait_for_timeout(500)
    for label in ("父类目", "编码来源", "类目名称", "平台费率", "分账规则", "初始状态"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.locator(".el-drawer").locator("button:has-text('取消')").last.click()
    page.wait_for_timeout(300)
    enable_btn = page.locator(".el-table__fixed-right button:has-text('启用（需审批）')").first
    if enable_btn.count() >= 1:
        enable_btn.click()
        page.get_by_text("当前状态（只读）").wait_for(timeout=10000)
        for label in ("当前状态（只读）", "拟设费率", "需资质", "启用理由", "审批人（只读）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        page.locator(".el-drawer").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    page.locator("button:has-text('编码规则')").first.click()
    page.get_by_text("前缀", exact=False).wait_for(timeout=10000)
    assert page.locator('[data-testid="category-code-preview"]').count() >= 1
    assert page.locator("button:has-text('保存规则')").count() >= 1
    chrome = page.locator('[data-testid="shop-categories"]').inner_text()
    assert "#p04" not in chrome.lower()





def test_ui_shop_admin_channels_payment(page):
    """SHOP-ADMIN-P06 / TC-P06-F02: 渠道与支付 · 商户支付进件。对照 #p06。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/channels")
    page.locator('[data-testid="shop-channels"]').wait_for(timeout=15000)
    assert page.get_by_text("抖店公域").count() >= 1
    assert page.get_by_text("微信支付服务商").count() >= 1
    assert page.get_by_text("商户支付进件").count() >= 1
    assert page.get_by_text("微信开放平台").count() >= 1
    assert page.get_by_text("回调 URL（只读）").count() >= 1
    assert page.locator("button:has-text('保存配置')").count() >= 1
    assert page.locator("button:has-text('密钥轮换')").count() >= 1
    assert page.locator("button:has-text('连通性测试')").count() >= 1
    page.locator("button:has-text('保存配置')").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("AppKey 格式错误").count() >= 1
    page.get_by_role("tab", name="微信支付服务商").click()
    page.get_by_text("服务商商户号").wait_for(timeout=5000)
    assert page.get_by_text("支付结果 notify（只读）").count() >= 1
    assert page.locator("button:has-text('证书轮换')").count() >= 1
    assert page.locator("button:has-text('v3 密钥轮换')").count() >= 1
    page.get_by_role("tab", name="商户支付进件").click()
    page.wait_for_timeout(1500)
    for label in ("商家", "主体", "进件状态", "子商户号", "结算账户", "最近提交", "商家管家"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.get_by_placeholder("搜索商家名 / 子商户号").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.locator(".toolbar-right").get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_admin_sms(page):
    """SHOP-ADMIN-P12 / TC-P12-F02: 短信管理。对照 #p12。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/sms")
    page.wait_for_timeout(1500)
    for label in ("通道配置", "签名管理", "模板管理", "商家分配", "发送记录"):
        assert page.get_by_text(label).count() >= 1
    assert page.get_by_text("+ 新建签名申请").count() >= 1
    assert page.get_by_placeholder("搜索签名 / 商家").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").first.wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").first.click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.get_by_role("tab", name="通道配置").click()
    page.wait_for_timeout(800)
    for label in ("AccessKey ID", "AccessKey Secret", "默认签名（平台通知）", "连通性（只读）"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator("button:has-text('保存')").count() >= 1
    assert page.locator("button:has-text('连通性测试')").count() >= 1
    page.get_by_role("tab", name="商家分配").click()
    page.wait_for_timeout(800)
    for col in ("商家", "领权签名", "领权模板", "本月已发"):
        assert page.get_by_text(col, exact=False).count() >= 1
    assert page.get_by_text("+ 分配短信资源").count() >= 1
    page.get_by_role("tab", name="发送记录").click()
    page.wait_for_timeout(800)
    page.locator("button:has-text('导出 CSV')").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_admin_product_reviews(page):
    """SHOP-ADMIN-P09 / TC-P09-L01: 商品审核待审队列与面板。对照 #p09。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/product-reviews")
    page.locator('[data-testid="shop-product-reviews"]').wait_for(timeout=15000)
    assert page.get_by_text("待审队列").count() >= 1
    assert page.get_by_text("已审出队").count() >= 1
    assert page.get_by_placeholder("搜索商品 / 商家").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    for label in ("商品", "商家", "类型", "机审", "提交时间"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.get_by_text("已审出队").first.click()
    page.wait_for_timeout(800)
    for label in ("审出结果", "审出时间", "在售状态"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.get_by_text("待审队列").first.click()
    page.wait_for_timeout(800)
    page.locator("button:has-text('高级筛选')").first.click()
    page.get_by_placeholder("商家套餐").wait_for(timeout=5000)
    assert page.get_by_text("是否首单公域").count() >= 1
    review_btn = page.locator(".el-table__fixed-right button:has-text('审核')").first
    if review_btn.count() >= 1:
        review_btn.click()
        page.locator('[data-testid="shop-product-review-panel"]').wait_for(timeout=10000)
        for label in ("商品快照", "机审明细", "内部备注（选填）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.locator("button:has-text('通过')").count() >= 1
        assert page.locator("button:has-text('驳回')").count() >= 1
        assert page.locator("button:has-text('预览买家页')").count() >= 1
    chrome = page.locator('[data-testid="shop-product-reviews"]').inner_text()
    assert "P09" not in chrome
    assert "未接通" not in chrome


def test_ui_shop_admin_roles_codes(page):
    """SHOP-ADMIN-P08 / TC-P08-F01: 角色与编码。对照 #p08a / #p08b / #p08f。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/roles-codes")
    page.locator('[data-testid="shop-roles-codes"]').wait_for(timeout=15000)
    for label in ("平台超管", "日常运营", "商家管家", "财务结算"):
        assert page.get_by_text(label).count() >= 1
    assert page.get_by_text("查看权限").count() >= 1
    assert page.get_by_text("绑定账号").count() >= 1
    assert page.get_by_text("权限码").count() >= 1
    perm_btn = page.locator("button:has-text('查看权限')").first
    if perm_btn.count() >= 1:
        perm_btn.click()
        page.get_by_text("查看权限 ·").wait_for(timeout=8000)
        assert page.locator(".el-drawer").get_by_text("权限码").count() >= 1
        page.locator(".el-drawer").locator("button:has-text('关闭')").last.click()
        page.wait_for_timeout(300)
    assert page.get_by_role("tab", name="编码规则").count() >= 1
    page.get_by_role("tab", name="编码规则").click()
    page.get_by_text("恢复全部默认").wait_for(timeout=8000)
    for label in ("实体", "entity_type", "前缀", "日期段", "序号宽度", "重置周期", "启用", "预览"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    assert page.locator("button:has-text('恢复全部默认')").count() >= 1
    refresh_btn = page.locator(".el-table__fixed-right button:has-text('刷新预览')").first
    if refresh_btn.count() >= 1:
        refresh_btn.click()
        page.wait_for_timeout(400)
    chrome = page.locator('[data-testid="shop-roles-codes"]').inner_text()
    assert "P08" not in chrome
    assert "#p08" not in chrome.lower()
    ui_goto(page, "/admin/users")
    page.locator('[data-testid="admin-users"]').wait_for(timeout=15000)
    assert page.get_by_text("获客商城角色").count() >= 1
    page.get_by_placeholder("手机号 / 昵称 / 租户名").fill("13800000000")
    page.locator("button:has-text('查询')").click()
    page.wait_for_timeout(1000)
    edit_btn = page.locator("button:has-text('编辑商城权限')").first
    assert edit_btn.count() >= 1
    edit_btn.click()
    page.locator('[data-testid="shop-edit-shop-perms"]').wait_for(timeout=8000)
    assert page.get_by_text("账号").count() >= 1
    assert page.get_by_text("（只读）").count() >= 1
    assert page.locator('[data-testid="shop-edit-shop-perms"]').get_by_text("角色").count() >= 1
    page.locator('[data-testid="shop-perm-audit-timeline"]').wait_for(timeout=5000)
    assert page.get_by_text("变更记录").count() >= 1
    assert page.get_by_text("时间").count() >= 1 or page.get_by_text("暂无变更记录").count() >= 1
    page.locator(".el-drawer").locator("button:has-text('取消')").last.click()


def test_ui_shop_admin_subscriptions(page):
    """SHOP-ADMIN-P11 / TC-P11-L01: 订阅台账。对照 #p11。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/subscriptions")
    page.locator('[data-testid="shop-subscription-page"]').wait_for(timeout=15000)
    assert page.get_by_text("待处理续费申请").count() >= 1
    assert page.get_by_text("人工开通（主套餐/叠加）").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_placeholder("订阅单号 / 商家名").count() >= 1
    for label in ("开通单号", "商家", "套餐", "订阅类型", "生效起", "生效止", "开通时间", "开通人", "状态"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.locator(".toolbar-right").get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.locator("button:has-text('人工开通（主套餐/叠加）')").click()
    page.wait_for_timeout(800)
    for label in ("选择套餐", "开通方式", "套餐标价（只读）", "应付金额", "运营备注（选填）", "确认开通", "合并预览（只读）"):
        assert page.get_by_text(label, exact=False).count() >= 1


def test_ui_shop_admin_renewal_todo(page):
    """SHOP-ADMIN-P11 / TC-P11-L01: 待处理续费待办在 P11 页内。对照 #p11-todo。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/subscriptions?todo=renewal")
    page.locator('[data-testid="shop-subscription-page"]').wait_for(timeout=15000)
    assert page.locator('[data-testid="shop-renewal-todo"]').count() >= 1
    assert page.get_by_text("待处理续费申请").count() >= 1
    assert page.get_by_text("待处理续费").count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    if page.get_by_role("button", name="去处理").count() >= 1:
        page.get_by_role("button", name="去处理").first.click()
        page.wait_for_timeout(600)
        assert page.get_by_text("暂存处理中").count() >= 1
        assert page.get_by_text("确认开通并结案").count() >= 1


def test_ui_shop_admin_plans(page):
    """SHOP-ADMIN-P10 / TC-P10-F01: 套餐配置字典与模板。对照 #p10-dict / #p10h。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/plans")
    page.locator('[data-testid="shop-plan-config"]').wait_for(timeout=15000)
    assert page.get_by_role("tab", name="功能字典").count() >= 1
    assert page.get_by_role("tab", name="套餐模板").count() >= 1
    assert page.get_by_placeholder("搜索 code / 名称").count() >= 1
    assert page.get_by_text("+ 新增分组").count() >= 1
    assert page.get_by_text("+ 新增子功能").count() >= 1
    assert page.locator("button:has-text('列设置')").count() >= 1
    assert page.locator("button:has-text('导出')").count() >= 1
    for label in ("名称 / 编码", "叠加模式", "埋点标识"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.get_by_role("tab", name="套餐模板").click()
    page.wait_for_timeout(800)
    assert page.get_by_placeholder("搜索套餐名").count() >= 1
    assert page.get_by_text("+ 新建主套餐").count() >= 1
    assert page.get_by_text("+ 新建加购包").count() >= 1
    for label in ("套餐", "互斥组", "每日提审", "适用主体"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.locator(".el-tab-pane:visible button:has-text('列设置')").click()
    page.get_by_text("创建人").wait_for(timeout=5000)
    assert page.get_by_text("最后修改人").count() >= 1
    page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
    page.wait_for_timeout(300)
    detail_btn = page.locator(".el-table__fixed-right button:has-text('详情')").first
    if detail_btn.count() >= 1:
        detail_btn.click()
        page.get_by_text("生效订阅数（只读）").wait_for(timeout=8000)
        page.locator(".el-dialog").locator("button:has-text('关闭')").last.click()
        page.wait_for_timeout(300)
    page.locator("button:has-text('+ 新建主套餐')").click()
    page.wait_for_timeout(800)
    for label in ("套餐名称", "售价", "套餐能力配置", "保存后上架", "适用主体类型"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator("button:has-text('刷新预览')").count() >= 1
    chrome = page.locator('[data-testid="shop-plan-config"]').inner_text()
    assert "P10" not in chrome
    assert "未接通" not in chrome


def test_ui_shop_admin_dashboard(page):
    """SHOP-ADMIN-P01 / TC-P01-F01: 平台经营看板。对照 #p01。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/dashboard")
    page.locator('[data-testid="shop-platform-dashboard"]').wait_for(timeout=15000)
    assert page.get_by_text("全站经营看板").count() >= 1
    assert page.get_by_text("导出日报").count() >= 1
    assert page.get_by_text("本月 GMV").count() >= 1
    assert page.get_by_text("待审商品").count() >= 1
    for label in ("商家", "本月 GMV", "订单", "状态", "最近活跃"):
        assert page.get_by_text(label, exact=False).count() >= 1


def test_ui_shop_admin_settlements(page):
    """SHOP-ADMIN-P05 / TC-P05-L01: 清结算列表。对照 #p05 / #p05a / #p05b。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/settlements")
    page.locator('[data-testid="shop-settlement-page"]').wait_for(timeout=15000)
    assert page.get_by_text("本月平台收入").count() >= 1
    assert page.get_by_text("待结算给商家").count() >= 1
    assert page.get_by_text("周结").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    for label in ("结算批次", "商家", "周期", "成交额", "平台抽成", "退款冲正", "应结"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.locator("button:has-text('高级筛选')").first.click()
    page.get_by_placeholder("周期起").wait_for(timeout=5000)
    assert page.get_by_placeholder("周期止").count() >= 1
    page.locator(".toolbar-right").get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    detail_btn = page.locator(".el-table__fixed-right button:has-text('详情')").first
    if detail_btn.count() >= 1:
        detail_btn.click()
        page.get_by_text("汇总（只读）").wait_for(timeout=10000)
        assert page.get_by_text("收款账户（只读）").count() >= 1
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    pay_btn = page.locator(".el-table__fixed-right button:has-text('确认打款')").first
    if pay_btn.count() >= 1:
        pay_btn.click()
        page.get_by_text("商家（只读）").wait_for(timeout=10000)
        for label in ("应结金额（只读）", "打款凭证（选填）", "备注（选填）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.locator("button:has-text('选择文件')").count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    chrome = page.locator('[data-testid="shop-settlement-page"]').inner_text()
    assert "#p05" not in chrome.lower()


def test_ui_shop_admin_moderation(page):
    """SHOP-ADMIN-P07 / TC-P07-L01: 违规稽查。对照 #p07 / #p07a / #p07b / #p07c。"""
    _platform_login(page)
    ui_goto(page, "/admin/shop/moderation")
    page.locator('[data-testid="shop-moderation-page"]').wait_for(timeout=15000)
    assert page.get_by_text("待处理").count() >= 1
    assert page.get_by_text("处理中").count() >= 1
    assert page.get_by_text("本月已结案").count() >= 1
    assert page.get_by_text("本月强制下架").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    for label in ("类型", "对象", "商家", "上报时间", "状态"):
        assert page.get_by_text(label, exact=False).count() >= 1
    assert page.locator(".el-table, .el-empty").count() >= 1
    page.locator("button:has-text('高级筛选')").first.click()
    page.locator(".adv-row").wait_for(timeout=5000)
    assert page.get_by_text("建单来源").count() >= 1
    page.locator(".toolbar-right").get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    view_btn = page.locator(".el-table__fixed-right button:has-text('查看')").first
    if view_btn.count() >= 1:
        view_btn.click()
        page.get_by_text("类型（只读）").wait_for(timeout=10000)
        for label in ("对象（只读）", "商家（只读）", "时间线（只读）", "处理结果（只读）", "附件（只读）"):
            assert page.get_by_text(label, exact=False).count() >= 1
        assert page.get_by_text("本批无文件预览").count() == 0
        page.locator(".el-drawer").locator("button:has-text('关闭')").last.click()
        page.wait_for_timeout(300)
    off_btn = page.locator(".el-table__fixed-right button:has-text('下架')").first
    if off_btn.count() >= 1:
        off_btn.click()
        page.get_by_text("工单（只读）").wait_for(timeout=10000)
        for label in ("将执行（只读）", "告警（只读）", "下架原因类型", "说明"):
            assert page.get_by_text(label, exact=False).count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    close_btn = page.locator(".el-table__fixed-right button:has-text('结案')").first
    if close_btn.count() >= 1:
        close_btn.click()
        page.get_by_text("处理结果").wait_for(timeout=10000)
        assert page.get_by_text("结案说明").count() >= 1
        assert page.get_by_text("是否通知商家").count() >= 1
        page.locator(".el-dialog").locator("button:has-text('取消')").last.click()
        page.wait_for_timeout(300)
    chrome = page.locator('[data-testid="shop-moderation-page"]').inner_text()
    assert "#p07" not in chrome.lower()
