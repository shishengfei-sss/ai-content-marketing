import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
import AdminLayout from './layouts/AdminLayout.vue'
import { useAuthStore } from './stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('./views/Register.vue'),
    meta: { public: true },
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
        path: 'users',
        name: 'AdminUsers',
        component: () => import('./views/admin/AdminUsers.vue'),
        meta: { title: '用户管理', platformAdmin: true },
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
        meta: { title: '工作台' },
      },
      {
        path: 'create',
        name: 'Create',
        component: () => import('./views/Create.vue'),
        meta: { title: '营销创作' },
      },
      {
        path: 'contents',
        name: 'Contents',
        component: () => import('./views/ContentLibrary.vue'),
        meta: { title: '内容库' },
      },
      {
        path: 'calendar',
        name: 'Calendar',
        component: () => import('./views/Calendar.vue'),
        meta: { title: '发布日历' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('./views/Knowledge.vue'),
        meta: { title: '知识库' },
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('./views/Analytics.vue'),
        meta: { title: '数据看板' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('./views/Settings.vue'),
        meta: { title: '设置' },
      },
      {
        path: 'settings/llm',
        name: 'SettingsLlm',
        component: () => import('./views/SettingsLlm.vue'),
        meta: { title: 'AI 模型' },
      },
      {
        path: 'settings/wechat',
        name: 'SettingsWechat',
        component: () => import('./views/SettingsWechat.vue'),
        meta: { title: '公众号绑定' },
      },
      {
        path: 'settings/brand',
        name: 'SettingsBrand',
        component: () => import('./views/SettingsBrand.vue'),
        meta: { title: '品牌设置' },
      },
      {
        path: 'settings/preference',
        name: 'SettingsPreference',
        component: () => import('./views/SettingsPreference.vue'),
        meta: { title: '我的偏好' },
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
  if (to.meta.public && auth.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    if (!auth.user) await auth.fetchMe()
    return auth.user?.role === 'platform_admin' ? '/admin' : '/dashboard'
  }
  if (to.meta.platformAdmin) {
    if (!auth.user) await auth.fetchMe()
    if (auth.user?.role !== 'platform_admin') {
      return '/dashboard'
    }
  }
})

export default router
