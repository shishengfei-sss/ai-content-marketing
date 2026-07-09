<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { NAV_ITEMS, hasAnyPermission, hasPermission } from '../config/permissions'
import { useAuthStore } from '../stores/auth'
import { usePinnedViews } from '../composables/usePinnedViews'
import { unpinSavedView } from '../composables/useCrmSavedViews'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { leadPinnedViews, customerPinnedViews, loadPinnedViews, pinnedForPath, viewRoute, viewIndex } =
  usePinnedViews()

const unpinningId = ref(null)

onMounted(() => {
  if (auth.isLoggedIn && !auth.user) auth.fetchMe()
  if (auth.isLoggedIn) loadPinnedViews()
  window.addEventListener('crm:pinned-views-changed', onPinnedChanged)
})

onUnmounted(() => {
  window.removeEventListener('crm:pinned-views-changed', onPinnedChanged)
})

function onPinnedChanged() {
  loadPinnedViews(true)
}

async function handleUnpinView(view) {
  if (!view?.id || unpinningId.value) return
  unpinningId.value = view.id
  try {
    await unpinSavedView(view)
    await loadPinnedViews(true)
  } catch (e) {
    ElMessage.error(e.message || '取消钉选失败')
  } finally {
    unpinningId.value = null
  }
}

const menuItems = computed(() => {
  const p = auth.permissions
  return NAV_ITEMS.filter((item) => {
    if (!item.permission && !item.permissionAny) return true
    if (item.permissionAny) return hasAnyPermission(p, item.permissionAny)
    return hasPermission(p, item.permission)
  })
})

function hasPinnedChildren(item) {
  return pinnedForPath(item.path).length > 0
}

const activeMenu = computed(() => {
  if (route.path.startsWith('/settings')) return '/settings'
  const viewId = route.query.view_id
  if (viewId && (route.path === '/crm/leads' || route.path === '/crm/customers')) {
    return viewIndex(route.path, String(viewId))
  }
  return route.path
})

const pageTitle = computed(() => route.meta.title || '工作台')

const tenants = computed(() => auth.user?.tenants || [])
const showTenantSwitcher = computed(() => tenants.value.length > 1)
const currentTenantLabel = computed(
  () => auth.activeTenantName || auth.user?.active_tenant?.name || '当前公司',
)

async function switchCompany(tenantId) {
  if (tenantId === auth.user?.active_tenant?.id) return
  try {
    await auth.switchTenant(tenantId)
    ElMessage.success('已切换公司')
    router.replace('/dashboard')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

const displayName = computed(
  () => auth.user?.display_name || auth.user?.phone || '用户',
)
const avatarChar = computed(() => displayName.value.charAt(0))
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-header__left">
        <div class="app-logo">
          <span class="app-logo__icon">AI</span>
          <span class="app-logo__text">智营获客</span>
        </div>
        <el-dropdown v-if="showTenantSwitcher" trigger="click" @command="switchCompany">
          <span class="tenant-switch">
            {{ currentTenantLabel }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="t in tenants"
                :key="t.id"
                :command="t.id"
                :disabled="t.id === auth.user?.active_tenant?.id"
              >
                {{ t.name }} · {{ t.role_name }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <span v-else class="app-header__subtitle">{{ currentTenantLabel }}</span>
      </div>
      <div class="app-header__center">
        <el-input
          placeholder="搜索内容、选题..."
          prefix-icon="Search"
          class="app-header__search"
          clearable
        />
      </div>
      <div class="app-header__right">
        <el-dropdown trigger="click">
          <div class="app-header__user">
            <el-avatar :size="32" style="background: #4096ff">{{ avatarChar }}</el-avatar>
            <span>{{ displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="auth.user?.role === 'platform_admin'" @click="router.push('/admin')">
                管理后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="app-body">
      <aside class="app-sidebar">
        <el-menu :default-active="activeMenu" router class="app-sidebar__menu">
          <template v-for="item in menuItems" :key="item.path">
            <el-sub-menu v-if="hasPinnedChildren(item)" :index="item.path">
              <template #title>
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.title }}</span>
              </template>
              <el-menu-item :index="item.path" :route="{ path: item.path }">
                全部{{ item.title }}
              </el-menu-item>
              <el-menu-item
                v-for="view in pinnedForPath(item.path)"
                :key="view.id"
                :index="viewIndex(item.path, view.id)"
                :route="viewRoute(item.path, view.id)"
                class="pinned-view-menu-item"
              >
                <span class="pinned-view-item">
                  <span class="pinned-view-item__label">{{ view.name }}</span>
                  <el-tooltip content="取消钉选" placement="right">
                    <span
                      class="pinned-view-item__unpin"
                      role="button"
                      tabindex="0"
                      @click.stop.prevent="handleUnpinView(view)"
                      @keydown.enter.prevent="handleUnpinView(view)"
                    >
                      <el-icon><StarFilled /></el-icon>
                    </span>
                  </el-tooltip>
                </span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </aside>

      <main class="app-main">
        <div class="app-main__breadcrumb">
          <span class="app-main__title">{{ pageTitle }}</span>
          <el-tag v-if="auth.user?.active_tenant" type="info" size="small">{{ currentTenantLabel }}</el-tag>
        </div>
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-header {
  height: var(--header-height);
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 18px;
}

.app-logo__icon {
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.tenant-switch,
.app-header__subtitle {
  font-size: 13px;
  opacity: 0.9;
  padding-left: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.3);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.app-header__center {
  flex: 1;
  max-width: 400px;
  margin: 0 40px;
}

.app-header__search {
  width: 100%;
}

.app-header__search :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.15);
  box-shadow: none;
  border: none;
}

.app-header__search :deep(.el-input__inner) {
  color: #fff;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-header__user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
}

.app-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.app-sidebar {
  width: var(--sidebar-width);
  background: #fff;
  border-right: 1px solid var(--color-border);
  flex-shrink: 0;
}

.app-sidebar__menu {
  border-right: none;
  padding-top: 8px;
}

.app-sidebar__menu :deep(.el-menu-item.is-active) {
  background: #e6f4ff;
  color: var(--color-primary);
}

.pinned-view-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 4px;
  min-width: 0;
}

.pinned-view-item__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pinned-view-item__unpin {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  flex-shrink: 0;
  opacity: 0.85;
  color: var(--el-color-warning);
  cursor: pointer;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
}

.pinned-view-menu-item:hover .pinned-view-item__unpin,
.pinned-view-item__unpin:focus-visible {
  opacity: 1;
}

.pinned-view-item__unpin:hover {
  background: rgba(230, 162, 60, 0.12);
}

.app-main {
  flex: 1;
  padding: 20px;
  overflow: auto;
  background: var(--color-bg-page);
}

.app-main__breadcrumb {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.app-main__title {
  font-size: var(--font-size-xl);
  font-weight: 600;
}
</style>
