<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { PAYMENT_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'

const paymentId = ref('')
const loading = ref(false)
const payment = ref(null)
const order = ref(null)

const METHOD_LABEL = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }

const paidAtLabel = computed(() => {
  if (!payment.value?.paid_at) return '—'
  return String(payment.value.paid_at).replace('T', ' ').slice(0, 16)
})

async function loadDetail() {
  if (!paymentId.value) return
  loading.value = true
  try {
    await ensureSession()
    const data = await crmApi.getPayment(paymentId.value)
    payment.value = data
    if (data.order_id) {
      try { order.value = await crmApi.getOrder(data.order_id) } catch { order.value = null }
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goOrder() {
  if (!payment.value?.order_id) return
  uni.navigateTo({ url: `/pages/crm/order-detail?id=${payment.value.order_id}` })
}

onLoad((query) => {
  paymentId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="payment">
      <view class="hero-card">
        <view class="hero-card__head">
          <text class="hero-card__title">{{ payment.payment_number }}</text>
          <text class="status">{{ PAYMENT_STATUS_LABEL[payment.status] || payment.status }}</text>
        </view>
        <view class="amount">{{ formatMoney(payment.amount) }}</view>
        <text class="sub">{{ METHOD_LABEL[payment.method] || payment.method }} · {{ paidAtLabel }}</text>
      </view>

      <view class="section">
        <text class="section__title">明细</text>
        <view class="desc-grid">
          <text class="desc-label">关联订单</text>
          <text class="desc-value link" @tap="goOrder">{{ order?.order_number || payment.order_id }}</text>
          <text class="desc-label">订单计划</text>
          <text class="desc-value">{{ payment.order_plan_total != null ? formatMoney(payment.order_plan_total) : '—' }}</text>
          <text class="desc-label">订单已回</text>
          <text class="desc-value">{{ payment.order_paid_total != null ? formatMoney(payment.order_paid_total) : '—' }}</text>
          <text class="desc-label">订单逾期</text>
          <text class="desc-value">{{ payment.order_overdue_amount != null ? formatMoney(payment.order_overdue_amount) : '—' }}</text>
          <text class="desc-label">备注</text>
          <text class="desc-value">{{ payment.remark || '—' }}</text>
        </view>
      </view>
    </template>
    <view v-else class="empty">回款不存在</view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; background: #f0f2f5; padding: 12px; box-sizing: border-box; }
.hero-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.hero-card__head { display: flex; justify-content: space-between; gap: 10px; }
.hero-card__title { flex: 1; font-size: 17px; font-weight: 600; }
.status { font-size: 11px; color: #1677ff; background: #e6f4ff; padding: 3px 10px; border-radius: 999px; height: fit-content; }
.amount { display: block; margin-top: 12px; font-size: 24px; font-weight: 700; color: #1677ff; }
.sub { display: block; margin-top: 4px; font-size: 13px; color: #94a3b8; }
.section { background: #fff; border-radius: 12px; padding: 14px 16px; }
.section__title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 12px; padding-left: 8px; border-left: 3px solid #1677ff; }
.desc-grid { display: grid; grid-template-columns: 5em 1fr; gap: 10px 8px; font-size: 13px; }
.desc-label { color: #94a3b8; }
.desc-value { color: #334155; word-break: break-all; }
.link { color: #1677ff; }
.empty { text-align: center; color: #94a3b8; padding: 40px 0; }
</style>
