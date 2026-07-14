/** H5 权限与菜单（与 Web / SRS §2.5 一致） */
export function hasPermission(permissions, code) {
  return (permissions || []).includes(code)
}

export function hasAnyPermission(permissions, codes) {
  const set = new Set(permissions || [])
  return codes.some((c) => set.has(c))
}

export function isPermDisabled(permissions, item) {
  return item.requires && !permissions.includes(item.requires)
}

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
      { type: 'inline', items: [{ code: 'content.create', label: '营销创作' }] },
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
      { type: 'inline', items: [{ code: 'team.role.manage', label: '管理角色', requires: 'team.member.view' }] },
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
]

export const CRM_MENU = [
  {
    title: '线索',
    desc: '跟进销售线索',
    url: '/pages/crm/leads',
    icon: '👤',
    iconColor: '#1677ff',
    permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all'],
  },
  {
    title: '客户',
    desc: '管理成交客户',
    url: '/pages/crm/customers',
    icon: '👥',
    iconColor: '#52c41a',
    permissionAny: ['crm.customer.list_own', 'crm.customer.list_team', 'crm.customer.list_territory', 'crm.customer.list_all'],
  },
  {
    title: '商机',
    desc: '跟进销售机会',
    url: '/pages/crm/deals',
    icon: '📈',
    iconColor: '#fa8c16',
    permissionAny: ['crm.deal.list_own', 'crm.deal.list_team', 'crm.deal.list_territory', 'crm.deal.list_all'],
  },
  {
    title: '订单',
    desc: '查看与管理订单',
    url: '/pages/crm/orders',
    icon: '💳',
    iconColor: '#0958d9',
    permissionAny: ['crm.order.list_own', 'crm.order.list_team', 'crm.order.list_territory', 'crm.order.list_all'],
  },
  {
    title: '报价',
    desc: '客户报价单',
    url: '/pages/crm/quotes',
    icon: '📄',
    iconColor: '#1677ff',
    permissionAny: ['crm.quote.list_own', 'crm.quote.list_all'],
  },
  {
    title: '合同',
    desc: '销售合同',
    url: '/pages/crm/contracts',
    icon: '📋',
    iconColor: '#722ed1',
    permissionAny: ['crm.contract.list_own', 'crm.contract.list_all'],
  },
  {
    title: '回款',
    desc: '回款登记与确认',
    url: '/pages/crm/payments',
    icon: '💰',
    iconColor: '#ff4d4f',
    permissionAny: [
      'crm.payment.list_own',
      'crm.payment.list_team',
      'crm.payment.list_territory',
      'crm.payment.list_all',
    ],
  },
  {
    title: '我的任务',
    desc: '待办与回访',
    url: '/pages/crm/tasks',
    icon: '📝',
    iconColor: '#1677ff',
    permissionAny: ['crm.task.list_own', 'crm.task.list_team', 'crm.task.list_territory', 'crm.task.list_all'],
  },
  {
    title: '营销活动',
    desc: '查看活动与线索',
    url: '/pages/crm/campaigns',
    icon: '🎯',
    iconColor: '#fa8c16',
    permissionAny: [
      'crm.campaign.list_own',
      'crm.campaign.list_team',
      'crm.campaign.list_territory',
      'crm.campaign.list_all',
    ],
  },
]

export function filterMenuByPermission(items, permissions) {
  return items.filter((item) => {
    if (item.permissionAny) return hasAnyPermission(permissions, item.permissionAny)
    return hasPermission(permissions, item.permission)
  })
}

export function hasAnyCrmListPermission(permissions) {
  return CRM_MENU.some((item) => hasAnyPermission(permissions, item.permissionAny))
}

export const MINE_MENU = [
  ...CRM_MENU,
  { title: '企业信息', url: '/pages/settings/tenant', permission: 'tenant.manage' },
  { title: '角色与成员', url: '/pages/settings/team', permissionAny: ['team.member.view', 'team.role.manage'] },
  { title: '我的偏好', url: '/pages/settings/preference', permission: 'preference.manage' },
  { title: 'AI 记忆', url: '/pages/settings/memory', permission: 'content.create' },
  { title: '公众号绑定', url: '/pages/wechat/wechat', permission: 'wechat.manage' },
]
