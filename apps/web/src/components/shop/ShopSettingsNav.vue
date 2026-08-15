<script setup>
/**
 * 设置五块横导航。对照 A15/A15-S/A18/A19 顶栏。
 */
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

defineProps({
  current: {
    type: String,
    required: true,
    // payment | sms | subscription | store | roles
  },
})

const router = useRouter()
const route = useRoute()

const ITEMS = [
  { key: 'payment', label: '支付与进件', path: '/shop/payment' },
  { key: 'sms', label: '短信 / 领权', path: '/shop/sms-settings' },
  { key: 'subscription', label: '套餐信息', path: '/shop/subscription' },
  { key: 'store', label: '单店设置', path: '/shop/store-settings' },
  { key: 'roles', label: '角色与成员', path: '/shop/roles-members' },
]

function go(item) {
  if (!item.path) {
    ElMessage.info(item.tip || '即将开放')
    return
  }
  if (route.path === item.path) return
  router.push(item.path)
}
</script>

<template>
  <div class="shop-settings-nav">
    <button
      v-for="item in ITEMS"
      :key="item.key"
      type="button"
      class="nav-item"
      :class="{ on: item.key === current }"
      @click="go(item)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<style scoped>
.shop-settings-nav {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--el-border-color, #e5e7eb);
  margin-bottom: 14px;
  font-size: 13px;
  flex-wrap: wrap;
}
.nav-item {
  border: none;
  background: transparent;
  padding: 8px 14px;
  color: #666;
  cursor: pointer;
}
.nav-item.on {
  color: #1677ff;
  font-weight: 700;
  border-bottom: 2px solid #1677ff;
  margin-bottom: -1px;
}
</style>
