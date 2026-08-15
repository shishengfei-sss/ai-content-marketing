import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
import AdminLayout from './layouts/AdminLayout.vue'
import { useAuthStore, WORKSPACE_MERCHANT, WORKSPACE_PLATFORM } from './stores/auth'
import { NAV_ITEMS, hasAnyPermission, hasPermission } from './config/permissions'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/Login.vue'),
    meta: { public: true, workspaceMode: WORKSPACE_MERCHANT },
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('./views/Login.vue'),
    meta: { public: true, workspaceMode: WORKSPACE_PLATFORM, platformLogin: true },
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
      {
        path: 'shop/dashboard',
        name: 'AdminShopDashboard',
        component: () => import('./views/admin/shop/PlatformDashboard.vue'),
        meta: { title: '概览', platformAdmin: true },
      },
      {
        path: 'shop/merchants',
        name: 'AdminShopMerchants',
        component: () => import('./views/admin/shop/MerchantsList.vue'),
        meta: { title: '商家租户', platformAdmin: true },
      },
      {
        path: 'shop/merchants/:tenantId',
        name: 'AdminShopMerchantDetail',
        component: () => import('./views/admin/shop/MerchantDetail.vue'),
        meta: { title: '商家详情', platformAdmin: true },
      },
      {
        path: 'shop/onboarding',
        name: 'AdminShopOnboarding',
        component: () => import('./views/admin/shop/OnboardingApplications.vue'),
        meta: { title: '入驻审核', platformAdmin: true },
      },
      {
        path: 'shop/plans',
        name: 'AdminShopPlans',
        component: () => import('./views/admin/shop/PlanConfig.vue'),
        meta: { title: '套餐配置', platformAdmin: true },
      },
      {
        path: 'shop/subscriptions',
        name: 'AdminShopSubscriptions',
        component: () => import('./views/admin/shop/Subscriptions.vue'),
        meta: { title: '订阅台账', platformAdmin: true },
      },
      {
        path: 'shop/product-reviews',
        name: 'AdminShopProductReviews',
        component: () => import('./views/admin/shop/ProductReviews.vue'),
        meta: { title: '商品审核', platformAdmin: true },
      },
      {
        path: 'shop/categories',
        name: 'AdminShopCategories',
        component: () => import('./views/admin/shop/CategoriesList.vue'),
        meta: { title: '类目与费率', platformAdmin: true },
      },
      {
        path: 'shop/roles-codes',
        name: 'AdminShopRolesAndCodes',
        component: () => import('./views/admin/shop/RolesAndCodes.vue'),
        meta: { title: '角色与编码', platformAdmin: true },
      },
      {
        path: 'shop/channels',
        name: 'AdminShopChannels',
        component: () => import('./views/admin/shop/ChannelPayConfig.vue'),
        meta: { title: '渠道与支付', platformAdmin: true },
      },
      {
        path: 'shop/settlements',
        name: 'AdminShopSettlements',
        component: () => import('./views/admin/shop/Settlements.vue'),
        meta: { title: '清结算', platformAdmin: true },
      },
      {
        path: 'shop/sms',
        name: 'AdminShopSms',
        component: () => import('./views/admin/shop/SmsManagement.vue'),
        meta: { title: '短信管理', platformAdmin: true },
      },
      {
        path: 'shop/moderation',
        name: 'AdminShopModeration',
        component: () => import('./views/admin/shop/ModerationCases.vue'),
        meta: { title: '违规稽查', platformAdmin: true },
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
        path: 'shop/overview',
        name: 'ShopOverview',
        component: () => import('./views/shop/DashboardOverview.vue'),
        meta: { title: '交易看板', permissionAny: ['shop.analytics.read'] },
      },
      {
        path: 'shop/dashboard',
        redirect: '/shop/overview',
      },
      {
        path: 'shop/console',
        redirect: '/shop/overview',
      },
      {
        path: 'shop/onboarding',
        name: 'ShopOnboarding',
        component: () => import('./views/shop/OnboardingApply.vue'),
        meta: { title: '开通商城' },
      },
      {
        path: 'shop/subscription',
        name: 'ShopSubscription',
        component: () => import('./views/shop/SubscriptionEntitlements.vue'),
        meta: {
          title: '套餐信息',
          permissionAny: ['shop.subscription.usage.read'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/payment',
        name: 'ShopPaymentOnboarding',
        component: () => import('./views/shop/PaymentOnboarding.vue'),
        meta: {
          title: '支付与进件',
          permissionAny: ['shop.settings.read', 'shop.settings.write'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/sms-settings',
        name: 'ShopSmsClaimSettings',
        component: () => import('./views/shop/SmsClaimSettings.vue'),
        meta: {
          title: '短信与领权',
          permissionAny: ['shop.settings.read', 'shop.settings.write'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/roles-members',
        name: 'ShopRolesMembers',
        component: () => import('./views/shop/RolesMembers.vue'),
        meta: {
          title: '角色与成员',
          permissionAny: ['shop.role.manage', 'team.member.view'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/products',
        name: 'ShopProducts',
        component: () => import('./views/shop/ProductsList.vue'),
        meta: { title: '商品管理', permissionAny: ['shop.product.read', 'shop.product.write'] },
      },
      {
        path: 'shop/products/new',
        name: 'ShopProductNew',
        component: () => import('./views/shop/ProductEdit.vue'),
        meta: { title: '新建商品', permissionAny: ['shop.product.write'] },
      },
      {
        path: 'shop/products/:id',
        name: 'ShopProductEdit',
        component: () => import('./views/shop/ProductEdit.vue'),
        meta: { title: '商品编辑', permissionAny: ['shop.product.read', 'shop.product.write'] },
      },
      {
        path: 'shop/orders',
        name: 'ShopOrders',
        component: () => import('./views/shop/OrdersList.vue'),
        meta: { title: '订单管理', permissionAny: ['shop.order.list_all', 'shop.order.view'] },
      },
      {
        path: 'shop/orders/:id',
        name: 'ShopOrderDetail',
        component: () => import('./views/shop/OrderDetail.vue'),
        meta: { title: '订单详情', permissionAny: ['shop.order.view', 'shop.order.list_all'] },
      },
      {
        path: 'shop/buyers',
        name: 'ShopBuyers',
        component: () => import('./views/shop/BuyersList.vue'),
        meta: { title: '买家', permissionAny: ['shop.buyer.list_all', 'shop.buyer.view'] },
      },
      {
        path: 'shop/buyers/:id',
        name: 'ShopBuyerDetail',
        component: () => import('./views/shop/BuyerDetail.vue'),
        meta: { title: '买家详情', permissionAny: ['shop.buyer.view', 'shop.buyer.list_all'] },
      },
      {
        path: 'shop/entitlements',
        name: 'ShopEntitlements',
        component: () => import('./views/shop/EntitlementsList.vue'),
        meta: {
          title: '权益',
          permissionAny: ['shop.entitlement.list_all', 'shop.entitlement.view'],
        },
      },
      {
        path: 'shop/verifications',
        name: 'ShopVerifications',
        component: () => import('./views/shop/Verifications.vue'),
        meta: {
          title: '核销台',
          permissionAny: ['shop.redemption.read', 'shop.redemption.execute'],
        },
      },
      {
        path: 'shop/redemptions',
        redirect: '/shop/verifications',
      },
      {
        path: 'shop/columns',
        name: 'ShopColumns',
        component: () => import('./views/shop/ColumnsList.vue'),
        meta: { title: '专栏管理', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/columns/:id',
        name: 'ShopColumnEdit',
        component: () => import('./views/shop/ColumnEdit.vue'),
        meta: { title: '专栏与课时', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/digital-packages',
        name: 'ShopDigitalPackages',
        component: () => import('./views/shop/DigitalPackagesList.vue'),
        meta: { title: '资料包', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/digital-packages/:id',
        name: 'ShopDigitalPackageEdit',
        component: () => import('./views/shop/DigitalPackageEdit.vue'),
        meta: { title: '资料包编辑', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/service-offers',
        name: 'ShopServiceOffers',
        component: () => import('./views/shop/ServiceOffersList.vue'),
        meta: { title: '服务定义', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/service-offers/:id',
        name: 'ShopServiceOfferEdit',
        component: () => import('./views/shop/ServiceOfferEdit.vue'),
        meta: { title: '服务与时段', permissionAny: ['shop.content.read', 'shop.content.write'] },
      },
      {
        path: 'shop/bookings',
        name: 'ShopBookings',
        component: () => import('./views/shop/BookingsList.vue'),
        meta: { title: '预约管理', permissionAny: ['shop.redemption.read'] },
      },
      {
        path: 'shop/invoices',
        name: 'ShopInvoices',
        component: () => import('./views/shop/InvoicesList.vue'),
        meta: {
          title: '发票管理',
          permissionAny: ['shop.invoice.list_all', 'shop.invoice.process'],
        },
      },
      {
        path: 'shop/channel-mappings',
        name: 'ShopChannelMappings',
        component: () => import('./views/shop/ChannelMappings.vue'),
        meta: {
          title: '公域映射',
          permissionAny: ['shop.channel.read', 'shop.channel.map'],
        },
      },
      {
        path: 'shop/channel-settings',
        name: 'ShopChannelSettings',
        component: () => import('./views/shop/ChannelSettings.vue'),
        meta: {
          title: '公域对接',
          permissionAny: ['shop.channel.read', 'shop.channel.map', 'shop.channel.write'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/settings',
        name: 'ShopSettingsHub',
        component: () => import('./views/shop/SettingsHub.vue'),
        meta: { title: '设置' },
      },
      {
        path: 'shop/store-settings',
        name: 'ShopStoreSettings',
        component: () => import('./views/shop/StoreSettings.vue'),
        meta: {
          title: '单店设置',
          permissionAny: ['shop.store.settings.read', 'shop.store.settings.write'],
          shopSettingsHub: true,
        },
      },
      {
        path: 'shop/stores',
        name: 'ShopStores',
        component: () => import('./views/shop/StoresList.vue'),
        meta: {
          title: '店铺管理',
          permissionAny: ['shop.store.manage', 'shop.store.settings.read'],
        },
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
        path: 'settings/account',
        name: 'SettingsAccount',
        component: () => import('./views/SettingsAccount.vue'),
        meta: { title: '我的账号' },
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

function firstAllowedPath(permissions, auth) {
  if (auth?.isShopClerk) return '/shop/verifications'
  for (const item of NAV_ITEMS) {
    if (item.shopOnboardingEntry || item.shopEntitlementsEntry) {
      if (item.permissionAny && hasAnyPermission(permissions, item.permissionAny)) return item.path
      if (item.permission && hasPermission(permissions, item.permission)) return item.path
      continue
    }
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

function redirectIfPermissionDenied(to, permissions, auth) {
  if (auth?.isShopClerk && !to.path.startsWith('/shop/verifications')) {
    return '/shop/verifications'
  }
  if (to.meta.permission && !hasPermission(permissions, to.meta.permission)) {
    const fallback = firstAllowedPath(permissions, auth)
    return to.path === fallback ? undefined : fallback
  }
  if (to.meta.permissionAny && !hasAnyPermission(permissions, to.meta.permissionAny)) {
    const fallback = firstAllowedPath(permissions, auth)
    return to.path === fallback ? undefined : fallback
  }
  return undefined
}

function loginHomePath(auth) {
  if (auth.isPlatformWorkspace) return '/admin'
  if (auth.needSelectTenant || auth.user?.need_select_tenant) return '/select-tenant'
  if (auth.isShopClerk) return '/shop/verifications'
  return firstAllowedPath(auth.permissions, auth)
}

function isPublicAuthRoute(path) {
  return path === '/login' || path === '/register' || path === '/admin/login'
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return to.meta.platformAdmin || to.path.startsWith('/admin') ? '/admin/login' : '/login'
  }

  if (!auth.isLoggedIn) return

  await ensureUser(auth)
  if (!auth.isLoggedIn) {
    return to.meta.public ? undefined : '/login'
  }

  if (auth.isPlatformWorkspace) {
    if (to.meta.platformAdmin) return
    if (to.meta.public) return loginHomePath(auth)
    return '/admin'
  }

  if (to.meta.platformAdmin) {
    const fallback = loginHomePath(auth)
    return to.path === fallback ? undefined : fallback
  }

  if (
    !to.meta.public &&
    to.path !== '/select-tenant' &&
    (auth.needSelectTenant || auth.user?.need_select_tenant)
  ) {
    return '/select-tenant'
  }

  if (to.meta.public && isPublicAuthRoute(to.path)) {
    const home = loginHomePath(auth)
    return to.path === home ? undefined : home
  }

  if (!to.meta.public) {
    return redirectIfPermissionDenied(to, auth.permissions, auth)
  }
})

export default router
