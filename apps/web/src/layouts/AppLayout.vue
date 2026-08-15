<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { NAV_MENUS, hasAnyPermission, hasPermission } from '../config/permissions'
import { useAuthStore, WORKSPACE_PLATFORM } from '../stores/auth'
import { usePinnedViews } from '../composables/usePinnedViews'
import { unpinSavedView } from '../composables/useCrmSavedViews'
import { clearCurrentShopId, useCurrentShop } from '../composables/useCurrentShop'
import CrmNotificationBell from '../components/crm/CrmNotificationBell.vue'
import { shopApi } from '../api/client'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { loadPinnedViews, pinnedForPath, viewRoute, viewIndex } = usePinnedViews()

const unpinningId = ref(null)
const shopOnboardingState = ref(null)
const {
  stores: shopStores,
  currentId: currentShopId,
  currentStore,
  planLabel: shopPlanLabel,
  roleLabel: shopRoleLabel,
  loadStores: loadShopStores,
  setCurrent: setCurrentShop,
} = useCurrentShop()

/** 对照 PRD 01-管理端UI.html #a01-select-spec · C13：顶栏「当前店铺」单选，级联 shop_id */

const showShopSwitcher = computed(
  () =>
    shopOnboardingState.value === 'onboarded' &&
    route.path.startsWith('/shop') &&
    !route.path.startsWith('/shop/onboarding') &&
    shopStores.value.length > 0,
)
const currentShopName = computed(() => currentStore.value?.name || '请选择店铺')
const shopSwitcherMeta = computed(() => {
  const parts = [shopPlanLabel.value, shopRoleLabel.value].filter(Boolean)
  return parts.join(' · ')
})

function onSwitchShop(id) {
  if (!id || String(id) === String(currentShopId.value)) return
  const s = shopStores.value.find((x) => String(x.id) === String(id))
  setCurrentShop(id)
  ElMessage.success(`已切换当前店：${s?.name || ''}`)
}

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      /* logout handled in store */
    }
  }
  if (auth.isLoggedIn) {
    loadPinnedViews()
    await loadShopOnboardingBanner()
  }
  window.addEventListener('crm:pinned-views-changed', onPinnedChanged)
})

onUnmounted(() => {
  window.removeEventListener('crm:pinned-views-changed', onPinnedChanged)
})

watch(
  () => [auth.isLoggedIn, auth.user?.active_tenant?.id],
  (now, prev) => {
    const prevTid = prev?.[1]
    const nowTid = now?.[1]
    if (prevTid && nowTid && prevTid !== nowTid) clearCurrentShopId()
    if (auth.isLoggedIn) loadShopOnboardingBanner()
    else shopOnboardingState.value = null
  },
)

async function loadShopOnboardingBanner() {
  if (!auth.isLoggedIn) {
    shopOnboardingState.value = null
    return
  }
  // 尚未拉到 me：先按未入驻展示，避免首屏空白
  if (!auth.user?.active_tenant) {
    shopOnboardingState.value = 'not_onboarded'
    return
  }
  try {
    const { data } = await shopApi.getOnboardingStatus()
    shopOnboardingState.value = data.state || 'not_onboarded'
    if (shopOnboardingState.value === 'onboarded') await loadShopStores()
  } catch (e) {
    // 接口未就绪/代理错误时仍引导开通，避免「看不见入口」
    console.warn('[shop] onboarding status failed', e?.message || e)
    shopOnboardingState.value = 'not_onboarded'
  }
}

const showShopBanner = computed(() => {
  if (auth.isShopClerk) return false
  // 开通商城页本身不再叠横幅（避免与表单重复）
  if (route.path.startsWith('/shop/onboarding')) return false
  return (
    shopOnboardingState.value === 'not_onboarded' ||
    shopOnboardingState.value === 'rejected' ||
    shopOnboardingState.value === 'reviewing'
  )
})
const shopBannerText = computed(() => {
  if (shopOnboardingState.value === 'rejected') return '入驻申请已驳回，请修改资料后重提'
  if (shopOnboardingState.value === 'reviewing') return '内容获客商城入驻审核中'
  return '开通内容获客商城，提交主体资质由平台审核（注册 ≠ 入驻）'
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

function itemVisible(item, permissions) {
  if (!item.permission && !item.permissionAny) return true
  if (item.permissionAny) return hasAnyPermission(permissions, item.permissionAny)
  return hasPermission(permissions, item.permission)
}

const menuItems = computed(() => {
  const p = auth.permissions
  if (auth.isShopClerk) {
    return NAV_MENUS.filter((menu) => menu.key === 'shop-verifications')
  }
  return NAV_MENUS.map((menu) => {
    if (menu.shopOnboardingEntry) {
      if (shopOnboardingState.value === 'onboarded') return null
      return menu
    }
    if (menu.shopEntitlementsEntry) {
      if (shopOnboardingState.value !== 'onboarded') return null
      return menu
    }
    if (!menu.children) {
      return itemVisible(menu, p) ? menu : null
    }
    const children = menu.children.filter((item) => itemVisible(item, p))
    if (!children.length) return null
    return { ...menu, children }
  }).filter(Boolean)
})

function hasPinnedChildren(item) {
  return pinnedForPath(item.path).length > 0
}

function pathMatchesItem(itemPath) {
  if (route.path === itemPath) return true
  if (itemPath !== '/' && route.path.startsWith(`${itemPath}/`)) return true
  return false
}

const activeMenu = computed(() => {
  if (route.path.startsWith('/settings')) return '/settings'
  if (route.meta?.shopSettingsHub) return '/shop/settings'
  const viewId = route.query.view_id
  if (viewId && (route.path === '/crm/leads' || route.path === '/crm/customers')) {
    return viewIndex(route.path, String(viewId))
  }
  return route.path
})

/** 当前路由所属分组/钉选子菜单默认展开 */
const defaultOpeneds = computed(() => {
  const open = []
  for (const menu of menuItems.value) {
    if (!menu.children) continue
    const activeChild = menu.children.find((c) => pathMatchesItem(c.path))
    if (!activeChild) continue
    open.push(menu.key)
    if (hasPinnedChildren(activeChild)) open.push(activeChild.path)
  }
  return open
})

const menuOpenKey = computed(() => defaultOpeneds.value.join('|'))

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
    router.replace(auth.isShopClerk ? '/shop/verifications' : '/dashboard')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

async function switchToPlatform() {
  try {
    await auth.switchWorkspace(WORKSPACE_PLATFORM)
    ElMessage.success('已切换到平台运营后台')
    router.push('/admin')
  } catch (e) {
    ElMessage.error(e.message || '切换失败')
  }
}

const displayName = computed(
  () => auth.user?.display_name || auth.user?.phone || '用户',
)
const avatarChar = computed(() => displayName.value.charAt(0))
</script>

<template>
  <div class="app-shell" :data-testid="auth.isShopClerk ? 'shop-clerk-shell' : undefined">
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
      <div v-if="!auth.isShopClerk" class="app-header__center">
        <el-input
          placeholder="搜索内容、选题..."
          prefix-icon="Search"
          class="app-header__search"
          clearable
        />
      </div>
      <div class="app-header__right">
        <span
          v-if="showShopSwitcher"
          class="shop-switch"
          data-testid="shop-current-store"
        >
          <el-dropdown trigger="click" @command="onSwitchShop">
            <span class="shop-switch__trigger">
              当前店铺：<b>{{ currentShopName }}</b>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="s in shopStores"
                  :key="s.id"
                  :command="s.id"
                  :disabled="String(s.id) === String(currentShopId)"
                >
                  {{ s.name }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span v-if="shopSwitcherMeta" class="shop-switch__meta"> · {{ shopSwitcherMeta }}</span>
        </span>
        <CrmNotificationBell v-if="auth.isLoggedIn && !auth.isShopClerk" />
        <el-dropdown trigger="click">
          <div class="app-header__user">
            <el-avatar :size="32" style="background: #4096ff">{{ avatarChar }}</el-avatar>
            <span>{{ displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="auth.canSwitchWorkspace" @click="switchToPlatform">
                平台运营后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="app-body">
      <aside class="app-sidebar">
        <el-menu
          :key="menuOpenKey"
          :default-active="activeMenu"
          :default-openeds="defaultOpeneds"
          router
          class="app-sidebar__menu"
        >
          <template v-for="menu in menuItems" :key="menu.key">
            <!-- 一级：无子项的单页入口 -->
            <el-menu-item v-if="!menu.children" :index="menu.path">
              <el-icon><component :is="menu.icon" /></el-icon>
              <span>{{ menu.title }}</span>
            </el-menu-item>

            <!-- 一级：业务分组 -->
            <el-sub-menu v-else :index="menu.key">
              <template #title>
                <el-icon><component :is="menu.icon" /></el-icon>
                <span>{{ menu.title }}</span>
              </template>

              <template v-for="item in menu.children" :key="item.path">
                <!-- 二级：含钉选视图时再嵌一层 -->
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
            </el-sub-menu>
          </template>
        </el-menu>
      </aside>

      <main class="app-main">
        <div
          v-if="showShopBanner"
          class="shop-onboarding-banner"
          :class="{ 'is-reviewing': shopOnboardingState === 'reviewing' }"
        >
          <span>{{ shopBannerText }}</span>
          <el-button
            v-if="shopOnboardingState !== 'reviewing'"
            size="small"
            type="primary"
            @click="router.push('/shop/onboarding')"
          >
            {{ shopOnboardingState === 'rejected' ? '修改重提' : '立即申请' }}
          </el-button>
          <el-button
            v-else
            size="small"
            @click="router.push('/shop/onboarding')"
          >
            查看进度
          </el-button>
        </div>
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

.shop-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #fff;
  opacity: 0.95;
  white-space: nowrap;
}

.shop-switch__trigger {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #fff;
}

.shop-switch__meta {
  opacity: 0.85;
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
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.app-sidebar__menu {
  border-right: none;
  padding-top: 8px;
  padding-bottom: 8px;
}

.app-sidebar__menu :deep(.el-menu-item.is-active) {
  background: #e6f4ff;
  color: var(--color-primary);
}

.app-sidebar__menu :deep(.el-sub-menu .el-menu-item) {
  min-width: 0;
  padding-left: 48px !important;
}

.app-sidebar__menu :deep(.el-sub-menu .el-sub-menu .el-menu-item) {
  padding-left: 64px !important;
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

.shop-onboarding-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  background: linear-gradient(90deg, #e8f3ff 0%, #f0f9ff 100%);
  border: 1px solid #b3d8ff;
  color: #1d39c4;
  font-size: 14px;
}

.shop-onboarding-banner.is-reviewing {
  background: #fff7e6;
  border-color: #ffd591;
  color: #ad6800;
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
