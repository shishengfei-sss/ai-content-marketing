/** 路由/菜单与权限 code 映射（与 SRS §2.5 一致） */

/** @typedef {{ code: string, label: string, requires?: string }} PermItem */
/** @typedef {{ type: 'scope', menu: string, items: PermItem[] } | { type: 'inline', items: PermItem[] }} PermRow */

/** @type {{ label: string, rows: PermRow[] }[]} */
export const PERMISSION_GROUPS = [
  {
    label: '工作台',
    rows: [
      {
        type: 'scope',
        menu: '工作台',
        items: [
          { code: 'dashboard.view', label: '访问' },
          { code: 'dashboard.view_all', label: '全公司统计', requires: 'dashboard.view' },
        ],
      },
    ],
  },
  {
    label: '数据看板',
    rows: [
      {
        type: 'scope',
        menu: '数据看板',
        items: [
          { code: 'analytics.view', label: '访问' },
          { code: 'analytics.view_all', label: '全公司统计', requires: 'analytics.view' },
        ],
      },
    ],
  },
  {
    label: '内容',
    rows: [
      {
        type: 'inline',
        items: [{ code: 'content.create', label: '营销创作' }],
      },
      {
        type: 'scope',
        menu: '内容库',
        items: [
          { code: 'content.list_own', label: '本人' },
          { code: 'content.list_all', label: '全公司', requires: 'content.list_own' },
        ],
      },
      {
        type: 'scope',
        menu: '查看文章',
        items: [
          { code: 'content.view_own', label: '本人' },
          { code: 'content.view_all', label: '任意', requires: 'content.view_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'content.edit', label: '编辑内容' },
          { code: 'content.delete', label: '删除内容' },
          { code: 'content.export', label: '导出' },
          { code: 'content.schedule', label: '发布日历' },
          { code: 'content.publish', label: '发布公众号' },
        ],
      },
    ],
  },
  {
    label: '知识库',
    rows: [
      {
        type: 'scope',
        menu: '知识库',
        items: [
          { code: 'knowledge.view', label: '查看' },
          { code: 'knowledge.manage', label: '管理', requires: 'knowledge.view' },
        ],
      },
    ],
  },
  {
    label: '设置',
    rows: [
      {
        type: 'inline',
        items: [
          { code: 'preference.manage', label: '我的偏好' },
          { code: 'brand.manage', label: '品牌设置' },
          { code: 'wechat.manage', label: '公众号绑定' },
          { code: 'llm.manage', label: 'AI 模型' },
          { code: 'tenant.manage', label: '企业信息' },
        ],
      },
    ],
  },
  {
    label: '团队',
    rows: [
      {
        type: 'scope',
        menu: '成员',
        items: [
          { code: 'team.member.view', label: '查看' },
          { code: 'team.member.manage', label: '管理', requires: 'team.member.view' },
        ],
      },
      {
        type: 'inline',
        items: [{ code: 'team.role.manage', label: '管理角色', requires: 'team.member.view' }],
      },
    ],
  },
  {
    label: 'CRM — 线索',
    rows: [
      {
        type: 'scope',
        menu: '线索列表',
        items: [
          { code: 'crm.lead.list_own', label: '本人' },
          { code: 'crm.lead.list_team', label: '下级', requires: 'crm.lead.list_own' },
          { code: 'crm.lead.list_territory', label: '地区', requires: 'crm.lead.list_own' },
          { code: 'crm.lead.list_all', label: '全公司', requires: 'crm.lead.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.lead.view', label: '查看', requires: 'crm.lead.list_own' },
          { code: 'crm.lead.create', label: '新建', requires: 'crm.lead.view' },
          { code: 'crm.lead.edit', label: '编辑', requires: 'crm.lead.view' },
          { code: 'crm.lead.assign', label: '分配负责人', requires: 'crm.lead.edit' },
          { code: 'crm.lead.convert', label: '转化客户', requires: 'crm.lead.edit' },
          { code: 'crm.lead.delete', label: '删除', requires: 'crm.lead.edit' },
          { code: 'crm.lead.import', label: '导入', requires: 'crm.lead.create' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 客户',
    rows: [
      {
        type: 'scope',
        menu: '客户列表',
        items: [
          { code: 'crm.customer.list_own', label: '本人' },
          { code: 'crm.customer.list_team', label: '下级', requires: 'crm.customer.list_own' },
          { code: 'crm.customer.list_territory', label: '地区', requires: 'crm.customer.list_own' },
          { code: 'crm.customer.list_all', label: '全公司', requires: 'crm.customer.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.customer.view', label: '查看', requires: 'crm.customer.list_own' },
          { code: 'crm.customer.create', label: '新建', requires: 'crm.customer.view' },
          { code: 'crm.customer.edit', label: '编辑', requires: 'crm.customer.view' },
          { code: 'crm.customer.assign', label: '分配负责人', requires: 'crm.customer.edit' },
          { code: 'crm.customer.delete', label: '删除', requires: 'crm.customer.edit' },
          { code: 'crm.customer.import', label: '导入', requires: 'crm.customer.create' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 任务',
    rows: [
      {
        type: 'scope',
        menu: '任务列表',
        items: [
          { code: 'crm.task.list_own', label: '本人' },
          { code: 'crm.task.list_team', label: '下级', requires: 'crm.task.list_own' },
          { code: 'crm.task.list_territory', label: '地区', requires: 'crm.task.list_own' },
          { code: 'crm.task.list_all', label: '全公司', requires: 'crm.task.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.task.create', label: '新建', requires: 'crm.task.list_own' },
          { code: 'crm.task.edit', label: '编辑', requires: 'crm.task.list_own' },
          { code: 'crm.task.assign', label: '指派执行人', requires: 'crm.task.edit' },
          { code: 'crm.task.delete', label: '删除', requires: 'crm.task.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 营销活动',
    rows: [
      {
        type: 'scope',
        menu: '活动列表',
        items: [
          { code: 'crm.campaign.list_own', label: '本人' },
          { code: 'crm.campaign.list_team', label: '下级', requires: 'crm.campaign.list_own' },
          { code: 'crm.campaign.list_territory', label: '地区', requires: 'crm.campaign.list_own' },
          { code: 'crm.campaign.list_all', label: '全公司', requires: 'crm.campaign.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.campaign.view', label: '查看', requires: 'crm.campaign.list_own' },
          { code: 'crm.campaign.create', label: '新建', requires: 'crm.campaign.view' },
          { code: 'crm.campaign.edit', label: '编辑', requires: 'crm.campaign.view' },
          { code: 'crm.campaign.manage', label: '管理状态', requires: 'crm.campaign.edit' },
          { code: 'crm.campaign.delete', label: '删除', requires: 'crm.campaign.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 组织与表单',
    rows: [
      {
        type: 'inline',
        items: [
          { code: 'crm.org.manage', label: '销售组织' },
          { code: 'crm.schema.manage', label: '表单字段管理' },
          { code: 'crm.activity.create', label: '写跟进记录' },
          { code: 'crm.pipeline.manage', label: '销售管道' },
          { code: 'crm.product.manage', label: '产品目录' },
          { code: 'crm.product.import', label: '产品导入', requires: 'crm.product.manage' },
        ],
      },
      {
        type: 'scope',
        menu: '列表视图',
        items: [
          { code: 'crm.view.save_own', label: '保存私有' },
          { code: 'crm.view.manage_public', label: '管理公开', requires: 'crm.view.save_own' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 商机',
    rows: [
      {
        type: 'scope',
        menu: '商机列表',
        items: [
          { code: 'crm.deal.list_own', label: '本人' },
          { code: 'crm.deal.list_team', label: '下级', requires: 'crm.deal.list_own' },
          { code: 'crm.deal.list_territory', label: '地区', requires: 'crm.deal.list_own' },
          { code: 'crm.deal.list_all', label: '全公司', requires: 'crm.deal.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.deal.view', label: '查看', requires: 'crm.deal.list_own' },
          { code: 'crm.deal.create', label: '新建', requires: 'crm.deal.view' },
          { code: 'crm.deal.edit', label: '编辑', requires: 'crm.deal.view' },
          { code: 'crm.deal.assign', label: '分配负责人', requires: 'crm.deal.edit' },
          { code: 'crm.deal.convert', label: '转订单', requires: 'crm.deal.view' },
          { code: 'crm.deal.close', label: '关闭赢单/输单', requires: 'crm.deal.edit' },
          { code: 'crm.deal.reopen', label: '重开商机', requires: 'crm.deal.close' },
          { code: 'crm.deal.delete', label: '删除', requires: 'crm.deal.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 报价',
    rows: [
      {
        type: 'inline',
        items: [
          { code: 'crm.quote.list_own', label: '本人列表' },
          { code: 'crm.quote.list_team', label: '团队列表', requires: 'crm.quote.list_own' },
          { code: 'crm.quote.list_all', label: '全公司列表', requires: 'crm.quote.list_own' },
          { code: 'crm.quote.view', label: '查看', requires: 'crm.quote.list_own' },
          { code: 'crm.quote.create', label: '新建', requires: 'crm.quote.view' },
          { code: 'crm.quote.edit', label: '编辑', requires: 'crm.quote.view' },
          { code: 'crm.quote.send', label: '发送', requires: 'crm.quote.edit' },
          { code: 'crm.quote.accept', label: '标记接受', requires: 'crm.quote.edit' },
          { code: 'crm.quote.delete', label: '删除', requires: 'crm.quote.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 合同',
    rows: [
      {
        type: 'inline',
        items: [
          { code: 'crm.contract.list_own', label: '本人列表' },
          { code: 'crm.contract.list_team', label: '团队列表', requires: 'crm.contract.list_own' },
          { code: 'crm.contract.list_all', label: '全公司列表', requires: 'crm.contract.list_own' },
          { code: 'crm.contract.view', label: '查看', requires: 'crm.contract.list_own' },
          { code: 'crm.contract.create', label: '新建', requires: 'crm.contract.view' },
          { code: 'crm.contract.edit', label: '编辑', requires: 'crm.contract.view' },
          { code: 'crm.contract.sign', label: '签署', requires: 'crm.contract.edit' },
          { code: 'crm.contract.approve', label: '审批', requires: 'crm.contract.view' },
          { code: 'crm.contract.delete', label: '删除', requires: 'crm.contract.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 订单',
    rows: [
      {
        type: 'scope',
        menu: '订单列表',
        items: [
          { code: 'crm.order.list_own', label: '本人' },
          { code: 'crm.order.list_team', label: '下级', requires: 'crm.order.list_own' },
          { code: 'crm.order.list_territory', label: '地区', requires: 'crm.order.list_own' },
          { code: 'crm.order.list_all', label: '全公司', requires: 'crm.order.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.order.view', label: '查看', requires: 'crm.order.list_own' },
          { code: 'crm.order.create', label: '新建', requires: 'crm.order.view' },
          { code: 'crm.order.edit', label: '编辑', requires: 'crm.order.view' },
          { code: 'crm.order.assign', label: '分配负责人', requires: 'crm.order.edit' },
          { code: 'crm.order.place', label: '下单确认', requires: 'crm.order.edit' },
          { code: 'crm.order.convert', label: '由商机/报价/合同转单', requires: 'crm.order.create' },
          { code: 'crm.order.delete', label: '删除', requires: 'crm.order.edit' },
        ],
      },
    ],
  },
  {
    label: 'CRM — 收款',
    rows: [
      {
        type: 'scope',
        menu: '回款列表',
        items: [
          { code: 'crm.payment.list_own', label: '本人' },
          { code: 'crm.payment.list_team', label: '下级', requires: 'crm.payment.list_own' },
          { code: 'crm.payment.list_territory', label: '地区', requires: 'crm.payment.list_own' },
          { code: 'crm.payment.list_all', label: '全公司', requires: 'crm.payment.list_own' },
        ],
      },
      {
        type: 'inline',
        items: [
          { code: 'crm.payment.view', label: '查看', requires: 'crm.payment.list_own' },
          { code: 'crm.payment.create', label: '登记回款', requires: 'crm.payment.view' },
          { code: 'crm.payment.edit', label: '编辑', requires: 'crm.payment.view' },
          { code: 'crm.payment.confirm', label: '确认到账', requires: 'crm.payment.edit' },
          { code: 'crm.payment.reverse', label: '冲销', requires: 'crm.payment.confirm' },
          { code: 'crm.payment.delete', label: '删除', requires: 'crm.payment.edit' },
        ],
      },
    ],
  },
]

/** 侧栏二级菜单：顶层为分组或单页入口；children 为二级项 */
export const NAV_MENUS = [
  {
    key: 'dashboard',
    path: '/dashboard',
    title: '工作台',
    icon: 'Odometer',
    permission: 'dashboard.view',
  },
  {
    key: 'content',
    title: '内容营销',
    icon: 'EditPen',
    children: [
      { path: '/create', title: '营销创作', icon: 'EditPen', permission: 'content.create' },
      {
        path: '/contents',
        title: '内容库',
        icon: 'Document',
        permissionAny: ['content.list_own', 'content.list_all'],
      },
      { path: '/calendar', title: '发布日历', icon: 'Calendar', permission: 'content.schedule' },
      {
        path: '/knowledge',
        title: '知识库',
        icon: 'Collection',
        permissionAny: ['knowledge.view', 'knowledge.manage'],
      },
      { path: '/analytics', title: '数据看板', icon: 'DataLine', permission: 'analytics.view' },
    ],
  },
  {
    key: 'crm-customer',
    title: '客户管理',
    icon: 'User',
    children: [
      {
        path: '/crm/leads',
        title: '线索',
        icon: 'User',
        permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all'],
      },
      {
        path: '/crm/tender-leads',
        title: '招标线索',
        icon: 'Tickets',
        permissionAny: [
          'crm.lead.list_own',
          'crm.lead.list_team',
          'crm.lead.list_territory',
          'crm.lead.list_all',
          'crm.lead.view',
        ],
      },
      {
        path: '/crm/tender-lead-analytics',
        title: '招标线索看板',
        icon: 'DataAnalysis',
        permissionAny: ['crm.lead.list_all', 'crm.lead.list_team', 'crm.pipeline.manage', 'analytics.view'],
      },
      {
        path: '/crm/lead-pools',
        title: '线索公海',
        icon: 'Coin',
        permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all'],
      },
      {
        path: '/crm/lead-insights',
        title: '线索洞察',
        icon: 'DataAnalysis',
        permissionAny: [
          'crm.lead.list_own',
          'crm.lead.list_all',
          'crm.customer.list_own',
          'crm.customer.list_all',
          'analytics.view_all',
        ],
      },
      {
        path: '/crm/customers',
        title: '客户',
        icon: 'OfficeBuilding',
        permissionAny: [
          'crm.customer.list_own',
          'crm.customer.list_team',
          'crm.customer.list_territory',
          'crm.customer.list_all',
        ],
      },
      {
        path: '/crm/customer-pools',
        title: '客户公海',
        icon: 'Coin',
        permissionAny: [
          'crm.customer.list_own',
          'crm.customer.list_team',
          'crm.customer.list_territory',
          'crm.customer.list_all',
        ],
      },
      {
        path: '/crm/tasks',
        title: '任务',
        icon: 'List',
        permissionAny: ['crm.task.list_own', 'crm.task.list_team', 'crm.task.list_territory', 'crm.task.list_all'],
      },
      {
        path: '/crm/campaigns',
        title: '营销活动',
        icon: 'Promotion',
        permissionAny: [
          'crm.campaign.list_own',
          'crm.campaign.list_team',
          'crm.campaign.list_territory',
          'crm.campaign.list_all',
        ],
      },
    ],
  },
  {
    key: 'crm-sales',
    title: '销售交易',
    icon: 'TrendCharts',
    children: [
      {
        path: '/crm/deals',
        title: '商机',
        icon: 'TrendCharts',
        permissionAny: ['crm.deal.list_own', 'crm.deal.list_team', 'crm.deal.list_territory', 'crm.deal.list_all'],
      },
      {
        path: '/crm/deal-funnel',
        title: '销售漏斗',
        icon: 'Filter',
        permissionAny: ['crm.deal.list_own', 'crm.deal.list_team', 'crm.deal.list_territory', 'crm.deal.list_all'],
      },
      {
        path: '/crm/quotes',
        title: '报价',
        icon: 'Document',
        permissionAny: ['crm.quote.list_own', 'crm.quote.list_team', 'crm.quote.list_all'],
      },
      {
        path: '/crm/contracts',
        title: '合同',
        icon: 'Notebook',
        permissionAny: ['crm.contract.list_own', 'crm.contract.list_team', 'crm.contract.list_all'],
      },
      {
        path: '/crm/orders',
        title: '订单',
        icon: 'List',
        permissionAny: ['crm.order.list_own', 'crm.order.list_team', 'crm.order.list_territory', 'crm.order.list_all'],
      },
      {
        path: '/crm/payments',
        title: '回款',
        icon: 'Money',
        permissionAny: [
          'crm.payment.list_own',
          'crm.payment.list_team',
          'crm.payment.list_territory',
          'crm.payment.list_all',
        ],
      },
      {
        path: '/crm/products',
        title: '产品',
        icon: 'Box',
        permission: 'crm.product.manage',
      },
      {
        path: '/crm/trade-report',
        title: '交易报表',
        icon: 'Histogram',
        permissionAny: [
          'crm.order.list_own',
          'crm.order.list_all',
          'crm.payment.list_own',
          'crm.payment.list_all',
          'analytics.view_all',
        ],
      },
    ],
  },
  {
    key: 'shop-onboarding',
    path: '/shop/onboarding',
    title: '开通商城',
    icon: 'ShoppingBag',
    shopOnboardingEntry: true,
  },
  {
    key: 'shop-overview',
    path: '/shop/overview',
    title: '概览',
    icon: 'DataAnalysis',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.analytics.read'],
  },
  {
    key: 'shop-products',
    path: '/shop/products',
    title: '商品管理',
    icon: 'Goods',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.product.read', 'shop.product.write'],
  },
  {
    key: 'shop-orders',
    path: '/shop/orders',
    title: '订单管理',
    icon: 'List',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.order.list_all', 'shop.order.view'],
  },
  {
    key: 'shop-buyers',
    path: '/shop/buyers',
    title: '买家',
    icon: 'User',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.buyer.list_all', 'shop.buyer.view'],
  },
  {
    key: 'shop-entitlements',
    path: '/shop/entitlements',
    title: '权益',
    icon: 'Medal',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.entitlement.list_all', 'shop.entitlement.view'],
  },
  {
    key: 'shop-verifications',
    path: '/shop/verifications',
    title: '核销台',
    icon: 'Checked',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.redemption.read', 'shop.redemption.execute'],
  },
  {
    key: 'shop-columns',
    path: '/shop/columns',
    title: '专栏管理',
    icon: 'Collection',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.content.read', 'shop.content.write'],
  },
  {
    key: 'shop-digital-packages',
    path: '/shop/digital-packages',
    title: '资料包',
    icon: 'FolderOpened',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.content.read', 'shop.content.write'],
  },
  {
    key: 'shop-service-offers',
    path: '/shop/service-offers',
    title: '服务定义',
    icon: 'Tickets',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.content.read', 'shop.content.write'],
  },
  {
    key: 'shop-bookings',
    path: '/shop/bookings',
    title: '预约管理',
    icon: 'Calendar',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.redemption.read'],
  },
  {
    key: 'shop-invoices',
    path: '/shop/invoices',
    title: '发票管理',
    icon: 'Tickets',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.invoice.list_all', 'shop.invoice.process'],
  },
  {
    key: 'shop-channel-mappings',
    path: '/shop/channel-mappings',
    title: '公域对接',
    icon: 'Link',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.channel.read', 'shop.channel.map'],
  },
  {
    key: 'shop-stores',
    path: '/shop/stores',
    title: '店铺管理',
    icon: 'Shop',
    shopEntitlementsEntry: true,
    permissionAny: ['shop.store.manage', 'shop.store.settings.read'],
  },
  {
    key: 'shop-settings-hub',
    path: '/shop/settings',
    title: '设置',
    icon: 'Setting',
    shopEntitlementsEntry: true,
    // 有任一设置子页权限即可进中心（卡片内再按权显隐）
    permissionAny: [
      'shop.settings.read',
      'shop.settings.write',
      'shop.store.settings.read',
      'shop.store.settings.write',
      'shop.subscription.usage.read',
      'shop.role.manage',
      'team.member.view',
      'shop.channel.write',
      'shop.channel.read',
    ],
  },
  { key: 'settings', path: '/settings', title: '企业设置', icon: 'Tools' },
]

/** 扁平叶子菜单（路由守卫 / 兼容旧引用） */
export const NAV_ITEMS = NAV_MENUS.flatMap((menu) => (menu.children ? menu.children : [menu]))

export function hasAnyPermission(permissions, codes) {
  const set = new Set(permissions || [])
  return codes.some((c) => set.has(c))
}

export function hasPermission(permissions, code) {
  return (permissions || []).includes(code)
}

export function isPermDisabled(permissions, item) {
  return item.requires && !permissions.includes(item.requires)
}
