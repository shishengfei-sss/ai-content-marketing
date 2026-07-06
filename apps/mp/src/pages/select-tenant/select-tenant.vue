<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { authApi } from '@/utils/api'
import { selectTenant } from '@/utils/session'

const loading = ref(false)
const tenants = ref([])

onLoad(async () => {
  try {
    const me = await authApi.me()
    tenants.value = me.tenants || []
    if (!me.need_select_tenant && me.active_tenant) {
      uni.switchTab({ url: '/pages/index/index' })
    }
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'none' })
  }
})

async function pick(tenantId) {
  loading.value = true
  try {
    await selectTenant(tenantId)
    uni.showToast({ title: '已进入工作空间', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 400)
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <view class="page">
    <view class="card">
      <text class="title">选择公司</text>
      <text class="hint">您的账号加入了多家公司，请选择工作空间</text>
      <view
        v-for="t in tenants"
        :key="t.id"
        class="tenant"
        @click="pick(t.id)"
      >
        <text class="tenant__name">{{ t.name }}</text>
        <text class="tenant__role">{{ t.role_name }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 48rpx;
  box-sizing: border-box;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx;
}
.title {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  margin-bottom: 12rpx;
}
.hint {
  display: block;
  color: #888;
  font-size: 26rpx;
  margin-bottom: 32rpx;
}
.tenant {
  padding: 28rpx;
  border: 1rpx solid #eee;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
}
.tenant__name {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
}
.tenant__role {
  font-size: 24rpx;
  color: #999;
}
</style>
