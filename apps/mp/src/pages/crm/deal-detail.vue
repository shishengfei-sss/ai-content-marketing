<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import { useEntitySchema } from '@/utils/useEntitySchema'
import { DEAL_STATUS_LABEL, formatMoney } from '@/utils/crmConstants'
import CrmEntityTasks from '@/components/crm/CrmEntityTasks.vue'

const dealId = ref('')
const loading = ref(false)
const deal = ref(null)
const customer = ref(null)
const pipelines = ref([])
const activities = ref([])
const permissions = ref([])
const members = ref([])
const stageSheetVisible = ref(false)
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
const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')

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
  const m = members.value.find((x) => x.user_id === deal.value.owner_user_id)
  return m?.display_name || m?.phone || '—'
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

const isClosed = computed(() => ['won', 'lost', 'abandoned'].includes(deal.value?.status))

async function loadDetail() {
  if (!dealId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    await loadSchema()
    try {
      members.value = await teamApi.listMembers()
      if (!Array.isArray(members.value)) members.value = []
    } catch {
      members.value = []
    }
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
    await taskPanelRef.value?.reload()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openStageSheet() {
  if (!canEdit() || isClosed.value) return
  stageSheetVisible.value = true
}

async function pickStage(stage) {
  stageSheetVisible.value = false
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
        <view v-if="canEdit() && !isClosed" class="stage-pick" @tap="openStageSheet">
          <text class="stage-pick__label">推进阶段</text>
          <text class="stage-pick__value">{{ currentStageName }}</text>
          <text class="stage-pick__arrow">▾</text>
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
        <view v-if="canActivity()" class="form">
          <picker :range="activityTypeOptions" range-key="label" @change="(e) => (activityForm.activity_type = activityTypeOptions[e.detail.value].value)">
            <view class="picker">类型：{{ activityTypeLabel(activityForm.activity_type) }}</view>
          </picker>
          <input v-model="activityForm.subject" class="input" placeholder="主题（可选）" />
          <textarea v-model="activityForm.content" class="textarea" placeholder="跟进内容" :adjust-position="true" />
          <button class="btn btn--primary" size="mini" hover-class="none" @tap="submitActivity">提交跟进</button>
        </view>
        <view v-for="item in activities" :key="item.id" class="line">
          <text class="line__meta">{{ activityTypeLabel(item.activity_type) }} · {{ item.created_at }}</text>
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

    <view v-if="stageSheetVisible" class="mask" @tap.self="stageSheetVisible = false">
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
  align-items: flex-end;
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
