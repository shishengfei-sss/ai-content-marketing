<script setup>
/**
 * M14 短信领权页。对照 PRD 02-买家端UI.html #m14
 * 三态：pending 领取 / expired·refunded 失败 / claimed 成功
 * 仍缺：真机微信手机号组件（当前 H5/Mock 用尾号校验录入）
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerShopId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const token = ref('')
const tenantId = ref('')
const loading = ref(true)
const submitting = ref(false)
const authorizing = ref(false)
const info = ref(null)
const buyer = ref(null)
const mobileInput = ref('')
const authorizedMobile = ref('')
const showAuth = ref(false)
const errorDetail = ref('')

const viewState = computed(() => {
  if (errorDetail.value && !info.value) return 'invalid'
  const st = info.value?.status
  if (st === 'expired' || st === 'refunded') return st
  if (st === 'claimed') return 'claimed'
  if (st === 'pending') return 'pending'
  return 'invalid'
})

const mobileDisplay = computed(() => {
  if (authorizedMobile.value) {
    const m = authorizedMobile.value
    return `${m.slice(0, 3)}****${m.slice(-4)}`
  }
  if (buyer.value?.mobile_masked) return buyer.value.mobile_masked
  return info.value?.mobile_masked || (info.value?.mobile_tail ? `****${info.value.mobile_tail}` : '—')
})

const canConfirm = computed(() => {
  if (viewState.value !== 'pending') return false
  if (!buyer.value) return false
  const mobile = authorizedMobile.value || buyer.value.mobile
  if (!mobile) return false
  const tail = info.value?.mobile_tail
  return !tail || mobile.endsWith(tail)
})

function readHashQuery() {
  try {
    const hash = String(typeof window !== 'undefined' ? window.location.hash || '' : '')
    const qi = hash.indexOf('?')
    const fromHash = qi >= 0 ? hash.slice(qi + 1) : ''
    const fromSearch =
      typeof window !== 'undefined' ? String(window.location.search || '').replace(/^\?/, '') : ''
    return new URLSearchParams(fromHash || fromSearch)
  } catch {
    return new URLSearchParams()
  }
}

async function resolvePendingToken() {
  const tid = tenantId.value || getShopBuyerTenantId()
  if (!tid) return
  tenantId.value = tid
  buyer.value = await ensureShopBuyerSession(tid)
  const pending = await shopBuyerApi.getPendingClaim()
  if (pending?.token) {
    token.value = String(pending.token)
    info.value = pending
    if (pending.tenant_id) tenantId.value = String(pending.tenant_id)
    if (pending.shop_id) setShopBuyerShopId(String(pending.shop_id))
  }
}

async function loadInfo() {
  loading.value = true
  errorDetail.value = ''
  try {
    if (!token.value) {
      try {
        await resolvePendingToken()
      } catch (e) {
        errorDetail.value = e.message || '请从短信里的领取链接打开'
        info.value = null
        return
      }
    }
    if (!token.value) {
      errorDetail.value = '请从短信里的领取链接打开，或到「我的」使用领权兑换'
      info.value = null
      return
    }
    if (!info.value) {
      info.value = await shopBuyerApi.getClaim(token.value)
    }
    if (info.value.tenant_id) tenantId.value = String(info.value.tenant_id)
    if (info.value.shop_id) setShopBuyerShopId(String(info.value.shop_id))
    if (info.value.tenant_id) setShopBuyerTenantId(String(info.value.tenant_id))
    if (viewState.value === 'pending' && tenantId.value) {
      try {
        buyer.value = await ensureShopBuyerSession(tenantId.value, `claim_${token.value.slice(0, 8)}`)
      } catch (e) {
        uni.showToast({ title: e.message || '请先登录', icon: 'none' })
      }
    }
  } catch (e) {
    errorDetail.value = e.message || '领权链接无效'
    info.value = null
  } finally {
    loading.value = false
  }
}

function openAuthorize() {
  showAuth.value = true
  mobileInput.value = ''
}

async function submitAuthorize() {
  const m = mobileInput.value.trim()
  if (!/^1\d{10}$/.test(m)) {
    uni.showToast({ title: '请输入正确手机号', icon: 'none' })
    return
  }
  const tail = info.value?.mobile_tail
  if (tail && !m.endsWith(tail)) {
    uni.showToast({ title: '手机号与购买号不一致', icon: 'none' })
    return
  }
  authorizing.value = true
  try {
    if (!buyer.value) {
      buyer.value = await ensureShopBuyerSession(tenantId.value, `claim_${token.value.slice(0, 8)}`)
    }
    authorizedMobile.value = m
    try {
      const bound = await shopBuyerApi.bindMobile(m)
      if (bound) buyer.value = bound
    } catch {
      /* 演示：bind 冲突时仍允许确认领取，confirm_claim 会挂手机号 */
    }
    showAuth.value = false
    uni.showToast({ title: '已授权', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e.message || '授权失败', icon: 'none' })
  } finally {
    authorizing.value = false
  }
}

async function confirmClaim() {
  if (!canConfirm.value) {
    uni.showToast({ title: '请先授权购买手机号', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const res = await shopBuyerApi.confirmClaim(token.value)
    if (res.status === 'claimed') {
      info.value = { ...info.value, status: 'claimed', message: '权益已开通，可开始学习' }
      uni.showToast({ title: '领取成功', icon: 'success' })
    }
  } catch (e) {
    const msg = e.message || '领取失败'
    if (e.status === 410 || msg.includes('过期')) {
      info.value = { ...info.value, status: 'expired', message: '领取码已过期，请联系商家' }
    } else if (msg.includes('退款')) {
      info.value = { ...info.value, status: 'refunded', message: '订单已退款，无法领取' }
    }
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goEntitlements() {
  uni.navigateTo({ url: '/pages/shop/entitlements' })
}

function contactSupport() {
  uni.showToast({ title: '请联系商家客服', icon: 'none' })
}

onLoad((query) => {
  const hashQ = readHashQuery()
  token.value = (query?.token || hashQ.get('token') || '').trim()
  tenantId.value = (query?.tenant_id || hashQ.get('tenant_id') || getShopBuyerTenantId() || '').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  loadInfo()
})
</script>

<template>
  <view class="page">
    <view class="nav">
      <text class="nav-title">领取课程</text>
      <text class="nav-sub">来自抖店 · 短信领权</text>
    </view>

    <view v-if="loading" class="state">加载中…</view>

    <template v-else-if="viewState === 'pending'">
      <view class="card goods">
        <view class="cover">抖店</view>
        <view class="goods-body">
          <text class="name">{{ info?.product_name || '课程权益' }}</text>
          <text class="meta">{{ info?.message || '请用购买手机号领取权益' }}</text>
        </view>
      </view>
      <view class="field">
        <text class="label">手机号 <text class="req">*</text></text>
        <view class="val-row">
          <text>{{ mobileDisplay }}</text>
          <text class="link" @click="openAuthorize">授权</text>
        </view>
      </view>
      <view class="footer">
        <button class="btn-primary" :loading="submitting" :disabled="!canConfirm" @click="confirmClaim">
          确认领取
        </button>
      </view>
    </template>

    <view v-else-if="viewState === 'expired'" class="state fail">
      <view class="icon fail-icon">✕</view>
      <text class="state-title">链接已失效</text>
      <text class="state-desc">{{ info?.message || '领取码已过期，请联系商家' }}</text>
      <button class="btn-ghost" @click="contactSupport">联系客服</button>
    </view>

    <view v-else-if="viewState === 'refunded'" class="state fail">
      <view class="icon fail-icon">✕</view>
      <text class="state-title">无法领取</text>
      <text class="state-desc">{{ info?.message || '订单已退款，无法领取' }}</text>
      <button class="btn-ghost" @click="contactSupport">联系客服</button>
    </view>

    <view v-else-if="viewState === 'claimed'" class="state ok">
      <view class="icon ok-icon">✓</view>
      <text class="state-title">领取成功</text>
      <text class="state-desc">{{ info?.message || '权益已开通，可开始学习' }}</text>
      <button class="btn-primary" @click="goEntitlements">去已购</button>
    </view>

    <view v-else class="state fail">
      <view class="icon fail-icon">✕</view>
      <text class="state-title">链接无效</text>
      <text class="state-desc">{{ errorDetail || '请从短信里的领取链接打开' }}</text>
    </view>

    <view v-if="showAuth" class="mask" @click="showAuth = false">
      <view class="sheet" @click.stop>
        <text class="sheet-title">授权手机号</text>
        <text class="sheet-hint">须与购买手机号一致（尾号 {{ info?.mobile_tail || '—' }}）</text>
        <input
          v-model="mobileInput"
          class="input"
          type="number"
          maxlength="11"
          placeholder="请输入购买手机号"
        />
        <view class="sheet-actions">
          <button class="btn-ghost" @click="showAuth = false">取消</button>
          <button class="btn-primary" :loading="authorizing" @click="submitAuthorize">确认</button>
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
  box-sizing: border-box;
}
.nav {
  margin-bottom: 16px;
}
.nav-title {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}
.nav-sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.cover {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.goods-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}
.name {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.meta {
  font-size: 12px;
  color: #64748b;
}
.field {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
}
.label {
  font-size: 13px;
  color: #475569;
}
.req {
  color: #ef4444;
}
.val-row {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 15px;
  color: #0f172a;
}
.link {
  color: #1677ff;
  font-weight: 600;
}
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -1px 0 #e2e8f0;
}
.btn-primary {
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
}
.btn-primary[disabled] {
  opacity: 0.45;
}
.btn-ghost {
  background: #fff;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font-size: 15px;
}
.state {
  margin-top: 48px;
  text-align: center;
  padding: 0 12px;
}
.icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  margin: 0 auto 12px;
  line-height: 56px;
  font-size: 28px;
  font-weight: 700;
}
.ok-icon {
  background: #dcfce7;
  color: #16a34a;
}
.fail-icon {
  background: #fee2e2;
  color: #dc2626;
}
.state-title {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.state-desc {
  display: block;
  margin: 10px 0 20px;
  font-size: 13px;
  color: #64748b;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
  z-index: 20;
}
.sheet {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
}
.sheet-title {
  display: block;
  font-size: 17px;
  font-weight: 700;
}
.sheet-hint {
  display: block;
  margin: 6px 0 14px;
  font-size: 12px;
  color: #64748b;
}
.input {
  background: #f1f5f9;
  border-radius: 10px;
  padding: 12px;
  font-size: 16px;
}
.sheet-actions {
  margin-top: 14px;
  display: flex;
  gap: 10px;
}
.sheet-actions button {
  flex: 1;
}
</style>
