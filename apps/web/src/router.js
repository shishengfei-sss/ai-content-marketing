import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
import AdminLayout from './layouts/AdminLayout.vue'
import { useAuthStore } from './stores/auth'
import { NAV_ITEMS, hasAnyPermission, hasPermission } from './config/permissions'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('./views/ForgotPassword.vue'),
    meta: { public: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('./views/Register.vue'),
    meta: { public: true },
  },
  {
    path: '/select-tenant',
    name: 'SelectTenant',
    component: () => import('./views/SelectTenant.vue'),
  },
  {
    path: '/admin',
    component: AdminLayout,
    meta: { platformAdmin: true },
    redirect: '/admin/contents',
    children: [
      {
        path: 'contents',
        name: 'AdminContents',
        component: () => import('./views/admin/AdminContents.vue'),
        meta: { title: '全站内容', platformAdmin: true },
      },
      {
        path: 'assistants',
        name: 'AdminAssistants',
        component: () => import('./views/admin/AdminAssistants.vue'),
        meta: { title: '营销顾问配置', platformAdmin: true },
      },
      {
        path: 'knowledge',
        name: 'AdminKnowledge',
        component: () => import('./views/admin/AdminKnowledge.vue'),
        meta: { title: '公共知识库', platformAdmin: true },
      },
      {
        path: 'tenants',
        name: 'AdminTenants',
        component: () => import('./views/admin/AdminTenants.vue'),
        meta: { title: '企业管理', platformAdmin: true },
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('./views/admin/AdminUsers.vue'),
        meta: { title: '账号管理', platformAdmin: true },
      },
      {
        path: 'platform-llm',
        name: 'AdminPlatformLlm',
        component: () => import('./views/admin/AdminPlatformLlm.vue'),
        meta: { title: '平台 AI', platformAdmin: true },
      },
      {
        path: 'platform-tender-leads',
        name: 'AdminPlatformTenderLeads',
        component: () => import('./views/admin/AdminPlatformTenderLeads.vue'),
        meta: { title: '招标线索公共池', platformAdmin: true },
      },
    ],
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('./views/Dashboard.vue'),
        meta: { title: '工作台', permission: 'dashboard.view' },
      },
      {
        path: 'create',
        name: 'Create',
        component: () => import('./views/Create.vue'),
        meta: { title: '营销创作', permission: 'content.create' },
      },
      {
        path: 'agent',
        name: 'Agent',
        component: () => import('./views/Create.vue'),
        meta: { title: 'AI 顾问', permission: 'content.create' },
      },
      {
        path: 'agent/workflows',
        name: 'AgentWorkflows',
        component: () => import('./views/Create.vue'),
        meta: { title: 'AI 工作流', permission: 'content.create' },
      },
      {
        path: 'contents',
        name: 'Contents',
        component: () => import('./views/ContentLibrary.vue'),
        meta: { title: '内容库', permissionAny: ['content.list_own', 'content.list_all'] },
      },
      {
        path: 'calendar',
        name: 'Calendar',
        component: () => import('./views/Calendar.vue'),
        meta: { title: '发布日历', permission: 'content.schedule' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('./views/Knowledge.vue'),
        meta: { title: '知识库', permissionAny: ['knowledge.view', 'knowledge.manage'] },
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('./views/Analytics.vue'),
        meta: { title: '数据看板', permission: 'analytics.view' },
      },
      {
        path: 'crm/leads',
        name: 'CrmLeads',
        component: () => import('./views/crm/Leads.vue'),
        meta: {
          title: '线索',
          permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all'],
        },
      },
      {
        path: 'crm/tender-leads',
        name: 'CrmTenderLeads',
        component: () => import('./views/crm/TenderLeads.vue'),
        meta: {
          title: '招标线索',
          permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all', 'crm.lead.view'],
        },
      },
      {
        path: 'crm/tender-lead-analytics',
        name: 'CrmTenderLeadAnalytics',
        component: () => import('./views/crm/TenderLeadAnalytics.vue'),
        meta: {
          title: '招标线索看板',
          permissionAny: ['crm.lead.list_all', 'crm.lead.list_team', 'crm.pipeline.manage', 'analytics.view'],
        },
      },
      {
        path: 'crm/lead-pools',
        name: 'CrmLeadPools',
        component: () => import('./views/crm/LeadPools.vue'),
        meta: {
          title: '线索公海',
          permissionAny: ['crm.lead.list_own', 'crm.lead.list_team', 'crm.lead.list_territory', 'crm.lead.list_all'],
        },
      },
      {
        path: 'crm/leads/:id',
        name: 'CrmLeadDetail',
        component: () => import('./views/crm/LeadDetail.vue'),
        meta: { title: '线索详情', permission: 'crm.lead.view' },
      },
      {
        path: 'crm/customers',
        name: 'CrmCustomers',
        component: () => import('./views/crm/Customers.vue'),
        meta: {
          title: '客户',
          permissionAny: ['crm.customer.list_own', 'crm.customer.list_team', 'crm.customer.list_territory', 'crm.customer.list_all'],
        },
      },
      {
        path: 'crm/customer-pools',
        name: 'CrmCustomerPools',
        component: () => import('./views/crm/CustomerPools.vue'),
        meta: {
          title: '客户公海',
          permissionAny: [
            'crm.customer.list_own',
            'crm.customer.list_team',
            'crm.customer.list_territory',
            'crm.customer.list_all',
          ],
        },
      },
      {
        path: 'crm/customers/:id',
        name: 'CrmCustomerDetail',
        component: () => import('./views/crm/CustomerDetail.vue'),
        meta: { title: '客户详情', permission: 'crm.customer.view' },
      },
      {
        path: 'crm/tasks',
        name: 'CrmTasks',
        component: () => import('./views/crm/Tasks.vue'),
        meta: {
          title: '任务',
          permissionAny: ['crm.task.list_own', 'crm.task.list_team', 'crm.task.list_territory', 'crm.task.list_all'],
        },
      },
      {
        path: 'crm/campaigns',
        name: 'CrmCampaigns',
        component: () => import('./views/crm/Campaigns.vue'),
        meta: {
          title: '营销活动',
          permissionAny: ['crm.campaign.list_own', 'crm.campaign.list_team', 'crm.campaign.list_territory', 'crm.campaign.list_all'],
        },
      },
      {
        path: 'crm/campaigns/:id',
        name: 'CrmCampaignDetail',
        component: () => import('./views/crm/CampaignDetail.vue'),
        meta: { title: '活动详情', permission: 'crm.campaign.view' },
      },
      {
        path: 'crm/deals',
        name: 'CrmDeals',
        component: () => import('./views/crm/Deals.vue'),
        meta: {
          title: '商机',
          permissionAny: ['crm.deal.list_own', 'crm.deal.list_team', 'crm.deal.list_territory', 'crm.deal.list_all'],
        },
      },
      {
        path: 'crm/deals/:id',
        name: 'CrmDealDetail',
        component: () => import('./views/crm/DealDetail.vue'),
        meta: { title: '商机详情', permission: 'crm.deal.view' },
      },
      {
        path: 'crm/deal-funnel',
        name: 'CrmDealFunnel',
        component: () => import('./views/crm/DealFunnel.vue'),
        meta: {
          title: '销售漏斗',
          permissionAny: ['crm.deal.list_own', 'crm.deal.list_team', 'crm.deal.list_territory', 'crm.deal.list_all'],
        },
      },
      {
        path: 'crm/trade-report',
        name: 'CrmTradeReport',
        component: () => import('./views/crm/TradeReport.vue'),
        meta: {
          title: '交易报表',
          permissionAny: [
            'crm.order.list_own',
            'crm.order.list_all',
            'crm.payment.list_own',
            'crm.payment.list_all',
            'analytics.view_all',
          ],
        },
      },
      {
        path: 'crm/lead-insights',
        name: 'CrmLeadInsights',
        component: () => import('./views/crm/LeadInsights.vue'),
        meta: {
          title: '线索洞察',
          permissionAny: [
            'crm.lead.list_own',
            'crm.lead.list_all',
            'crm.customer.list_own',
            'crm.customer.list_all',
            'analytics.view_all',
          ],
        },
      },
      {
        path: 'crm/quotes',
        name: 'CrmQuotes',
        component: () => import('./views/crm/Quotes.vue'),
        meta: {
          title: '报价',
          permissionAny: ['crm.quote.list_own', 'crm.quote.list_all'],
        },
      },
      {
        path: 'crm/quotes/cpq/new',
        name: 'CrmCpqQuoteCreate',
        component: () => import('./views/crm/CpqQuoteCreate.vue'),
        meta: { title: 'CPQ 配置报价', permission: 'crm.quote.create' },
      },
      {
        path: 'crm/quotes/:id',
        name: 'CrmQuoteDetail',
        component: () => import('./views/crm/QuoteDetail.vue'),
        meta: { title: '报价详情', permission: 'crm.quote.view' },
      },
      {
        path: 'crm/contracts',
        name: 'CrmContracts',
        component: () => import('./views/crm/Contracts.vue'),
        meta: {
          title: '合同',
          permissionAny: ['crm.contract.list_own', 'crm.contract.list_all'],
        },
      },
      {
        path: 'crm/contracts/:id',
        name: 'CrmContractDetail',
        component: () => import('./views/crm/ContractDetail.vue'),
        meta: { title: '合同详情', permission: 'crm.contract.view' },
      },
      {
        path: 'crm/orders',
        name: 'CrmOrders',
        component: () => import('./views/crm/Orders.vue'),
        meta: {
          title: '订单',
          permissionAny: ['crm.order.list_own', 'crm.order.list_team', 'crm.order.list_territory', 'crm.order.list_all'],
        },
      },
      {
        path: 'crm/orders/:id',
        name: 'CrmOrderDetail',
        component: () => import('./views/crm/OrderDetail.vue'),
        meta: { title: '订单详情', permission: 'crm.order.view' },
      },
      {
        path: 'crm/payments',
        name: 'CrmPayments',
        component: () => import('./views/crm/Payments.vue'),
        meta: {
          title: '回款',
          permissionAny: ['crm.payment.list_own', 'crm.payment.list_team', 'crm.payment.list_territory', 'crm.payment.list_all'],
        },
      },
      {
        path: 'crm/payments/:id',
        name: 'CrmPaymentDetail',
        component: () => import('./views/crm/PaymentDetail.vue'),
        meta: { title: '回款详情', permission: 'crm.payment.view' },
      },
      {
        path: 'crm/products',
        name: 'CrmProducts',
        component: () => import('./views/crm/Products.vue'),
        meta: { title: '产品目录', permission: 'crm.product.manage' },
      },
      {
        path: 'crm/products/:id',
        name: 'CrmProductDetail',
        component: () => import('./views/crm/ProductDetail.vue'),
        meta: { title: '产品详情', permission: 'crm.product.manage' },
      },
      {
        path: 'settings/pipeline',
        name: 'SettingsPipeline',
        component: () => import('./views/SettingsPipeline.vue'),
        meta: { title: '销售管道', permission: 'crm.pipeline.manage' },
      },
      {
        path: 'settings/number-rules',
        name: 'SettingsNumberRules',
        component: () => import('./views/SettingsNumberRules.vue'),
        meta: { title: '编号规则', permission: 'crm.pipeline.manage' },
      },
      {
        path: 'settings/product-master-data',
        name: 'SettingsProductMasterData',
        component: () => import('./views/SettingsProductMasterData.vue'),
        meta: { title: '产品基础数据', permission: 'crm.product.manage' },
      },
      {
        path: 'settings/campaign-channels',
        name: 'SettingsCampaignChannels',
        component: () => import('./views/SettingsCampaignChannels.vue'),
        meta: { title: '活动投放渠道', permission: 'crm.campaign.manage' },
      },
      {
        path: 'settings/lead-pools',
        name: 'SettingsLeadPools',
        component: () => import('./views/SettingsLeadPools.vue'),
        meta: { title: '线索公海', permission: 'crm.lead.edit' },
      },
      {
        path: 'settings/customer-pools',
        name: 'SettingsCustomerPools',
        component: () => import('./views/SettingsCustomerPools.vue'),
        meta: { title: '客户公海', permission: 'crm.customer.edit' },
      },
      {
        path: 'settings/icp',
        name: 'SettingsIcp',
        component: () => import('./views/SettingsIcp.vue'),
        meta: {
          title: 'ICP 画像',
          permissionAny: ['crm.lead.edit', 'crm.pipeline.manage'],
        },
      },
      {
        path: 'settings/assignment-rules',
        name: 'SettingsAssignmentRules',
        component: () => import('./views/SettingsAssignmentRules.vue'),
        meta: {
          title: '线索分配规则',
          permissionAny: ['crm.lead.edit', 'crm.pipeline.manage'],
        },
      },
      {
        path: 'settings/lead-scoring',
        name: 'SettingsLeadScoring',
        component: () => import('./views/SettingsLeadScoring.vue'),
        meta: {
          title: '线索评分规则',
          permissionAny: ['crm.lead.edit', 'crm.pipeline.manage'],
        },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('./views/Settings.vue'),
        meta: { title: '设置' },
      },
      {
        path: 'settings/tenant',
        name: 'SettingsTenant',
        component: () => import('./views/SettingsTenant.vue'),
        meta: { title: '企业信息', permission: 'tenant.manage' },
      },
      {
        path: 'settings/team',
        name: 'SettingsTeam',
        component: () => import('./views/SettingsTeam.vue'),
        meta: { title: '角色与成员', permissionAny: ['team.member.view', 'team.role.manage'] },
      },
      {
        path: 'settings/members',
        name: 'SettingsMembers',
        component: () => import('./views/SettingsTeam.vue'),
        meta: { title: '角色与成员', permissionAny: ['team.member.view', 'team.role.manage'] },
      },
      {
        path: 'settings/crm-org',
        name: 'SettingsCrmOrg',
        component: () => import('./views/SettingsCrmOrg.vue'),
        meta: { title: '销售组织', permission: 'crm.org.manage' },
      },
      {
        path: 'settings/crm-schema',
        name: 'SettingsSchema',
        component: () => import('./views/SettingsSchema.vue'),
        meta: { title: '表单字段', permission: 'crm.schema.manage' },
      },
      {
        path: 'settings/tags',
        name: 'SettingsTags',
        component: () => import('./views/SettingsTags.vue'),
        meta: {
          title: '业务标签',
          permissionAny: ['crm.schema.manage', 'crm.pipeline.manage', 'crm.lead.edit', 'crm.customer.edit'],
        },
      },
      {
        path: 'settings/llm',
        name: 'SettingsLlm',
        component: () => import('./views/SettingsLlm.vue'),
        meta: { title: 'AI 模型', permission: 'llm.manage' },
      },
      {
        path: 'settings/wechat',
        name: 'SettingsWechat',
        component: () => import('./views/SettingsWechat.vue'),
        meta: { title: '公众号绑定', permission: 'wechat.manage' },
      },
      {
        path: 'settings/brand',
        name: 'SettingsBrand',
        component: () => import('./views/SettingsBrand.vue'),
        meta: { title: '品牌设置', permission: 'brand.manage' },
      },
      {
        path: 'settings/preference',
        name: 'SettingsPreference',
        component: () => import('./views/SettingsPreference.vue'),
        meta: { title: '我的偏好', permission: 'preference.manage' },
      },
      {
        path: 'settings/memory',
        name: 'SettingsMemory',
        component: () => import('./views/SettingsMemory.vue'),
        meta: { title: 'AI 记忆', permission: 'content.create' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function firstAllowedPath(permissions) {
  for (const item of NAV_ITEMS) {
    if (!item.permission && !item.permissionAny) return item.path
    if (item.permissionAny && hasAnyPermission(permissions, item.permissionAny)) return item.path
    if (item.permission && hasPermission(permissions, item.permission)) return item.path
  }
  return '/settings'
}

async function ensureUser(auth) {
  if (!auth.isLoggedIn || auth.user) return
  try {
    await auth.fetchMe()
  } catch {
    /* fetchMe 失败时会 logout；无效 token 不应阻塞公开页 */
  }
}

function redirectIfPermissionDenied(to, permissions) {
  if (to.meta.permission && !hasPermission(permissions, to.meta.permission)) {
    const fallback = firstAllowedPath(permissions)
    return to.path === fallback ? undefined : fallback
  }
  if (to.meta.permissionAny && !hasAnyPermission(permissions, to.meta.permissionAny)) {
    const fallback = firstAllowedPath(permissions)
    return to.path === fallback ? undefined : fallback
  }
  return undefined
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return '/login'
  }

  if (!auth.isLoggedIn) return

  await ensureUser(auth)
  if (!auth.isLoggedIn) {
    return to.meta.public ? undefined : '/login'
  }

  if (auth.user?.role === 'platform_admin') {
    if (to.meta.platformAdmin) return
    if (to.meta.public) return '/admin'
    return '/admin'
  }

  if (
    !to.meta.public &&
    to.path !== '/select-tenant' &&
    (auth.needSelectTenant || auth.user?.need_select_tenant)
  ) {
    return '/select-tenant'
  }

  if (to.meta.public && (to.path === '/login' || to.path === '/register')) {
    if (auth.needSelectTenant || auth.user?.need_select_tenant) return '/select-tenant'
    const home = firstAllowedPath(auth.permissions)
    return to.path === home ? undefined : home
  }

  if (to.meta.platformAdmin && auth.user?.role !== 'platform_admin') {
    const fallback = firstAllowedPath(auth.permissions)
    return to.path === fallback ? undefined : fallback
  }

  if (!to.meta.public) {
    return redirectIfPermissionDenied(to, auth.permissions)
  }
})

export default router
