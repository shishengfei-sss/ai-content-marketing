/** 路由/菜单与权限 code 映射（与 SRS §2.5 一致） */
export const PERMISSION_GROUPS = [
  {
    label: '工作台',
    items: [
      { code: 'dashboard.view', label: '访问工作台' },
      { code: 'dashboard.view_all', label: '全公司统计', requires: 'dashboard.view' },
    ],
  },
  {
    label: '数据看板',
    items: [
      { code: 'analytics.view', label: '访问数据看板' },
      { code: 'analytics.view_all', label: '全公司统计', requires: 'analytics.view' },
    ],
  },
  {
    label: '内容',
    items: [
      { code: 'content.create', label: '营销创作' },
      { code: 'content.list_own', label: '内容库（本人）' },
      { code: 'content.view_own', label: '查看本人文章' },
      { code: 'content.list_all', label: '内容库（全公司）', requires: 'content.list_own' },
      { code: 'content.view_all', label: '查看任意文章', requires: 'content.view_own' },
      { code: 'content.edit', label: '编辑内容' },
      { code: 'content.delete', label: '删除内容' },
      { code: 'content.export', label: '导出' },
      { code: 'content.schedule', label: '发布日历' },
      { code: 'content.publish', label: '发布公众号' },
    ],
  },
  {
    label: '知识库',
    items: [
      { code: 'knowledge.view', label: '查看知识库' },
      { code: 'knowledge.manage', label: '管理知识库', requires: 'knowledge.view' },
    ],
  },
  {
    label: '设置',
    items: [
      { code: 'preference.manage', label: '我的偏好' },
      { code: 'brand.manage', label: '品牌设置' },
      { code: 'wechat.manage', label: '公众号绑定' },
      { code: 'llm.manage', label: 'AI 模型' },
      { code: 'tenant.manage', label: '企业信息' },
    ],
  },
  {
    label: '团队',
    items: [
      { code: 'team.member.view', label: '查看成员' },
      { code: 'team.member.manage', label: '管理成员', requires: 'team.member.view' },
      { code: 'team.role.manage', label: '管理角色', requires: 'team.member.view' },
    ],
  },
]

export const NAV_ITEMS = [
  { path: '/dashboard', title: '工作台', icon: 'Odometer', permission: 'dashboard.view' },
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
  { path: '/settings', title: '设置', icon: 'Setting' },
]

export function hasAnyPermission(permissions, codes) {
  const set = new Set(permissions || [])
  return codes.some((c) => set.has(c))
}

export function hasPermission(permissions, code) {
  return (permissions || []).includes(code)
}
