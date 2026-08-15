<script setup>
/**
 * M06 已购（学习中心）。对照 PRD 02-买家端UI.html #m06
 * 类型 Chip · 状态×操作矩阵 → M07/M09/M10
 */
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const openidHint = ref('')

const loading = ref(false)
const items = ref([])
const error = ref('')
const typeFilter = ref('') // '' | course | digital | service

const TYPE_CHIPS = [
  { key: '', label: '全部' },
  { key: 'course', label: '课程' },
  { key: 'digital', label: '资料' },
  { key: 'service', label: '服务' },
]

const filtered = computed(() => {
  if (!typeFilter.value) return items.value
  return items.value.filter((i) => i.product_type === typeFilter.value)
})

function typeLabel(t) {
  return { course: '课程', digital: '资料', service: '服务' }[t] || t || '—'
}

function subText(row) {
  if (row.status === 'revoked') return '权限已关闭'
  if (row.status === 'expired') return '权益已过期'
  if (row.product_type === 'service') {
    const rem = row.remaining_count
    const tot = row.total_count
    if (rem != null) return `剩余 ${rem} 次${tot != null ? ` · 共 ${tot} 次` : ''}`
    return '服务权益'
  }
  if (row.product_type === 'digital') return '资料可领取'
  return '可继续学习'
}

function actionLabel(row) {
  if (row.status === 'revoked') return '已关闭'
  if (row.status === 'expired') return '已过期'
  if (row.product_type === 'service') return '预约'
  if (row.product_type === 'digital') return '领取'
  return '继续学'
}

function isDisabled(row) {
  return row.status !== 'active'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const tid = getShopBuyerTenantId()
    if (!tid) {
      error.value = '请先完成领权或买家登录'
      items.value = []
      return
    }
    await ensureShopBuyerSession(tid, openidHint.value || undefined)
    const data = await shopBuyerApi.listEntitlements({ page: 1, page_size: 50 })
    items.value = data.items || []
  } catch (e) {
    error.value = e.message || '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

function onAction(row) {
  if (row.status === 'revoked') {
    uni.showToast({ title: '权限已关闭，如有疑问联系客服', icon: 'none' })
    return
  }
  if (row.status === 'expired') {
    uni.showToast({ title: '权益已过期', icon: 'none' })
    return
  }
  if (row.product_type === 'service') {
    if (row.remaining_count != null && row.remaining_count <= 0) {
      uni.showToast({ title: '剩余次数不足', icon: 'none' })
      return
    }
    uni.navigateTo({
      url: `/pages/shop/booking?entitlement_id=${row.id}`,
    })
    return
  }
  if (row.product_type === 'digital') {
    uni.navigateTo({ url: `/pages/shop/materials?entitlement_id=${row.id}` })
    return
  }
  uni.navigateTo({ url: `/pages/shop/learn?entitlement_id=${row.id}` })
}

function goOrders() {
  uni.navigateTo({ url: '/pages/shop/orders' })
}

function goBookings() {
  uni.navigateTo({ url: '/pages/shop/bookings' })
}

onLoad((query) => {
  const tid = (query?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (query?.openid || '').trim()
})
onShow(load)
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">已购</text>
      <text class="sub">课程 · 资料 · 服务</text>
    </view>

    <view class="chips">
      <text
        v-for="c in TYPE_CHIPS"
        :key="c.key || 'all'"
        class="chip"
        :class="{ on: typeFilter === c.key }"
        @click="typeFilter = c.key"
      >
        {{ c.label }}
      </text>
    </view>

    <view class="links">
      <text class="link" @click="goBookings">我的预约</text>
      <text class="link" @click="goOrders">我的订单</text>
    </view>

    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="error" class="empty">{{ error }}</view>
    <view v-else-if="!filtered.length" class="empty">
      <text class="empty-title">还没有已购内容</text>
      <text class="empty-sub">购买后即可在此学习</text>
    </view>
    <view v-else class="list">
      <view
        v-for="row in filtered"
        :key="row.id"
        class="card"
        :class="{ disabled: isDisabled(row) }"
      >
        <view class="thumb" :class="row.product_type || 'course'">
          {{ typeLabel(row.product_type).slice(0, 1) }}
        </view>
        <view class="body">
          <text class="name">{{ row.product_name || '商品' }}</text>
          <text class="meta" :class="{ danger: row.status === 'revoked', warn: row.status === 'expired' }">
            {{ subText(row) }}
          </text>
        </view>
        <button
          class="btn"
          :class="{ primary: !isDisabled(row) }"
          size="mini"
          :disabled="isDisabled(row)"
          @click="onAction(row)"
        >
          {{ actionLabel(row) }}
        </button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px;
  box-sizing: border-box;
}
.head {
  margin-bottom: 12px;
}
.title {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}
.sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.chip {
  padding: 6px 12px;
  border-radius: 999px;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  border: 1px solid #e2e8f0;
}
.chip.on {
  background: #e6f4ff;
  color: #1677ff;
  border-color: #91caff;
  font-weight: 600;
}
.links {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}
.link {
  font-size: 13px;
  color: #1677ff;
  font-weight: 600;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 48px;
  font-size: 14px;
}
.empty-title {
  display: block;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 6px;
}
.empty-sub {
  display: block;
  font-size: 12px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.card.disabled {
  opacity: 0.55;
}
.thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #0369a1;
  background: #e0f2fe;
  flex-shrink: 0;
}
.thumb.digital {
  background: #fef3c7;
  color: #b45309;
}
.thumb.service {
  background: #dcfce7;
  color: #15803d;
}
.body {
  flex: 1;
  min-width: 0;
}
.name {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.meta {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.meta.danger {
  color: #dc2626;
}
.meta.warn {
  color: #b45309;
}
.btn {
  flex-shrink: 0;
  margin: 0;
  background: #f1f5f9;
  color: #64748b;
  border: none;
  border-radius: 8px;
  font-size: 12px;
}
.btn.primary {
  background: #1677ff;
  color: #fff;
}
</style>
