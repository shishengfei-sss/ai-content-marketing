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
