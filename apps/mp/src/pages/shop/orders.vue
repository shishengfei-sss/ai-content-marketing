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
    <view class="head">
      <text class="title">我的订单</text>
      <text class="sub">查售后 · 退款 · 开票</text>
    </view>

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
    <view v-else-if="!list.length" class="empty">暂无订单</view>
    <view v-else class="list">
      <view v-for="row in list" :key="row.id" class="card" @click="goDetail(row)">
        <view class="top">
          <text class="no">订单 {{ row.order_no }}</text>
          <text class="st">{{ STATUS_LABEL[row.status] || row.status }}</text>
        </view>
        <text class="name">{{ row.product_name || '商品' }} · {{ fmtMoney(row.amount_cents) }}</text>
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
          <!-- 已关闭 / 待领权：仅进详情 -->
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px;
  padding-bottom: 40px;
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
.tabs {
  display: flex;
  gap: 0;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 12px;
  overflow: hidden;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 13px;
  color: #64748b;
}
.tab.on {
  color: #1677ff;
  font-weight: 700;
  background: #e6f4ff;
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
}
.top {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
}
.st {
  font-weight: 600;
}
.name {
  display: block;
  margin: 10px 0 12px;
  font-weight: 600;
  font-size: 15px;
  color: #0f172a;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.btn {
  margin: 0;
  border: none;
  border-radius: 8px;
  font-size: 12px;
}
.btn.primary {
  background: #1677ff;
  color: #fff;
}
.btn.danger {
  background: #fff1f0;
  color: #cf1322;
}
.btn.ghost {
  background: #f1f5f9;
  color: #334155;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
