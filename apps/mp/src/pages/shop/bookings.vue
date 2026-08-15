<script setup>
/**
 * M10c 我的预约列表。对照 PRD #m10c · #m10d
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const loading = ref(false)
const items = ref([])
const tab = ref('active') // active | done

const STATUS_LABEL = {
  booked: '待服务',
  completed: '已完成',
  cancelled: '已取消',
}

const filtered = computed(() => {
  if (tab.value === 'active') return items.value.filter((i) => i.status === 'booked')
  return items.value.filter((i) => i.status !== 'booked')
})

async function load() {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId())
    const data = await shopBuyerApi.listBookings({ page: 1, page_size: 50 })
    items.value = data.items || []
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function viewCode(row) {
  uni.navigateTo({
    url: `/pages/shop/verify-code?entitlement_id=${row.entitlement_id}&booking_id=${row.id}&slot=${encodeURIComponent(
      `${row.booked_date} ${row.booked_time_slot}`
    )}`,
  })
}

function cancel(row) {
  uni.showModal({
    title: '确认取消本次预约？',
    content: '取消后核销码失效，不扣减次数，名额将释放给其他买家。',
    confirmText: '确认取消',
    confirmColor: '#dc2626',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await shopBuyerApi.cancelBooking(row.id, 'buyer_cancel')
        uni.showToast({ title: '已取消', icon: 'success' })
        await load()
      } catch (e) {
        uni.showToast({ title: e.message || '取消失败', icon: 'none' })
      }
    },
  })
}

onShow(load)
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">我的预约</text>
    </view>
    <view class="chips">
      <text class="chip" :class="{ on: tab === 'active' }" @click="tab = 'active'">待服务</text>
      <text class="chip" :class="{ on: tab === 'done' }" @click="tab = 'done'">已完成/取消</text>
    </view>
    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="!filtered.length" class="empty">暂无预约</view>
    <view v-else class="list">
      <view v-for="row in filtered" :key="row.id" class="card">
        <view class="row">
          <text class="name">{{ row.product_name || '服务' }} {{ row.booked_date }} {{ row.booked_time_slot }}</text>
          <text class="badge">{{ STATUS_LABEL[row.status] || row.status }}</text>
        </view>
        <view v-if="row.status === 'booked'" class="ops">
          <text class="link" @click="viewCode(row)">查看码</text>
          <button class="btn" size="mini" @click="cancel(row)">取消预约</button>
        </view>
        <text v-else-if="row.cancel_reason === 'expired_unredeemed'" class="hint">已取消 · 过期未核销</text>
        <text v-else-if="row.cancel_reason === 'slot_closed'" class="hint">已取消 · 关闭时段</text>
        <text v-else-if="row.cancel_reason" class="hint">已取消</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f7fb;
  padding: 16px;
}
.head {
  margin-bottom: 12px;
}
.title {
  font-size: 20px;
  font-weight: 700;
}
.chips {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.chip {
  padding: 6px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  color: #64748b;
}
.chip.on {
  background: #e6f4ff;
  border-color: #91caff;
  color: #1677ff;
  font-weight: 600;
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
.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.name {
  font-size: 13px;
  font-weight: 600;
  flex: 1;
}
.badge {
  font-size: 11px;
  color: #1677ff;
  flex-shrink: 0;
}
.ops {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}
.link {
  color: #1677ff;
  font-size: 13px;
  font-weight: 600;
}
.btn {
  margin: 0;
  background: #fff;
  border: 1px solid #cbd5e1;
  color: #334155;
  border-radius: 8px;
}
.hint {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: #94a3b8;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
