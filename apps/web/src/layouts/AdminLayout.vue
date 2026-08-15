<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore, WORKSPACE_MERCHANT, WORKSPACE_PLATFORM } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) await auth.fetchMe()
})

const baseMenuItems = [
  { path: '/admin/contents', title: '全站内容', icon: 'Document' },
  { path: '/admin/tenants', title: '企业管理', icon: 'OfficeBuilding' },
  { path: '/admin/users', title: '账号管理', icon: 'User' },
  { path: '/admin/assistants', title: '营销顾问配置', icon: 'MagicStick' },
  { path: '/admin/knowledge', title: '公共知识库', icon: 'Collection' },
  { path: '/admin/platform-llm', title: '平台 AI', icon: 'Cpu' },
  { path: '/admin/platform-tender-leads', title: '招标线索公共池', icon: 'Tickets' },
]

const shopMenuItems = [
  {
    path: '/admin/shop/dashboard',
    title: '概览',
    icon: 'DataAnalysis',
    anyPerm: ['platform.shop.analytics'],
  },
  {
    path: '/admin/shop/merchants',
    title: '商家租户',
    icon: 'Shop',
    anyPerm: [
      'platform.shop.merchant.read',
      'platform.shop.merchant.list_all',
      'platform.shop.merchant.list_assigned',
    ],
  },
  {
    path: '/admin/shop/onboarding',
    title: '入驻审核',
    icon: 'Checked',
    anyPerm: [
      'platform.shop.approve',
      'platform.shop.onboarding.initiate',
      'platform.shop.merchant.read',
    ],
  },
  {
    path: '/admin/shop/plans',
    title: '套餐配置',
    icon: 'Ticket',
    anyPerm: ['platform.shop.plan.manage'],
  },
  {
    path: '/admin/shop/subscriptions',
    title: '订阅台账',
    icon: 'Sell',
    anyPerm: [
      'platform.shop.subscription.manage',
      'platform.shop.subscription.read',
    ],
  },
  {
    path: '/admin/shop/product-reviews',
    title: '商品审核',
    icon: 'DocumentChecked',
    anyPerm: ['platform.shop.product.review'],
  },
  {
    path: '/admin/shop/moderation',
    title: '违规稽查',
    icon: 'Warning',
    anyPerm: ['platform.shop.moderate'],
  },
  {
    path: '/admin/shop/categories',
    title: '类目与费率',
    icon: 'PriceTag',
    anyPerm: ['platform.shop.fee.manage'],
  },
  {
    path: '/admin/shop/roles-codes',
    title: '角色与编码',
    icon: 'Key',
    anyPerm: ['platform.shop.analytics', 'platform.shop.fee.manage'],
  },
  {
    path: '/admin/shop/channels',
    title: '渠道与支付',
    icon: 'SetUp',
    anyPerm: ['platform.shop.channel', 'platform.shop.merchant.read'],
  },
  {
    path: '/admin/shop/settlements',
    title: '清结算',
    icon: 'Wallet',
    anyPerm: ['platform.shop.settlement'],
  },
  {
    path: '/admin/shop/sms',
    title: '短信管理',
    icon: 'ChatDotRound',
    anyPerm: ['platform.shop.channel', 'platform.shop.merchant.read'],
  },
]

const showShopGroup = computed(() =>
  shopMenuItems.some((item) => auth.hasAnyPlatformShopPermission(item.anyPerm)),
)

const visibleShopItems = computed(() =>
  shopMenuItems.filter((item) => auth.hasAnyPlatformShopPermission(item.anyPerm)),
)

const activeMenu = computed(() => {
  if (route.path.startsWith('/admin/shop/dashboard')) return '/admin/shop/dashboard'
  if (route.path.startsWith('/admin/shop/merchants')) return '/admin/shop/merchants'
  if (route.path.startsWith('/admin/shop/onboarding')) return '/admin/shop/onboarding'
  if (route.path.startsWith('/admin/shop/plans')) return '/admin/shop/plans'
  if (route.path.startsWith('/admin/shop/subscriptions')) return '/admin/shop/subscriptions'
  if (route.path.startsWith('/admin/shop/product-reviews')) return '/admin/shop/product-reviews'
  if (route.path.startsWith('/admin/shop/moderation')) return '/admin/shop/moderation'
  if (route.path.startsWith('/admin/shop/categories')) return '/admin/shop/categories'
  if (route.path.startsWith('/admin/shop/roles-codes')) return '/admin/shop/roles-codes'
  if (route.path.startsWith('/admin/shop/channels')) return '/admin/shop/channels'
  if (route.path.startsWith('/admin/shop/settlements')) return '/admin/shop/settlements'
  if (route.path.startsWith('/admin/shop/sms')) return '/admin/shop/sms'
  return route.path
})
const pageTitle = computed(() => route.meta.title || '管理后台')

function handleLogout() {
  auth.logout()
  router.push('/admin/login')
}

async function switchToMerchant() {
  try {
    await auth.switchWorkspace(WORKSPACE_MERCHANT)
    ElMessage.success('已切换到商家工作台')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message || '切换失败')
  }
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
        <el-button v-if="auth.canSwitchWorkspace" link type="primary" @click="switchToMerchant">
          我的商家工作台
        </el-button>
        <span>{{ displayName }}</span>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <div class="admin-body">
      <aside class="admin-sidebar">
        <el-menu :default-active="activeMenu" router class="admin-menu">
          <el-menu-item v-for="item in baseMenuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
          <el-sub-menu v-if="showShopGroup" index="shop-content">
            <template #title>
              <el-icon><component :is="'Shop'" /></el-icon>
              <span>内容获客</span>
            </template>
            <el-menu-item v-for="item in visibleShopItems" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </el-menu-item>
          </el-sub-menu>
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
  overflow: hidden;
}

.admin-sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #eee;
  overflow-y: auto;
}

.admin-menu {
  border-right: none;
}

.admin-main {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
}

.admin-main__title {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
}
</style>
