<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) await auth.fetchMe()
})

const menuItems = [
  { path: '/admin/contents', title: '全站内容', icon: 'Document' },
  { path: '/admin/tenants', title: '企业管理', icon: 'OfficeBuilding' },
  { path: '/admin/users', title: '账号管理', icon: 'User' },
  { path: '/admin/assistants', title: 'AI 助手', icon: 'MagicStick' },
  { path: '/admin/knowledge', title: '公共知识库', icon: 'Collection' },
  { path: '/admin/platform-llm', title: '平台 AI', icon: 'Cpu' },
]

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => route.meta.title || '管理后台')

function handleLogout() {
  auth.logout()
  router.push('/login')
}

const displayName = computed(
  () => auth.user?.phone || auth.user?.display_name || '管理员',
)
</script>

<template>
  <div class="admin-shell">
    <header class="admin-header">
      <div class="admin-header__left">
        <span class="admin-logo">管理后台</span>
        <el-tag type="warning" size="small">platform_admin</el-tag>
      </div>
      <div class="admin-header__right">
        <el-button link type="primary" @click="router.push('/dashboard')">用户工作台</el-button>
        <span>{{ displayName }}</span>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <div class="admin-body">
      <aside class="admin-sidebar">
        <el-menu :default-active="activeMenu" router class="admin-menu">
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </aside>
      <main class="admin-main">
        <h2 class="admin-main__title">{{ pageTitle }}</h2>
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f5f5f5;
}

.admin-header {
  height: 56px;
  background: #001529;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.admin-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-logo {
  font-size: 18px;
  font-weight: 600;
}

.admin-header__right {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
}

.admin-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.admin-sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
}

.admin-menu {
  border-right: none;
}

.admin-main {
  flex: 1;
  padding: 24px;
  overflow: auto;
}

.admin-main__title {
  font-size: 20px;
  margin: 0 0 16px;
}
</style>
