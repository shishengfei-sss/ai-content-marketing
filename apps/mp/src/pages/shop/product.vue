<script setup>
/**
 * M03 商品详情。对照 PRD 02-买家端UI.html #m03
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  ensureShopBuyerSession,
  getShopBuyerTenantId,
  setShopBuyerTenantId,
  shopBuyerApi,
} from '@/utils/shopApi'

const productId = ref('')
const tenantId = ref('')
const loading = ref(false)
const detail = ref(null)
const error = ref('')

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

function typeLabel(t) {
  return { course: '课程', digital: '资料', service: '服务' }[t] || t
}

const ctaLabel = computed(() => {
  const d = detail.value
  if (!d) return '加载中'
  if (d.status !== 'on_sale') return '已下架'
  if (d.purchase_state === 'purchased') {
    if (d.type === 'course') return '去学习'
    if (d.type === 'digital') return '去领取'
    if (d.type === 'service') return '去预约'
    return '已购买'
  }
  if ((d.price_cents || 0) <= 0) return '免费领取'
  return '立即购买'
})

const ctaDisabled = computed(() => {
  const d = detail.value
  if (!d) return true
  return d.status !== 'on_sale'
})

async function load() {
  if (!productId.value) {
    error.value = '缺少商品标识'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const tid = tenantId.value || getShopBuyerTenantId()
    if (tid) {
      setShopBuyerTenantId(tid)
      await ensureShopBuyerSession(tid)
    }
    detail.value = await shopBuyerApi.getProduct(productId.value)
  } catch (e) {
    error.value = e.message || '加载失败'
    detail.value = null
  } finally {
    loading.value = false
  }
}

function goCheckout() {
  const d = detail.value
  if (!d || ctaDisabled.value) return
  if (d.purchase_state === 'purchased') {
    if (d.type === 'course') {
      uni.navigateTo({ url: `/pages/shop/learn?entitlement_id=${d.entitlement_id}` })
    } else if (d.type === 'digital') {
      uni.navigateTo({ url: `/pages/shop/materials?entitlement_id=${d.entitlement_id}` })
    } else if (d.type === 'service') {
      uni.navigateTo({ url: `/pages/shop/booking?entitlement_id=${d.entitlement_id}` })
    }
    return
  }
  uni.navigateTo({
    url: `/pages/shop/checkout?product_id=${d.id}&tenant_id=${tenantId.value || getShopBuyerTenantId()}`,
  })
}

function onLessonTap(les) {
  if (les.locked) {
    uni.showToast({ title: '购买后可学习', icon: 'none' })
    return
  }
  const d = detail.value
  const tid = tenantId.value || getShopBuyerTenantId()
  if (d?.entitlement_id) {
    uni.navigateTo({
      url: `/pages/shop/player?entitlement_id=${d.entitlement_id}&lesson_id=${les.id}`,
    })
    return
  }
  if (les.is_trial) {
    uni.navigateTo({
      url: `/pages/shop/player?product_id=${d.id}&lesson_id=${les.id}&tenant_id=${tid}`,
    })
    return
  }
  uni.showToast({ title: '购买后可学习', icon: 'none' })
}

function goBackHome() {
  const d = detail.value
  if (!d?.shop_id) {
    uni.navigateBack()
    return
  }
  uni.redirectTo({
    url: `/pages/shop/home?shop_id=${d.shop_id}&tenant_id=${tenantId.value || getShopBuyerTenantId()}`,
  })
}

onLoad((q) => {
  productId.value = (q?.id || q?.product_id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  load()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="hint">加载中…</view>
    <view v-else-if="error" class="error">{{ error }}</view>
    <template v-else-if="detail">
      <view class="cover-wrap">
        <image v-if="detail.cover_url" :src="detail.cover_url" mode="aspectFill" class="cover" />
        <view v-else class="cover cover-placeholder">{{ typeLabel(detail.type) }}</view>
      </view>

      <view class="panel">
        <view class="price">{{ fmtMoney(detail.price_cents) }}</view>
        <view v-if="detail.line_price_cents" class="line-price">{{ fmtMoney(detail.line_price_cents) }}</view>
        <view class="name">{{ detail.name }}</view>
        <view v-if="detail.subtitle" class="subtitle">{{ detail.subtitle }}</view>
        <view class="meta">
          <text>{{ typeLabel(detail.type) }}</text>
          <text v-if="detail.lesson_count"> · {{ detail.lesson_count }} 课时</text>
          <text v-if="detail.asset_count"> · {{ detail.asset_count }} 个文件</text>
          <text v-if="detail.service_times"> · {{ detail.service_times }} 次</text>
          <text> · 已售 {{ detail.sales_count || 0 }}</text>
        </view>
      </view>

      <view v-if="detail.lessons?.length" class="panel">
        <view class="section-title">课程目录</view>
        <view
          v-for="les in detail.lessons"
          :key="les.id"
          class="lesson-row"
          @click="onLessonTap(les)"
        >
          <view class="lesson-title">
            {{ les.title }}
            <text v-if="les.is_trial" class="trial-tag">试看</text>
          </view>
          <view class="lesson-meta">
            {{ Math.ceil((les.duration_sec || 0) / 60) }} 分钟
            <text v-if="les.locked" class="locked"> · 未解锁</text>
          </view>
        </view>
      </view>

      <view class="footer">
        <button class="ghost" @click="goBackHome">回店铺</button>
        <button class="primary" :disabled="ctaDisabled" @click="goCheckout">{{ ctaLabel }}</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 80px;
}
.hint,
.error {
  padding: 40px 16px;
  text-align: center;
  color: #94a3b8;
}
.error {
  color: #cf1322;
}
.cover-wrap {
  background: #fff;
}
.cover {
  width: 100%;
  height: 200px;
}
.cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  color: #64748b;
  font-size: 16px;
}
.panel {
  margin: 12px 16px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
}
.price {
  color: #cf1322;
  font-size: 22px;
  font-weight: 600;
}
.line-price {
  color: #94a3b8;
  font-size: 13px;
  text-decoration: line-through;
  margin-left: 8px;
}
.name {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}
.subtitle {
  margin-top: 6px;
  font-size: 14px;
  color: #64748b;
}
.meta {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
}
.lesson-row {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}
.lesson-row:last-child {
  border-bottom: none;
}
.lesson-title {
  font-size: 14px;
  color: #334155;
}
.trial-tag {
  margin-left: 6px;
  font-size: 11px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 2px 6px;
  border-radius: 4px;
}
.lesson-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
.locked {
  color: #f59e0b;
}
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
}
.ghost,
.primary {
  flex: 1;
  height: 44px;
  line-height: 44px;
  border-radius: 22px;
  font-size: 15px;
}
.ghost {
  background: #f1f5f9;
  color: #334155;
}
.primary {
  background: #1677ff;
  color: #fff;
}
.primary[disabled] {
  opacity: 0.5;
}
</style>
