<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { PAYMENT_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'
import { formatDateTime } from '@/utils/datetime'

const paymentId = ref('')
const loading = ref(false)
const acting = ref(false)
const payment = ref(null)
const order = ref(null)
const members = ref([])
const permissions = ref([])
const currentUserId = ref('')

const METHOD_LABEL = { bank: '银行', wechat: '微信', alipay: '支付宝', cash: '现金', other: '其他' }

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
const isOwner = computed(() => sameUserId(payment.value?.owner_user_id, currentUserId.value))
const canConfirm = computed(
  () =>
    hasPermission(permissions.value, 'crm.payment.confirm') &&
    isOwner.value &&
    payment.value?.status === 'pending',
)
const canReverse = computed(
  () =>
    hasPermission(permissions.value, 'crm.payment.reverse') &&
    isOwner.value &&
    payment.value?.status === 'confirmed',
)
const hasAnyAction = computed(() => canConfirm.value || canReverse.value)

const paidAtLabel = computed(() => formatDateTime(payment.value?.paid_at, { withSeconds: false }))
const ownerLabel = computed(() => {
  if (!payment.value?.owner_user_id) return '—'
  const m = members.value.find((x) => sameUserId(x.user_id, payment.value.owner_user_id))
  return m?.display_name || m?.phone || '—'
})

async function loadDetail() {
  if (!paymentId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    currentUserId.value = user?.id || user?.user_id || ''
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    const data = await crmApi.getPayment(paymentId.value)
    payment.value = data
    if (data.order_id) {
      try {
        order.value = await crmApi.getOrder(data.order_id)
      } catch {
        order.value = null
      }
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function runAction(fn, okMsg) {
  if (acting.value || !payment.value) return
  acting.value = true
  try {
    await fn()
    uni.showToast({ title: okMsg, icon: 'success' })
    await loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

function handleConfirm() {
  uni.showModal({
    title: '确认到账',
    content: '确定确认该回款已到账？',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.confirmPayment(payment.value.id), '已确认到账')
    },
  })
}

function handleReverse() {
  uni.showModal({
    title: '冲销回款',
    content: '确定冲销该回款？此操作不可撤销。',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.reversePayment(payment.value.id), '已冲销')
    },
  })
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

      <view v-if="hasAnyAction" class="actions">
        <button
          v-if="canConfirm"
          class="act act--ok"
          hover-class="none"
          :disabled="acting"
          @tap="handleConfirm"
        >确认到账</button>
        <button
          v-if="canReverse"
          class="act act--danger"
          hover-class="none"
          :disabled="acting"
          @tap="handleReverse"
        >冲销</button>
      </view>

      <view class="section">
        <text class="section__title">明细</text>
        <view class="desc-grid">
          <text class="desc-label">负责人</text>
          <text class="desc-value">{{ ownerLabel }}</text>
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
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.act {
  margin: 0; padding: 0 14px; height: 32px; line-height: 32px; font-size: 13px;
  background: #fff; color: #334155; border: 1px solid #e2e8f0; border-radius: 8px;
}
.act--ok { background: #52c41a; color: #fff; border-color: #52c41a; }
.act--danger { background: #fff; color: #ff4d4f; border-color: #ffccc7; }
.act[disabled] { opacity: 0.5; }
.section { background: #fff; border-radius: 12px; padding: 14px 16px; }
.section__title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 12px; padding-left: 8px; border-left: 3px solid #1677ff; }
.desc-grid { display: grid; grid-template-columns: 5em 1fr; gap: 10px 8px; font-size: 13px; }
.desc-label { color: #94a3b8; }
.desc-value { color: #334155; word-break: break-all; }
.link { color: #1677ff; }
.empty { text-align: center; color: #94a3b8; padding: 40px 0; }
</style>
