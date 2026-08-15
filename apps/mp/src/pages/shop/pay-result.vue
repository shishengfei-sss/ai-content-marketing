<script setup>
/**
 * M05 支付结果。对照 PRD 02-买家端UI.html #m05
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const orderId = ref('')
const tenantId = ref('')
const status = ref('paid')
const order = ref(null)

const isPaid = computed(() => (order.value?.status || status.value) === 'paid')
const title = computed(() => (isPaid.value ? '支付成功' : '支付处理中'))

async function load() {
  if (!orderId.value) return
  try {
    const tid = tenantId.value || getShopBuyerTenantId()
    if (tid) {
      setShopBuyerTenantId(tid)
      await ensureShopBuyerSession(tid)
    }
    order.value = await shopBuyerApi.getOrder(orderId.value)
    status.value = order.value?.status || status.value
  } catch {
    /* 展示 URL 状态即可 */
  }
}

function goEntitlements() {
  const tid = tenantId.value || getShopBuyerTenantId()
  uni.redirectTo({ url: `/pages/shop/entitlements?tenant_id=${tid}` })
}

function goOrders() {
  const tid = tenantId.value || getShopBuyerTenantId()
  uni.redirectTo({ url: `/pages/shop/orders?tenant_id=${tid}` })
}

onLoad((q) => {
  orderId.value = (q?.order_id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  status.value = (q?.status || 'paid').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  load()
})
</script>

<template>
  <view class="page">
    <view class="icon" :class="{ ok: isPaid }">{{ isPaid ? '✓' : '…' }}</view>
    <view class="title">{{ title }}</view>
    <view v-if="order?.product_name" class="sub">{{ order.product_name }}</view>
    <view v-if="order?.order_no" class="sub">订单号 {{ order.order_no }}</view>

    <view class="actions">
      <button class="primary" @click="goEntitlements">查看已购</button>
      <button class="ghost" @click="goOrders">我的订单</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #fff;
  padding: 48px 24px;
  text-align: center;
}
.icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 36px;
  line-height: 72px;
}
.icon.ok {
  background: #f6ffed;
  color: #52c41a;
}
.title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
}
.sub {
  margin-top: 8px;
  font-size: 14px;
  color: #64748b;
}
.actions {
  margin-top: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.primary,
.ghost {
  height: 44px;
  line-height: 44px;
  border-radius: 22px;
  font-size: 15px;
}
.primary {
  background: #1677ff;
  color: #fff;
}
.ghost {
  background: #f1f5f9;
  color: #334155;
}
</style>
