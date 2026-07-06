"""企业功能权限 Catalog（与 docs/需求规格.md §2.5 一致）。"""

from __future__ import annotations

# 全部权限 code
ALL_PERMISSIONS: tuple[str, ...] = (
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

SYSTEM_ROLE_ADMIN = "admin"
SYSTEM_ROLE_EDITOR = "editor"

PLATFORM_ADMIN_ROLE = "platform_admin"
