<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { CONTRACT_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'
import { contractActions } from '@/utils/contractActions'

const contractId = ref('')
const loading = ref(false)
const acting = ref(false)
const contract = ref(null)
const customer = ref(null)
const relatedOrders = ref([])
const members = ref([])
const permissions = ref([])
const userId = ref('')
const rejectVisible = ref(false)
const rejectReason = ref('')

const TYPE_LABEL = { new: '新签', renewal: '续约', addon: '增订' }

function sameUserId(a, b) {
  if (!a || !b) return false
  return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
}
const isOwner = computed(() => sameUserId(contract.value?.owner_user_id, userId.value))
const actions = computed(() =>
  contractActions({
    status: contract.value?.status,
    isOwner: isOwner.value,
    canEdit: hasPermission(permissions.value, 'crm.contract.edit'),
    canSign: hasPermission(permissions.value, 'crm.contract.sign'),
    canApprove: hasPermission(permissions.value, 'crm.contract.approve'),
    canCreate: hasPermission(permissions.value, 'crm.contract.create'),
    canDelete: hasPermission(permissions.value, 'crm.contract.delete'),
    canConvert: hasPermission(permissions.value, 'crm.order.convert'),
  }),
)
const hasAnyAction = computed(() =>
  ['send', 'submit', 'withdraw', 'approve', 'reject', 'sign', 'activate', 'terminate', 'convert', 'clone'].some(
    (k) => actions.value[k],
  ),
)

const ownerLabel = computed(() => {
  if (!contract.value?.owner_user_id) return '—'
  const m = members.value.find((x) => x.user_id === contract.value.owner_user_id)
  return m?.display_name || m?.phone || '—'
})

async function loadDetail() {
  if (!contractId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    userId.value = user?.id || user?.user_id || ''
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    const data = await crmApi.getContract(contractId.value)
    contract.value = data
    if (data.customer_id) {
      try {
        customer.value = await crmApi.getCustomer(data.customer_id)
      } catch {
        customer.value = null
      }
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

async function runAction(fn, okMsg) {
  if (acting.value || !contract.value) return
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

function handleSend() {
  runAction(() => crmApi.sendContract(contract.value.id), '已发送')
}
function handleSubmit() {
  runAction(() => crmApi.submitContract(contract.value.id), '已提交')
}
function handleWithdraw() {
  uni.showModal({
    title: '撤回审批',
    content: '确定撤回？合同将回到草稿。',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.withdrawContract(contract.value.id), '已撤回')
    },
  })
}
function handleApprove() {
  runAction(() => crmApi.approveContract(contract.value.id), '已通过')
}
function handleSign() {
  uni.showModal({
    title: '签署合同',
    content: '确定签署该合同？',
    success: (res) => {
      if (res.confirm) {
        runAction(
          () =>
            crmApi.signContract(contract.value.id, {
              signed_amount: contract.value.signed_amount ?? contract.value.amount,
            }),
          '已签署',
        )
      }
    },
  })
}
function handleActivate() {
  uni.showModal({
    title: '开始执行',
    content: '确定开始执行该合同？',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.activateContract(contract.value.id), '已开始执行')
    },
  })
}
function handleTerminate() {
  uni.showModal({
    title: '终止合同',
    content: '确定终止该合同？',
    success: (res) => {
      if (res.confirm) runAction(() => crmApi.terminateContract(contract.value.id), '已终止')
    },
  })
}
function handleConvert() {
  uni.showModal({
    title: '生成订单',
    content: '确定从该合同生成订单？',
    success: (res) => {
      if (!res.confirm) return
      runAction(async () => {
        const data = await crmApi.convertContractToOrder(contract.value.id)
        const orderId = data?.order_id || data?.id
        if (orderId) {
          uni.navigateTo({ url: `/pages/crm/order-detail?id=${orderId}` })
        }
      }, '已生成订单')
    },
  })
}
function handleClone() {
  runAction(async () => {
    const data = await crmApi.cloneContract(contract.value.id)
    if (data?.id) {
      uni.navigateTo({ url: `/pages/crm/contract-detail?id=${data.id}` })
    }
  }, '已复制')
}
async function submitReject() {
  if (!rejectReason.value.trim()) {
    uni.showToast({ title: '请填写驳回原因', icon: 'none' })
    return
  }
  await runAction(
    () => crmApi.rejectContract(contract.value.id, { reason: rejectReason.value.trim() }),
    '已驳回',
  )
  rejectVisible.value = false
  rejectReason.value = ''
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
        <view class="kpi-row">
          <view class="kpi-item">
            <text class="kpi-item__label">合同金额</text>
            <text class="kpi-item__val">{{ formatMoney(contract.amount) }}</text>
          </view>
          <view class="kpi-item">
            <text class="kpi-item__label">签约金额</text>
            <text class="kpi-item__val">{{ contract.signed_amount != null ? formatMoney(contract.signed_amount) : '—' }}</text>
          </view>
          <view class="kpi-item">
            <text class="kpi-item__label">差额</text>
            <text class="kpi-item__val">{{ contract.amount_diff != null ? formatMoney(contract.amount_diff) : '—' }}</text>
          </view>
          <view class="kpi-item">
            <text class="kpi-item__label">剩余天数</text>
            <text class="kpi-item__val">{{ contract.days_remaining != null ? contract.days_remaining + ' 天' : '—' }}</text>
          </view>
        </view>
      </view>

      <view v-if="hasAnyAction" class="actions">
        <button v-if="actions.send" class="act" hover-class="none" :disabled="acting" @tap="handleSend">发送</button>
        <button v-if="actions.submit" class="act act--primary" hover-class="none" :disabled="acting" @tap="handleSubmit">提交</button>
        <button v-if="actions.withdraw" class="act" hover-class="none" :disabled="acting" @tap="handleWithdraw">撤回</button>
        <button v-if="actions.approve" class="act act--ok" hover-class="none" :disabled="acting" @tap="handleApprove">通过</button>
        <button v-if="actions.reject" class="act act--danger" hover-class="none" :disabled="acting" @tap="rejectVisible = true">驳回</button>
        <button v-if="actions.sign" class="act act--ok" hover-class="none" :disabled="acting" @tap="handleSign">签署</button>
        <button v-if="actions.activate" class="act act--primary" hover-class="none" :disabled="acting" @tap="handleActivate">开始执行</button>
        <button v-if="actions.terminate" class="act act--danger" hover-class="none" :disabled="acting" @tap="handleTerminate">终止</button>
        <button v-if="actions.convert" class="act act--primary" hover-class="none" :disabled="acting" @tap="handleConvert">生成订单</button>
        <button v-if="actions.clone" class="act" hover-class="none" :disabled="acting" @tap="handleClone">复制</button>
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
.page { min-height: 100vh; background: #f0f2f5; padding: 12px; box-sizing: border-box; padding-bottom: 40px; }
.hero-card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.hero-card__head { display: flex; justify-content: space-between; gap: 10px; }
.hero-card__title { flex: 1; font-size: 17px; font-weight: 600; }
.status { font-size: 11px; color: #1677ff; background: #e6f4ff; padding: 3px 10px; border-radius: 999px; height: fit-content; }
.amount { display: block; margin-top: 12px; font-size: 24px; font-weight: 700; color: #1677ff; }
.sub { display: block; margin-top: 4px; font-size: 13px; color: #94a3b8; }
.kpi-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #f1f5f9; }
.kpi-item { flex: 1 1 40%; min-width: 100px; }
.kpi-item__label { display: block; font-size: 11px; color: #94a3b8; }
.kpi-item__val { display: block; margin-top: 4px; font-size: 14px; font-weight: 600; color: #334155; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.act {
  margin: 0; padding: 0 14px; height: 32px; line-height: 32px; font-size: 13px;
  background: #fff; color: #334155; border: 1px solid #e2e8f0; border-radius: 8px;
}
.act--primary { background: #1677ff; color: #fff; border-color: #1677ff; }
.act--ok { background: #52c41a; color: #fff; border-color: #52c41a; }
.act--danger { background: #fff; color: #ff4d4f; border-color: #ffccc7; }
.act[disabled] { opacity: 0.5; }
.section { background: #fff; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.section__title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 12px; padding-left: 8px; border-left: 3px solid #1677ff; }
.desc-grid { display: grid; grid-template-columns: 5em 1fr; gap: 10px 8px; font-size: 13px; }
.desc-label { color: #94a3b8; }
.desc-value { color: #334155; }
.line-card { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.line-card__name { display: block; font-size: 14px; font-weight: 500; }
.line-card__meta { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
.empty, .empty-inline { text-align: center; color: #94a3b8; padding: 24px 0; font-size: 13px; }
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
