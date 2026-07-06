<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { MINE_MENU, hasAnyPermission, hasPermission } from '@/utils/permissions'
import { ensureSession, fetchMe, logout, switchTenant } from '@/utils/session'

const user = ref(null)

const profile = computed(() => ({
  name: user.value?.display_name || user.value?.phone || '用户',
  company: user.value?.active_tenant?.name || '未选择公司',
  initial: (user.value?.display_name || user.value?.phone || '?').slice(0, 1),
}))

const menuItems = computed(() => {
  const p = user.value?.permissions || []
  return MINE_MENU.filter((item) => {
    if (item.permissionAny) return hasAnyPermission(p, item.permissionAny)
    return hasPermission(p, item.permission)
  })
})

const tenants = computed(() => user.value?.tenants || [])
const showSwitch = computed(() => tenants.value.length > 1)

async function loadProfile() {
  try {
    user.value = await ensureSession()
    if (user.value) user.value = await fetchMe()
  } catch {
    user.value = null
  }
}

function go(url) {
  uni.navigateTo({ url })
}

function pickCompany() {
  if (!showSwitch.value) return
  const names = tenants.value.map((t) => `${t.name} (${t.role_name})`)
  uni.showActionSheet({
    itemList: names,
    success: async (res) => {
      const t = tenants.value[res.tapIndex]
      if (t.id === user.value?.active_tenant?.id) return
      try {
        await switchTenant(t.id)
        uni.showToast({ title: '已切换公司', icon: 'success' })
        await loadProfile()
      } catch (e) {
        uni.showToast({ title: e.message, icon: 'none' })
      }
    },
  })
}

function handleLogout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出当前账号吗？',
    success(res) {
      if (res.confirm) logout()
    },
  })
}

onShow(loadProfile)
</script>

<template>
  <view class="page">
    <view class="profile">
      <view class="avatar">{{ profile.initial }}</view>
      <view>
        <text class="profile__name">{{ profile.name }}</text>
        <text class="profile__company" @click="pickCompany">
          {{ profile.company }}
          <text v-if="showSwitch" class="switch-hint"> · 切换</text>
        </text>
      </view>
    </view>

    <view class="menu">
      <view v-for="item in menuItems" :key="item.url" class="menu-item" @click="go(item.url)">
        <text>{{ item.title }}</text>
        <text class="menu-item__arrow">›</text>
      </view>
    </view>

    <view class="logout-wrap">
      <button class="btn-logout" @click="handleLogout">退出登录</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 48rpx;
}
.profile {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: #fff;
  padding: 40rpx 32rpx;
  margin-bottom: 24rpx;
}
.avatar {
  width: 96rpx;
  height: 96rpx;
  background: #1677ff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  font-weight: 600;
}
.profile__name {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  margin-bottom: 6rpx;
}
.profile__company {
  font-size: 26rpx;
  color: #666;
}
.switch-hint {
  color: #1677ff;
}
.menu {
  background: #fff;
  margin-bottom: 24rpx;
}
.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 30rpx;
}
.menu-item__arrow {
  color: #ccc;
  font-size: 36rpx;
}
.logout-wrap {
  padding: 0 32rpx;
}
.btn-logout {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: #fff;
  color: #ff4d4f;
  font-size: 30rpx;
  border-radius: 12rpx;
  border: 1rpx solid #ffccc7;
}
.btn-logout::after {
  border: none;
}
</style>
