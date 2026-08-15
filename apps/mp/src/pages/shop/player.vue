<script setup>
/**
 * M08 播放器（最小壳）。对照 PRD #m08
 * Mock：无真实视频流时用进度条模拟播放并上报进度
 */
import { computed, onUnmounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const entitlementId = ref('')
const lessonId = ref('')
const courseId = ref('')
const productId = ref('')
const tenantId = ref('')
const product = ref(null)
const lesson = ref(null)
const outline = ref(null)
const position = ref(0)
const duration = ref(600)
const rate = ref(1)
const playing = ref(false)
const showTrialEnd = ref(false)
let timer = null
let reportTick = 0

const rates = [1, 1.25, 1.5, 2]
const progressPct = computed(() => {
  if (!duration.value) return 0
  return Math.min(100, Math.round((position.value / duration.value) * 100))
})
const timeLabel = computed(() => {
  const fmt = (s) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }
  return `${fmt(position.value)} / ${fmt(duration.value)}`
})
const trialLimit = computed(() => {
  if (!lesson.value?.is_trial) return null
  return lesson.value.trial_seconds || duration.value
})
const isTrialSession = computed(() => !entitlementId.value && !!productId.value)
const buyProductId = computed(() => productId.value || outline.value?.product_id || '')
const buyPrice = computed(() => product.value?.price_cents)

function fmtMoney(cents) {
  return `¥${((cents || 0) / 100).toFixed(2)}`
}

async function load() {
  try {
    const tid = tenantId.value || getShopBuyerTenantId()
    if (tid) await ensureShopBuyerSession(tid)
    if (isTrialSession.value) {
      product.value = await shopBuyerApi.getProduct(productId.value)
      lesson.value = (product.value.lessons || []).find((l) => l.id === lessonId.value)
      if (!lesson.value) throw new Error('课时不存在')
      if (!lesson.value.is_trial) throw new Error('该课时不支持试看')
      duration.value = lesson.value.duration_sec || 600
      position.value = 0
      return
    }
    outline.value = await shopBuyerApi.getOutline(entitlementId.value)
    lesson.value = (outline.value.lessons || []).find((l) => l.id === lessonId.value)
    if (!lesson.value) throw new Error('课时不存在')
    if (lesson.value.locked) throw new Error('购买后可学习')
    duration.value = lesson.value.duration_sec || 600
    position.value = lesson.value.position_sec || 0
    courseId.value = outline.value.course_id
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  }
}

async function report(force = false) {
  if (isTrialSession.value) return
  reportTick += 1
  if (!force && reportTick % 3 !== 0) return
  try {
    await shopBuyerApi.upsertLessonProgress(entitlementId.value, lessonId.value, {
      course_id: courseId.value,
      position_sec: Math.floor(position.value),
      progress_pct: progressPct.value,
    })
  } catch {
    /* ignore */
  }
}

function tick() {
  if (!playing.value) return
  position.value = Math.min(duration.value, position.value + rate.value)
  const limit = trialLimit.value
  if (limit != null && position.value >= limit && (isTrialSession.value || outline.value?.entitlement_status !== 'active')) {
    playing.value = false
    showTrialEnd.value = true
    clearInterval(timer)
    timer = null
    report(true)
    return
  }
  if (position.value >= duration.value) {
    playing.value = false
    clearInterval(timer)
    timer = null
    report(true)
    return
  }
  report(false)
}

function togglePlay() {
  if (showTrialEnd.value) return
  playing.value = !playing.value
  if (playing.value) {
    if (timer) clearInterval(timer)
    timer = setInterval(tick, 1000)
  } else {
    clearInterval(timer)
    timer = null
    report(true)
  }
}

function setRate(r) {
  rate.value = r
}

function goBuy() {
  const pid = buyProductId.value
  if (!pid) {
    uni.showToast({ title: '缺少商品', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/shop/checkout?product_id=${pid}&tenant_id=${tenantId.value || getShopBuyerTenantId()}`,
  })
}

function replayTrial() {
  showTrialEnd.value = false
  position.value = 0
}

function backCatalog() {
  if (isTrialSession.value && productId.value) {
    uni.navigateBack({
      fail: () =>
        uni.redirectTo({
          url: `/pages/shop/product?id=${productId.value}&tenant_id=${tenantId.value || getShopBuyerTenantId()}`,
        }),
    })
    return
  }
  uni.navigateBack({ fail: () => uni.redirectTo({ url: `/pages/shop/learn?entitlement_id=${entitlementId.value}` }) })
}

onLoad((q) => {
  entitlementId.value = (q?.entitlement_id || '').trim()
  lessonId.value = (q?.lesson_id || '').trim()
  courseId.value = (q?.course_id || '').trim()
  productId.value = (q?.product_id || '').trim()
  tenantId.value = (q?.tenant_id || '').trim()
  if (tenantId.value) setShopBuyerTenantId(tenantId.value)
  load()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  report(true)
})
</script>

<template>
  <view class="page">
    <view class="stage" @click="togglePlay">
      <view class="play-btn">{{ playing ? '❚❚' : '▶' }}</view>
      <text class="stage-title">{{ lesson?.title || '播放中' }}</text>
      <text class="stage-sub">{{ product?.name || outline?.product_name || '' }} · Mock 播放</text>
    </view>
    <view class="panel">
      <view class="time-row">
        <text>{{ timeLabel }}</text>
        <text v-if="lesson?.is_trial" class="badge">试看</text>
      </view>
      <view class="bar"><view class="bar-i" :style="{ width: progressPct + '%' }" /></view>
      <view class="rates">
        <text
          v-for="r in rates"
          :key="r"
          class="chip"
          :class="{ on: rate === r }"
          @click="setRate(r)"
        >
          {{ r }}x
        </text>
      </view>
      <button class="btn" @click="togglePlay">{{ playing ? '暂停' : '播放' }}</button>
      <button class="btn ghost" @click="backCatalog">返回目录</button>
    </view>

    <view v-if="showTrialEnd" class="mask">
      <view class="sheet">
        <text class="sheet-title">试看已结束 · 购买后继续学习</text>
        <text v-if="buyPrice != null" class="price">{{ fmtMoney(buyPrice) }}</text>
        <text class="hint">完整课程需购买后领取权益再学</text>
        <button class="btn buy-cta" @click="goBuy">立即购买</button>
        <text class="link" @click="replayTrial">重播试看</text>
        <text class="link" @click="backCatalog">返回目录</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #0f172a;
  color: #fff;
}
.stage {
  height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #0f172a, #1e293b);
}
.play-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-bottom: 12px;
}
.stage-title {
  font-weight: 700;
  font-size: 15px;
}
.stage-sub {
  margin-top: 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
}
.panel {
  background: #f5f7fb;
  color: #0f172a;
  border-radius: 16px 16px 0 0;
  padding: 16px;
  min-height: calc(100vh - 220px);
}
.time-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}
.badge {
  color: #1677ff;
  font-weight: 600;
}
.bar {
  height: 6px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}
.bar-i {
  height: 100%;
  background: #1677ff;
}
.rates {
  display: flex;
  gap: 8px;
  margin: 14px 0;
}
.chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  font-size: 11px;
  color: #64748b;
}
.chip.on {
  background: #e6f4ff;
  border-color: #91caff;
  color: #1677ff;
  font-weight: 600;
}
.btn {
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 10px;
  margin-bottom: 8px;
  font-weight: 600;
}
.btn.ghost {
  background: #fff;
  color: #334155;
  border: 1px solid #cbd5e1;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: flex-end;
}
.sheet {
  width: 100%;
  background: #fff;
  color: #0f172a;
  border-radius: 16px 16px 0 0;
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
  text-align: center;
}
.sheet-title {
  display: block;
  font-weight: 700;
  margin-bottom: 8px;
}
.price {
  display: block;
  color: #dc2626;
  font-weight: 800;
  font-size: 22px;
  margin-bottom: 8px;
}
.hint {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}
.link {
  display: block;
  margin-top: 10px;
  color: #94a3b8;
  font-size: 12px;
}
</style>
