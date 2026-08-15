<script setup>
/**
 * M10 服务预约。对照 PRD #m10 · #m10-times-card
 * 关联 A07 service_offer：拉真实开放槽；否则回退本地演示槽（兼容旧商品）
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const entitlementId = ref('')
const ent = ref(null)
const loading = ref(true)
const submitting = ref(false)
const selected = ref(null) // { slot_id?, date, slot }
/** times_card | booking */
const mode = ref('times_card')
const apiSlots = ref([])
const useApiSlots = ref(false)

const FALLBACK_SLOTS = ['10:00-11:00', '14:00-15:00', '16:00-17:00']

function pad(n) {
  return String(n).padStart(2, '0')
}
function addDays(base, n) {
  const d = new Date(base)
  d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function fmtSlot(isoStart, isoEnd) {
  const s = new Date(isoStart)
  const e = new Date(isoEnd)
  const date = `${s.getFullYear()}-${pad(s.getMonth() + 1)}-${pad(s.getDate())}`
  const slot = `${pad(s.getHours())}:${pad(s.getMinutes())}-${pad(e.getHours())}:${pad(e.getMinutes())}`
  return { date, slot }
}

const slotRows = computed(() => {
  if (useApiSlots.value) {
    return (apiSlots.value || []).map((s) => {
      const { date, slot } = fmtSlot(s.start_at, s.end_at)
      return {
        key: s.id,
        slot_id: s.id,
        date,
        slot,
        full: !s.selectable,
        label: s.selectable ? `余 ${Math.max(0, s.capacity - s.booked_count)}` : s.status === 'full' ? '已满' : '不可选',
      }
    })
  }
  const today = new Date()
  const rows = []
  for (let i = 1; i <= 3; i++) {
    const date = addDays(today, i)
    for (const slot of FALLBACK_SLOTS) {
      rows.push({
        key: `${date}|${slot}`,
        date,
        slot,
        full: false,
        label: '可选',
      })
    }
  }
  return rows
})

const remainingText = computed(() => {
  const rem = ent.value?.remaining_count
  return rem != null ? `剩余 ${rem} 次` : '服务预约'
})

const showSlotPicker = computed(() => mode.value === 'booking' || !ent.value?.service_offer_id)

async function load() {
  loading.value = true
  try {
    const tid = getShopBuyerTenantId()
    await ensureShopBuyerSession(tid)
    const data = await shopBuyerApi.listEntitlements({ page: 1, page_size: 50 })
    ent.value = (data.items || []).find((i) => i.id === entitlementId.value) || null
    if (!ent.value) throw new Error('权益不存在')
    if (ent.value.status !== 'active') throw new Error('权益已关闭')

    if (ent.value.service_offer_id) {
      const slotsRes = await shopBuyerApi.listServiceSlots(ent.value.service_offer_id, {
        entitlement_id: entitlementId.value,
      })
      mode.value = slotsRes.mode || ent.value.service_mode || 'booking'
      if (mode.value === 'booking') {
        useApiSlots.value = true
        apiSlots.value = slotsRes.slots || []
      } else {
        useApiSlots.value = false
      }
    } else {
      // 旧商品：有次数字段 → 次数卡主路径
      mode.value = ent.value.remaining_count != null ? 'times_card' : 'booking'
      useApiSlots.value = false
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function pick(row) {
  if (row.full) return
  selected.value = { key: row.key, slot_id: row.slot_id, date: row.date, slot: row.slot }
}

async function confirmBooking() {
  if (!selected.value) {
    uni.showToast({ title: '请选择时段', icon: 'none' })
    return
  }
  if (ent.value?.remaining_count != null && ent.value.remaining_count <= 0) {
    uni.showToast({ title: '剩余次数不足', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const body = { entitlement_id: entitlementId.value }
    if (selected.value.slot_id) {
      body.slot_id = selected.value.slot_id
    } else {
      body.booked_date = selected.value.date
      body.booked_time_slot = selected.value.slot
    }
    const booking = await shopBuyerApi.createBooking(body)
    uni.redirectTo({
      url: `/pages/shop/verify-code?entitlement_id=${entitlementId.value}&booking_id=${booking.id}&slot=${encodeURIComponent(
        `${selected.value.date} ${selected.value.slot}`
      )}`,
    })
  } catch (e) {
    uni.showToast({ title: e.message || '预约失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function getCodeOnly() {
  if (ent.value?.remaining_count != null && ent.value.remaining_count <= 0) {
    uni.showToast({ title: '剩余次数不足', icon: 'none' })
    return
  }
  if (!ent.value?.verify_code) {
    uni.showToast({ title: '暂无核销码', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/shop/verify-code?entitlement_id=${entitlementId.value}&mode=times_card`,
  })
}

function goMyBookings() {
  uni.navigateTo({ url: '/pages/shop/bookings' })
}

onLoad((q) => {
  entitlementId.value = (q?.entitlement_id || '').trim()
  if (!entitlementId.value) {
    uni.showToast({ title: '缺少权益', icon: 'none' })
    return
  }
  load()
})
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">{{ ent?.product_name || '预约咨询' }}</text>
      <text class="sub">{{ remainingText }}</text>
    </view>

    <view v-if="loading" class="empty">加载中…</view>

    <template v-else-if="ent">
      <view v-if="mode === 'times_card'" class="info-card">
        <text class="info-title">权益说明</text>
        <text class="info-body">
          共 {{ ent.total_count ?? '—' }} 次 · 剩余 {{ ent.remaining_count ?? '—' }} 次
          {'\n'}到店出示核销码，店员核销后扣 1 次
          {'\n'}无需选择时段也可直接获取核销码
        </text>
        <button class="btn-primary" @click="getCodeOnly">获取核销码</button>
      </view>

      <template v-if="showSlotPicker && mode === 'booking'">
        <view class="section-title">选择时段 · {{ remainingText }}</view>
        <view v-if="!slotRows.length" class="empty">暂无可预约时段</view>
        <view
          v-for="row in slotRows"
          :key="row.key"
          class="slot"
          :class="{
            on: selected && selected.key === row.key || (selected && selected.slot_id && selected.slot_id === row.slot_id),
            full: row.full,
          }"
          @click="pick(row)"
        >
          <view>
            <text class="slot-main">{{ row.date }} {{ row.slot }}</text>
            <text class="slot-sub">{{ row.label || (row.full ? '已满' : '可选') }}</text>
          </view>
          <text
            v-if="selected && (selected.slot_id === row.slot_id || (!row.slot_id && selected.date === row.date && selected.slot === row.slot))"
            class="badge"
          >
            选中
          </text>
        </view>

        <view class="footer">
          <button class="btn-ghost" @click="goMyBookings">我的预约</button>
          <button class="btn-primary" :loading="submitting" @click="confirmBooking">确认预约</button>
        </view>
      </template>

      <view v-else-if="mode === 'times_card'" class="footer">
        <button class="btn-ghost" @click="goMyBookings">我的预约</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px 16px 100px;
  box-sizing: border-box;
}
.head {
  margin-bottom: 14px;
}
.title {
  display: block;
  font-size: 18px;
  font-weight: 700;
}
.sub {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.info-card {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 16px;
}
.info-title {
  display: block;
  font-weight: 700;
  margin-bottom: 6px;
}
.info-body {
  display: block;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  white-space: pre-line;
  margin-bottom: 12px;
}
.section-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
}
.slot {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.slot.on {
  border-color: #1677ff;
}
.slot.full {
  opacity: 0.45;
}
.slot-main {
  display: block;
  font-size: 13px;
  font-weight: 600;
}
.slot-sub {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #64748b;
}
.badge {
  font-size: 11px;
  color: #1677ff;
  font-weight: 700;
}
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 10px;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -1px 0 #e2e8f0;
}
.btn-primary {
  flex: 1;
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-weight: 600;
}
.btn-ghost {
  background: #fff;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
