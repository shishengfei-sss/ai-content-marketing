<script setup>
/**
 * M11 我的订单（订单中心）。对照 PRD 02-买家端UI.html #m11
 * Tab：全部 / 待付款 / 已付款 / 退款；卡片操作矩阵 → M12 / M12-A/B/C / M13
 */
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const loading = ref(false)
const items = ref([])
const tab = ref('') // '' | pending_payment | paid | refund
const openidHint = ref('')

const TABS = [
  { key: '', label: '全部' },
  { key: 'pending_payment', label: '待付款' },
  { key: 'paid', label: '已付款' },
  { key: 'refund', label: '退款' },
]

const STATUS_LABEL = {
  pending_payment: '待付款',
  paid: '已付款',
  claim_pending: '待领权',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
}

const busyId = ref('')

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function typeLabel(t) {
  return { course: '课程', digital: '资料', service: '服务' }[t] || '商品'
}

function typeChar(t) {
  return typeLabel(t).slice(0, 1)
}

function statusClass(st) {
  if (st === 'pending_payment') return 'st-warn'
  if (st === 'paid' || st === 'claim_pending') return 'st-ok'
  if (st === 'refunding') return 'st-muted'
  if (st === 'refunded' || st === 'closed') return 'st-off'
  return 'st-muted'
}

function shortNo(no) {
  const s = String(no || '')
  if (s.length <= 14) return s
  return `${s.slice(0, 6)}…${s.slice(-6)}`
}

function fmtTime(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId(), openidHint.value || undefined)
    const params = { page: 1, page_size: 50 }
    if (tab.value) params.status = tab.value
    const data = await shopBuyerApi.listOrders(params)
    items.value = data.items || []
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function selectTab(key) {
  tab.value = key
  load()
}

function goDetail(row) {
  uni.navigateTo({ url: `/pages/shop/order-detail?id=${row.id}` })
}

function canInvoice(row) {
  return row.status === 'paid' && (row.invoice_status === 'none' || row.invoice_status === 'rejected')
}

function goInvoice(row) {
  if (row.invoice_status === 'issued') {
    uni.navigateTo({ url: `/pages/shop/invoice?order_id=${row.id}&view=1` })
    return
  }
  if (row.invoice_status === 'submitted' || row.invoice_status === 'pending') {
    uni.showToast({ title: '待商家开具', icon: 'none' })
    return
  }
  if (!canInvoice(row)) {
    uni.showToast({ title: '该订单不可开票', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/shop/invoice?order_id=${row.id}` })
}

function goRefund(row) {
  uni.navigateTo({ url: `/pages/shop/order-detail?id=${row.id}&action=refund` })
}

function goRefundProgress(row) {
  uni.navigateTo({ url: `/pages/shop/order-detail?id=${row.id}&action=progress` })
}

async function pay(row) {
  busyId.value = row.id
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId())
    const data = await shopBuyerApi.payOrder(row.id)
    if (data.prepay) {
      uni.showToast({ title: '请完成微信支付', icon: 'none' })
    } else {
      uni.showToast({ title: '支付成功', icon: 'success' })
    }
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '支付失败', icon: 'none' })
  } finally {
    busyId.value = ''
  }
}

function cancel(row) {
  uni.showModal({
    title: '确认取消订单？',
    content: '取消后订单关闭，需重新下单购买',
    confirmText: '确认取消',
    confirmColor: '#cf1322',
    success: async (res) => {
      if (!res.confirm) return
      busyId.value = row.id
      try {
        await shopBuyerApi.cancelOrder(row.id)
        uni.showToast({ title: '已取消', icon: 'success' })
        await load()
      } catch (e) {
        uni.showToast({ title: e.message || '取消失败', icon: 'none' })
      } finally {
        busyId.value = ''
      }
    },
  })
}

const list = computed(() => items.value)

onLoad((query) => {
  const tid = (query?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (query?.openid || '').trim()
})
onShow(load)
</script>

<template>
  <view class="page">
    <text class="sr-only">我的订单</text>
    <view class="hint">查售后 · 退款 · 开票</view>

    <view class="tabs">
      <view
        v-for="t in TABS"
        :key="t.key || 'all'"
        class="tab"
        :class="{ on: tab === t.key }"
        @click="selectTab(t.key)"
      >
        {{ t.label }}
      </view>
    </view>

    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="!list.length" class="empty">
      <view class="empty-ico">🧾</view>
      <text class="empty-title">暂无订单</text>
      <text class="empty-sub">购买后可在此查售后、退款与开票</text>
    </view>
    <view v-else class="list">
      <view
        v-for="row in list"
        :key="row.id"
        class="card"
        :class="{ dim: row.status === 'closed' }"
        @click="goDetail(row)"
      >
        <view class="top">
          <text class="no">订单 {{ shortNo(row.order_no) }}</text>
          <text class="st" :class="statusClass(row.status)">
            {{ STATUS_LABEL[row.status] || row.status }}
          </text>
        </view>
        <view class="body">
          <view class="thumb" :class="row.type || 'course'">{{ typeChar(row.type) }}</view>
          <view class="info">
            <text class="name">{{ row.product_name || '商品' }}</text>
            <view class="meta">
              <text class="tag">{{ typeLabel(row.type) }}</text>
              <text v-if="fmtTime(row.created_at)" class="time">{{ fmtTime(row.created_at) }}</text>
            </view>
          </view>
          <text class="price">{{ fmtMoney(row.amount_cents) }}</text>
        </view>
        <view class="actions" @click.stop>
          <template v-if="row.status === 'pending_payment'">
            <button class="btn ghost" size="mini" :disabled="busyId === row.id" @click="cancel(row)">
              取消
            </button>
            <button class="btn primary" size="mini" :disabled="busyId === row.id" @click="pay(row)">
              去支付
            </button>
          </template>
          <template v-else-if="row.status === 'paid'">
            <button class="btn ghost" size="mini" @click="goInvoice(row)">
              {{ row.invoice_status === 'issued' ? '查看发票' : '开票' }}
            </button>
            <button class="btn danger" size="mini" @click="goRefund(row)">退款</button>
          </template>
          <template v-else-if="row.status === 'refunding' || row.status === 'refunded'">
            <button class="btn ghost" size="mini" @click="goRefundProgress(row)">查看进度</button>
          </template>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 12px 14px 40px;
  box-sizing: border-box;
  position: relative;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.hint {
  font-size: 12px;
  color: #64748b;
  margin: 2px 4px 10px;
}
.tabs {
  display: flex;
  padding: 4px;
  background: #fff;
  border-radius: 12px;
  margin-bottom: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}
.tab {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  font-size: 13px;
  color: #64748b;
  border-radius: 8px;
}
.tab.on {
  color: #1677ff;
  font-weight: 700;
  background: #e8f3ff;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.card.dim {
  opacity: 0.72;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.no {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.st {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.st-warn {
  background: #fffbeb;
  color: #d97706;
}
.st-ok {
  background: #ecfdf5;
  color: #059669;
}
.st-muted {
  background: #f1f5f9;
  color: #475569;
}
.st-off {
  background: #f8fafc;
  color: #94a3b8;
}
.body {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 12px;
}
.thumb {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
  background: #e8f3ff;
  color: #1677ff;
}
.thumb.digital {
  background: #fff7e6;
  color: #d48806;
}
.thumb.service {
  background: #ecfdf5;
  color: #059669;
}
.info {
  flex: 1;
  min-width: 0;
}
.name {
  display: block;
  font-weight: 700;
  font-size: 15px;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.tag {
  font-size: 11px;
  color: #1677ff;
  background: #e8f3ff;
  padding: 1px 6px;
  border-radius: 4px;
}
.time {
  font-size: 11px;
  color: #94a3b8;
}
.price {
  flex-shrink: 0;
  font-size: 16px;
  font-weight: 700;
  color: #e11d48;
  padding-top: 2px;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}
.btn {
  margin: 0;
  border: none;
  border-radius: 999px;
  font-size: 12px;
  padding: 0 14px;
  height: 30px;
  line-height: 30px;
}
.btn.primary {
  background: #1677ff;
  color: #fff;
}
.btn.danger {
  background: #fff1f2;
  color: #e11d48;
}
.btn.ghost {
  background: #f8fafc;
  color: #334155;
  border: 1px solid #e2e8f0;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 56px;
}
.empty-ico {
  font-size: 36px;
  margin-bottom: 8px;
}
.empty-title {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: #64748b;
}
.empty-sub {
  display: block;
  margin-top: 6px;
  font-size: 12px;
}
</style>
