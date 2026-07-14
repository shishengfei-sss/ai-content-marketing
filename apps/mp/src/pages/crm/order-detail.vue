<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { ORDER_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'

const orderId = ref('')
const loading = ref(false)
const order = ref(null)
const customer = ref(null)
const members = ref([])

const SOURCE_LABEL = { deal: '商机', quote: '报价', contract: '合同', manual: '手工' }

const ownerLabel = computed(() => {
  if (!order.value?.owner_user_id) return '—'
  const m = members.value.find((x) => x.user_id === order.value.owner_user_id)
  return m?.display_name || m?.phone || '—'
})

async function loadDetail() {
  if (!orderId.value) return
  loading.value = true
  try {
    await ensureSession()
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    const data = await crmApi.getOrder(orderId.value)
    order.value = data
    if (data.customer_id) {
      try {
        customer.value = await crmApi.getCustomer(data.customer_id)
      } catch {
        customer.value = null
      }
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((query) => {
  orderId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="order">
      <view class="hero-card">
        <view class="hero-card__head">
          <text class="hero-card__title">{{ order.title || order.order_number }}</text>
          <text class="status">{{ ORDER_STATUS_LABEL[order.status] || order.status }}</text>
        </view>
        <view class="amount">{{ formatMoney(order.amount) }}</view>
        <text class="sub">{{ order.order_number }}</text>
      </view>

      <view class="section">
        <text class="section__title">基本信息</text>
        <view class="desc-grid">
          <text class="desc-label">客户</text><text class="desc-value">{{ customer?.company_name || '—' }}</text>
          <text class="desc-label">来源</text><text class="desc-value">{{ SOURCE_LABEL[order.source] || order.source || '—' }}</text>
          <text class="desc-label">负责人</text><text class="desc-value">{{ ownerLabel }}</text>
          <text class="desc-label">下单日期</text>
          <text class="desc-value">{{ order.order_date ? new Date(order.order_date).toLocaleDateString('zh-CN') : '—' }}</text>
        </view>
      </view>

      <view v-if="order.lines?.length" class="section">
        <text class="section__title">订单明细</text>
        <view v-for="line in order.lines" :key="line.id" class="line-card">
          <text class="line-card__name">{{ line.product_name }}</text>
          <text class="line-card__meta">数量 {{ line.quantity }} · {{ formatMoney(line.subtotal) }}</text>
        </view>
      </view>
    </template>
    <view v-else class="empty">订单不存在</view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
}

.hero-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.hero-card__head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.hero-card__title {
  flex: 1;
  font-size: 17px;
  font-weight: 600;
}

.status {
  font-size: 11px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 3px 10px;
  border-radius: 999px;
}

.amount {
  display: block;
  margin-top: 12px;
  font-size: 24px;
  font-weight: 700;
  color: #1677ff;
}

.sub {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: #94a3b8;
}

.section {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.section__title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #1677ff;
}

.desc-grid {
  display: grid;
  grid-template-columns: 5em 1fr;
  gap: 10px 8px;
  font-size: 13px;
}

.desc-label {
  color: #94a3b8;
}

.desc-value {
  color: #334155;
}

.line-card {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.line-card__name {
  display: block;
  font-size: 14px;
  font-weight: 500;
}

.line-card__meta {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
}
</style>
