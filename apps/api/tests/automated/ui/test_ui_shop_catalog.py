"""商品与内容管理 UI — 对照 PRD #a02/#a03/#a04/#a06/#a14。已落地页去 skip。"""
from __future__ import annotations

import pytest

from tests.automated.ui.conftest import ui_goto, ui_login


def test_ui_shop_catalog_product_list(page):
    """SHOP-CAT-001 / A02: 商品列表 §0b（封面/销量/公域/导出/列设置/批量）。"""
    ui_login(page)
    ui_goto(page, "/shop/products")
    page.wait_for_selector(".el-table", timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("批量提交审核").count() >= 1
    assert page.get_by_text("批量下架").count() >= 1
    assert page.get_by_text("+ 新建商品").count() >= 1
    for label in ("封面", "名称", "销量", "公域"):
        assert page.get_by_text(label, exact=False).count() >= 1
    page.get_by_text("导出", exact=False).first.click()
    page.get_by_text("当前筛选").wait_for(timeout=3000)
    assert page.get_by_text("列配置").count() >= 1
    page.get_by_text("当前筛选").click()
    page.get_by_text("导出任务").wait_for(timeout=8000)
    exp = page.locator(".el-dialog").filter(has_text="导出任务")
    assert "下载" in exp.inner_text()
    assert "当前筛选" in exp.inner_text()
    page.keyboard.press("Escape")


def test_ui_shop_catalog_product_new(page):
    """SHOP-CAT-002 / A03: 新建商品页含平台类目与类型卡片。"""
    ui_login(page)
    ui_goto(page, "/shop/products/new")
    page.wait_for_timeout(1500)
    assert page.get_by_text("平台类目").count() >= 1
    assert page.get_by_text("课程").count() >= 1
    assert page.get_by_text("提交审核").count() >= 1
    assert page.get_by_text("存草稿").count() >= 1


def test_ui_shop_catalog_column(page):
    """SHOP-CAT-004 / A04: 专栏列表 §0b（Tab/高级筛选/导出/列设置）。对照 #a04。"""
    ui_login(page)
    ui_goto(page, "/shop/columns")
    page.wait_for_selector(".el-table", timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.locator('[data-testid="shop-columns"]').count() >= 1
    assert page.get_by_text("全部专栏").count() >= 1
    assert page.get_by_text("高级筛选").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("+ 新建专栏").count() >= 1
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
    page.get_by_text("高级筛选").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("引用商品 ≥").count() >= 1 or page.get_by_placeholder("引用商品 ≥").count() >= 1
    assert page.get_by_placeholder("更新起").count() >= 1
    page.get_by_text("+ 新建专栏").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("创建并编辑").count() >= 1
    assert page.get_by_placeholder("请输入专栏标题").count() >= 1


def test_ui_shop_catalog_digital_packages(page):
    """SHOP-CAT-A06: 资料包列表 §0b（Tab/导出/列设置）。对照 #a06。"""
    ui_login(page)
    ui_goto(page, "/shop/digital-packages")
    page.wait_for_selector(".el-table", timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.locator('[data-testid="shop-packages"]').count() >= 1
    assert page.get_by_text("全部资料包").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("+ 新建资料包").count() >= 1
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
    page.get_by_text("+ 新建资料包").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("创建并编辑").count() >= 1
    assert page.get_by_placeholder("请输入资料包标题").count() >= 1
    assert page.get_by_text("交付方式").count() >= 1
    assert page.get_by_text("在线查看").count() >= 1


def test_ui_shop_catalog_digital_package_edit(page):
    """SHOP-CAT-A06-edit: 资料包编辑页（上传弹窗/发布确认）。对照 #a06-edit / #a06a / #a06b。"""
    ui_login(page)
    ui_goto(page, "/shop/digital-packages")
    page.wait_for_selector(".el-table", timeout=15000)
    page.get_by_text("+ 新建资料包").first.click()
    page.wait_for_timeout(400)
    page.get_by_placeholder("请输入资料包标题").fill("验收资料包编辑")
    page.get_by_text("创建并编辑").click()
    page.wait_for_selector('[data-testid="shop-package-edit"]', timeout=15000)
    assert page.get_by_text("← 返回列表").count() >= 1
    assert page.get_by_text("保存").count() >= 1
    assert page.get_by_text("包内文件").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_placeholder("搜索文件名").count() >= 1
    assert page.get_by_text("+ 添加文件").count() >= 1
    assert page.get_by_text("最大下载次数").count() >= 1
    page.get_by_text("+ 添加文件").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("开始上传").count() >= 1
    assert page.get_by_text("点击或拖拽上传").count() >= 1
    assert page.get_by_text("上传文件").count() >= 1


def test_ui_shop_catalog_service_offers(page):
    """SHOP-CAT-A07: 服务列表 §0b（Tab/模式筛选/导出/列设置）。对照 #a07。"""
    ui_login(page)
    ui_goto(page, "/shop/service-offers")
    page.wait_for_selector(".el-table", timeout=15000)
    assert page.locator(".el-table").count() >= 1
    assert page.locator('[data-testid="shop-offers"]').count() >= 1
    assert page.get_by_text("全部服务").count() >= 1
    assert page.get_by_text("导出").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("+ 新建服务").count() >= 1
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
    page.get_by_text("+ 新建服务").first.click()
    page.wait_for_timeout(400)
    assert page.get_by_text("创建并编辑").count() >= 1
    assert page.get_by_placeholder("请输入服务标题").count() >= 1
    assert page.get_by_text("次数卡").count() >= 1
    assert page.get_by_text("单次时长(分)").count() >= 1


def test_ui_shop_catalog_service_offer_edit(page):
    """SHOP-CAT-A07-edit: 服务编辑页（时段工具栏/保存）。对照 #a07-edit。"""
    ui_login(page)
    ui_goto(page, "/shop/service-offers")
    page.wait_for_selector(".el-table", timeout=15000)
    page.get_by_text("+ 新建服务").first.click()
    page.wait_for_timeout(400)
    page.get_by_placeholder("请输入服务标题").fill("验收服务编辑")
    page.get_by_text("创建并编辑").click()
    page.wait_for_selector("text=可预约时段", timeout=15000)
    assert page.locator('[data-testid="shop-offer-edit"]').count() >= 1
    assert page.get_by_text("← 返回列表").count() >= 1
    assert page.get_by_text("保存").count() >= 1
    assert page.get_by_text("全部时段").count() >= 1
    assert page.get_by_text("列设置").count() >= 1
    assert page.get_by_text("批量生成").count() >= 1
    assert page.get_by_text("单次时长(分)").count() >= 1


def test_ui_shop_catalog_channel_mappings(page):
    """SHOP-CAT-A14: 商品映射列表 §0b（高级筛选/导出/列设置）。对照 #a14-list。"""
    ui_login(page)
    ui_goto(page, "/shop/channel-mappings")
    page.wait_for_timeout(1500)
    assert page.locator(".el-table, .el-alert").count() >= 1
    assert page.get_by_text("新建映射").count() >= 1 or page.get_by_text("公域").count() >= 1
    assert page.get_by_text("全部映射").count() >= 1
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


@pytest.mark.skip(reason="无独立「课程库」页；课程经专栏 A04/A05 + 商品 A03（对照 #a04）")
def test_ui_shop_catalog_course(page):
    """历史 SHOP-CAT-003：独立课程页未规划。"""
    ui_login(page)
    ui_goto(page, "/shop/courses")


@pytest.mark.skip(reason="Phase1 无库存 SKU 页（内容商品非实物库存）")
def test_ui_shop_catalog_inventory(page):
    """历史 SHOP-CAT-005：库存页不适用。"""
    ui_login(page)
    ui_goto(page, "/shop/inventory")
