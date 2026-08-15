"""企业功能权限 Catalog（与 docs/00-总览/需求规格.md §2.5、§2.8 一致）。

内容获客商城 Phase1 权限见 docs/01-PRD/21-内容获客商城-phase1/05-角色权限.html#catalog
"""

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
    "crm.deal.reopen",
    "crm.deal.delete",
    "crm.pipeline.manage",
    # v0.7 产品 / v1.4 导入
    "crm.product.manage",
    "crm.product.import",
    # v0.7 报价
    "crm.quote.list_own",
    "crm.quote.list_team",
    "crm.quote.list_all",
    "crm.quote.view",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.quote.send",
    "crm.quote.accept",
    "crm.quote.delete",
    # v0.7 合同
    "crm.contract.list_own",
    "crm.contract.list_team",
    "crm.contract.list_all",
    "crm.contract.view",
    "crm.contract.create",
    "crm.contract.edit",
    "crm.contract.sign",
    "crm.contract.approve",
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
    "crm.order.approve",
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

# 内容获客商城 · 平台运营端（跨租户，不参与 Membership）
PLATFORM_SHOP_PERMISSIONS: tuple[str, ...] = (
    "platform.shop.analytics",
    "platform.shop.approve",
    "platform.shop.channel",
    "platform.shop.fee.manage",
    "platform.shop.merchant.assign",
    "platform.shop.merchant.list_all",
    "platform.shop.merchant.list_assigned",
    "platform.shop.merchant.manage",
    "platform.shop.merchant.read",
    "platform.shop.merchant.tag",
    "platform.shop.merchant.tag.manage",
    "platform.shop.moderate",
    "platform.shop.onboarding.initiate",
    "platform.shop.plan.manage",
    "platform.shop.product.force_off",
    "platform.shop.product.review",
    "platform.shop.settlement",
    "platform.shop.subscription.manage",
    "platform.shop.subscription.read",
)

# 内容获客商城 · 商家端（租户内 shop.*）
SHOP_MERCHANT_PERMISSIONS: tuple[str, ...] = (
    "shop.analytics.read",
    "shop.buyer.list_all",
    "shop.buyer.view",
    "shop.channel.map",
    "shop.channel.read",
    "shop.channel.write",
    "shop.content.read",
    "shop.content.write",
    "shop.entitlement.list_all",
    "shop.entitlement.revoke",
    "shop.entitlement.view",
    "shop.invoice.list_all",
    "shop.invoice.process",
    "shop.invoice.view",
    "shop.order.close",
    "shop.order.export",
    "shop.order.list_all",
    "shop.order.list_own",
    "shop.order.refund",
    "shop.order.resend_notify",
    "shop.order.view",
    "shop.product.delete",
    "shop.product.publish",
    "shop.product.read",
    "shop.product.submit_review",
    "shop.product.write",
    "shop.redemption.execute",
    "shop.redemption.list_all",
    "shop.redemption.list_own",
    "shop.redemption.read",
    "shop.role.manage",
    "shop.settings.read",
    "shop.settings.write",
    "shop.store.manage",
    "shop.store.settings.read",
    "shop.store.settings.write",
    "shop.subscription.usage.read",
)

# 全部权限 code（租户 Membership；不含 platform.shop.*）
ALL_PERMISSIONS: tuple[str, ...] = _BASE_PERMISSIONS + CRM_PERMISSIONS + SHOP_MERCHANT_PERMISSIONS

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
        "team.member.view",
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
        "crm.deal.reopen",
        "crm.deal.delete",
        # v0.7 报价（与商机一致：经理看团队，admin 全公司）
        "crm.quote.list_team",
        "crm.quote.send",
        "crm.quote.accept",
        "crm.quote.delete",
        # v0.7 合同
        "crm.contract.list_team",
        "crm.contract.create",
        "crm.contract.edit",
        "crm.contract.sign",
        "crm.contract.approve",
        "crm.contract.delete",
        # v0.7 订单
        "crm.order.list_team",
        "crm.order.list_territory",
        "crm.order.assign",
        "crm.order.approve",
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

# 商城商家端内置角色（Phase1 种子化，见 05-角色权限#roles）
SYSTEM_ROLE_SHOP_ADMIN = "shop_admin"
SYSTEM_ROLE_SHOP_CONTENT = "shop_content"
SYSTEM_ROLE_SHOP_SUPPORT = "shop_support"
SYSTEM_ROLE_SHOP_CLERK = "shop_clerk"

SHOP_BUILTIN_ROLE_CODES: frozenset[str] = frozenset(
    {
        SYSTEM_ROLE_SHOP_ADMIN,
        SYSTEM_ROLE_SHOP_CONTENT,
        SYSTEM_ROLE_SHOP_SUPPORT,
        SYSTEM_ROLE_SHOP_CLERK,
    }
)

SHOP_ADMIN_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(SHOP_MERCHANT_PERMISSIONS) - frozenset(
    {
        "shop.role.manage",
        "shop.channel.write",  # 租户级公域对接（选链路/路径/回调验通）仅企业管理员
    }
)

SHOP_CONTENT_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "shop.analytics.read",
        "shop.content.read",
        "shop.content.write",
        "shop.product.delete",
        "shop.product.publish",
        "shop.product.read",
        "shop.product.submit_review",
        "shop.product.write",
        "shop.subscription.usage.read",
    }
)

SHOP_SUPPORT_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "shop.analytics.read",
        "shop.buyer.list_all",
        "shop.buyer.view",
        "shop.content.read",
        "shop.entitlement.list_all",
        "shop.entitlement.revoke",
        "shop.entitlement.view",
        "shop.invoice.list_all",
        "shop.invoice.process",
        "shop.invoice.view",
        "shop.order.export",
        "shop.order.list_all",
        "shop.order.refund",
        "shop.order.resend_notify",
        "shop.order.view",
        "shop.product.read",
        "shop.redemption.read",
        "shop.subscription.usage.read",
    }
)

SHOP_CLERK_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "shop.redemption.execute",
        "shop.redemption.list_own",
        "shop.redemption.read",
    }
)


def membership_is_shop_clerk(membership) -> bool:
    """对照 #a08-clerk：店员壳判定。"""
    role = getattr(membership, "role", None) if membership is not None else None
    return getattr(role, "code", None) == SYSTEM_ROLE_SHOP_CLERK

SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    SYSTEM_ROLE_SHOP_ADMIN: SHOP_ADMIN_DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_SHOP_CONTENT: SHOP_CONTENT_DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_SHOP_SUPPORT: SHOP_SUPPORT_DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_SHOP_CLERK: SHOP_CLERK_DEFAULT_PERMISSIONS,
}

# 平台商城子角色（挂接 platform_admin 账号，Phase1 可选模板）
PLATFORM_SHOP_ROLE_OPS = "platform_shop_ops"
PLATFORM_SHOP_ROLE_CS = "platform_shop_cs"
PLATFORM_SHOP_ROLE_FINANCE = "platform_shop_finance"

PLATFORM_SHOP_ROLE_CODES: frozenset[str] = frozenset(
    {
        PLATFORM_SHOP_ROLE_OPS,
        PLATFORM_SHOP_ROLE_CS,
        PLATFORM_SHOP_ROLE_FINANCE,
    }
)

PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "platform.shop.analytics",
        "platform.shop.approve",
        "platform.shop.merchant.assign",
        "platform.shop.merchant.list_all",
        "platform.shop.merchant.manage",
        "platform.shop.merchant.read",
        "platform.shop.merchant.tag",
        "platform.shop.merchant.tag.manage",
        "platform.shop.moderate",
        "platform.shop.plan.manage",
        "platform.shop.product.force_off",
        "platform.shop.product.review",
        "platform.shop.subscription.manage",
        "platform.shop.subscription.read",
    }
)

PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "platform.shop.analytics",
        "platform.shop.merchant.list_assigned",
        "platform.shop.merchant.read",
        "platform.shop.merchant.tag",
        "platform.shop.onboarding.initiate",
        "platform.shop.subscription.read",
    }
)

PLATFORM_SHOP_FINANCE_DEFAULT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "platform.shop.analytics",
        "platform.shop.fee.manage",
        "platform.shop.settlement",
        "platform.shop.subscription.read",
    }
)

PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    PLATFORM_SHOP_ROLE_OPS: PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS,
    PLATFORM_SHOP_ROLE_CS: PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS,
    PLATFORM_SHOP_ROLE_FINANCE: PLATFORM_SHOP_FINANCE_DEFAULT_PERMISSIONS,
}

PLATFORM_SHOP_PERMISSION_LABELS: dict[str, str] = {
    "platform.shop.analytics": "经营看板只读",
    "platform.shop.approve": "入驻审核",
    "platform.shop.channel": "公域渠道与支付进件",
    "platform.shop.fee.manage": "类目与费率",
    "platform.shop.merchant.assign": "分配管家",
    "platform.shop.merchant.list_all": "全站商家数据范围",
    "platform.shop.merchant.list_assigned": "仅看分配给自己的商家",
    "platform.shop.merchant.manage": "暂停/恢复",
    "platform.shop.merchant.read": "商家列表/详情 + 跟进写",
    "platform.shop.merchant.tag": "挂接已有标签",
    "platform.shop.merchant.tag.manage": "新建标签名",
    "platform.shop.moderate": "违规稽查",
    "platform.shop.onboarding.initiate": "帮客户发起入驻",
    "platform.shop.plan.manage": "套餐配置",
    "platform.shop.product.force_off": "商品强制下架",
    "platform.shop.product.review": "商品人审",
    "platform.shop.settlement": "清结算写",
    "platform.shop.subscription.manage": "开通/续费",
    "platform.shop.subscription.read": "查看套餐/到期",
    "platform.user.manage": "管理其他运营账号",
}

# P08-A 矩阵展示顺序（含默认未授予项，对照 06#p08a）
PLATFORM_SHOP_ROLE_MATRIX_CODES: dict[str, tuple[str, ...]] = {
    PLATFORM_SHOP_ROLE_CS: (
        "platform.shop.merchant.list_assigned",
        "platform.shop.merchant.read",
        "platform.shop.merchant.tag",
        "platform.shop.merchant.tag.manage",
        "platform.shop.onboarding.initiate",
        "platform.shop.subscription.read",
        "platform.shop.analytics",
        "platform.shop.approve",
        "platform.shop.subscription.manage",
        "platform.shop.merchant.manage",
        "platform.shop.merchant.assign",
    ),
    PLATFORM_SHOP_ROLE_OPS: (
        "platform.shop.merchant.list_all",
        "platform.shop.merchant.assign",
        "platform.shop.merchant.read",
        "platform.shop.merchant.tag",
        "platform.shop.merchant.tag.manage",
        "platform.shop.onboarding.initiate",
        "platform.shop.approve",
        "platform.shop.merchant.manage",
        "platform.shop.plan.manage",
        "platform.shop.subscription.manage",
        "platform.shop.product.review",
        "platform.shop.moderate",
        "platform.shop.product.force_off",
        "platform.shop.analytics",
        "platform.shop.settlement",
        "platform.user.manage",
    ),
    PLATFORM_SHOP_ROLE_FINANCE: (
        "platform.shop.settlement",
        "platform.shop.fee.manage",
        "platform.shop.subscription.read",
        "platform.shop.analytics",
        "platform.shop.approve",
        "platform.shop.subscription.manage",
        "platform.shop.merchant.manage",
    ),
}

PLATFORM_SHOP_ROLE_META: tuple[dict[str, str], ...] = (
    {
        "code": "",
        "name": "平台超管",
        "code_label": "platform_admin",
        "summary": "全部 platform.shop.* + 主站租户/账号管理",
    },
    {
        "code": PLATFORM_SHOP_ROLE_OPS,
        "name": "日常运营",
        "code_label": PLATFORM_SHOP_ROLE_OPS,
        "summary": "入驻/审核/暂停恢复、套餐开通、稽查；list_all 全站商家",
    },
    {
        "code": PLATFORM_SHOP_ROLE_CS,
        "name": "商家管家",
        "code_label": PLATFORM_SHOP_ROLE_CS,
        "summary": "仅 list_assigned 所辖客户 · 代建入驻 · 续费跟进 · 无审核/暂停/开通写",
    },
    {
        "code": PLATFORM_SHOP_ROLE_FINANCE,
        "name": "财务结算",
        "code_label": PLATFORM_SHOP_ROLE_FINANCE,
        "summary": "清结算、对账、费率只读、看板只读",
    },
)

PLATFORM_ADMIN_ROLE = "platform_admin"
