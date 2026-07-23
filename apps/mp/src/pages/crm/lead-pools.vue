<script setup>
import { computed, ref, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { crmApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { formatDateTime } from '@/utils/datetime'

const loading = ref(false)
const claimingId = ref('')
const permissions = ref([])
const pools = ref([])
const activePoolId = ref('')
const leads = ref([])

const canClaim = () => hasPermission(permissions.value, 'crm.lead.edit')
const activePool = computed(() => pools.value.find((p) => p.id === activePoolId.value) || null)

async function loadPools() {
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    const data = await crmApi.listLeadPools()
    pools.value = Array.isArray(data) ? data : []
    if (!pools.value.length) {
      activePoolId.value = ''
      leads.value = []
      return
    }
    if (!activePoolId.value || !pools.value.some((p) => p.id === activePoolId.value)) {
      activePoolId.value = pools.value[0].id
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载公海失败', icon: 'none' })
    pools.value = []
    leads.value = []
  } finally {
    loading.value = false
  }
}

async function loadLeads() {
  if (!activePoolId.value) {
    leads.value = []
    return
  }
  loading.value = true
  try {
    const data = await crmApi.listLeadPoolLeads(activePoolId.value)
    leads.value = Array.isArray(data) ? data : []
  } catch (e) {
    uni.showToast({ title: e.message || '加载公海线索失败', icon: 'none' })
    leads.value = []
  } finally {
    loading.value = false
  }
}

function selectPool(id) {
  if (activePoolId.value === id) return
  activePoolId.value = id
}

function goLead(row) {
  uni.navigateTo({ url: `/pages/crm/lead-detail?id=${row.id}` })
}

async function claim(row) {
  if (!canClaim() || !activePoolId.value) return
  const { confirm } = await new Promise((resolve) => {
    uni.showModal({
      title: '认领线索',
      content: `认领「${row.company_name}」？认领后将归到你名下。`,
      success: resolve,
      fail: () => resolve({ confirm: false }),
    })
  })
  if (!confirm) return
  claimingId.value = row.id
  try {
    await crmApi.claimLeadFromPool(activePoolId.value, row.id)
    uni.showToast({ title: '已认领', icon: 'success' })
    await loadLeads()
    uni.navigateTo({ url: `/pages/crm/lead-detail?id=${row.id}` })
  } catch (e) {
    uni.showToast({ title: e.message || '认领失败', icon: 'none' })
  } finally {
    claimingId.value = ''
  }
}

function formatTime(v) {
  return formatDateTime(v, { withSeconds: false })
}

watch(activePoolId, (id) => {
  if (id) loadLeads()
})

onShow(() => {
  loadPools().then(() => {
    if (activePoolId.value) loadLeads()
  })
})
</script>

<template>
  <view class="page">
    <view class="hint-card">
      <text class="hint-title">线索公海</text>
      <text class="hint-sub">查看待认领线索；可先看详情，认领后进入「我的线索」跟进。</text>
    </view>

    <view v-if="loading && !pools.length" class="empty">加载中…</view>
    <view v-else-if="!pools.length" class="empty">暂无线索公海</view>

    <template v-else>
      <scroll-view scroll-x class="pool-tabs" :show-scrollbar="false">
        <view
          v-for="p in pools"
          :key="p.id"
          class="pool-tab"
          :class="{ 'pool-tab--on': p.id === activePoolId }"
          @tap="selectPool(p.id)"
        >
          {{ p.name }}
        </view>
      </scroll-view>

      <view v-if="activePool" class="meta-row">
        <text v-if="activePool.auto_reclaim_days">自动回收 {{ activePool.auto_reclaim_days }} 天</text>
        <text>待认领 {{ leads.length }} 条</text>
      </view>

      <view v-if="loading && !leads.length" class="empty">加载中…</view>
      <view v-else-if="!leads.length" class="empty">该公海暂无待认领线索</view>

      <view v-for="row in leads" :key="row.id" class="card" @tap="goLead(row)">
        <view class="card__head">
          <text class="card__title">{{ row.company_name }}</text>
          <text class="card__status">{{ row.status || '—' }}</text>
        </view>
        <text class="card__meta">
          {{ row.contact_name || '—' }} · {{ row.mobile || row.phone || '—' }}
        </text>
        <text class="card__meta">
          来源 {{ row.source || '—' }} · 评分 {{ row.lead_score ?? '—' }}
        </text>
        <text class="card__meta">入库 {{ formatTime(row.created_at) }}</text>
        <view v-if="canClaim()" class="card__acts" @tap.stop>
          <button
            class="btn btn--primary"
            size="mini"
            :loading="claimingId === row.id"
            @tap="claim(row)"
          >
            认领
          </button>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 12px;
  box-sizing: border-box;
}
.hint-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}
.hint-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
}
.hint-sub {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.5;
}
.pool-tabs {
  white-space: nowrap;
  margin-bottom: 10px;
}
.pool-tab {
  display: inline-block;
  padding: 6px 14px;
  margin-right: 8px;
  border-radius: 999px;
  background: #fff;
  font-size: 13px;
  color: #595959;
}
.pool-tab--on {
  background: #1677ff;
  color: #fff;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #8c8c8c;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 10px;
}
.card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.card__title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}
.card__status {
  font-size: 12px;
  color: #1677ff;
}
.card__meta {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #8c8c8c;
}
.card__acts {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
.btn {
  margin: 0;
}
.btn--primary {
  background: #1677ff;
  color: #fff;
}
.empty {
  text-align: center;
  padding: 40px 12px;
  color: #8c8c8c;
  font-size: 13px;
}
</style>
