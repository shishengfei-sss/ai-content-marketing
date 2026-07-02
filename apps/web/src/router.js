import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
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
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return '/login'
  }
  if (to.meta.public && auth.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
    return '/dashboard'
  }
})

export default router
