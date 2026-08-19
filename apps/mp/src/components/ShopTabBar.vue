<script setup>
/**
 * 买家底栏。对照 PRD 02-买家端UI.html #m02 / #m15：首页 · 已购 · 我的
 */
import { shopNavQuery } from '@/utils/shopApi'

const props = defineProps({
  active: { type: String, required: true },
  shopId: { type: String, default: '' },
  tenantId: { type: String, default: '' },
  openid: { type: String, default: '' },
})

const ITEMS = [
  { key: 'home', path: '/pages/shop/home', icon: '🏠', label: '首页' },
  { key: 'ents', path: '/pages/shop/entitlements', icon: '📚', label: '已购' },
  { key: 'mine', path: '/pages/shop/mine', icon: '👤', label: '我的' },
]

function qs() {
  return shopNavQuery({
    shopId: props.shopId,
    tenantId: props.tenantId,
    openid: props.openid,
  })
}

function go(path) {
  uni.redirectTo({ url: `${path}${qs()}` })
}
</script>

<template>
  <view class="bottom-nav">
    <view
      v-for="it in ITEMS"
      :key="it.key"
      class="nav-item"
      :class="{ active: active === it.key }"
      @click="go(it.path)"
    >
      <text class="ico">{{ it.icon }}</text>
      <text class="lab">{{ it.label }}</text>
    </view>
  </view>
</template>

<style scoped>
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 56px;
  padding-bottom: env(safe-area-inset-bottom);
  display: flex;
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid #eef2f6;
  box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.04);
  z-index: 20;
  backdrop-filter: blur(12px);
}
.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: #94a3b8;
}
.nav-item.active {
  color: #1677ff;
}
.ico {
  font-size: 18px;
  line-height: 1.1;
}
.lab {
  font-size: 11px;
  font-weight: 500;
}
.nav-item.active .lab {
  font-weight: 700;
}
</style>
