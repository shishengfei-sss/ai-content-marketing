import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
import AdminLayout from './layouts/AdminLayout.vue'
import { useAuthStore } from './stores/auth'
import { hasAnyPermission, hasPermission } from './config/permissions'

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
        meta: { title: 'AI 助手', platformAdmin: true },
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return '/login'
  }
  if (auth.isLoggedIn && !to.meta.public && to.path !== '/select-tenant') {
    if (!auth.user) await auth.fetchMe()
    if (auth.user?.role !== 'platform_admin' && (auth.needSelectTenant || auth.user?.need_select_tenant)) {
      return '/select-tenant'
    }
  }
  if (to.meta.public && auth.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    if (!auth.user) await auth.fetchMe()
    if (auth.user?.role === 'platform_admin') return '/admin'
    if (auth.needSelectTenant || auth.user?.need_select_tenant) return '/select-tenant'
    return '/dashboard'
  }
  if (to.meta.platformAdmin) {
    if (!auth.user) await auth.fetchMe()
    if (auth.user?.role !== 'platform_admin') {
      return '/dashboard'
    }
  }
  if (!to.meta.public && auth.isLoggedIn && (to.meta.permission || to.meta.permissionAny)) {
    if (!auth.user) await auth.fetchMe()
    const p = auth.permissions
    if (to.meta.permission && !hasPermission(p, to.meta.permission)) {
      return '/dashboard'
    }
    if (to.meta.permissionAny && !hasAnyPermission(p, to.meta.permissionAny)) {
      return '/dashboard'
    }
  }
})

export default router
