<script setup>
/**
 * M10b 预约成功 · 核销码。对照 PRD #m10b
 */
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const code = ref('')
const productName = ref('')
const slotText = ref('')
const mode = ref('booking')
const loading = ref(true)
const openidHint = ref('')

async function load(entitlementId) {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId(), openidHint.value || undefined)
    const data = await shopBuyerApi.listEntitlements({ page: 1, page_size: 50 })
    const ent = (data.items || []).find((i) => i.id === entitlementId)
    if (!ent?.verify_code) throw new Error('暂无核销码')
    code.value = ent.verify_code
    productName.value = ent.product_name || '服务'
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function copyCode() {
  if (!code.value) return
  uni.setClipboardData({
    data: code.value,
    success: () => uni.showToast({ title: '已复制', icon: 'success' }),
  })
}

function goBookings() {
  uni.navigateTo({ url: '/pages/shop/bookings' })
}

function goEntitlements() {
  uni.redirectTo({ url: '/pages/shop/entitlements' })
}

onLoad((q) => {
  mode.value = q?.mode === 'times_card' ? 'times_card' : 'booking'
  slotText.value = q?.slot ? decodeURIComponent(q.slot) : ''
  const tid = (q?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (q?.openid || '').trim()
  const eid = (q?.entitlement_id || '').trim()
  if (eid) load(eid)
  else {
    loading.value = false
    uni.showToast({ title: '缺少权益', icon: 'none' })
  }
})
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">{{ mode === 'times_card' ? '核销码' : '预约成功' }}</text>
      <text class="sub">请妥善保存核销码</text>
    </view>
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else>
      <view class="card">
        <text class="name">{{ productName }}</text>
        <text v-if="slotText" class="slot">预约时段 {{ slotText }}</text>
        <text v-else class="slot">到店核销 · 次数卡</text>
        <text class="code">{{ code || '—' }}</text>
        <button class="btn-primary" @click="copyCode">复制核销码</button>
      </view>
      <view class="actions">
        <button class="btn-ghost" @click="goBookings">我的预约</button>
        <button class="btn-ghost" @click="goEntitlements">回已购</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px;
}
.head {
  margin-bottom: 16px;
}
.title {
  display: block;
  font-size: 20px;
  font-weight: 700;
}
.sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.card {
  background: #fff;
  border-radius: 14px;
  padding: 20px 16px;
  text-align: center;
}
.name {
  display: block;
  font-weight: 700;
  font-size: 16px;
}
.slot {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}
.code {
  display: block;
  margin: 20px 0;
  font-size: 36px;
  font-weight: 800;
  letter-spacing: 4px;
  color: #0f172a;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-weight: 600;
}
.actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
.btn-ghost {
  flex: 1;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  color: #334155;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
