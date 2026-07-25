<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import { DEAL_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'
import CrmEntityTasks from '@/components/crm/CrmEntityTasks.vue'
import { formatDateTime } from '@/utils/datetime'

const dealId = ref('')
const loading = ref(false)
const deal = ref(null)
const customer = ref(null)
const pipelines = ref([])
const activities = ref([])
const permissions = ref([])
const members = ref([])
const stageSheetVisible = ref(false)
const assignVisible = ref(false)
const selectedOwner = ref('')
const taskPanelRef = ref(null)

const { fields, loadSchema, formatCell } = useEntitySchema('deal')

const activityForm = ref({ activity_type: 'call', subject: '', content: '' })
const activityTypeOptions = [
  { value: 'call', label: '电话' },
  { value: 'visit', label: '拜访' },
  { value: 'wechat', label: '微信' },
  { value: 'email', label: '邮件' },
  { value: 'other', label: '其他' },
]

const canEdit = () => hasPermission(permissions.value, 'crm.deal.edit')
const canAssignPerm = () => hasPermission(permissions.value, 'crm.deal.assign')
const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')
const canClosePerm = () => hasPermission(permissions.value, 'crm.deal.close')
const canReopenPerm = () => hasPermission(permissions.value, 'crm.deal.reopen')
const currentUserId = ref('')
const sameUserId = (a, b) =>
  !!a && !!b && String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
const isDealOwner = () => sameUserId(deal.value?.owner_user_id, currentUserId.value)
const isClosed = computed(() => ['won', 'lost', 'abandoned'].includes(deal.value?.status))
/** 编辑 / 推进阶段：权限 + 负责人 + 未关闭 */
const canMutateDeal = () => canEdit() && isDealOwner() && !isClosed.value
/** 写跟进：跟进权限 + 负责人（与 Web 对齐） */
const canWriteDealActivity = () => canActivity() && isDealOwner()
const canAssign = () => canAssignPerm() && !isClosed.value
const canCloseDeal = () => canClosePerm() && isDealOwner() && !isClosed.value
const canReopenDeal = () => canReopenPerm() && isClosed.value

const closeVisible = ref(false)
const closeBusy = ref(false)
const closeForm = ref({ status: 'won', amount: null, reason: '' })

const stages = computed(() => {
  const pipe = pipelines.value.find((p) => String(p.id) === String(deal.value?.pipeline_id))
  return pipe?.stages || []
})

const currentStageName = computed(() => {
  const s = stages.value.find((x) => String(x.id) === String(deal.value?.stage_id))
  return s?.name || '—'
})

const ownerLabel = computed(() => {
  if (!deal.value?.owner_user_id) return '—'
  const m = members.value.find((x) => String(x.user_id).replace(/-/g, '') === String(deal.value.owner_user_id).replace(/-/g, ''))
  return m?.display_name || m?.phone || '—'
})

const selectedOwnerLabel = computed(() => {
  if (!selectedOwner.value) return '选择成员'
  const m = members.value.find((x) => String(x.user_id) === String(selectedOwner.value))
  return m?.display_name || m?.phone || '已选择'
})

const extraFields = computed(() => {
  const row = deal.value || {}
  return (fields.value || [])
    .filter((f) => {
      if (f.is_active === false || !f.show_in_form) return false
      const key = f.field_key
      if (['title', 'amount', 'status', 'stage_id', 'pipeline_id', 'customer_id', 'owner_user_id'].includes(key)) return false
      const val = row[key] !== undefined ? row[key] : row.extra_data?.[key]
      return val !== undefined && val !== null && val !== ''
    })
    .map((f) => ({
      label: f.label,
      value: formatCell(row, f.field_key, f.field_type),
    }))
})

async function loadDetail() {
  if (!dealId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    currentUserId.value = user?.id || ''
    await loadSchema()
    const [dealData, pipeData, acts] = await Promise.all([
      crmApi.getDeal(dealId.value),
      crmApi.listPipelines(),
      crmApi.listDealActivities(dealId.value),
    ])
    deal.value = dealData
    pipelines.value = Array.isArray(pipeData) ? pipeData : []
    activities.value = Array.isArray(acts) ? acts : []
    if (dealData.customer_id) {
      try {
        customer.value = await crmApi.getCustomer(dealData.customer_id)
      } catch {
        customer.value = null
      }
    }
    try {
      if (canAssign()) {
        members.value = await crmApi.listAssignableOwners({
          include_user_id: dealData.owner_user_id || undefined,
        })
      } else {
        members.value = await teamApi.listMembers()
      }
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
    await taskPanelRef.value?.reload()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openAssign() {
  selectedOwner.value = deal.value?.owner_user_id || ''
  assignVisible.value = true
}

async function submitAssign() {
  if (!selectedOwner.value) {
    uni.showToast({ title: '请选择负责人', icon: 'none' })
    return
  }
  try {
    await crmApi.updateDeal(dealId.value, { owner_user_id: selectedOwner.value })
    assignVisible.value = false
    try {
      const dealData = await crmApi.getDeal(dealId.value)
      deal.value = dealData
      uni.showToast({ title: '已分配', icon: 'success' })
      if (canAssign()) {
        members.value = await crmApi.listAssignableOwners({
          include_user_id: dealData.owner_user_id || undefined,
        }).catch(() => [])
        if (!Array.isArray(members.value)) members.value = []
      }
    } catch (e) {
      const msg = e.message || ''
      if (e.status === 403 || msg.includes('无权访问')) {
        uni.showToast({ title: '已分配，已不在可见范围', icon: 'none' })
        setTimeout(() => uni.navigateBack(), 800)
        return
      }
      throw e
    }
  } catch (e) {
    uni.showToast({ title: e.message || '分配失败', icon: 'none' })
  }
}

function openStageSheet() {
  if (!canMutateDeal()) {
    uni.showToast({ title: '仅商机负责人可推进阶段', icon: 'none' })
    return
  }
  stageSheetVisible.value = true
}

async function pickStage(stage) {
  stageSheetVisible.value = false
  if (!canMutateDeal()) return
  if (!stage || String(stage.id) === String(deal.value?.stage_id)) return
  try {
    await crmApi.changeDealStage(dealId.value, { stage_id: stage.id })
    uni.showToast({ title: '阶段已更新', icon: 'success' })
    await loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '推进失败', icon: 'none' })
  }
}

async function submitActivity() {
  if (!canWriteDealActivity()) {
    uni.showToast({ title: '仅商机负责人可写跟进', icon: 'none' })
    return
  }
  if (!activityForm.value.content.trim()) {
    uni.showToast({ title: '请填写跟进内容', icon: 'none' })
    return
  }
  try {
    await crmApi.createDealActivity(dealId.value, {
      activity_type: activityForm.value.activity_type,
      subject: activityForm.value.subject || null,
      content: activityForm.value.content.trim(),
    })
    uni.showToast({ title: '已添加跟进', icon: 'success' })
    activityForm.value = { activity_type: 'call', subject: '', content: '' }
    activities.value = await crmApi.listDealActivities(dealId.value)
  } catch (e) {
    uni.showToast({ title: e.message || '添加失败', icon: 'none' })
  }
}

function openClose(status) {
  if (!canCloseDeal()) return
  closeForm.value = {
    status,
    amount: status === 'won' ? Number(deal.value?.amount || 0) : null,
    reason: '',
  }
  closeVisible.value = true
}

async function submitClose() {
  if (!canCloseDeal() || closeBusy.value) return
  if (closeForm.value.status === 'lost' && !closeForm.value.reason?.trim()) {
    uni.showToast({ title: '请填写输单原因', icon: 'none' })
    return
  }
  closeBusy.value = true
  try {
    await crmApi.closeDeal(dealId.value, {
      status: closeForm.value.status,
      amount: closeForm.value.status === 'won' ? Number(closeForm.value.amount || 0) : null,
      loss_reason: closeForm.value.reason || null,
      reason: closeForm.value.reason || null,
    })
    uni.showToast({ title: '商机已关闭', icon: 'success' })
    closeVisible.value = false
    await loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '关闭失败', icon: 'none' })
  } finally {
    closeBusy.value = false
  }
}

function handleReopen() {
  if (!canReopenDeal()) return
  uni.showModal({
    title: '重开商机',
    content: '将恢复为进行中，并回退到管道首个非终态阶段。确定重开？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await crmApi.reopenDeal(dealId.value)
        uni.showToast({ title: '商机已重开', icon: 'success' })
        await loadDetail()
      } catch (e) {
        uni.showToast({ title: e.message || '重开失败', icon: 'none' })
      }
    },
  })
}

function activityTypeLabel(type) {
  return activityTypeOptions.find((o) => o.value === type)?.label || type
}

onLoad((query) => {
  dealId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="deal">
      <view class="hero-card">
        <view class="hero-card__head">
          <text class="hero-card__title">{{ deal.title }}</text>
          <text class="status">{{ DEAL_STATUS_LABEL[deal.status] || deal.status }}</text>
        </view>
        <view class="stats">
          <view class="stat">
            <text class="stat__val">{{ formatMoney(deal.amount) }}</text>
            <text class="stat__lbl">商机金额</text>
          </view>
          <view class="stat">
            <text class="stat__val">{{ deal.probability ?? 0 }}%</text>
            <text class="stat__lbl">成交概率</text>
          </view>
          <view class="stat">
            <text class="stat__val">{{ currentStageName }}</text>
            <text class="stat__lbl">当前阶段</text>
          </view>
        </view>
        <view v-if="canMutateDeal()" class="stage-pick" @tap="openStageSheet">
          <text class="stage-pick__label">推进阶段</text>
          <text class="stage-pick__value">{{ currentStageName }}</text>
          <text class="stage-pick__arrow">▾</text>
        </view>
        <view v-if="canAssign() || canCloseDeal() || canReopenDeal()" class="hero-actions">
          <button v-if="canAssign()" class="btn" size="mini" hover-class="none" @tap="openAssign">分配负责人</button>
          <button v-if="canCloseDeal()" class="btn btn--ok" size="mini" hover-class="none" @tap="openClose('won')">赢单</button>
          <button v-if="canCloseDeal()" class="btn btn--danger" size="mini" hover-class="none" @tap="openClose('lost')">输单</button>
          <button v-if="canReopenDeal()" class="btn btn--warn" size="mini" hover-class="none" @tap="handleReopen">重开</button>
        </view>
      </view>

      <view class="section">
        <text class="section__title">基本信息</text>
        <view class="desc-grid">
          <text class="desc-label">商机编号</text><text class="desc-value">{{ deal.deal_number || '—' }}</text>
          <text class="desc-label">客户</text><text class="desc-value">{{ customer?.company_name || '—' }}</text>
          <text class="desc-label">负责人</text><text class="desc-value">{{ ownerLabel }}</text>
          <text class="desc-label">预计成交</text>
          <text class="desc-value">{{ deal.expected_close_date ? formatCell(deal, 'expected_close_date', 'datetime') : '—' }}</text>
          <text v-if="deal.next_step" class="desc-label">下一步</text>
          <text v-if="deal.next_step" class="desc-value">{{ deal.next_step }}</text>
          <text v-if="deal.description" class="desc-label">描述</text>
          <text v-if="deal.description" class="desc-value desc-value--block">{{ deal.description }}</text>
          <template v-for="item in extraFields" :key="item.label">
            <text class="desc-label">{{ item.label }}</text>
            <text class="desc-value">{{ item.value }}</text>
          </template>
        </view>
      </view>

      <view class="section">
        <text class="section__title">跟进记录</text>
        <view v-if="canWriteDealActivity()" class="form">
          <picker :range="activityTypeOptions" range-key="label" @change="(e) => (activityForm.activity_type = activityTypeOptions[e.detail.value].value)">
            <view class="picker">类型：{{ activityTypeLabel(activityForm.activity_type) }}</view>
          </picker>
          <input v-model="activityForm.subject" class="input" placeholder="主题（可选）" />
          <textarea v-model="activityForm.content" class="textarea" placeholder="跟进内容" :adjust-position="true" />
          <button class="btn btn--primary" size="mini" hover-class="none" @tap="submitActivity">提交跟进</button>
        </view>
        <view v-for="item in activities" :key="item.id" class="line">
          <text class="line__meta">{{ activityTypeLabel(item.activity_type) }} · {{ formatDateTime(item.created_at) }}</text>
          <text v-if="item.subject" class="line__subject">{{ item.subject }}</text>
          <text>{{ item.content }}</text>
        </view>
        <view v-if="!activities.length" class="empty">暂无跟进</view>
      </view>

      <view class="section">
        <text class="section__title">任务</text>
        <CrmEntityTasks ref="taskPanelRef" entity-type="deal" :entity-id="dealId" />
      </view>
    </template>
    <view v-else class="empty">商机不存在</view>

    <view v-if="stageSheetVisible" class="mask mask--sheet" @tap.self="stageSheetVisible = false">
      <view class="sheet" @tap.stop>
        <text class="sheet__title">选择阶段</text>
        <scroll-view scroll-y class="sheet__scroll">
          <view
            v-for="stage in stages"
            :key="stage.id"
            class="sheet__opt"
            :class="{ 'sheet__opt--active': String(stage.id) === String(deal?.stage_id) }"
            @tap="pickStage(stage)"
          >
            {{ stage.name }}
            <text v-if="stage.probability != null" class="sheet__prob">{{ stage.probability }}%</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="assignVisible" class="mask mask--center" @tap="assignVisible = false">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">分配负责人</text>
        <text class="dialog__hint">仅可分配给本人、下属或同级别销售经理</text>
        <picker
          mode="selector"
          :range="members.map((m) => m.display_name || m.phone)"
          @change="(e) => (selectedOwner = members[e.detail.value]?.user_id || '')"
        >
          <view class="picker">{{ selectedOwnerLabel }}</view>
        </picker>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="assignVisible = false">取消</button>
          <button class="btn btn--primary" hover-class="none" @tap="submitAssign">保存</button>
        </view>
      </view>
    </view>

    <view v-if="closeVisible" class="mask mask--center" @tap="closeVisible = false">
      <view class="dialog" @tap.stop>
        <text class="dialog__title">{{ closeForm.status === 'won' ? '确认赢单' : '确认输单' }}</text>
        <input
          v-if="closeForm.status === 'won'"
          v-model="closeForm.amount"
          class="input"
          type="digit"
          placeholder="成交金额"
        />
        <textarea
          v-if="closeForm.status === 'lost'"
          v-model="closeForm.reason"
          class="textarea"
          placeholder="输单原因（必填）"
          :adjust-position="true"
        />
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="closeVisible = false">取消</button>
          <button
            class="btn"
            :class="closeForm.status === 'won' ? 'btn--ok' : 'btn--danger'"
            hover-class="none"
            :loading="closeBusy"
            @tap="submitClose"
          >确认</button>
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
  padding-bottom: 24px;
}

.hero-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.hero-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.hero-card__title {
  flex: 1;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
}

.status {
  font-size: 11px;
  color: #1677ff;
  background: #e6f4ff;
  padding: 3px 10px;
  border-radius: 999px;
}

.stats {
  display: flex;
  margin-top: 14px;
  border-top: 1px solid #f1f5f9;
  padding-top: 12px;
}

.stat {
  flex: 1;
  text-align: center;
  border-right: 1px solid #f1f5f9;
}

.stat:last-child {
  border-right: none;
}

.stat__val {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #1677ff;
}

.stat__lbl {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.stage-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f0f7ff;
  border: 1px solid #bfdbfe;
}

.stage-pick__label {
  font-size: 13px;
  color: #64748b;
}

.stage-pick__value {
  flex: 1;
  text-align: right;
  font-size: 14px;
  font-weight: 600;
  color: #1677ff;
}

.stage-pick__arrow {
  color: #94a3b8;
  font-size: 12px;
}

.section {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.section__title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #1677ff;
}

.desc-grid {
  display: grid;
  grid-template-columns: 5.5em 1fr;
  gap: 10px 8px;
  font-size: 13px;
}

.desc-label {
  color: #94a3b8;
}

.desc-value {
  color: #334155;
  word-break: break-all;
}

.desc-value--block {
  grid-column: 1 / -1;
  margin-top: -4px;
  line-height: 1.5;
}

.form {
  margin-bottom: 12px;
}

.input,
.textarea,
.picker {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 14px;
  box-sizing: border-box;
  background: #fff;
}

.textarea {
  min-height: 72px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}

.btn--ok {
  background: #52c41a !important;
  color: #fff !important;
}

.btn--danger {
  background: #fff !important;
  color: #ff4d4f !important;
  border: 1px solid #ffccc7 !important;
}

.btn--warn {
  background: #fff7e6 !important;
  color: #d46b08 !important;
  border: 1px solid #ffd591 !important;
}

.line {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  color: #334155;
}

.line__meta {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.line__subject {
  display: block;
  font-weight: 600;
  margin-bottom: 4px;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px 0;
  font-size: 13px;
}

.mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
}

.mask--sheet {
  align-items: flex-end;
}

.mask--center {
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
}

.dialog {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}

.dialog__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  display: block;
}

.dialog__hint {
  display: block;
  font-size: 12px;
  color: #8c8c8c;
  margin: -4px 0 12px;
  line-height: 1.4;
}

.dialog__acts {
  display: flex;
  gap: 10px;
}

.dialog__acts .btn {
  flex: 1;
  font-size: 14px;
}

.hero-actions {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sheet {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 16px;
  max-height: 60vh;
}

.sheet__title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.sheet__scroll {
  max-height: 45vh;
}

.sheet__opt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 15px;
}

.sheet__opt--active {
  color: #1677ff;
  font-weight: 600;
}

.sheet__prob {
  font-size: 12px;
  color: #94a3b8;
}
</style>
