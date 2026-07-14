"""企业功能权限 Catalog（与 docs/需求规格.md §2.5、§2.8 一致）。"""

from __future__ import annotations

_BASE_PERMISSIONS: tuple[str, ...] = (
    # 创作与内容
    "content.create",
    "content.list_own",
    "content.view_own",
    "content.list_all",
    "content.view_all",
    "content.edit",
    "content.delete",
    "content.export",
    "content.schedule",
    "content.publish",
    # 知识库
    "knowledge.view",
    "knowledge.manage",
    # 设置
    "preference.manage",
    "brand.manage",
    "wechat.manage",
    "llm.manage",
    "tenant.manage",
    # 工作台与数据看板
    "dashboard.view",
    "dashboard.view_all",
    "analytics.view",
    "analytics.view_all",
    # 团队
    "team.member.view",
    "team.member.manage",
    "team.role.manage",
)

CRM_PERMISSIONS: tuple[str, ...] = (
    # 线索
    "crm.lead.list_own",
    "crm.lead.list_team",
    "crm.lead.list_territory",
    "crm.lead.list_all",
    "crm.lead.view",
    "crm.lead.create",
    "crm.lead.edit",
    "crm.lead.assign",
    "crm.lead.convert",
    "crm.lead.delete",
    # 客户
    "crm.customer.list_own",
    "crm.customer.list_team",
    "crm.customer.list_territory",
    "crm.customer.list_all",
    "crm.customer.view",
    "crm.customer.create",
    "crm.customer.edit",
    "crm.customer.assign",
    "crm.customer.delete",
    # 任务
    "crm.task.list_own",
    "crm.task.list_team",
    "crm.task.list_territory",
    "crm.task.list_all",
    "crm.task.create",
    "crm.task.edit",
    "crm.task.assign",
    "crm.task.delete",
    # 营销活动
    "crm.campaign.list_own",
    "crm.campaign.list_team",
    "crm.campaign.list_territory",
    "crm.campaign.list_all",
    "crm.campaign.view",
    "crm.campaign.create",
    "crm.campaign.edit",
    "crm.campaign.manage",
    "crm.campaign.delete",
    # 组织、表单、跟进、视图、导入
    "crm.org.manage",
    "crm.schema.manage",
    "crm.activity.create",
    "crm.view.save_own",
    "crm.view.manage_public",
    "crm.lead.import",
    "crm.customer.import",
    # v0.7 商机与管道
    "crm.deal.list_own",
    "crm.deal.list_team",
    "crm.deal.list_territory",
    "crm.deal.list_all",
    "crm.deal.view",
    "crm.deal.create",
    "crm.deal.edit",
    "crm.deal.assign",
    "crm.deal.convert",
    "crm.deal.close",
    "crm.deal.delete",
    "crm.pipeline.manage",
    # v0.7 产品
    "crm.product.manage",
    # v0.7 报价
    "crm.quote.list_own",
    "crm.quote.list_all",
    "crm.quote.view",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.quote.send",
    "crm.quote.accept",
    "crm.quote.delete",
    # v0.7 合同
    "crm.contract.list_own",
    "crm.contract.list_all",
    "crm.contract.view",
    "crm.contract.create",
    "crm.contract.edit",
    "crm.contract.sign",
    "crm.contract.delete",
    # v0.7 订单
    "crm.order.list_own",
    "crm.order.list_team",
    "crm.order.list_territory",
    "crm.order.list_all",
    "crm.order.view",
    "crm.order.create",
    "crm.order.edit",
    "crm.order.assign",
    "crm.order.place",
    "crm.order.convert",
    "crm.order.delete",
    # v0.7 收款
    "crm.payment.list_own",
    "crm.payment.list_team",
    "crm.payment.list_territory",
    "crm.payment.list_all",
    "crm.payment.view",
    "crm.payment.create",
    "crm.payment.edit",
    "crm.payment.confirm",
    "crm.payment.reverse",
    "crm.payment.delete",
)

# 全部权限 code
ALL_PERMISSIONS: tuple[str, ...] = _BASE_PERMISSIONS + CRM_PERMISSIONS

# editor 内置角色默认权限（§2.5 带 ✅）
EDITOR_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "content.create",
        "content.list_own",
        "content.view_own",
        "preference.manage",
        "dashboard.view",
        "analytics.view",
    }
)

SALES_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "preference.manage",
        "dashboard.view",
        "analytics.view",
        "crm.lead.list_own",
        "crm.lead.view",
        "crm.lead.create",
        "crm.lead.edit",
        "crm.lead.convert",
        "crm.customer.list_own",
        "crm.customer.view",
        "crm.customer.create",
        "crm.customer.edit",
        "crm.activity.create",
        "crm.task.list_own",
        "crm.task.create",
        "crm.task.edit",
        "crm.view.save_own",
        "crm.lead.import",
        "crm.customer.import",
        # v0.7 商机
        "crm.deal.list_own",
        "crm.deal.view",
        "crm.deal.create",
        "crm.deal.edit",
        "crm.deal.convert",
        "crm.deal.close",
        # v0.7 报价
        "crm.quote.list_own",
        "crm.quote.view",
        "crm.quote.create",
        "crm.quote.edit",
        # v0.7 合同
        "crm.contract.list_own",
        "crm.contract.view",
        # v0.7 订单
        "crm.order.list_own",
        "crm.order.view",
        "crm.order.create",
        "crm.order.edit",
        "crm.order.place",
        "crm.order.convert",
        # v0.7 收款
        "crm.payment.list_own",
        "crm.payment.view",
        "crm.payment.create",
        "crm.payment.edit",
    }
)

SALES_MANAGER_DEFAULT_PERMISSIONS: frozenset[str] = SALES_DEFAULT_PERMISSIONS | frozenset(
    {
        "crm.lead.list_team",
        "crm.lead.list_territory",
        "crm.customer.list_team",
        "crm.customer.list_territory",
        "crm.task.list_team",
        "crm.task.list_territory",
        "crm.lead.assign",
        "crm.customer.assign",
        "crm.task.assign",
        "crm.lead.delete",
        "crm.customer.delete",
        "crm.view.manage_public",
        "dashboard.view_all",
        "analytics.view_all",
        "team.member.view",
        # v0.7 商机
        "crm.deal.list_team",
        "crm.deal.list_territory",
        "crm.deal.assign",
        "crm.deal.delete",
        # v0.7 报价
        "crm.quote.list_all",
        "crm.quote.send",
        "crm.quote.accept",
        "crm.quote.delete",
        # v0.7 合同
        "crm.contract.list_all",
        "crm.contract.create",
        "crm.contract.edit",
        "crm.contract.sign",
        "crm.contract.delete",
        # v0.7 订单
        "crm.order.list_team",
        "crm.order.list_territory",
        "crm.order.assign",
        "crm.order.delete",
        # v0.7 收款
        "crm.payment.list_team",
        "crm.payment.list_territory",
        "crm.payment.confirm",
        "crm.payment.reverse",
        "crm.payment.delete",
    }
)

MARKETING_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "preference.manage",
        "dashboard.view",
        "analytics.view",
        "content.create",
        "content.list_own",
        "content.view_own",
        "content.export",
        "content.schedule",
        "knowledge.view",
        "crm.campaign.list_own",
        "crm.campaign.view",
        "crm.campaign.create",
        "crm.campaign.edit",
        "crm.campaign.manage",
        "crm.campaign.list_all",
        "crm.lead.list_own",
        "crm.lead.view",
        "crm.lead.create",
        "crm.lead.edit",
        "crm.lead.convert",
        "crm.lead.list_all",
        "crm.customer.list_own",
        "crm.customer.view",
        "crm.view.save_own",
        # v0.7 商机（只读 + 新建）
        "crm.deal.list_own",
        "crm.deal.view",
        "crm.deal.create",
        # v0.7 报价（只读）
        "crm.quote.list_own",
        "crm.quote.view",
        # v0.7 合同（只读）
        "crm.contract.list_own",
        "crm.contract.view",
        # v0.7 订单（只读）
        "crm.order.list_own",
        "crm.order.view",
    }
)

SYSTEM_ROLE_CODES: frozenset[str] = frozenset(
    {"admin", "editor", "sales", "sales_manager", "marketing"}
)

SYSTEM_ROLE_ADMIN = "admin"
SYSTEM_ROLE_EDITOR = "editor"
SYSTEM_ROLE_SALES = "sales"
SYSTEM_ROLE_SALES_MANAGER = "sales_manager"
SYSTEM_ROLE_MARKETING = "marketing"

PLATFORM_ADMIN_ROLE = "platform_admin"
