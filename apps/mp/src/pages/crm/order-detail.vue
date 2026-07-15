<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { ORDER_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'

const orderId = ref('')
const loading = ref(false)
const acting = ref(false)
const order = ref(null)
const customer = ref(null)
const members = ref([])
const permissions = ref([])
const rejectVisible = ref(false)
const rejectReason = ref('')

const SOURCE_LABEL = { deal: '商机', quote: '报价', contract: '合同', manual: '手工' }

const canPlace = () => hasPermission(permissions.value, 'crm.order.place')
const canApprove = () => hasPermission(permissions.value, 'crm.order.approve')
const canEdit = () => hasPermission(permissions.value, 'crm.order.edit')

const ownerLabel = computed(() => {
  if (!order.value?.owner_user_id) return '—'
  const m = members.value.find((x) => x.user_id === order.value.owner_user_id)
  return m?.display_name || m?.phone || '—'
})

async function loadDetail() {
  if (!orderId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    const data = await crmApi.getOrder(orderId.value)
    order.value = data
    if (data.customer_id) {
      try {
        customer.value = await crmApi.getCustomer(data.customer_id)
      } catch {
        customer.value = null
      }
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function runAction(fn, okMsg) {
  if (acting.value || !order.value) return
  acting.value = true
  try {
    await fn()
    uni.showToast({ title: okMsg, icon: 'success' })
    await loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  } finally {
    acting.value = false
  }
}

function handleConfirm() {
  runAction(() => crmApi.confirmOrder(order.value.id), '已确认')
}
function handleSubmit() {
  runAction(() => crmApi.submitOrder(order.value.id), '已提交')
}
function handleApprove() {
  runAction(() => crmApi.approveOrder(order.value.id), '已通过')
}
function handleCancel() {
  uni.showModal({
    title: '取消订单',
    content: '确定取消该订单？',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.cancelOrder(order.value.id), '已取消')
    },
  })
}
async function submitReject() {
  if (!rejectReason.value.trim()) {
    uni.showToast({ title: '请填写驳回原因', icon: 'none' })
    return
  }
  await runAction(
    () => crmApi.rejectOrder(order.value.id, { reason: rejectReason.value.trim() }),
    '已驳回',
  )
  rejectVisible.value = false
  rejectReason.value = ''
}

onLoad((query) => {
  orderId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="order">
      <view class="hero-card">
        <view class="hero-card__head">
          <text class="hero-card__title">{{ order.title || order.order_number }}</text>
          <text class="status">{{ ORDER_STATUS_LABEL[order.status] || order.status }}</text>
        </view>
        <view class="amount">{{ formatMoney(order.amount) }}</view>
        <text class="sub">{{ order.order_number }}</text>
      </view>

      <view class="actions">
        <button
          v-if="canPlace() && (order.status === 'draft' || order.status === 'rejected')"
          class="act act--primary"
          hover-class="none"
          :disabled="acting"
          @tap="handleSubmit"
        >提交审批</button>
        <button
          v-if="canPlace() && order.status === 'draft'"
          class="act act--ok"
          hover-class="none"
          :disabled="acting"
          @tap="handleConfirm"
        >直接确认</button>
        <button
          v-if="canApprove() && order.status === 'pending_approval'"
          class="act act--ok"
          hover-class="none"
          :disabled="acting"
          @tap="handleApprove"
        >通过</button>
        <button
          v-if="canApprove() && order.status === 'pending_approval'"
          class="act act--danger"
          hover-class="none"
          :disabled="acting"
          @tap="rejectVisible = true"
        >驳回</button>
        <button
          v-if="canEdit() && order.status !== 'cancelled' && order.status !== 'completed'"
          class="act"
          hover-class="none"
          :disabled="acting"
          @tap="handleCancel"
        >取消</button>
      </view>

      <view class="section">
        <text class="section__title">基本信息</text>
        <view class="desc-grid">
          <text class="desc-label">客户</text><text class="desc-value">{{ customer?.company_name || '—' }}</text>
          <text class="desc-label">来源</text><text class="desc-value">{{ SOURCE_LABEL[order.source] || order.source || '—' }}</text>
          <text class="desc-label">负责人</text><text class="desc-value">{{ ownerLabel }}</text>
          <text class="desc-label">下单日期</text>
          <text class="desc-value">{{ order.order_date ? new Date(order.order_date).toLocaleDateString('zh-CN') : '—' }}</text>
        </view>
      </view>

      <view v-if="order.lines?.length" class="section">
        <text class="section__title">订单明细</text>
        <view v-for="line in order.lines" :key="line.id" class="line-card">
          <text class="line-card__name">{{ line.name || line.product_name }}</text>
          <text class="line-card__meta">数量 {{ line.quantity }} · {{ formatMoney(line.line_total ?? line.subtotal) }}</text>
        </view>
      </view>
    </template>
    <view v-else class="empty">订单不存在</view>

    <view v-if="rejectVisible" class="mask" @tap.self="rejectVisible = false">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">驳回审批</text>
        <textarea v-model="rejectReason" class="textarea" maxlength="500" placeholder="请填写驳回原因" />
        <view class="dialog__acts">
          <button class="act" hover-class="none" @tap="rejectVisible = false">取消</button>
          <button class="act act--danger" hover-class="none" :disabled="acting" @tap="submitReject">确认驳回</button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
  padding-bottom: 40px;
}
.hero-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}
.hero-card__head { display: flex; justify-content: space-between; gap: 10px; }
.hero-card__title { flex: 1; font-size: 17px; font-weight: 600; }
.status {
  font-size: 11px; color: #1677ff; background: #e6f4ff;
  padding: 3px 10px; border-radius: 999px; height: fit-content;
}
.amount { display: block; margin-top: 12px; font-size: 24px; font-weight: 700; color: #1677ff; }
.sub { display: block; margin-top: 4px; font-size: 13px; color: #94a3b8; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.act {
  margin: 0; font-size: 13px; padding: 0 14px; height: 34px; line-height: 34px;
  border-radius: 8px; background: #fff; color: #334155; border: 1px solid #e2e8f0;
}
.act--primary { background: #1677ff; color: #fff; border-color: #1677ff; }
.act--ok { background: #52c41a; color: #fff; border-color: #52c41a; }
.act--danger { background: #ff4d4f; color: #fff; border-color: #ff4d4f; }
.section {
  background: #fff; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px;
}
.section__title {
  display: block; font-size: 15px; font-weight: 600; margin-bottom: 12px;
  padding-left: 8px; border-left: 3px solid #1677ff;
}
.desc-grid { display: grid; grid-template-columns: 5em 1fr; gap: 10px 8px; font-size: 13px; }
.desc-label { color: #94a3b8; }
.desc-value { color: #334155; }
.line-card { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.line-card__name { display: block; font-size: 14px; font-weight: 500; }
.line-card__meta { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
.empty { text-align: center; color: #94a3b8; padding: 40px 0; }
.mask {
  position: fixed; inset: 0; z-index: 2000; background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.dialog { width: 100%; max-width: 360px; background: #fff; border-radius: 12px; padding: 16px; }
.dialog__title { display: block; font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.textarea {
  width: 100%; min-height: 90px; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 10px; font-size: 14px; box-sizing: border-box;
}
.dialog__acts { display: flex; gap: 10px; margin-top: 12px; }
.dialog__acts .act { flex: 1; }
</style>
