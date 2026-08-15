<script setup>
/**
 * M04 确认订单。对照 PRD 02-买家端UI.html #m04
 */
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const productId = ref('')
const tenantId = ref('')
const openidHint = ref('')
const loading = ref(false)
const submitting = ref(false)
const detail = ref(null)
const buyer = ref(null)
const mobile = ref('')
const error = ref('')

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

async function load() {
  if (!productId.value) {
    error.value = '缺少商品标识'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const tid = tenantId.value || getShopBuyerTenantId()
    if (!tid) throw new Error('缺少商家标识')
    setShopBuyerTenantId(tid)
    buyer.value = await ensureShopBuyerSession(tid, openidHint.value || undefined)
    detail.value = await shopBuyerApi.getProduct(productId.value)
    if (buyer.value?.mobile) mobile.value = buyer.value.mobile
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!detail.value || submitting.value) return
  submitting.value = true
  try {
    const tid = tenantId.value || getShopBuyerTenantId()
    await ensureShopBuyerSession(tid, openidHint.value || undefined)
    const phone = (mobile.value || '').trim()
    if (!buyer.value?.mobile) {
      if (!/^1\d{10}$/.test(phone)) {
        uni.showToast({ title: '请输入正确手机号', icon: 'none' })
        return
      }
      buyer.value = await shopBuyerApi.bindMobile(phone)
    }
    const created = await shopBuyerApi.createOrder(productId.value)
    const order = created.order || created
    const payRes = await shopBuyerApi.payOrder(order.id)
    const paid = payRes.order || payRes
    uni.redirectTo({
      url: `/pages/shop/pay-result?order_id=${paid.id}&status=${paid.status || 'paid'}&tenant_id=${tid}`,
    })
  } catch (e) {
    uni.showToast({ title: e.message || '下单失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

onLoad((q) => {
  productId.value = (q?.product_id || q?.id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  openidHint.value = (q?.openid || '').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  load()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="hint">加载中…</view>
    <view v-else-if="error" class="error">{{ error }}</view>
    <template v-else-if="detail">
      <view class="card">
        <view class="row">
          <text class="label">商品</text>
          <text class="value">{{ detail.name }}</text>
        </view>
        <view class="row">
          <text class="label">类型</text>
          <text class="value">{{ detail.type === 'course' ? '课程' : detail.type === 'digital' ? '资料' : '服务' }}</text>
        </view>
        <view class="row">
          <text class="label">应付金额</text>
          <text class="amount">{{ fmtMoney(detail.price_cents) }}</text>
        </view>
      </view>

      <view class="card">
        <view class="section-title">联系手机</view>
        <input
          v-model="mobile"
          class="mobile-input"
          type="number"
          maxlength="11"
          placeholder="用于订单通知与领权"
          :disabled="!!buyer?.mobile"
        />
        <view v-if="buyer?.mobile" class="tip">已绑定 {{ buyer.mobile }}</view>
      </view>

      <view class="footer">
        <view class="total">合计 <text class="amount">{{ fmtMoney(detail.price_cents) }}</text></view>
        <button class="primary" :loading="submitting" @click="submit">
          {{ (detail.price_cents || 0) <= 0 ? '确认领取' : '确认支付' }}
        </button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fa;
  padding: 16px;
  padding-bottom: 88px;
}
.hint,
.error {
  padding: 40px 0;
  text-align: center;
  color: #94a3b8;
}
.error {
  color: #cf1322;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}
.row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 14px;
}
.label {
  color: #64748b;
}
.value {
  color: #1e293b;
  max-width: 60%;
  text-align: right;
}
.amount {
  color: #cf1322;
  font-weight: 600;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
}
.mobile-input {
  height: 40px;
  padding: 0 12px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 14px;
}
.tip {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.total {
  font-size: 14px;
  color: #334155;
}
.primary {
  min-width: 140px;
  height: 44px;
  line-height: 44px;
  background: #1677ff;
  color: #fff;
  border-radius: 22px;
  font-size: 15px;
}
</style>
