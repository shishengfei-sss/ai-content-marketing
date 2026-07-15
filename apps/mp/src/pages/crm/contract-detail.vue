<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { CONTRACT_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'

const contractId = ref('')
const loading = ref(false)
const contract = ref(null)
const customer = ref(null)
const relatedOrders = ref([])
const members = ref([])

const TYPE_LABEL = { new: '新签', renewal: '续约', addon: '增订' }

const ownerLabel = computed(() => {
  if (!contract.value?.owner_user_id) return '—'
  const m = members.value.find((x) => x.user_id === contract.value.owner_user_id)
  return m?.display_name || m?.phone || '—'
})

async function loadDetail() {
  if (!contractId.value) return
  loading.value = true
  try {
    await ensureSession()
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    const data = await crmApi.getContract(contractId.value)
    contract.value = data
    if (data.customer_id) {
      try { customer.value = await crmApi.getCustomer(data.customer_id) } catch { customer.value = null }
    }
    try {
      const orders = await crmApi.listOrders({ contract_id: contractId.value, page: 1, page_size: 50 })
      relatedOrders.value = orders?.items || []
    } catch {
      relatedOrders.value = []
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goOrder(item) {
  uni.navigateTo({ url: `/pages/crm/order-detail?id=${item.id}` })
}

onLoad((query) => {
  contractId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="contract">
      <view class="hero-card">
        <view class="hero-card__head">
          <text class="hero-card__title">{{ contract.title }}</text>
          <text class="status">{{ CONTRACT_STATUS_LABEL[contract.status] || contract.status }}</text>
        </view>
        <view class="amount">{{ formatMoney(contract.signed_amount != null ? contract.signed_amount : contract.amount) }}</view>
        <text class="sub">{{ contract.contract_number }} · {{ TYPE_LABEL[contract.contract_type] || contract.contract_type }}</text>
      </view>

      <view class="section">
        <text class="section__title">基本信息</text>
        <view class="desc-grid">
          <text class="desc-label">客户</text><text class="desc-value">{{ customer?.company_name || '—' }}</text>
          <text class="desc-label">金额</text><text class="desc-value">{{ formatMoney(contract.amount) }}</text>
          <text class="desc-label">负责人</text><text class="desc-value">{{ ownerLabel }}</text>
          <text class="desc-label">到期日</text>
          <text class="desc-value">{{ contract.end_date ? String(contract.end_date).slice(0, 10) : '—' }}</text>
        </view>
      </view>

      <view class="section">
        <text class="section__title">关联订单（{{ relatedOrders.length }}）</text>
        <view v-if="!relatedOrders.length" class="empty-inline">暂无关联订单</view>
        <view v-for="o in relatedOrders" :key="o.id" class="line-card" @tap="goOrder(o)">
          <text class="line-card__name">{{ o.title || o.order_number }}</text>
          <text class="line-card__meta">{{ o.order_number }} · {{ formatMoney(o.amount) }}</text>
        </view>
      </view>
    </template>
    <view v-else class="empty">合同不存在</view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; background: #f0f2f5; padding: 12px; box-sizing: border-box; }
.hero-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.hero-card__head { display: flex; justify-content: space-between; gap: 10px; }
.hero-card__title { flex: 1; font-size: 17px; font-weight: 600; }
.status { font-size: 11px; color: #1677ff; background: #e6f4ff; padding: 3px 10px; border-radius: 999px; height: fit-content; }
.amount { display: block; margin-top: 12px; font-size: 24px; font-weight: 700; color: #1677ff; }
.sub { display: block; margin-top: 4px; font-size: 13px; color: #94a3b8; }
.section { background: #fff; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.section__title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 12px; padding-left: 8px; border-left: 3px solid #1677ff; }
.desc-grid { display: grid; grid-template-columns: 5em 1fr; gap: 10px 8px; font-size: 13px; }
.desc-label { color: #94a3b8; }
.desc-value { color: #334155; }
.line-card { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.line-card__name { display: block; font-size: 14px; font-weight: 500; }
.line-card__meta { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
.empty, .empty-inline { text-align: center; color: #94a3b8; padding: 24px 0; font-size: 13px; }
</style>
